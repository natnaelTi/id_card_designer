# Changelog

## 0.2.1

- Fix Desk boot on early Frappe v16 by detecting the unsafe Desktop Icon loader, retaining workspace/sidebar navigation, and removing only this app's incompatible icon during migration. No framework monkeypatch or core edits.
- Add a real boot regression that reproduces the original failure before repairing it, plus Frappe 16.2.1 in CI alongside v15 and current v16.
- Support actual missing-glyph reporting on WeasyPrint 66 used by early v16.
- Explicitly set inline Content-Disposition on app PDF responses; early v16 drops the requested disposition. Other responses are untouched.

## 0.2.0

- Serialized optimistic autosave for both faces, explicit failure/offline/conflict states, encrypted session recovery, conflict copies and navigation flush.
- Nested affine groups, ungroup without drift, multi-selection, alignment/distribution, locks, rich text, shared assets and QR controls.
- Bounded deterministic vector QR with an actual decoder/PDF raster regression suite; institutional references and admin-approved HTTPS origins only.
- Measured text clipping, font coverage, transformed physical bounds, intentional masks/bleed, blocking preflight, crop marks and TrimBox.
- Pinned prepared PDF publications, revocation, session isolation, audit retention, strict image byte handling and upload normalization before v16 metadata processing.
- v15/v16 permission/list API compatibility, native v16 navigation, modern test cases, isolated install/migrate/uninstall lifecycle scripts and GitHub Actions.

## 0.1.0

Initial two-face templates, protected demo, publication/default/revision workflow, User-form private PDF printing, visual/code editors and profile bindings.
