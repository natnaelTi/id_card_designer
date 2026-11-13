# Verification — 13 November 2026

## Results

| Check | Result |
| --- | --- |
| Native Frappe suite | **27 tests passed**, 47.346 seconds on the final backend |
| Fresh installation | Passed on `id-card-designer-fresh.localhost`, Frappe + this app only |
| Two subsequent migrations | Passed; one bundled demo, customized design/default and demo snapshot preserved |
| Browser acceptance | Real Chromium UI, actual Frappe calls, uploads and PDFs; see coverage below |
| JavaScript parsing / Python lint and formatting | Passed |
| Bench asset build | Passed (exit 0); shared-cache warnings noted below |
| Python wheel | Built; includes DocType/Page JSON and JS, hooks, modules, font and font license |
| Font coverage | Bundled FreeSerif contains all Latin/Ethiopic glyphs used by the fictional sample |
| Core preservation | Frappe and ERPNext Git working trees unchanged; existing Tele Tena changes untouched |

The native suite consists of **12 renderer tests and 15 Frappe workflow tests**. Tests generate actual PDF bytes and parse them with pypdf. They cover card dimensions/page count/order, bleed and artwork outside trim, embedded fonts/Ethiopic strings, malicious HTML/CSS/binding rejection, safe text and style-attribute escaping, invalid geometry, long values, independent faces, idempotent seeding, draft/publication isolation, revision restore, defaults, disabled templates, role restrictions, direct document/API access, User read/print access, token ownership, field allowlisting, stale saves, profile privacy, private portrait/template-image access, EXIF orientation and transparent-image preservation.

Fresh-install acceptance independently verifies the final app's five DocTypes, roles and workspace. It creates exactly one enabled published built-in/default, duplicates and publishes a customer design, changes the default, runs two native migrations, and verifies neither that design/default nor the original demo snapshot changes. It creates a fictional User and Profile and generates a real PDF containing **Live Fixture**, **Applied Sciences**, and the selected record's contact details, with no substitution of fictional preview values.

## Browser coverage

`browser_acceptance.cjs` uses Playwright 1.63.0 and cached Chromium 153 on this WSL instance. It performs real browser actions and actual HTTP calls:

1. Open the protected demo and duplicate it.
2. Add distinct text to each face; save, reload, and verify the independent scene contents.
3. Drag an object, save its canonical coordinates, and publish.
4. Upload a real image with Frappe FileUploader and save/publish the resulting image element.
5. Switch to Code mode through its confirmation, creating a separate draft; edit syntax-highlighted Ace source and preview an actual PDF.
6. Open a saved User form, inspect the template gallery and confirm the configured default is preselected.
7. Click Print, reserve a new tab, and verify a CSRF-protected POST returns status 200, `application/pdf`, `Content-Disposition: inline`, and `Cache-Control: no-store, private`.
8. Check visibility on unsaved and unauthorized User forms and for a permitted printer with explicitly shared source-User access.

The test captures actual server PDF bytes by forwarding the PDF request through Playwright's HTTP transport before fulfilling the browser response. Chromium's built-in PDF viewer otherwise makes its response body unavailable through the page's DevTools resource reader. The PDF bytes are **not mocked**.

The standalone development server does not run Socket.IO; those background polling requests return 404. This does not affect the tested synchronous builder, upload, saving or rendering workflows. A normal Bench deployment supplies its normal Socket.IO service. The asset build also warns that the pre-existing Bench common Redis cache is unavailable; the two isolated sites use their own healthy cache on port 13328. The shared service configuration was left unchanged, and the test-site cache was cleared successfully.

## Physical PDF evidence

pypdf reports:

| Artifact | Pages | Page 1 MediaBox (mm) | Page 2 MediaBox (mm) |
| --- | --- | --- | --- |
| `artifacts/demo.pdf` | **2** | **85.6000 × 53.9800** | **85.6000 × 53.9800** |
| `artifacts/browser-print.pdf` | **2** | **85.6000 × 53.9800** | **85.6000 × 53.9800** |
| `artifacts/code-preview.pdf` | **2** | **85.6000 × 53.9800** | **85.6000 × 53.9800** |
| `artifacts/fresh-live-fixture.pdf` | **2** | **85.6000 × 53.9800** | **85.6000 × 53.9800** |
| 3 mm bleed test | **2** | **91.6000 × 59.9800** | **91.6000 × 59.9800** |

No blank third page, letterhead, browser header/footer, or default A4/Letter page is generated. The first face contains front identity labels; the second contains return instructions. Both sample faces visibly include `SAMPLE / NOT VALID ID`. Exported PDFs are local development artifacts excluded from Git. `artifacts/pdf-evidence.json` records the reproducible standalone demo measurements.

## Reproduce

From the Bench root, with a disposable site only:

```bash
# Existing test runtime:
./env/bin/python apps/id_card_designer/scripts/dev_runtime.py start

# On a new checkout, after starting its isolated services, create the named test site once:
# ./env/bin/python apps/id_card_designer/scripts/dev_runtime.py create

bench --site id-card-designer-test.localhost set-config allow_tests true
bench --site id-card-designer-test.localhost run-tests --app id_card_designer
./env/bin/python -m unittest id_card_designer.tests.test_rendering -v

# Local-only login/image fixture; refuses a non-test site name:
./env/bin/python apps/id_card_designer/scripts/prepare_browser_test.py

# Optional browser-test dependencies; production printing does not require these:
npm ci --prefix apps/id_card_designer
cd apps/id_card_designer
npx playwright install chromium
npm run test:browser
```

This run reused the already installed Playwright package without changing another app:

```bash
NODE_PATH=/home/frappe/teletena-browser-tools/node_modules \
  node apps/id_card_designer/scripts/browser_acceptance.cjs
```

Fresh installation/migration acceptance refuses to overwrite the named fresh site or database:

```bash
./env/bin/python apps/id_card_designer/scripts/fresh_acceptance.py
```

It has already been run successfully in this workspace. To repeat that test, use another explicitly disposable site/database pair in a copy of the script; do not drop an existing site to satisfy its assertion.

Build and export:

```bash
bench build --app id_card_designer
./env/bin/pip wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/id-card-runtime/dist apps/id_card_designer
./env/bin/python apps/id_card_designer/scripts/export_demo.py
```

Lint/format tools used locally (Ruff was installed under `/tmp`, not added to the Bench Python environment):

```bash
/tmp/id-card-devtools/bin/ruff check apps/id_card_designer
/tmp/id-card-devtools/bin/ruff format --check apps/id_card_designer
node --check apps/id_card_designer/scripts/browser_acceptance.cjs
```

Runtime status/stop commands act only on matching owned PIDs:

```bash
./env/bin/python apps/id_card_designer/scripts/dev_runtime.py status
./env/bin/python apps/id_card_designer/scripts/dev_runtime.py stop
```

The loopback-only preview is at `http://localhost:8028/app/id-card-builder/national-id-inspired-demo`. Login fixture credentials are in the private `/tmp/id-card-runtime/browser-login.json`; alternatively set your own **test-site** Administrator password with `bench --site id-card-designer-test.localhost set-admin-password YOUR_LOCAL_PASSWORD`. The fixture changes only the explicitly disposable site. Temporary MariaDB/Redis data is not durable and is not a production deployment.

## Failures resolved during development

- Existing database socket was inactive and system root login unavailable: used a separate temporary MariaDB database and loopback Redis instead of changing existing services.
- Missing test-site cache/setup state initially prevented Desk boot: initialized only the disposable site's setup state and private cache configuration.
- Switching publication checks to server-owned flags required reloading preview workers; verified forged client flags are rejected.
- The native uploader's size limit is measured in bytes, not MB: corrected the 5 MB limit and added an actual browser upload plus private-asset PDF coverage.
- The fixed Desk page header overlapped the first toolbar row: corrected the builder's offset/sticky positioning and bounded sidebar scrolling; native pointer clicks now pass without forced clicks.
- The browser PDF extension hides response bodies after taking over navigation: capture real bytes in the HTTP transport rather than mocking a renderer.
- Portrait normalization originally needed explicit EXIF orientation and alpha preservation: fixed and covered with real uploaded JPEG/PNG files.

## Manual checks still required

Frappe v16; Firefox/Safari/mobile; real popup blocking and browser PDF download preferences; physical 100% print scaling/duplex alignment; unusually long real-world Unicode names; institution-specific font choices; production User/Profile/File permissions; role-controlled asset sharing. See README's explicit limitations for unfinished optional/editor enhancements. No production-site rollout was performed.
