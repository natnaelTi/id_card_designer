"""Synthetic preset tests. No supplied artwork, signature or portrait is in this repository."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from PIL import Image
from pypdf import PdfReader

try:
    from frappe.tests import IntegrationTestCase, UnitTestCase
except ImportError:
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

    UnitTestCase = unittest.TestCase
if not getattr(frappe.local, "site", None):
    UnitTestCase = unittest.TestCase

from id_card_designer import api
from id_card_designer import rendering as r
from id_card_designer.calendar import (
    ethiopian_to_gregorian,
    format_ethiopian,
    gregorian_to_ethiopian,
)
from id_card_designer.install import DEMO_NAME
from id_card_designer.presets import baic


def synthetic_bundle(folder):
    assets = {}
    for name in ("background", "logo", "seal", "signature", "demo_portrait"):
        out = Path(folder) / (name + ".png")
        Image.new(
            "RGBA",
            (180, 120) if name != "background" else (856, 540),
            {
                "background": "#F7F8EF",
                "logo": "#154C48",
                "seal": "#20208080",
                "signature": "#10101080",
                "demo_portrait": "#91B0A0",
            }[name],
        ).save(out)
        assets[name] = out.name
    (Path(folder) / "manifest.json").write_text(json.dumps(dict(assets=assets)))


class BAICUnitTests(UnitTestCase):
    def test_calendar_known_dates_leap_day_and_round_trip(self):
        for g, e in [
            ("2025-10-22", (2018, 2, 12)),
            ("2025-09-11", (2018, 1, 1)),
            ("2023-09-12", (2016, 1, 1)),
            ("2023-09-11", (2015, 13, 6)),
            ("2024-09-11", (2017, 1, 1)),
        ]:
            self.assertEqual(gregorian_to_ethiopian(g), e)
            self.assertEqual(ethiopian_to_gregorian(*e).isoformat(), g)
        self.assertEqual(format_ethiopian("2025-10-22"), "12 / 02 / 2018 E.C.")
        self.assertEqual(format_ethiopian(None), "")
        with self.assertRaises(ValueError):
            ethiopian_to_gregorian(2018, 13, 6)

    def test_role_translation_contacts_and_preview_separation(self):
        with patch(
            "frappe.get_single",
            return_value=SimpleNamespace(baic_office_contact="Institution office"),
        ):
            data = baic.context(
                {},
                dict(baic.DEMO, profile_role_title=" Member ", profile_chapel="Bole Parish Chapel"),
                preview=False,
            )
            self.assertEqual(data["card_role"], "Vision Partner")
            self.assertEqual(data["card_role_translation"], "የራዕይ ተካፋይ")
            self.assertEqual(data["card_chapel"], "Bole Chapel")
            self.assertEqual(data["card_office"], "Institution office")
            self.assertEqual(data["profile_card_number"], "BAIC-001248")
            self.assertFalse(data["card_is_preview"])
            other = baic.context({}, dict(baic.DEMO, profile_role_title="Pastor"), preview=False)
            self.assertEqual(other["card_role"], "Pastor")
            self.assertEqual(other["card_role_translation"], "")
            translated = baic.context(
                {},
                dict(baic.DEMO, profile_role_title="Pastor", profile_role_translation="ፓስተር"),
                preview=False,
            )
            self.assertEqual(translated["card_role_translation"], "ፓስተር")
            absent = baic.context({}, {}, preview=False)
            for field in ("card_phone", "card_email", "card_number", "card_chapel", "card_office"):
                if field != "card_office":
                    self.assertFalse(absent[field])
        demo = baic.context({}, preview=True)
        self.assertEqual(demo["profile_card_number"], "BAIC|DEMO|BAIC-001248")
        self.assertEqual(demo["card_full_name"], "DAWIT SAMUEL TESFAYE")
        blank = baic.context({}, preview=True, variant="design")
        self.assertEqual(blank["card_preview_badge"], "DESIGN SAMPLE")
        self.assertFalse(blank["user_image"])

    def test_separate_elements_anchors_and_optional_visibility(self):
        front, back = baic.scenes(
            dict.fromkeys(("background", "logo", "seal", "signature"), "/private/files/test.png")
        )
        portrait = next(e for e in front if e.get("field") == "user_image")
        self.assertEqual(
            [portrait[k] for k in ("x", "y", "width", "height")], [3.8, 15.5, 21.3, 27.3]
        )
        seal = next(e for e in front if e["type"] == "image" and e["x"] == 17.15)
        self.assertGreater(front.index(seal), front.index(portrait))
        self.assertNotIn("clip", seal)
        outline = next(e for e in front if e.get("name") == "Portrait outline")
        self.assertEqual(outline["style"]["border"], "0.4pt solid #A9BCAA")
        self.assertGreater(front.index(outline), front.index(portrait))
        self.assertLess(front.index(outline), front.index(seal))
        signature = next(e for e in back if e["type"] == "image" and e["x"] == 39.5)
        self.assertEqual(signature["style"]["opacity"], "0.29")
        qr = next(e for e in back if e["type"] == "qr")
        self.assertEqual([qr[k] for k in ("x", "y", "width", "height")], [59.8, 14.9, 22, 22])
        optional = [
            e
            for e in front + back
            if e.get("visible_if") in ("card_department", "card_phone", "card_email")
        ]
        self.assertEqual(len(optional), 6)
        self.assertNotIn("DEPARTMENT", r.render_elements(optional, {}))

    def test_required_data_is_preset_specific_and_has_no_issue_date_fallback(self):
        with patch("frappe.get_single", return_value=SimpleNamespace(baic_office_contact="")):
            data = baic.context(
                {}, dict(full_name="Synthetic User", profile_issue_date="2025-10-22"), preview=False
            )
        self.assertEqual(data["card_anointment"], "")
        self.assertTrue(baic.required_issues(dict(preset_key=baic.KEY), data))
        self.assertEqual(baic.required_issues({}, data), [])

    def test_qr_600dpi_fonts_and_centered_bleed_boxes(self):
        import base64

        import pymupdf
        import zxingcpp

        raw = io.BytesIO()
        Image.new("RGBA", (20, 20), "#F7F8EF").save(raw, format="PNG")
        uri = "data:image/png;base64," + base64.b64encode(raw.getvalue()).decode()
        assets = dict.fromkeys(
            ("background", "logo", "seal", "signature"), "/private/files/synthetic.png"
        )
        front, back = baic.scenes(assets)
        s = dict(
            editor_mode="Visual",
            width_mm=85.6,
            height_mm=53.98,
            bleed_mm=0,
            safe_margin_mm=0,
            crop_marks=0,
            preset_key=baic.KEY,
            demo_portrait="/private/files/synthetic.png",
            front_layout=json.dumps(front),
            back_layout=json.dumps(back),
        )
        data = baic.context(s, preview=True)
        with patch.object(r, "asset", return_value=uri):
            content = r.pdf(s, data)
            report = r.preflight(s, data)
            self.assertEqual(report["errors"], [])
            self.assertIn("Open Sans", report["fonts_used"])
            self.assertIn("Noto Sans Ethiopic", report["fonts_used"])
            doc = pymupdf.open(stream=content, filetype="pdf")
            pix = doc[1].get_pixmap(dpi=600, alpha=False)
            self.assertEqual((pix.width, pix.height), (2023, 1276))
            decoded = zxingcpp.read_barcode(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            )
            self.assertIsNotNone(decoded)
            self.assertEqual(decoded.text, "BAIC|DEMO|BAIC-001248")
            for font in doc[0].get_fonts():
                self.assertTrue(doc.extract_font(font[0])[3], "Fonts must be embedded")
            s.update(bleed_mm=3, crop_marks=1)
            # The normal visual-to-code wrapper must preserve the full bleed artwork.
            from bs4 import BeautifulSoup

            encoded = base64.b64encode(s["front_layout"].encode()).decode()
            code = dict(
                s, editor_mode="Code", front_html=f'<ic-scene source="{encoded}"></ic-scene>'
            )
            visual_bg = BeautifulSoup(r.side_html(s, "front", data), "html.parser").find("div")
            code_bg = BeautifulSoup(r.side_html(code, "front", data), "html.parser").find("div")
            self.assertEqual(code_bg["style"], visual_bg["style"])
            self.assertIn("width:91.6mm", code_bg["style"])
            pages = PdfReader(io.BytesIO(r.pdf(s, data))).pages
            self.assertEqual(len(pages), 2)
            for page in pages:
                self.assertAlmostEqual(float(page.mediabox.width) * 25.4 / 72, 91.6, places=3)
                self.assertAlmostEqual(float(page.mediabox.height) * 25.4 / 72, 59.98, places=3)
                self.assertAlmostEqual(float(page.trimbox.left) * 25.4 / 72, 3, places=3)
                self.assertAlmostEqual(float(page.trimbox.width) * 25.4 / 72, 85.6, places=3)
                self.assertAlmostEqual(float(page.trimbox.height) * 25.4 / 72, 53.98, places=3)

    def test_measured_fitting_and_unfittable_name_preflight(self):
        from weasyprint.formatting_structure.boxes import TextBox

        from id_card_designer.preflight import descendants

        e = baic.text("DAWIT SAMUEL TESFAYE", 5, 10, 36, 9, height=4.7, fit=7)
        s = dict(
            editor_mode="Visual",
            width_mm=85.6,
            height_mm=53.98,
            bleed_mm=0,
            front_layout=json.dumps([e]),
            back_layout=json.dumps([baic.text("BACK", 5, 10, 50, 8)]),
            safe_margin_mm=0,
        )
        pages = r.render_pages(s, {})
        sizes = [
            x.style["font_size"] * 72 / 96
            for x in descendants(pages[0].pages[0]._page_box)
            if isinstance(x, TextBox)
        ]
        self.assertTrue(sizes)
        self.assertTrue(all(7 <= n < 9 for n in sizes))
        self.assertEqual(r.preflight(s, {})["errors"], [])
        e["text"] = "VERY LONG NAME " * 80
        s["front_layout"] = json.dumps([e])
        self.assertTrue([i for i in r.preflight(s, {})["errors"] if i["code"] == "text_clipped"])


class BAICWorkflowTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("baic_case")
        self.bundle = tempfile.TemporaryDirectory()
        self.addCleanup(self.bundle.cleanup)
        synthetic_bundle(self.bundle.name)
        self.original_default = frappe.get_single("ID Card Settings").default_template
        baic.setup(self.bundle.name)
        self.doc = api.duplicate_template(baic.NAME)
        self.user = "baic-synthetic@org.example.invalid"
        if not frappe.db.exists("User", self.user):
            frappe.get_doc(
                dict(
                    doctype="User",
                    email=self.user,
                    first_name="Synthetic",
                    last_name="Partner",
                    send_welcome_email=0,
                    user_type="System User",
                )
            ).insert()
        image = frappe.get_doc(
            dict(
                doctype="File",
                file_name="baic-test-portrait.png",
                content=(Path(self.bundle.name) / "demo_portrait.png").read_bytes(),
                is_private=1,
                attached_to_doctype="User",
                attached_to_name=self.user,
            )
        ).insert()
        user = frappe.get_doc("User", self.user)
        user.user_image = image.file_url
        user.save()
        profile = frappe.get_doc(
            dict(
                doctype="ID Card Profile",
                user=self.user,
                chapel="Bole Chapel",
                anointment_date="2025-10-22",
                role_title="Member",
                card_number="ORG-BAIC-TEST-01",
                address_line_1="Synthetic address",
                address_line_2="Addis Ababa",
            )
        )
        if not frappe.db.exists("ID Card Profile", self.user):
            profile.insert()
        settings = frappe.get_single("ID Card Settings")
        settings.baic_office_contact = "Synthetic chapel office / office@example.invalid"
        settings.save()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="baic_case")
        super().tearDown()

    def test_setup_is_optional_idempotent_and_preserves_admin_publications_and_default(self):
        doc = api.get_template_for_builder(baic.NAME)
        doc["title"] = "Administrator edited BAIC"
        saved = api.save_draft(doc)
        published = api.publish_template(saved["name"])
        before = frappe.get_doc("ID Card Template", baic.NAME).published_snapshot
        count = frappe.db.count("File")
        self.assertFalse(baic.setup(self.bundle.name)["created"])
        self.assertEqual(
            frappe.get_doc("ID Card Template", baic.NAME).title, "Administrator edited BAIC"
        )
        self.assertEqual(frappe.get_doc("ID Card Template", baic.NAME).published_snapshot, before)
        self.assertEqual(frappe.db.count("File"), count)
        self.assertEqual(
            frappe.get_single("ID Card Settings").default_template, self.original_default
        )
        self.assertTrue(frappe.get_doc("ID Card Template", DEMO_NAME).builtin)
        self.assertEqual(published["status"], "Published")

    def test_real_published_user_pdf_pinned_revision_and_no_demo_badges(self):
        d = api.publish_template(self.doc["name"])
        token = api.prepare_pdf(d["name"], self.user)["token"]
        d["front_layout"] = d["front_layout"].replace("FULL NAME", "DRAFT ONLY NAME")
        api.save_draft(d)
        api.deliver_pdf(token)
        pages = PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages
        self.assertEqual(len(pages), 2)
        text = "\n".join(p.extract_text() for p in pages)
        self.assertIn("SYNTHETIC PARTNER", text)
        self.assertIn("12 / 02 / 2018 E.C.", text)
        self.assertIn("Vision Partner", text)
        for forbidden in (
            "DRAFT ONLY",
            "SAMPLE",
            "DEMO QR",
            "DEMO - NOT VALID",
            "None",
            "null",
            "Member",
        ):
            self.assertNotIn(forbidden, text)
        for page in pages:
            self.assertAlmostEqual(float(page.mediabox.width) * 25.4 / 72, 85.6, places=3)
            self.assertAlmostEqual(float(page.mediabox.height) * 25.4 / 72, 53.98, places=3)

    def test_private_assets_and_no_issuance_mode_flag(self):
        d = api.publish_template(self.doc["name"])
        self.assertTrue(
            all(
                f.is_private
                for f in frappe.get_all(
                    "File", filters={"attached_to_doctype": "ID Card Asset"}, fields=["is_private"]
                )
            )
        )
        element = next(
            e for e in json.loads(d["front_layout"]) if e["type"] == "image" and e.get("src")
        )
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            r.asset(element["src"])
        with self.assertRaises(frappe.PermissionError):
            api.prepare_pdf(d["name"], self.user)
        frappe.set_user("Administrator")
        frappe.db.set_value("ID Card Profile", self.user, "card_number", "")
        with self.assertRaises(frappe.ValidationError):
            api.print_user_id(d["name"], self.user)
