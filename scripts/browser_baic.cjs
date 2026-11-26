/* Normal Desk workflow against a marked synthetic acceptance site. Supplied artwork stays private. */
const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
const base=process.env.ID_CARD_TEST_URL;assert.match(base,/^http:\/\/id-card-designer-test\.localhost:\d+$/);
const dir=process.env.ID_CARD_ARTIFACT_DIR;assert.ok(dir&&path.isAbsolute(dir),'Use an absolute private artifact directory');assert.ok(!path.resolve(dir).startsWith(path.resolve(__dirname,'..')+path.sep),'Artwork evidence must stay outside the public repo');fs.mkdirSync(dir,{recursive:true});
const login=JSON.parse(fs.readFileSync(process.env.ID_CARD_LOGIN_FILE));const fixture=JSON.parse(fs.readFileSync(process.env.ID_CARD_BAIC_FIXTURE));
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--host-resolver-rules=MAP id-card-designer-test.localhost 127.0.0.1']});
try{
 const context=await browser.newContext({viewport:{width:1560,height:1100}});const page=await context.newPage();page.setDefaultTimeout(90000);const errors=[];page.on('pageerror',e=>errors.push(e.message));let captures=0;
 await context.route('**/api/method/id_card_designer.api.deliver_pdf',async route=>{const req=route.request();const response=await route.fetch({url:req.url().replace('id-card-designer-test.localhost','127.0.0.1'),headers:{...req.headers(),host:'id-card-designer-test.localhost'},timeout:120000});assert.equal(response.status(),200);assert.match(response.headers()['content-disposition'],/^inline/);assert.match(response.headers()['cache-control'],/no-store/);const bytes=await response.body();assert.equal(bytes.subarray(0,5).toString(),'%PDF-');fs.writeFileSync(path.join(dir,captures++===0?'demo-preview.pdf':'issued-user.pdf'),bytes);await route.fulfill({response});});
 await page.goto(base+'/login');await page.evaluate(async l=>{const r=await fetch('/api/method/login',{method:'POST',body:new URLSearchParams({usr:l.usr,pwd:l.pwd})});if(!r.ok)throw Error('Login failed');},login);
 const btn=(name)=>page.getByRole('button',{name,exact:true});const saved=()=>page.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Saved'),null,{timeout:90000});
 const api=(method,args={})=>page.evaluate(async({method,args})=>(await frappe.call({method:'id_card_designer.api.'+method,args,type:'POST'})).message,{method,args});
 await page.goto(base+'/app/id-card-builder/'+fixture.template);await btn('Save draft').waitFor();await saved();await page.evaluate(()=>document.fonts.ready);
 await page.getByLabel('Title',{exact:true}).fill('BAIC Vision Partnership Card - round-trip');await saved();await btn('back').click();await saved();await page.reload();await saved();assert.equal(await page.getByLabel('Title',{exact:true}).inputValue(),'BAIC Vision Partnership Card - round-trip');
 await page.getByLabel('Title',{exact:true}).fill('BAIC Vision Partnership Card');await saved();
 await page.getByLabel('Fictional preview',{exact:true}).selectOption('design');await page.locator('.ic-element').filter({hasText:'DESIGN SAMPLE'}).waitFor();await page.screenshot({path:path.join(dir,'blank-front.png'),fullPage:true});
 await page.getByLabel('Fictional preview',{exact:true}).selectOption('demo');await page.locator('.ic-element').filter({hasText:'DAWIT SAMUEL TESFAYE'}).waitFor();await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:path.join(dir,'designer-front.png'),fullPage:true});await btn('back').click();await page.evaluate(()=>document.fonts.ready);
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('.ic-element')).some(e=>e.querySelector('img')&&e.querySelector('img').src.startsWith('data:image/')));
 const disclaimer=page.locator('.ic-element').filter({hasText:'For BAIC Kingdom Chapel vision partnership identification only.'});
 assert.ok(await disclaimer.evaluate(e=>e.scrollHeight<=e.clientHeight+1),'Designer must show both approved disclaimer lines without clipping');
 assert.ok((await disclaimer.textContent()).includes('Not a government-issued ID. If found, return to the chapel office.'));
 await page.screenshot({path:path.join(dir,'designer-back.png'),fullPage:true});
 const doc=await api('get_template_for_builder',{name:fixture.template});assert.equal(JSON.parse(doc.front_layout).find(e=>e.field==='user_image').width,21.3);assert.equal(JSON.parse(doc.back_layout).find(e=>e.type==='qr').width,22);
 const report=await api('preflight_template',{name:fixture.template});assert.deepEqual(report.errors,[]);assert.ok(report.fonts_used.includes('Noto Sans Ethiopic'));
 const preview=context.waitForEvent('response',r=>r.url().includes('api.deliver_pdf'));await btn('Preview PDF').click();assert.equal((await preview).status(),200);
 await btn('Publish').click();await page.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.startsWith('Published'),null,{timeout:120000});
 assert.ok((await api('list_usable_templates')).some(t=>t.name===fixture.template));
 await page.goto(base+'/app/user/'+encodeURIComponent(fixture.user));await btn('Print ID Card').click();await page.locator('.modal:visible select[data-fieldname="template"]').selectOption(fixture.template);await page.screenshot({path:path.join(dir,'user-print-dialog.png'),fullPage:true});
 const delivery=context.waitForEvent('response',r=>r.url().includes('api.deliver_pdf'));await page.locator('.modal:visible .btn-primary, .modal:visible .btn-modal-primary').click();assert.equal((await delivery).status(),200);
 assert.equal(captures,2);assert.deepEqual(errors,[]);console.log('PASS BAIC: designer front/back save/reload, blank/demo previews, embedded local fonts, real PDF preview, normal manager publication, published selector, permitted User print and private inline delivery.');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
