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
