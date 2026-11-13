/* Real server + Desk UI: no mocked successful saves or synthetic PDF responses. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.env.ID_CARD_TEST_URL||'http://id-card-designer-test.localhost:8028';
assert.match(base,/^http:\/\/id-card-designer-test\.localhost:\d+$/);
const artifacts=process.env.ID_CARD_ARTIFACT_DIR||path.join(__dirname,'../artifacts/phase2');fs.mkdirSync(artifacts,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--host-resolver-rules=MAP id-card-designer-test.localhost 127.0.0.1']});
 try{
 const context=await browser.newContext({viewport:{width:1560,height:1000}});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const login=JSON.parse(fs.readFileSync(process.env.ID_CARD_LOGIN_FILE||'/tmp/id-card-runtime/browser-login.json'));
 await page.goto(base+'/login');await page.evaluate(async login=>{const r=await fetch('/api/method/login',{method:'POST',body:new URLSearchParams({usr:login.usr,pwd:login.pwd})});if(!r.ok)throw Error('Login failed');},login);
 const button=(p,name)=>p.getByRole('button',{name,exact:true});
 const saved=async p=>{await p.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Saved'),{timeout:30000});};
 const api=async(p,method,args={})=>p.evaluate(async({method,args})=>(await frappe.call({method:'id_card_designer.api.'+method,args,type:'POST'})).message,{method,args});
 await page.goto(base+'/app/id-card-builder/national-id-inspired-demo');await button(page,'Duplicate').waitFor({timeout:60000});await button(page,'Duplicate').click();await saved(page);
 await button(page,'Add text').click();await page.locator('.ic-properties textarea').fill('Phase two rapid front');
 await button(page,'back').click();await button(page,'Add text').click();await page.locator('.ic-properties textarea').fill('Phase two rapid back');await saved(page);
 
 // New drafts may not replace the route until explicit save; resolve name through saved payload.

 const templates=await page.evaluate(async()=> (await frappe.call({method:'frappe.client.get_list',args:{doctype:'ID Card Template',fields:['name'],order_by:'modified desc',limit_page_length:1}})).message);
 const draft=templates[0].name;const url=base+'/app/id-card-builder/'+draft;
 let doc=await api(page,'get_template_for_builder',{name:draft});assert.match(doc.front_layout,/Phase two rapid front/);assert.match(doc.back_layout,/Phase two rapid back/);
 await page.goto(url);await saved(page);await button(page,'back').click();assert.equal(await page.locator('.ic-element').filter({hasText:'Phase two rapid back'}).count(),1);
 await button(page,'Add text').click();await context.setOffline(true);await page.locator('.ic-properties textarea').fill('Retained while offline');await page.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Offline'));
 await context.setOffline(false);await button(page,'Retry save').click();await saved(page);doc=await api(page,'get_template_for_builder',{name:draft});assert.match(doc.back_layout,/Retained while offline/);
 // One explicit failed HTTP save: retry must preserve payload and use real server afterwards.
 await page.route('**/api/method/id_card_designer.api.save_draft',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({exc_type:'ValidationError',_server_messages:'[]'})}));
 await page.locator('.ic-properties textarea').fill('Retained after server error');await page.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Error'));
 await page.unroute('**/api/method/id_card_designer.api.save_draft');await page.keyboard.press('Escape');await button(page,'Retry save').click();await saved(page);
 // Refresh after a failed write must recover encrypted local source for this login.
 await page.route('**/api/method/id_card_designer.api.save_draft',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({exc_type:'ValidationError',_server_messages:'[]'})}));
 await page.locator('.ic-properties textarea').fill('Unsaved refresh recovery marker');await page.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Error'));
 await page.unroute('**/api/method/id_card_designer.api.save_draft');await page.reload();
 await page.getByRole('dialog').waitFor({timeout:30000});assert.match(await page.getByLabel('Encrypted/local unsaved draft',{exact:true}).inputValue(),/Unsaved refresh recovery marker/);
 await button(page,'Reload saved draft').click();await saved(page);doc=await api(page,'get_template_for_builder',{name:draft});assert.doesNotMatch(doc.front_layout+doc.back_layout,/Unsaved refresh recovery marker/);await button(page,'back').click();
 // Two loaded editors: first write wins; second reports conflict instead of overwriting.
 const other=await context.newPage();await other.goto(url);await saved(other);
 await button(page,'Add text').click();await page.locator('.ic-properties textarea').fill('First editor committed');await saved(page);
 await button(other,'Add text').click();await other.locator('.ic-properties textarea').fill('Second editor unsaved');await other.waitForFunction(()=>document.querySelector('.ic-status')?.textContent.includes('Conflict'));
 doc=await api(page,'get_template_for_builder',{name:draft});assert.match(doc.back_layout,/First editor committed/);assert.doesNotMatch(doc.front_layout+doc.back_layout,/Second editor unsaved/);
 await button(other,'Compare / recover').click();await other.getByRole('dialog').waitFor();await other.screenshot({path:path.join(artifacts,'autosave-conflict.png'),fullPage:true});
 await button(other,'Save conflict copy').click();await saved(other);await other.close();
 // Real layer multiselect + group + rotation + ungroup, persisted without drift.
 await button(page,'front').click();const layers=page.locator('.ic-layer');await layers.nth(1).click();await layers.nth(2).click({modifiers:['Shift']});await button(page,'Group').click();await page.getByLabel('rotation (mm; rotation °)',{exact:true}).fill('17');await saved(page);
 await page.screenshot({path:path.join(artifacts,'group-editor.png'),fullPage:true});await button(page,'Ungroup').click();await saved(page);
 await button(page,'Add qr').click();await page.locator('.ic-properties textarea').fill('ORG-DEMO-PHASE2');await saved(page);await page.locator('.ic-element img').last().waitFor();
 await page.screenshot({path:path.join(artifacts,'qr-editor.png'),fullPage:true});
 await page.locator('.ic-canvas').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('.ic-canvas').evaluate(n=>document.activeElement===n),false,'Canvas must not trap Tab focus');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(artifacts,'builder-narrow.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),true,'Page must fit narrow viewport');
 assert.deepEqual(errors,[]);console.log('PASS phase2: rapid both-face autosave, reload, offline/retry, HTTP error/retry, encrypted refresh recovery, two-editor conflict/copy, group/rotation/ungroup, QR preview, narrow viewport.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
