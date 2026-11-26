# BAIC Vision Partnership Card

This optional editable preset uses the normal ID Card Template, builder, publication, User selector and private PDF pipeline. It is **not installed automatically**. No BAIC business app is required. It never replaces the protected generic sample or changes the site's default.

## Install/import on a staging site

From this repository's bench (the inspected remote is `origin`):

```bash
# Review branch, not a production deployment:
git -C apps/id_card_designer fetch origin
git -C apps/id_card_designer switch feature/baic-vision-partnership-card
bench --site YOUR_STAGING_SITE migrate
bench build --app id_card_designer
bench --site YOUR_STAGING_SITE clear-cache
# Restart the normal web/worker processes after updating Python code.
```

Extract the original supplied artwork with the standalone tool, using Python with PyMuPDF 1.26.7. The arguments are explicit, so alternate attachment filenames work:

```bash
python apps/id_card_designer/scripts/extract_baic_bundle.py \
  /private/path/BAIC_Vision_Partnership_Card_Front_and_Back.pdf \
  /private/path/BAIC_Demo_Vision_Partnership_Card_Front_and_Back.pdf \
  /private/path/baic-bundle

bench --site YOUR_STAGING_SITE execute id_card_designer.presets.baic.setup \
  --kwargs '{"bundle_path":"/private/path/baic-bundle"}'
```

The extractor reconstructs alpha using each original image's soft mask. The bundle contains separate logo, decorative background (not a finished card raster), seal, signature and fictional portrait PNGs, a manifest, and a private reference-analysis report. It refuses to write inside this public repository. Keep this bundle, supplied PDFs and all rendered evidence private; no signature, portrait or supplied branding is committed.

Setup validates and normalizes all five images before creating an editable **Draft** named **BAIC Vision Partnership Card**, ID `baic-vision-partnership-card`. Logo/background/seal/signature use private Files attached to managed shared **ID Card Asset** records. The demo portrait uses a private File attached to the template. Re-running setup returns the existing template without changing its title, layouts, publications, revisions, assets or default selection. Existing shared Asset images are also preserved. Setup does not create Users or profiles, publish, populate production contacts, or select a new default. A normal Frappe backup of database **and private files** preserves these assets.

Open `/app/id-card-builder/baic-vision-partnership-card` or use Open Designer from its Template form. Front/back layers remain individually editable: text, portrait, branding, seal, signature and QR. Save/reload works through existing autosave and optimistic concurrency. **Fictional preview** selects populated demo or blank design. The existing Preview User control supports permitted record previews; previews remain marked SAMPLE even when using a real record. Publish with an ID Card Manager after review. Published, enabled and audience-permitted BAIC templates then appear in **User → Print ID Card**. No separate BAIC printing route exists.

## Configure before issuance

1. In **ID Card Settings**, enter `baic_office_contact`, the approved institutional chapel-office contact. It is different from the partner's phone/email. Only managers can edit settings; fictional demo contacts are never production fallbacks.
2. Use a saved User with its actual full name, permitted private portrait, and partner phone/email.
3. Create the app-owned **ID Card Profile** linked to that User. Fill chapel, Gregorian anointment date, organizational card number and address. Set a role title/approved translation if needed and optional department.
4. Configure template audience roles, source-User read **and print**, Profile and File access. An app printing role alone does not grant access to all Users. Managers alone can publish.
5. Inspect live-record preflight and PDF before issuance. Missing required BAIC data or office settings blocks issuance. Optional department, phone, email and second address line hide their values and labels when absent. Readable text must fit; there is no silent truncation or shrinking below the preset minimum.

The printed label **DEPARTMENT** follows the explicit approved label list and PDF. Legacy title-case “Department”, “Member”, “Membership Card” and “Parish” are not used as preset labels or demo chapel names. This does not rename any ERP business terminology. `Parish`/`Parish Chapel` in a chapel display value is presented as `Chapel`, without altering the stored source. Actual role titles such as Department Coordinator remain actual positions, subject to measured fit.

## Field mapping

| Card value | Source | Formatting/fallback | Visibility/required rule |
|---|---|---|---|
| Full name | approved `User.full_name` | uppercase `card_full_name` | required |
| Portrait | approved `User.user_image` private File | proportional cover, 1.2mm rounded mask; **no live demo fallback** | required |
| Chapel | `ID Card Profile.chapel` | `profile_chapel` → `card_chapel`; legacy Parish wording normalized for display | required |
| Date of anointment | `Profile.anointment_date` **Gregorian Date** | explicit Ethiopian conversion → `card_anointment` | required; never issue/creation date |
| Chapel role | `Profile.role_title` | empty or exact legacy Member → Vision Partner; preserve other positions | always displayed |
| Role translation | `Profile.role_translation` | fixed የራዕይ ተካፋይ only for Vision Partner; approved source translation for another role, otherwise empty | hide if absent |
| Department | `Profile.department` | `card_department`, no fallback | hide value **and label** if absent |
| Card number | `Profile.card_number` | `card_number` for footer; `profile_card_number` for live QR | required, no issuance fallback |
| Address | `Profile.address_line_1`, `address_line_2` | `card_address_1/2`, no demo fallback | line 1 required; line 2 optional |
| Partner phone | permitted `User.mobile_no`, then `User.phone` | `card_phone` | hide value/label if absent |
| Partner email | permitted `User.email` | `card_email` | hide value/label if absent |
| Chapel office | `ID Card Settings.baic_office_contact` | `card_office`, independent of User contacts | required for live output |

Only explicitly approved Profile fields were added. Core User, Member and unrelated apps were not modified. No BAIC app or linked Member schema was found in the inspected bench (Frappe, ERPNext, Tele Tena, ID Card Designer). If an institution has a separate BAIC source elsewhere, map its permitted values into these Profile fields; do not broaden the renderer's field allowlist or permission model.

### Calendar semantics

Frappe Date fields are Gregorian. `anointment_date` is labeled accordingly. The renderer converts using Ethiopian Amete Mihret/ICU CE-calendar epoch arithmetic; the `E.C.` suffix is added **only after conversion**. Never paste an EC date into that Gregorian Date field. For an EC source, first call the explicit helper `ethiopian_to_gregorian(year, month, day)`.

Known regression cases:

| Gregorian source | Ethiopian display |
|---|---|
| 2025-10-22 | 12 / 02 / 2018 E.C. |
| 2025-09-11 | 01 / 01 / 2018 E.C. |
| 2023-09-12 | 01 / 01 / 2016 E.C. |
| 2023-09-11 | 06 / 13 / 2015 E.C. (leap day) |
| 2024-09-11 | 01 / 01 / 2017 E.C. |

Algorithm reference: [Unicode ICU Ethiopic calendar](https://github.com/unicode-org/icu/blob/main/icu4c/source/i18n/ethpccal.cpp), [CE calendar](https://github.com/unicode-org/icu/blob/main/icu4c/source/i18n/cecal.cpp). The implementation includes invalid-day and round-trip tests.

## Design, fitting, fonts and QR

Trim is exactly **85.60 × 53.98mm**. Source PDFs measured 85.600013 × 53.980012mm (rounding). The separate decorative background preserves the ivory/sage chapel arch/cross. Teal `#154C48`, text `#183A36`, muted `#526D62`, gold `#B09455`, pale sage `#E5EDE4` and ivory `#F7F8EF` are the approved palette; background shading comes from the actual supplied image.

Original anchors (x/y/width/height mm): logo both sides `3.8/2.7/8.7/8.7`; portrait `3.8/15.5/21.3/27.3`; seal `17.15/40/11.6/7.73`; signature `39.5/26/19.1/7.4`; QR including quiet zone `59.8/14.9/22/22`. Seal comes after the portrait in layer order and uses its own box, not the portrait mask. Only about 25% of its rectangular area intersects the photo. The signature is 29% opacity, ends at x=58.6mm, and leaves 1.2mm before the QR's white quiet-zone box. QR remains fully opaque. The gold footer rule starts at y=47.9mm; teal starts at 48.4mm.

English uses local Open Sans Regular/600 Semibold/700 Bold. Amharic uses local Noto Sans Ethiopic Regular. Full local TTFs and OFL licenses are packaged, with provenance under `public/fonts`; PDF and editor share the same font registry/CSS. Missing font files fail generation and missing rendered glyphs fail BAIC preflight. No production font/network fetch occurs. Baselines and the source PDF's explicit tracking (0.3pt body, 0.42pt institution heading, 0.38pt subtitle, etc.) are preserved.

Optional `fit_min_pt` is a reusable scene property. PDF fitting searches a bounded quarter-point range using **actual WeasyPrint LineBox layout**. The editor uses the same local font files and quarter-point limit, with geometric-precision text rendering to avoid small-font hinting changing line breaks. Converting a visual scene to code preserves its bleed extension. If text still does not fit at the minimum, preflight reports `text_clipped` and BAIC blocks publication/printing. This is deliberately not automatic truncation or arbitrary font shrinking. Extremely long names, roles, addresses and translations require a designer to adjust the layout, then re-publish normally.

Preview/demo flags are computed server-side by the existing authenticated preview path, never accepted as issuance data. Fictional demo uses the supplied values, extracted portrait, SAMPLE and DEMO - NOT VALID on the front, DEMO QR on the back. Blank preview uses DESIGN SAMPLE and placeholders. Live printing always reads the permitted User/Profile, omits preview badges/placeholders, uses actual office settings, and logs the actual pinned published revision.

The existing QR component encodes `BAIC|DEMO|BAIC-001248` in fictional demo and the actual `profile_card_number` for issuance. It does not encode personal contacts or assert identity verification. Existing HTTPS origin restrictions, minimum module size, contrast and at least four quiet-zone modules remain in force; unscannable geometry/payload configuration is rejected. No portal/service was invented.

Three-millimetre bleed uses **91.60 × 59.98mm MediaBox**, centered **85.60 × 53.98mm TrimBox**, zero margins. The background's edge pixels extend into bleed while preserving its trim composition; edge-touching decorative bars extend too. Existing crop marks remain supported. Shadows and Desk margins never enter PDF/PNG exports.

## Reproducible verification

Backend tests use synthetic raster assets generated in a temporary private bundle; no supplied personal artwork is committed or required in CI:

```bash
bench --site YOUR_DISPOSABLE_TEST_SITE run-tests --app id_card_designer
npm run test:unit
ruff check .
ruff format --check .
python -m build --wheel
```

For the real-asset browser proof, `scripts/prepare_baic_acceptance.py` and the existing `prepare_browser_test.py` require an **explicitly marked disposable** `id-card-*-test.localhost` site. The former deliberately creates a synthetic User/Profile only for this test workflow. See the test record for environment variables, the loopback WSGI server, and commands. `scripts/browser_baic.cjs` refuses to store supplied-artwork evidence inside the public repository. It exercises real server saves, previews, publication, User selection and PDF POST delivery; successful operations/PDF bytes are not mocked.

`scripts/verify_baic_exports.py` produces raw front/back PNGs at 600dpi (**2023 × 1276px**), decodes demo/live QR, checks exact wording and embedded fonts, measures page geometry and compares both faces beside the references at matched scale. These outputs remain private because they contain the supplied signature/portrait/logo. Physical printer/duplex tests were not performed.
