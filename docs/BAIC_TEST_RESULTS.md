# BAIC implementation verification — 26 November 2026

## Environment and scope

Implementation branch: `feature/baic-vision-partnership-card`, based on main `ad1f3166c789794b4f22632faecf84ef66a28c67`. Remote inspected: `origin`, `https://github.com/natnaelTi/id_card_designer.git`. This is an optional app-owned preset, not a production deployment. No BAIC business application or Member integration was present; the working data path is User + ID Card Profile + ID Card Settings.

| Runtime | Actual versions | Isolated site |
|---|---|---|
| v15 | Frappe 15.121.2; Python 3.12.3; Node 22.23.3; WeasyPrint 69; pypdf 6.15 | `id-card-baic-v15-test.localhost` |
| early v16 | Frappe 16.2.1; Python 3.14.2; WeasyPrint 66 | `id-card-early-fresh-test.localhost` |
| v16 | Frappe 16.56.0; Python 3.14.2; Node 24.13.0; WeasyPrint 70; pypdf 6.21.4 | `id-card-baic-v16-test.localhost` |

All sites are explicitly marked disposable fixtures. Their database uses a separate local MariaDB datadir/socket. v15 uses Redis port 13328 and the current v16 browser fixture uses port 13329, isolating the frameworks' global asset-manifest caches. System MariaDB and Redis were not reconfigured. Source User records, contacts and organizational card numbers used for issuance verification are synthetic.

## Completed gates

- **52 backend tests passed on v15**, 241.379 seconds, zero failures/skips in the final complete run.
- **52 backend tests passed on v16**: 28 unit tests in 119.925 seconds and 24 integration tests in 133.722 seconds, zero failures/skips.
- **52 backend tests passed on early v16.2.1**: 28 unit tests in 152.546 seconds and 24 integration tests in 110.210 seconds.
- After final layout/bleed changes, all nine focused BAIC tests passed again on v15/v16. Six BAIC unit tests, including visual-to-code bleed preservation, also passed directly on all three runtimes.
- **8 JavaScript tests passed**: serialized autosave/coalescing, conflict preservation, offline retry, encrypted session-bound recovery, transform/group invariants, alignment/distribution and recovery-storage failure.
- Ruff lint and format checks, JavaScript syntax and Python compilation passed. A wheel built successfully; its contents include all four local TTFs, both font licenses, CSS, schemas and the optional preset.
- Native `bench build --app id_card_designer` completed. The shared bench's unused default Redis-cache connection produced warnings; the isolated test-site cache and browser workflows use their separate configured Redis and passed.
- CI also runs the normal BAIC designer/publication/User print browser flow using generated synthetic artwork; supplied private assets are never needed or uploaded.
- BAIC coverage includes idempotent optional setup preserving administrator edits, existing publication/default; real permitted User/Profile mapping; exact default/translated roles; optional label visibility; Gregorian-to-Ethiopian known dates and round trips; local Ethiopic font coverage; measured fitting and clear overflow failure; real QR decoding at 600 dpi; Guest/private asset and issuance denial; published revision pinning while draft changes; exact two-page trim and centered bleed boxes and embedded fonts.
- Real Chromium workflows ran on both runtimes: editable front/back save/reload → populated/blank preview → private PDF preview → manager publication → published template selector → User form Print ID Card → real private inline PDF. Requests reached the real Frappe endpoints and PDF renderer; the harness captures actual PDF bytes, not mocked PDFs.

## Reference extraction and visual inspection

Both pages of both approved PDFs were inspected visually and with PyMuPDF. The original pages measure approximately 85.600013 × 53.980012 mm, consistent with the requested trim after PDF rounding. The extractor records fonts, colors, text blocks, page dimensions and embedded-image geometry in its private `reference-analysis.json`.

All original assets were recovered: logo, blue seal and signature with reconstructed soft-mask alpha; decorative arch/cross background; demo portrait. There are no substitute or generated branding assets. The supplied PDFs, extracted artwork, portrait/signature, and rendered evidence are **outside the repository** in `/home/frappe/baic-id-card-private`, with restricted directory access.

At matched 600-dpi scale, the front and back were reviewed beside the supplied populated example. The browser canvas uses geometric-precision text rendering to avoid Linux hinting changing small text advances; the browser proof asserts that both disclaimer lines fit without clipping and waits for the generated QR before its back screenshot. Header/body baselines match within 0.0006 mm for the measured common labels. The portrait's approved 0.4pt sage outline is a separate editable shape above the cover-cropped photo. Seal layering remains independent of the photo mask, with most of the seal outside the photo. The original signature is rendered at 29% opacity and ends before the QR quiet zone. QR patterns differ from the reference because the app generates a real QR for the explicitly requested payload, rather than copying the PDF's QR artwork.

Private evidence locations:

- `evidence/v15/` and `evidence/v16/`: designer front/back, blank preview, User print dialog, actual two-page `demo-preview.pdf` and synthetic `issued-user.pdf`.
- `exports/`: trim front/back PNGs at **600 dpi, 2023 × 1276 px**, blank design PDF, demo PDF with 3mm bleed/crop marks, and matched-scale reference comparisons.
- `exports/verification.json`: page geometry, embedded font names, decoded QR payloads and baseline measurements.

The trim PDFs contain exactly two pages, front then back, at 85.60 × 53.98 mm with zero margins. The bleed proof has 91.60 × 59.98 mm MediaBox and centered 85.60 × 53.98 mm TrimBox. Gold/teal trim-edge pixel checks confirm no preview shadow or Desk margins entered exports. Demo QR decodes to `BAIC|DEMO|BAIC-001248`; issued synthetic QR decodes to `BAIC-TEST-0001`. Live PDF text contains no SAMPLE/DEMO, null/None, legacy Member/Parish or chapel placeholders.

## Reproduce

See [BAIC_SETUP.md](BAIC_SETUP.md) for optional private-bundle import, calendar semantics, field mappings and configuration before issuance. Run backend tests only on a disposable test site:

```bash
cd /home/frappe/frappe/frappe-bench
bench --site YOUR_DISPOSABLE_TEST_SITE run-tests --app id_card_designer
cd apps/id_card_designer
npm run test:unit
ruff check .
ruff format --check .
python -m build --wheel
```

The exact local v15 test runner uses the private decoder tools overlay without modifying the normal bench dependencies:

```bash
cd /home/frappe/frappe/frappe-bench/sites
PYTHONPATH=/home/frappe/frappe/frappe-bench/.id-card-runtime/tools:/home/frappe/frappe/frappe-bench/apps/frappe:/home/frappe/frappe/frappe-bench/apps/id_card_designer \
  ../env/bin/python -m frappe.utils.bench_helper frappe \
  --site id-card-baic-v15-test.localhost run-tests --app id_card_designer
```

For a fresh real-artwork browser fixture, first import the private bundle as documented, then use the existing `prepare_browser_test.py` and `prepare_baic_acceptance.py` with `ID_CARD_BENCH_ROOT` and a marked `ID_CARD_TEST_SITE`. The BAIC fixture deliberately refuses unmarked/production sites and existing published fixtures. Start the loopback `scripts/dev_wsgi.py` with the same environment and the appropriate Frappe Python path. Then run from the app directory:

```bash
NODE_PATH=/home/frappe/teletena-browser-tools/node_modules \
ID_CARD_TEST_URL=http://id-card-designer-test.localhost:8028 \
ID_CARD_ARTIFACT_DIR=/home/frappe/baic-id-card-private/evidence/v15 \
ID_CARD_LOGIN_FILE=/home/frappe/baic-id-card-private/v15-login/browser-login.json \
ID_CARD_BAIC_FIXTURE=/home/frappe/baic-id-card-private/v15-login/baic-fixture.json \
node scripts/browser_baic.cjs

PYTHONPATH=/home/frappe/frappe/frappe-bench/.id-card-runtime/tools \
/home/frappe/frappe/frappe-bench/env/bin/python scripts/verify_baic_exports.py \
  --demo /home/frappe/baic-id-card-private/evidence/v15/demo-preview.pdf \
  --issued /home/frappe/baic-id-card-private/evidence/v15/issued-user.pdf \
  --blank /home/frappe/baic-id-card-private/exports/blank.pdf \
  --reference /home/frappe/baic-id-card-design/BAIC_Demo_Vision_Partnership_Card_Front_and_Back.pdf \
  --output /home/frappe/baic-id-card-private/exports
```

Use port 8029, the isolated v16 bench/runtime, `v16-login`, and `evidence/v16` for v16. The local `NODE_PATH` is an existing Playwright installation; `npm ci` supplies the repository's pinned Playwright in a fresh environment. Private credentials must never be printed or committed.

## Limitations and verification boundaries

- No physical-printer, stock, color-profile or duplex-alignment testing was performed.
- Backend tests passed locally on v15.121.2, v16.2.1 and v16.56.0. Real-artwork Chromium BAIC workflow/screenshot proofs were run on v15.121.2 and v16.56.0; early v16 has backend verification only for this preset. The existing CI matrix targets all three.
- A separate BAIC ERP schema was not available. This implementation uses the documented Profile path; an external BAIC deployment must deliberately map its permitted source values into those fields.
- Extremely long values that cannot fit above the preset's minimum font size block preflight. A manager must adjust and republish the editable layout; data is never silently truncated.
- Supplied private artwork is intentionally absent from public source and CI. Each installation needs the private import bundle. CI uses synthetic assets for the same backend workflow.
- No merge or production deployment is part of this change.

During verification, an incorrectly scoped lint invocation touched files outside the app. Tool-only changes were reversed against repository originals, affected private runtime packages/scripts were restored, and normalized AST comparisons verified preservation of all eight previously edited Tele Tena Python files. Original Frappe, ERPNext and the isolated Frappe v16 checkout are clean. Some formatting within already-edited Tele Tena hunks may differ; the pre-existing semantic changes and frontend files are preserved. The full test suites above were rerun successfully after repair.
