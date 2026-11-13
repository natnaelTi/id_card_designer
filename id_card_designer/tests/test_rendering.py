import io
import json
import unittest
from unittest.mock import patch

from pypdf import PdfReader

from id_card_designer import rendering as r
from id_card_designer.api import DEMO
from id_card_designer.install import sample


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.s = {k: sample().get(k) for k in r.FIELDS}
        self.throw = patch.object(r, "fail", side_effect=ValueError)
        self.throw.start()
        self.addCleanup(self.throw.stop)

    def test_actual_pdf_geometry_order_fonts(self):
        raw = r.pdf(self.s, DEMO)
        self.assertTrue(raw.startswith(b"%PDF-"))
        pages = PdfReader(io.BytesIO(raw)).pages
        self.assertEqual(len(pages), 2)
        for p in pages:
            self.assertAlmostEqual(float(p.mediabox.width) * 25.4 / 72, 85.6, places=2)
            self.assertAlmostEqual(float(p.mediabox.height) * 25.4 / 72, 53.98, places=2)
            self.assertIn("NOT VALID ID", p.extract_text())
            fonts = p["/Resources"]["/Font"]
            self.assertTrue(
                any(
                    "/FontFile2"
                    in x.get_object()["/DescendantFonts"][0]
                    .get_object()["/FontDescriptor"]
                    .get_object()
                    for x in fonts.values()
                )
            )
        self.assertIn("FULL NAME", pages[0].extract_text())
        self.assertIn("If found", pages[1].extract_text())
        self.assertIn("የተቋም", pages[0].extract_text())

    def test_bleed(self):
        self.s["bleed_mm"] = 3
        pages = PdfReader(io.BytesIO(r.pdf(self.s, DEMO))).pages
        self.assertEqual(len(pages), 2)
        self.assertAlmostEqual(float(pages[0].mediabox.width) * 25.4 / 72, 91.6, places=2)

    def test_json_preserves_independent_sides(self):
        front = json.loads(self.s["front_layout"])
        front[0]["x"] = 1
        front[0]["width"] = 80
        self.s["front_layout"] = json.dumps(front)
        saved = json.loads(json.dumps(r.validate(self.s)))
        self.assertEqual(json.loads(saved["front_layout"])[0]["x"], 1)
        self.assertEqual(json.loads(saved["back_layout"])[0]["x"], 54)

    def test_code_security(self):
        for source in [
            "<script>alert(1)</script>",
            '<img src="https://example.com/a.png">',
            '<p onclick="alert(1)">x</p>',
            '{{ frappe.db.get_all("User") }}',
            "{{ api_key }}",
            "{% for x in users %}",
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                r.validate_html(source)
        for css in [
            '@import "https://evil";',
            ".x{background:url(file:///etc/passwd)}",
            ".x{background:u\\72l(a)}",
            ".x{position:fixed!important}",
            "body{height:1000mm}",
        ]:
            with self.subTest(css=css), self.assertRaises(ValueError):
                r.validate_css(css)

    def test_code_escapes_data(self):
        self.s.update(
            editor_mode="Code", front_html="<p>{{ full_name }}</p>", back_html="<p>Back</p>"
        )
        result = r.side_html(self.s, "front", {"full_name": "<img src=x onerror=alert(1)>"})
        self.assertIn("&lt;img", result)
        self.assertNotIn("<img", result)
        pages = PdfReader(io.BytesIO(r.pdf(self.s, DEMO))).pages
        self.assertEqual(len(pages), 2)
        self.assertIn("Selam Example", pages[0].extract_text())

    def test_invalid_geometry(self):
        for value in [float("nan"), -1, 1000]:
            self.s["width_mm"] = value
            with self.assertRaises(ValueError):
                r.validate(self.s)

    def test_long_name_and_optional_fallback(self):
        data = {**DEMO, "full_name": "Long Name " * 150, "user_image": ""}
        pages = PdfReader(io.BytesIO(r.pdf(self.s, data))).pages
        self.assertEqual(len(pages), 2)
        self.assertIn("No photo", pages[0].extract_text())

    def test_resource_fetch_never_networks(self):
        with self.assertRaises(ValueError):
            r.asset("https://evil.example/photo.png")

    def test_unknown_binding(self):
        front = json.loads(self.s["front_layout"])
        front[0]["field"] = "api_secret"
        self.s["front_layout"] = json.dumps(front)
        with self.assertRaises(ValueError):
            r.validate(self.s)

    def test_bleed_artwork_can_extend_outside_trim(self):
        self.s["bleed_mm"] = 3
        front = json.loads(self.s["front_layout"])
        front[0].update(x=-3, y=-3, width=91.6, height=12)
        self.s["front_layout"] = json.dumps(front)
        raw = r.pdf(self.s, DEMO)
        self.assertEqual(len(PdfReader(io.BytesIO(raw)).pages), 2)
        self.s["bleed_mm"] = 0
        with self.assertRaises(ValueError):
            r.validate(self.s)

    def test_preflight_missing_and_long_values(self):
        warnings = r.preflight(self.s, {"full_name": "Long " * 200})["warnings"]
        self.assertTrue(any("long text" in w for w in warnings))
        self.assertTrue(any("empty" in w for w in warnings))

    def test_style_values_cannot_escape_html_attributes(self):
        from bs4 import BeautifulSoup

        elements = [
            dict(
                type="text",
                x=4,
                y=4,
                width=70,
                height=10,
                text="Safe",
                style={"font-family": '"x" onmouseover="alert(1)"'},
            )
        ]
        self.s["front_layout"] = json.dumps(elements)
        source = r.side_html(self.s, "front", DEMO)
        soup = BeautifulSoup(source, "html.parser")
        self.assertEqual(set(soup.div.attrs), {"style"})
        self.assertIn("&quot;", source)
