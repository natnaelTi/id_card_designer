import io
import json
import unittest

import frappe
from PIL import Image
from pypdf import PdfReader

from id_card_designer import rendering as r
from id_card_designer.api import DEMO
from id_card_designer.geometry import child_transform, multiply, transform
from id_card_designer.install import sample

try:
    from frappe.tests import UnitTestCase
except ImportError:
    UnitTestCase = unittest.TestCase
if not getattr(frappe.local, "site", None):
    UnitTestCase = unittest.TestCase


class Phase2RenderingTests(UnitTestCase):
    def setUp(self):
        super().setUp()
        self.s = {k: sample().get(k) for k in r.FIELDS}
        from unittest.mock import patch

        patcher = patch.object(r, "fail", side_effect=ValueError)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_actual_qr_decoder_at_print_dpi_and_rotation(self):
        import pymupdf
        import zxingcpp

        for rotation in (0, 90):
            element = dict(
                type="qr",
                x=5,
                y=5,
                width=25,
                height=25,
                rotation=rotation,
                text="INSTITUTION-DEMO-0001",
                style={},
            )
            self.s["front_layout"] = json.dumps([element])
            raw = r.pdf(self.s, DEMO)
            doc = pymupdf.open(stream=raw, filetype="pdf")
            for dpi in (300, 600):
                pix = doc[0].get_pixmap(dpi=dpi, alpha=False)
                decoded = zxingcpp.read_barcode(
                    Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                )
                self.assertIsNotNone(decoded)
                self.assertEqual(decoded.text, "INSTITUTION-DEMO-0001")

    def test_code_qr_is_explicit_and_decodable(self):
        import pymupdf
        import zxingcpp

        self.s.update(
            editor_mode="Code",
            front_html='<ic-qr text="ORG-DEMO-2" size="25"></ic-qr>',
            back_html="<p>SAMPLE / NOT VALID ID</p>",
        )
        raw = r.pdf(self.s, DEMO)
        pix = pymupdf.open(stream=raw, filetype="pdf")[0].get_pixmap(dpi=300, alpha=False)
        self.assertEqual(
            zxingcpp.read_barcode(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ).text,
            "ORG-DEMO-2",
        )

    def test_qr_injection_pii_contrast_and_quiet_zone(self):
        from id_card_designer.qr import make

        e = dict(type="qr", width=25, height=25, text="ORG-DEMO")
        for change in [
            dict(text="javascript:alert(1)"),
            dict(text="https://evil.invalid"),
            dict(text="Fayda FIN 1234"),
            dict(field="email"),
            dict(qr_quiet=0),
            dict(qr_dark="#ffffff"),
            dict(qr_dark="url(http://evil)"),
            dict(width=4, height=4),
        ]:
            with (
                self.subTest(change=change),
                self.assertRaises((ValueError, frappe.ValidationError)),
            ):
                make({**e, **change}, DEMO)

    def test_exact_measured_clipped_text_and_rotated_bounds(self):
        self.s["front_layout"] = json.dumps(
            [
                dict(
                    type="text",
                    x=1,
                    y=1,
                    width=30,
                    height=2,
                    rotation=45,
                    text="Long " * 100,
                    style={"font-size": "12pt"},
                )
            ]
        )
        report = r.preflight(self.s, DEMO)
        codes = {i["code"] for i in report["errors"]}
        self.assertIn("text_clipped", codes)
        self.assertIn("outside_media", codes)
        element = json.loads(self.s["front_layout"])[0]
        element["allow_clip"] = True
        self.s["front_layout"] = json.dumps([element])
        self.assertFalse(
            any(
                i["code"] == "text_clipped" and i["severity"] == "error"
                for i in r.preflight(self.s, DEMO)["issues"]
            )
        )

    def test_group_serialization_and_pdf_raster_equivalence(self):
        import pymupdf
        from PIL import ImageChops, ImageStat

        leaf = dict(
            type="text",
            x=5,
            y=5,
            width=30,
            height=8,
            rotation=12,
            text="Group · ሰላም",
            style={"font-size": "9pt"},
        )
        group = dict(
            type="group",
            x=3,
            y=4,
            width=50,
            height=25,
            base_width=40,
            base_height=30,
            rotation=17,
            children=[leaf],
            style={},
        )
        self.s["front_layout"] = json.dumps([group])
        raw_group = r.pdf(self.s, DEMO)
        flat = {
            **leaf,
            "x": 0,
            "y": 0,
            "rotation": 0,
            "affine": multiply(child_transform(group), transform(leaf)),
        }
        self.s["front_layout"] = json.dumps([flat])
        raw_flat = r.pdf(self.s, DEMO)
        images = []
        for raw in (raw_group, raw_flat):
            pix = pymupdf.open(stream=raw, filetype="pdf")[0].get_pixmap(dpi=300, alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        self.assertLess(max(ImageStat.Stat(ImageChops.difference(*images)).mean), 0.15)
        self.assertEqual(len(PdfReader(io.BytesIO(raw_flat)).pages), 2)

    def test_legacy_scene_crop_marks_and_trimbox(self):
        self.s.update(bleed_mm=3, crop_marks=1)
        raw = r.pdf(self.s, DEMO)
        pages = PdfReader(io.BytesIO(raw)).pages
        self.assertEqual(len(pages), 2)
        self.assertAlmostEqual(float(pages[0].trimbox.width) * 25.4 / 72, 85.6, places=3)
        self.assertAlmostEqual(float(pages[0].mediabox.width) * 25.4 / 72, 91.6, places=3)
        self.assertIn("NOT VALID ID", pages[0].extract_text())

    def test_group_caps_and_css_resource_limits(self):
        leaf = dict(type="text", x=0, y=0, width=2, height=2, text="x")
        group = dict(type="group", x=0, y=0, width=20, height=20, children=[leaf] * 101)
        with self.assertRaises(ValueError):
            r.scene([group], 85.6, 53.98)
        for css in [".x{font-size:1e100px}", ".x{width:calc(999999mm)}"]:
            with self.assertRaises(ValueError):
                r.validate_css(css)
