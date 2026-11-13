# Using and administering ID Card Designer

## First setup

Assign **ID Card Designer** to design staff, **ID Card Manager** to publication administrators, and **ID Card Printer** to printing staff. System Managers can administer all three workflows. These roles never grant access to all Users: configure ordinary Frappe User read/print permissions and Profile/File sharing for your institution.

Open **ID Card Designer** in Desk; duplicate the protected unofficial demo or create a blank template. All measurements are millimetres. The default trim is 85.60 × 53.98 mm. Front and back are separate scenes. The sample and fictional preview always identify themselves as SAMPLE / NOT VALID ID.

## Editing and recovery

Both faces autosave after 700 ms of inactivity. The status reports Unsaved, Saving…, Saved, Error, Offline/Disconnected or Conflict. Save draft, Publish and navigation flush pending writes. An unsafe browser exit warns. A crash/refresh can recover unsaved source from AES-GCM encrypted sessionStorage for the same login; the encryption key stays in memory and Redis, scoped to the login session with a 24-hour lifetime. No portrait bytes or PDF files are persisted in browser storage. Browser storage is best-effort: if unavailable, online server saving still works. Offline recovery requires available sessionStorage and Web Crypto.

For a conflict, use **Compare / recover**. Compare saved source with local source, then **Reload saved draft** or **Save conflict copy**. The app never automatically overwrites the other editor. Retry save recovers transient server/network errors. A conflict copy is a new unpublished template.

Select multiple layers using Shift-click. Group/Ungroup preserve affine world geometry, including rotated and nonuniformly resized groups. Groups can nest six levels, with 100 total objects per face. Move/resize/rotate a group, align/distribute selections, reorder, lock/unlock, duplicate and delete. Properties use physical coordinates. Ungrouped sheared transforms retain a six-value affine matrix rather than rounding to a rotation. Undo/redo stores scene checkpoints.

Keyboard: arrows nudge 0.1 mm; Shift-arrows nudge 1 mm; Delete deletes; Ctrl/Cmd+D duplicates; Ctrl/Cmd+G groups; Ctrl/Cmd+Shift+G ungroups; Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z undo/redo; Ctrl/Cmd+S saves. Inputs retain normal text-editing shortcuts. PageUp/PageDown cycle selected layers. Tab moves focus between native labeled controls and the canvas.

Use **Add richtext** for approved b/strong/em/i/p/span/br markup, or convert a visual draft to a separate code copy. The generated `<ic-scene>` retains bindings, conditions, fallbacks, groups and date rules. Code accepts a bounded HTML/CSS subset and `{{ approved_field }}` placeholders, never Jinja or executable scripts. Arbitrary edited HTML cannot be converted back into visual objects.

## Images and QR

Upload local PNG/JPEG/WebP through the builder. Files attach privately to a saved template, normalize EXIF orientation and retain alpha. Bounds: 5 MB input, 24 million decoded pixels; unusually large normalized output is downsampled. Remote URLs and user-supplied SVG are disabled. Managers can create **ID Card Asset** records for a shared institutional image library; content access is checked on the server.

QR supports static organizational text (maximum 512 UTF-8 bytes) or **profile_card_number**, with a fallback. ECC L/M/Q/H, 4–12 quiet-zone modules, square geometry and dark-on-light contrast of at least 7:1 are enforced. Printed modules must be at least 0.25 mm after transforms; skew, distortion and transparency are blocked. Code example:

```html
<ic-qr text="ORG-DEMO-001" size="25" error="M" quiet="4"></ic-qr>
```

An optional HTTPS URL must match the manager-approved **QR application origin**; credentials, fragments and query strings are disabled. The renderer never requests that URL. This app issues no verification tokens, offers no identity verifier, and has no government credential integration. Use an opaque institutional reference rather than personal information.

## Preflight and publication

**Preflight** measures the actual WeasyPrint text boxes and embedded-font glyph coverage, affine object bounds, safe area, bleed, QR geometry and pagination. It highlights affected objects. Set the safe margin, enable **Severe preflight errors → Block**, and inspect both faces using representative long and non-Latin values. Intentional clipping/bleed flags distinguish masks/backgrounds from accidental overflow. QR and pagination failures always block. Missing fields are warnings. Font shrinking is not automatic.

Manager publication atomically snapshots the saved draft, retaining 30 prior publications. Further autosaves leave printable content unchanged. **Restore revision** makes a draft; publish it explicitly to roll back production output. The default must stay active and published. Duplicate the immutable built-in sample to customize it.

With 3 mm bleed, MediaBox becomes 91.60 × 59.98 mm and TrimBox remains 85.60 × 53.98 mm. Optional crop marks occupy the bleed and require at least 3 mm. Print at actual size/100%; test your printer's duplex feed orientation and margins physically.

## Printing, access and retention

On a saved permitted User, choose **Print ID Card**, select a published template, and open the new tab. It receives a real two-page private inline PDF: front then back. Browser controls provide print/download. The prepared request pins the published revision, expires after 60 seconds and belongs to its originating login session. Delivery rechecks current template audience/availability and User read/print permission. Managers or the owner can revoke outstanding descriptors using `id_card_designer.api.revoke_pdf` (POST).

PDF bytes are generated on demand, never saved as public Files or cached on the server. Responses use private/no-store headers. A downloaded copy cannot be revoked. Print audit records contain User/template/revision references, not PDF contents; the daily app scheduler deletes audit records older than the configured 1–3650 days (default 90). No scheduler cleanup deletes templates, portraits, profiles or Users. Ensure normal Frappe scheduler operation for audit retention.

## Troubleshooting

- **No print action:** save the User and check both the ID Card Printer role and ordinary User read/print permissions.
- **PDF expired:** reopen the dialog; do not share descriptor tokens or URLs.
- **Image denied:** check attachment permissions and that its File is readable to the printing user.
- **Missing glyph:** use bundled FreeSerif or install an appropriate local font, then check PDF font embedding and raster output.
- **Conflict:** compare/recover, never retry stale source by changing its modification timestamp.
- **Popup blocked:** allow this site's print tab and retry the native dialog.
- **Failed assets after upgrade:** run migrate, build, clear-cache and restart the normal bench processes.
