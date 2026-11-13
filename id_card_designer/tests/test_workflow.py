import io
import json

import frappe

try:
    from frappe.tests import IntegrationTestCase, change_settings
except ImportError:
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase
    from frappe.tests.utils import change_settings
from pypdf import PdfReader

from id_card_designer import api
from id_card_designer.install import DEMO_NAME, seed


class WorkflowTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        for email, role in [
            ("designer@id.test", "ID Card Designer"),
            ("printer@id.test", "ID Card Printer"),
            ("manager@id.test", "ID Card Manager"),
            ("plain@id.test", None),
        ]:
            if not frappe.db.exists("User", email):
                user = frappe.get_doc(
                    dict(
                        doctype="User",
                        email=email,
                        first_name=email.split("@")[0],
                        send_welcome_email=0,
                        user_type="System User",
                    )
                ).insert()
                if role:
                    user.add_roles(role)
        self.copy = api.duplicate_template(DEMO_NAME)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_seed_idempotent_and_protected(self):
        before = frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot
        seed()
        seed()
        self.assertEqual(frappe.db.count("ID Card Template", {"builtin": 1}), 1)
        self.assertEqual(frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot, before)
        with self.assertRaises(frappe.PermissionError):
            d = frappe.get_doc("ID Card Template", DEMO_NAME)
            d.title = "bad"
            d.save()
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("ID Card Template", DEMO_NAME)

    def test_publish_snapshot_draft_restore(self):
        d = api.publish_template(self.copy["name"])
        first = frappe.get_doc("ID Card Template", d["name"]).published_snapshot
        front = json.loads(d["front_layout"])
        front[2]["text"] = "New draft title"
        d["front_layout"] = json.dumps(front)
        api.save_draft(d)
        self.assertEqual(frappe.get_doc("ID Card Template", d["name"]).published_snapshot, first)
        api.publish_template(d["name"])
        self.assertEqual(len(api.list_revisions(d["name"])), 1)
        restored = api.restore_revision(d["name"], 1)
        self.assertNotIn("New draft title", restored["front_layout"])
        self.assertIn(
            "New draft title", frappe.get_doc("ID Card Template", d["name"]).published_snapshot
        )
        api.publish_template(d["name"])
        self.assertEqual(frappe.get_doc("ID Card Template", d["name"]).revision, 3)

    def test_default_and_availability(self):
        api.publish_template(self.copy["name"])
        api.set_default_template(self.copy["name"])
        self.assertEqual(frappe.get_single("ID Card Settings").default_template, self.copy["name"])
        self.assertEqual(sum(t["is_default"] for t in api.list_usable_templates()), 1)
        d = api.get_template_for_builder(self.copy["name"])
        d["enabled"] = 0
        with self.assertRaises(frappe.ValidationError):
            api.save_draft(d)
        api.set_default_template(DEMO_NAME)
        api.save_draft(d)
        self.assertNotIn(self.copy["name"], [t["name"] for t in api.list_usable_templates()])

    def test_roles_and_direct_document_routes(self):
        frappe.set_user("plain@id.test")
        for fn, args in [
            (api.list_usable_templates, ()),
            (api.get_preview_data, ()),
            (api.get_template_for_builder, (DEMO_NAME,)),
            (api.prepare_pdf, (DEMO_NAME, "plain@id.test")),
        ]:
            with self.assertRaises(frappe.PermissionError):
                fn(*args)
        frappe.set_user("designer@id.test")
        self.assertEqual(api.get_preview_data()["full_name"], "Selam Example")
        d = api.get_template_for_builder(self.copy["name"])
        d["title"] = "Designer draft"
        api.save_draft(d)
        for fn, args in [
            (api.publish_template, (d["name"],)),
            (api.set_default_template, (d["name"],)),
            (api.print_user_id, (DEMO_NAME, "Administrator")),
        ]:
            with self.assertRaises(frappe.PermissionError):
                fn(*args)
        with self.assertRaises(frappe.PermissionError):
            api.get_preview_data("Administrator")
        direct = frappe.get_doc("ID Card Template", d["name"])
        direct.status = "Published"
        with self.assertRaises(frappe.PermissionError):
            direct.save()

    def test_manager_publication_and_hidden_fields(self):
        frappe.set_user("manager@id.test")
        published = api.publish_template(self.copy["name"])
        self.assertEqual(published["status"], "Published")
        self.assertTrue(frappe.get_doc("ID Card Template", published["name"]).published_snapshot)

    def test_printer_source_permission_and_token_owner(self):
        frappe.set_user("printer@id.test")
        self.assertTrue(api.list_usable_templates())
        with self.assertRaises(frappe.PermissionError):
            api.print_user_id(DEMO_NAME, "Administrator")
        # Own User has Frappe's normal read/print access; no broad User grants from the app.
        frappe.set_user("Administrator")
        frappe.share.add("User", "printer@id.test", user="printer@id.test", read=1)
        frappe.set_user("printer@id.test")
        url = api.prepare_pdf(DEMO_NAME, "printer@id.test")
        token = url["token"]
        api.deliver_pdf(token)
        self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF-"))
        frappe.set_user("manager@id.test")
        with self.assertRaises(frappe.PermissionError):
            api.deliver_pdf(token)

    def test_real_user_pdf_and_log(self):
        api.print_user_id(DEMO_NAME, "designer@id.test")
        raw = frappe.local.response.filecontent
        pages = PdfReader(io.BytesIO(raw)).pages
        self.assertEqual(len(pages), 2)
        self.assertIn("designer", pages[0].extract_text())
        self.assertIn("designer@id.test", "\n".join(page.extract_text() for page in pages))
        self.assertTrue(frappe.db.exists("ID Card Print Log", {"source_user": "designer@id.test"}))

    def test_field_schema_and_stale_draft(self):
        fields = [f["fieldname"] for f in api.get_field_schema()]
        for f in ["api_key", "api_secret", "new_password", "reset_password_key"]:
            self.assertNotIn(f, fields)
        d = dict(self.copy)
        d["modified"] = "2000-01-01"
        with self.assertRaises(frappe.TimestampMismatchError):
            api.save_draft(d)

    def test_profile_fields_require_source_and_profile_read(self):
        from id_card_designer.security import user_data

        profile = frappe.get_doc(
            dict(
                doctype="ID Card Profile",
                user="designer@id.test",
                department="Research",
                card_number="INSTITUTION-17",
                local_name="ሰላም",
                issue_date="2026-01-01",
                expiry_date="2027-01-01",
            )
        ).insert()
        self.assertEqual(user_data("designer@id.test")["profile_department"], "Research")
        frappe.set_user("designer@id.test")
        self.assertFalse(frappe.has_permission("ID Card Profile", "read", doc=profile))
        with self.assertRaises(frappe.PermissionError):
            api.get_preview_data("Administrator")
        frappe.set_user("manager@id.test")
        self.assertFalse(frappe.has_permission("ID Card Profile", "read", doc=profile))

    def test_private_image_permission_and_invalid_content(self):
        from PIL import Image

        from id_card_designer.rendering import asset
        from id_card_designer.testing import save_file

        out = io.BytesIO()
        Image.new("RGB", (600, 600), "teal").save(out, format="PNG")
        f = save_file("id-card-test.png", out.getvalue(), "User", "Administrator", is_private=1)
        self.assertTrue(asset(f.file_url).startswith("data:image/png;base64,"))
        frappe.set_user("designer@id.test")
        with self.assertRaises(frappe.PermissionError):
            asset(f.file_url)

    def test_client_flags_cannot_publish(self):
        frappe.set_user("designer@id.test")
        direct = frappe.get_doc("ID Card Template", self.copy["name"])
        direct.flags.publishing = True
        direct.status = "Published"
        with self.assertRaises(frappe.PermissionError):
            direct.save()

    def test_capability_checks_do_not_show_permission_errors(self):
        frappe.set_user("plain@id.test")
        before = len(getattr(frappe.local, "message_log", []) or [])
        self.assertEqual(api.capabilities(), dict(design=False, manage=False, print=False))
        self.assertEqual(len(getattr(frappe.local, "message_log", []) or []), before)

    def test_audience_filters_api_and_direct_read(self):
        api.publish_template(self.copy["name"])
        d = frappe.get_doc("ID Card Template", self.copy["name"])
        d.allowed_roles = "ID Card Manager"
        d.save()
        frappe.set_user("printer@id.test")
        self.assertNotIn(d.name, [x["name"] for x in api.list_usable_templates()])
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("ID Card Template", d.name).check_permission("read")

    def test_private_template_asset_is_usable_by_authorized_printer(self):
        from PIL import Image

        from id_card_designer.testing import save_file

        out = io.BytesIO()
        Image.new("RGB", (700, 900), "teal").save(out, format="PNG")
        f = save_file(
            "institution-logo.png",
            out.getvalue(),
            "ID Card Template",
            self.copy["name"],
            is_private=1,
        )
        d = api.get_template_for_builder(self.copy["name"])
        front = json.loads(d["front_layout"])
        image = next(e for e in front if e["type"] == "image")
        image.update(field="", src=f.file_url)
        d["front_layout"] = json.dumps(front)
        api.save_draft(d)
        api.publish_template(d["name"])
        frappe.share.add("User", "printer@id.test", user="printer@id.test", read=1)
        frappe.set_user("printer@id.test")
        api.print_user_id(d["name"], "printer@id.test")
        p = PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages
        self.assertEqual(len(p), 2)
        self.assertTrue(p[0]["/Resources"]["/XObject"])

    def test_image_orientation_and_transparency_survive_normalization(self):
        import base64

        from PIL import Image

        from id_card_designer.rendering import asset
        from id_card_designer.testing import save_file

        image = Image.new("RGB", (40, 20), "teal")
        exif = Image.Exif()
        exif[274] = 6
        out = io.BytesIO()
        image.save(out, format="JPEG", exif=exif)
        # v16 strips EXIF at generic upload by default. Preserve the orientation in
        # this fixture to test our normalizer itself; the app uploader normalizes before insert.
        with change_settings("System Settings", strip_exif_metadata_from_uploaded_images=0):
            file = save_file(
                "rotated-photo.jpg", out.getvalue(), "User", "Administrator", is_private=1
            )
        normalized = Image.open(io.BytesIO(base64.b64decode(asset(file.file_url).split(",", 1)[1])))
        self.assertEqual(normalized.size, (20, 40))
        out = io.BytesIO()
        Image.new("RGBA", (20, 20), (0, 100, 50, 0)).save(out, format="PNG")
        file = save_file(
            "transparent-logo.png", out.getvalue(), "User", "Administrator", is_private=1
        )
        normalized = Image.open(io.BytesIO(base64.b64decode(asset(file.file_url).split(",", 1)[1])))
        self.assertEqual(normalized.getpixel((0, 0))[3], 0)

    def test_prepared_pdf_pins_revision_and_revocation(self):
        published = api.publish_template(self.copy["name"])
        token = api.prepare_pdf(published["name"], "designer@id.test")["token"]
        front = json.loads(published["front_layout"])
        front.append(dict(type="text", x=5, y=10, width=70, height=5, text="NEW REVISION MARKER"))
        published["front_layout"] = json.dumps(front)
        api.save_draft(published)
        api.publish_template(published["name"])
        api.deliver_pdf(token)
        text = "\n".join(
            p.extract_text() for p in PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages
        )
        self.assertNotIn("NEW REVISION MARKER", text)
        api.revoke_pdf(token)
        with self.assertRaises(frappe.PermissionError):
            api.deliver_pdf(token)

    def test_publish_rejects_stale_editor_and_blocked_geometry(self):
        stale = dict(self.copy)
        current = dict(self.copy, title="Concurrent saved draft")
        current = api.save_draft(current)
        with self.assertRaises(frappe.TimestampMismatchError):
            api.save_draft(stale)
        with self.assertRaises(frappe.TimestampMismatchError):
            api.publish_template(current["name"], stale["modified"])
        current["block_severe"] = 1
        current["front_layout"] = json.dumps(
            [dict(type="text", x=75, y=0, width=10, height=5, rotation=45, text="Outside")]
        )
        current = api.save_draft(current)
        with self.assertRaises(frappe.ValidationError):
            api.publish_template(current["name"], current["modified"])
        self.assertFalse(frappe.get_doc("ID Card Template", current["name"]).published_snapshot)

    def test_qr_preview_authorization_and_sensitive_bindings(self):
        element = dict(type="qr", x=5, y=5, width=25, height=25, text="ORG-DEMO")
        self.assertTrue(
            api.qr_preview(json.dumps(element)).startswith("data:image/svg+xml;base64,")
        )
        with self.assertRaises(frappe.PermissionError):
            frappe.set_user("plain@id.test")
            api.qr_preview(json.dumps(element))
        frappe.set_user("designer@id.test")
        with self.assertRaises(frappe.PermissionError):
            api.qr_preview(json.dumps(element), "Administrator")
        with self.assertRaises(frappe.ValidationError):
            api.qr_preview(json.dumps(dict(element, field="email")))

    def test_session_bound_recovery_key_and_no_source_data(self):
        first = api.draft_key()
        self.assertEqual(first, api.draft_key())
        frappe.set_user("designer@id.test")
        self.assertNotEqual(first, api.draft_key())
        self.assertNotIn("api_secret", json.dumps(api.get_field_schema()))

    def test_asset_upload_rejects_unrelated_target_and_script(self):
        frappe.local.form_dict = frappe._dict(doctype="User", docname="Administrator")
        with self.assertRaises(frappe.ValidationError):
            api.upload_asset()
        frappe.local.form_dict = frappe._dict(doctype="ID Card Template", docname=self.copy["name"])
        frappe.local.uploaded_file = b'<svg onload="alert(1)"></svg>'
        frappe.local.uploaded_filename = "unsafe.svg"
        with self.assertRaises(frappe.ValidationError):
            api.upload_asset()

    def test_inline_pdf_header_is_app_scoped(self):
        from werkzeug.wrappers import Response

        previous = getattr(frappe.local, "id_card_pdf", False)
        try:
            frappe.local.id_card_pdf = True
            response = Response()
            api.secure_pdf_headers(response)
            self.assertEqual(
                response.headers["Content-Disposition"], 'inline; filename="institutional-id.pdf"'
            )
            self.assertIn("no-store", response.headers["Cache-Control"])
            frappe.local.id_card_pdf = False
            other = Response()
            api.secure_pdf_headers(other)
            self.assertNotIn("Content-Disposition", other.headers)
        finally:
            frappe.local.id_card_pdf = previous
