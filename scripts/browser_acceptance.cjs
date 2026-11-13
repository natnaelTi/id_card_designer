const { chromium } = require("playwright");
const fs = require("fs");
const assert = require("node:assert/strict");
const path=require("node:path");
const artifacts=process.env.ID_CARD_ARTIFACT_DIR||path.join(__dirname,"../artifacts");fs.mkdirSync(artifacts,{recursive:true});
const loginFile=process.env.ID_CARD_LOGIN_FILE||"/tmp/id-card-runtime/browser-login.json";
(async () => {
  const base =
    process.env.ID_CARD_TEST_URL ||
    "http://id-card-designer-test.localhost:8028";
  assert.match(base, /id-card-designer-test\.localhost/);
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--host-resolver-rules=MAP id-card-designer-test.localhost 127.0.0.1",
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1560, height: 1000 },
  });
  const page = await context.newPage();
  let pdfIndex = 0;
  await context.route(
    "**/api/method/id_card_designer.api.deliver_pdf",
    async (route) => {
      const req = route.request();
      const response = await route.fetch({
        url: req.url().replace("id-card-designer-test.localhost", "127.0.0.1"),
        headers: { ...req.headers(), host: "id-card-designer-test.localhost" },
      });
      assert.equal(response.status(), 200);
      const bytes = await response.body();
      assert.equal(bytes.subarray(0, 5).toString(), "%PDF-");
      fs.writeFileSync(
        artifacts + "/" +
          (pdfIndex++ === 0 ? "code-preview.pdf" : "browser-print.pdf"),
        bytes
      );
      await route.fulfill({ response });
    }
  );
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base + "/login");
  const login = JSON.parse(
    fs.readFileSync(loginFile)
  );
  await page.evaluate(async (login) => {
    const response = await fetch("/api/method/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ usr: login.usr, pwd: login.pwd }),
    });
    if (!response.ok) throw Error("Browser login failed");
  }, login);
  await page.goto(base + "/app/id-card-builder/national-id-inspired-demo");
  await page
    .getByText("Protected sample — duplicate to edit", { exact: false })
    .waitFor({ timeout: 60000 });
  await page.screenshot({
    path: artifacts + "/builder-demo.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Duplicate", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.includes("Saved")
  );
  await page.getByRole("button", { name: "Add text", exact: true }).click();
  const text = page.locator(".ic-properties textarea");
  await text.fill("Browser acceptance front");
  await text.dispatchEvent("change");
  await page.getByRole("button", { name: "back", exact: true }).click();
  await page.getByRole("button", { name: "Add text", exact: true }).click();
  await text.fill("Browser acceptance back");
  await text.dispatchEvent("change");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.includes("Saved")
  );
  const url = page.url();
  await page.reload();
  await page.getByText("Saved", { exact: false }).first().waitFor();
  await page.getByRole("button", { name: "back", exact: true }).click();
  assert.equal(
    await page
      .locator(".ic-element")
      .filter({ hasText: "Browser acceptance back" })
      .count(),
    1
  );
  await page.getByRole("button", { name: "front", exact: true }).click();
  assert.equal(
    await page
      .locator(".ic-element")
      .filter({ hasText: "Browser acceptance front" })
      .count(),
    1
  );
  // Drag the added text element and persist physical coordinates.
  const added = page
    .locator(".ic-element")
    .filter({ hasText: "Browser acceptance front" });
  const bb = await added.boundingBox();
  await page.mouse.move(bb.x + 10, bb.y + 10);
  await page.mouse.down();
  await page.mouse.move(bb.x + 40, bb.y + 20, { steps: 5 });
  await page.mouse.up();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.includes("Saved")
  );
  await page.getByRole("button", { name: "Upload image", exact: true }).click();
  await page
    .locator('.modal:visible input[type="file"]')
    .setInputFiles(path.join(path.dirname(loginFile),"test-logo.png"));
  await page.locator(".modal:visible .btn-primary").click();
  await page
    .locator('.ic-element img[src*="test-logo"]')
    .waitFor({ timeout: 30000 });
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.includes("Saved")
  );
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.startsWith("Published")
  );
  await page.screenshot({
    path: artifacts + "/builder-edited.png",
    fullPage: true,
  });
  // Conversion creates a separate draft; Ace changes are validated through a real PDF.
  await page.getByLabel("Mode", { exact: true }).selectOption("Code");
  await page.locator(".modal:visible .btn-primary").click();
  await page
    .locator(".ic-code .ace_editor")
    .first()
    .waitFor({ timeout: 30000 });
  await page.evaluate(() =>
    ace
      .edit(document.querySelector(".ic-code-editor"))
      .setValue(
        '<div style="padding:4mm;font-size:12pt">Code front {{ full_name }} · ሰላም</div>',
        -1
      )
  );
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".ic-status")?.textContent.includes("Saved")
  );
  await page.screenshot({
    path: artifacts + "/code-editor.png",
    fullPage: true,
  });
  const preview = context.waitForEvent("response", (r) =>
    r.url().includes("api.deliver_pdf")
  );
  await page.getByRole("button", { name: "Preview PDF", exact: true }).click();
  assert.equal((await preview).status(), 200);
  await page.goto(base + "/app/user/Administrator");
  await page
    .getByRole("button", { name: "Print ID Card", exact: true })
    .waitFor({ timeout: 30000 });
  await page
    .getByRole("button", { name: "Print ID Card", exact: true })
    .click();
  await page
    .locator('.modal:visible select[data-fieldname="template"]')
    .waitFor();
  const select = page.locator(
    '.modal:visible select[data-fieldname="template"]'
  );
  assert.equal(await select.inputValue(), "national-id-inspired-demo");
  await page.screenshot({
    path: artifacts + "/print-dialog.png",
    fullPage: true,
  });
  const response = context.waitForEvent("response", (r) =>
    r.url().includes("api.deliver_pdf")
  );
  await page.locator(".modal:visible .btn-primary").click();
  const pdfResponse = await response;
  assert.equal(pdfResponse.status(), 200);
  assert.match(pdfResponse.headers()["content-type"], /application\/pdf/);
  assert.match(pdfResponse.headers()["content-disposition"], /^inline/);
  assert.match(pdfResponse.headers()["cache-control"], /no-store/);
  assert.equal(pdfIndex, 2);
  await page.evaluate(() => {
    const doc = frappe.model.get_new_doc("User");
    frappe.set_route("Form", "User", doc.name);
  });
  await page.waitForFunction(
    () => window.cur_frm?.doctype === "User" && cur_frm.is_new()
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Print ID Card", exact: true })
      .count(),
    0
  );
  for (const actor of login.actors || []) {
    const actorContext = await browser.newContext();
    const actorPage = await actorContext.newPage();
    await actorPage.goto(base + "/login");
    await actorPage.evaluate(async (login) => {
      const r = await fetch("/api/method/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ usr: login.usr, pwd: login.pwd }),
      });
      if (!r.ok) throw Error("Actor login failed");
    }, actor);
    const capsDone = actorPage.waitForResponse((r) =>
      r.url().includes("id_card_designer.api.capabilities")
    );
    await actorPage.goto(base + "/app/user/" + actor.usr);
    await actorPage.waitForFunction(
      () => window.cur_frm?.doctype === "User" && !cur_frm.is_new()
    );
    await capsDone;
    if (actor.can_print)
      await actorPage
        .getByRole("button", { name: "Print ID Card", exact: true })
        .waitFor();
    assert.equal(
      await actorPage
        .getByRole("button", { name: "Print ID Card", exact: true })
        .count(),
      actor.can_print ? 1 : 0
    );
    await actorContext.close();
  }
  assert.equal(errors.length, 0, errors.join("\n"));
  console.log(
    "PASS: independent sides save/reload; drag/save; real image upload; publish; visual-to-code copy; Ace edit and actual PDF preview; User dialog default; new-tab inline PDF; CSRF POST delivery and private response headers; action hidden on unsaved/unauthorized forms and shown for an authorized printer."
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
