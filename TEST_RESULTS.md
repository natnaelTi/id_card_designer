# Phase-two verification record

All fixtures are synthetic. No production site was installed, migrated or used for tests. Counts below exclude skipped tests. The source and CI workflow are public in [PR #1](https://github.com/natnaelTi/id_card_designer/pull/1); the Actions checks are the release merge gate.

## Exact local environment

| Component | Baseline bench | Isolated current-v16 bench |
|---|---|---|
| Frappe | 15.121.2 (`fd533e8`) | 16.56.0 (`49789a1`) |
| Python | 3.12.3 | 3.14.2 |
| Node | 22.23.3 | 24.13.0 |
| WeasyPrint | 69.0 | 70.0 |
| pypdf | 6.15.0 | 6.21.4 |
| Pillow | 12.3.0 | 13.0.0 |
| MariaDB | 10.11.14 | 10.11.14 |
| Redis | 7.0.15 (isolated port 13328) | 7.0.15 (isolated port 13328) |
| Browser | Chrome for Testing 153.0.8010.12 | same |
| Playwright | 1.63.0 | 1.63.0 |
| QR | segno 1.6.6, zxing-cpp 3.1.1 | same |
| PDF rasterizer | PyMuPDF 1.26.7 test overlay | PyMuPDF 1.26.7 |

The original installed v16.2.1 was first tested, then rejected as the release target because its Desktop Icon loader fails before Desk can boot with a dictionary passed as a document name. The current v16 checkout and virtual environment were provisioned separately; the original framework and all other installed apps were preserved.

## Completed gates

- Original baseline `cb66a7d`: 27 native backend tests passed before feature changes.
- Phase-two backend run before the final font regression: v15 **39/39**; v16 **19/19 unit + 20/20 integration**. Final matrix with the additional font regression: v15 **40/40 in 110.378 s**; v16 **20/20 unit in 62.592 s + 20/20 integration in 62.988 s**; **zero skipped**.
- Node queue/geometry/encryption: **8/8**, zero failures/skips (`npm run test:unit`).
- Chromium original workflow: passed v15 and current v16. Both-face persistence, physical drag, actual private image upload, publication, separate visual-to-code copy, actual Ace edit and PDF preview, native User print dialog/default/new-tab inline PDF, CSRF delivery and cache headers. Unsaved/unauthorized User actions remain hidden; permitted printer action is shown.
- Chromium phase-two workflow: passed v15 and current v16. Rapid two-face autosaves without Save, reload, offline/reconnect/retry, injected HTTP 500/retry (no mocked successful saves), encrypted unsaved-source recovery after refresh, real two-editor conflict/no overwrite/recovered copy, shift-selection/group/rotation/ungroup, vector QR preview, desktop and 390 px layout. No unhandled browser errors; Tab exits the canvas without a keyboard trap. Only the failed HTTP response is intercepted; all successful operations reach real Frappe.
- Fresh install, two idempotent migrations preserving custom publication/default/profile and real User PDF: passed separately on v15/current v16.
- Uninstall/reinstall: passed on both explicitly marked disposable sites; framework Users preserved, exactly one protected demo and default restored.
- Ruff lint/format, JavaScript syntax and wheel package-resource inspection: passed. Wheel includes DocTypes, patches.txt, JS, font and font license.
- `bench setup-chrome` on isolated current v16: passed using the explicit cached Chromium executable. App PDF rendering uses WeasyPrint, not browser rendering or wkhtmltopdf.

## Reproduction

Production installation commands are in README. Tests require an initialized disposable Frappe site; do not run the full database-dependent suite with plain `python -m unittest`.

```bash
# In the selected v15/v16 bench, with the app installed:
bench --site id-card-YOUR-NAME-test.localhost set-config allow_tests true
bench --site id-card-YOUR-NAME-test.localhost run-tests --app id_card_designer

# From the application repository:
npm ci
npm run test:unit
ruff check .
ruff format --check .
python -m build --wheel
```

The [Actions workflow](.github/workflows/verify.yml) reproduces the complete clean install matrix on Ubuntu 24.04, MariaDB 10.11 and Redis 7, pinned framework tags, matching Python/Node versions, native PDF libraries, real backend tests and Playwright Chromium. It invokes:

```bash
# Environment variables choose an isolated bench/site/database/Redis.
# setup refuses an existing site; lifecycle refuses unmarked sites.
./env/bin/python /path/to/app/scripts/setup_acceptance_site.py
./env/bin/python /path/to/app/scripts/lifecycle_acceptance.py preserve
bench build --app frappe
bench build --app id_card_designer
bench --site "$ID_CARD_TEST_SITE" run-tests --app id_card_designer
./env/bin/python /path/to/app/scripts/prepare_browser_test.py
# Start loopback-only gunicorn using scripts/dev_wsgi.py as in Actions.
npm run test:browser
npm run test:phase2
./env/bin/python /path/to/app/scripts/lifecycle_acceptance.py reinstall
```

Browser fixture credentials remain in a private runtime file outside the repo and are never uploaded. Screenshots/PDF artifacts use only synthetic names, `.invalid` addresses and neutral organizational references. Runtime logs are under the surrounding bench's private `.id-card-runtime/evidence`, not in the published app.

## PDF evidence

[Verification JSON](artifacts/phase2/pdf-verification.json) records exactly **2 pages**, each **85.5999998972 × 53.9799999194 mm**, tolerance **0.01 mm** against 85.60 × 53.98. Front/back order and synthetic names/Amharic text are asserted. Bundled FreeSerif is embedded. QR `ORG-DEMO-0001` decodes from the back-page 300 DPI raster. The native regression also decodes QR at **300 and 600 DPI, 0° and 90°**, checks code-mode QR, grouped/flattened raster equivalence, legacy scenes, 3 mm bleed/crop marks/TrimBox, measured clipping/rotated bounds, font shaping and unsupported glyphs.

- [Synthetic two-page QR PDF](artifacts/phase2/demo-qr.pdf)
- [Front raster](artifacts/phase2/demo-1.png), [back raster](artifacts/phase2/demo-2.png)
- [v16 builder](artifacts/phase2/v16/builder-demo.png), [Ace](artifacts/phase2/v16/code-editor.png), [print dialog](artifacts/phase2/v16/print-dialog.png)
- [Groups](artifacts/phase2/v16/group-editor.png), [QR](artifacts/phase2/v16/qr-editor.png), [conflict recovery](artifacts/phase2/v16/autosave-conflict.png), [390 px](artifacts/phase2/v16/builder-narrow.png)
- Equivalent v15 screenshots: `artifacts/phase2/v15/`.

## Failure findings resolved

- v16 permission hooks needed explicit allowed booleans; list API limit spelling differs.
- v16 generic File content conversion/metadata processing required byte-preserving test fixtures and app upload normalization before EXIF stripping.
- Redis request-local cached misses caused unstable recovery keys in a single request; atomic SET NX initialization fixes concurrent tabs.
- Bench discovery requires patches.txt; its absence prevented fresh CI install despite editable package installation.
- Current Desk uses `btn-modal-primary`; browser tests now support both native versions.
- WeasyPrint 70 requires URLFetcherResponse for custom data fetches. The strict no-network resource adapter supports old/new APIs.
- Font objects populate during PDF serialization. Inspect actual renderer missing-glyph data after serialization to handle fallback/shaping/ligatures rather than an incomplete font list or subset cmap.
- An attempted standalone unittest invocation failed because QR URL policy reads site settings; the supported gate is the native site runner. An early browser run overlapped disposable uninstall and was discarded/repeated sequentially.

## Remaining deployment checks

No production rollout, physical printer/duplex test, Firefox/Safari run or certified PDF/X/CMYK/ICC conversion is claimed. Gallery thumbnails remain schematic. Arbitrary HTML cannot round-trip into visual layers, and no government verifier is implemented. See ADMIN_GUIDE for all bounded-format/resource constraints and access/retention behavior.


## 0.2.1 early-v16 Desk boot regression

The reported Selfmade traceback was reproduced on unmodified Frappe **16.2.1**, Python **3.14.2**, WeasyPrint **66.0** with the previously installed app icon. `scripts/desktop_boot_acceptance.py` first asserts the real `get_bootinfo()` failure, then runs the idempotent navigation repair twice and asserts real Desk boot succeeds with the workspace/sidebar retained. The same script passes on Frappe **16.56.0**, retaining its supported desktop icon. Cleanup is restricted to the exact app-owned icon/sidebar pair, with a unit test proving unrelated icons are untouched. CI now includes both early/current v16 and v15; early/current v16 run this real boot recovery gate in addition to the full backend/browser/lifecycle suite. Earlier counts in this document describe 0.2.0; 0.2.1 adds two navigation unit tests.
