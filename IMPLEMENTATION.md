# Implementation and milestone record

The initial plan prioritized the complete saved-User → published-template → inline-PDF workflow before editor polish. The implementation is a standalone custom app; no Frappe, ERPNext or Tele Tena source files were changed.

| Milestone | Implemented result |
| --- | --- |
| Foundation and permissions | Five DocTypes; manager/designer/printer roles; source-User and field-level read checks; template audiences; protected default; settings; optional 1:1 institutional profile; audit metadata |
| User printing and PDF | `doctype_js` User action, native gallery/default selection, popup reservation, CSRF POST delivery, two-page physical-size PDFs, local fonts, permitted images, private cache headers |
| Sample and editing | Protected unofficial bilingual sample; millimetre scenes; native Page canvas with editable elements, uploads, properties/layers, history, keyboard support, front/back independence, presets and bleed |
| Code and publication | Separate-copy visual-to-code scaffold, local Ace editor, restricted placeholders/HTML/CSS, draft snapshots, manager publication/defaults and rollback, stable live printing |
| Verification and delivery | 27 passing native tests; Chromium end-to-end acceptance; independent fresh install and two migrations; build/wheel checks; sample PDFs, screenshots, documentation and scoped runtime helpers |

## Architecture

- `hooks.py` integrates the User form and template form, registers install/migrate hooks, PDF response headers and document permission guards. Hooks apply only to sites where the app is installed.
- `security.py` defines capabilities and discovers permitted known User fields. Optional profile fields are explicitly approved and separately permission-checked. User authentication/security fields are not exposed.
- `api.py` is the authenticated API boundary. Standard Frappe document permission checks remain in force. Publication and default switching lock the app's settings DocType row, and request transactions provide atomic commit/rollback.
- `ID Card Template` stores editable source independently from the published snapshot and a bounded history of publications. Its controller rejects direct alteration of protected fields; publication flags live in server request state, not caller-supplied document flags.
- `rendering.py` validates the scene and the small HTML/CSS language, resolves permitted images, escapes text/attributes, embeds the bundled font, renders one fixed-size page per face, and merges exactly two pages with pypdf. Its resource fetcher only decodes generated in-memory PNG/font data.
- The native `id-card-builder` Page uses Frappe's Page, Dialog, FileUploader and Ace facilities. Geometry is stored in millimetres; pixel scaling is view-only. This avoids an additional production frontend framework/build dependency while reusing the installed Desk controls.
- Uploaded scene assets attach to the owning template using normal Frappe File mechanisms. Private source portraits retain their original File permissions. The audit log stores who generated a card, the source User link, template/revision and success status, without storing PDF bytes.
- Browser delivery uses a random 60-second identity/session-bound Redis capability. A reserved tab posts the capability and native CSRF token, so neither User data nor tokens enter PDF-delivery URLs or access logs. Rendering rechecks all access.

## Installation and upgrade behavior

The seed routine inserts missing roles, workspace, default settings and one protected sample. It never rewrites an existing sample or customer template. Normal DocType synchronization adds schema changes; saved scenes, published snapshots and a chosen customer default remain intact. Two actual migrations were tested after creating/customizing/publishing/selecting another template.

The app is registered in this Bench's `sites/apps.txt` and installed in its Python environment. Only two newly created development sites were installed/migrated. Temporary services and logs are under `/tmp/id-card-runtime`; incomplete directories from failed initial connection attempts were moved into that private runtime archive rather than left as broken Bench sites. Existing applications, sites and production services were preserved.

## Scope and limitations

The working end-to-end features above are implemented. Optional/editor enhancements are explicitly unfinished: autosave, grouping, dynamic object alignment guides, a visual rich-text toolbar, global asset-library management, QR/barcode generation, crop marks, PDF/X/CMYK support and exact text-overflow measurement. Code mode is intentionally a safe subset and has no HTML-to-visual round trip. See README for details and TEST_RESULTS for remaining manual/browser/physical-printer and Frappe-v16 checks.

## Phase-two continuation (2026-11-13)

The phase-one sections above are a historical milestone record, not the release verification matrix. See TEST_RESULTS.md for current results.

1. Reverified baseline cb66a7d on the existing v15 framework (27 tests), confirmed app-only history/empty remote, bootstrapped main, and developed on feature/finish-id-card-designer. Existing uncommitted Tele Tena work was preserved.
2. Added canonical affine geometry, nested groups and lossless flattening; serialized optimistic autosave with encrypted recovery; explicit code scene/QR primitives; managed image assets and bounded normalization.
3. Replaced character estimates with actual renderer text/geometry/font measurement, added safe-zone/bleed/mask exceptions, mandatory QR/pagination blocks, configurable severe blocks, crop marks and TrimBox. Prepared private PDFs pin publication snapshots/revisions.
4. Added security/PDF/raster/decoder tests, real browser failure/conflict/recovery tests, disposable lifecycle scripts, and GitHub Actions against official pinned releases.
5. Actual failure findings and fixes: v16 permission hooks must explicitly return True for allowed access; v16 list limits use `limit`; binary File content must remain bytes; normalize uploads before native EXIF processing; Redis request-local cached misses cannot initialize recovery keys reliably (use atomic SET NX EX); Bench requires patches.txt for app discovery; WeasyPrint 70 requires URLFetcherResponse for custom resources.
6. The available v16.2.1 framework had an upstream Desktop Icon boot failure (`frappe.get_doc("Desktop Icon", dictionary)`), so release verification moved to a separately cloned official v16.56.0, Python 3.14 and Node 24, with its own virtual environment. No installed framework checkout was changed. Current v16 pins WeasyPrint 70, requiring the compatible response adapter.
7. Runtime evidence moved out of /tmp after the previous usage-limit restart removed temporary services/logs. The private `.id-card-runtime` directory belongs to the surrounding bench and is never part of the application repository. All sites are explicitly marked disposable, use synthetic fixtures, and connect to a private socket database/Redis. Lifecycle uninstall refuses unmarked or incorrectly named sites.

Remaining product boundaries are documented in README and ADMIN_GUIDE: safe declarative code rather than executable HTML/Jinja, no government verification, schematic gallery thumbnails, RGB rather than certified press-color output, Chromium browser coverage rather than untested browsers/printers. These are not silently reported as completed integrations.
