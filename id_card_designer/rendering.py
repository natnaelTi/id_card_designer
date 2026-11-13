"""A small, validated scene/HTML language. No Jinja, scripts, external resources or CSS URLs."""

import base64
import html
import io
import json
import math
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import frappe
import tinycss2
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

from id_card_designer.security import SAFE_FIELDS

FIELDS = (
    "editor_mode",
    "width_mm",
    "height_mm",
    "bleed_mm",
    "front_layout",
    "back_layout",
    "front_html",
    "back_html",
    "shared_css",
)
TYPES = {"text", "image", "shape", "line"}
STYLE_KEYS = {
    "color",
    "background",
    "font-size",
    "font-weight",
    "font-family",
    "line-height",
    "text-align",
    "opacity",
    "border",
    "border-radius",
    "padding",
    "object-fit",
    "letter-spacing",
}
CSS_PROPERTIES = STYLE_KEYS | {
    "width",
    "height",
    "max-width",
    "max-height",
    "min-width",
    "min-height",
    "display",
    "position",
    "left",
    "right",
    "top",
    "bottom",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "overflow",
    "white-space",
    "word-break",
    "overflow-wrap",
    "box-sizing",
    "transform",
    "transform-origin",
    "vertical-align",
    "border-width",
    "border-color",
    "border-style",
    "flex",
    "flex-direction",
    "gap",
    "align-items",
    "justify-content",
    "grid-template-columns",
    "grid-template-rows",
}
PLACEHOLDER = re.compile(r"{{\s*([a-z_]+)\s*}}")


def fail(message):
    frappe.throw(message, frappe.ValidationError)


def number(value, low, high):
    try:
        v = float(value)
    except (ValueError, TypeError):
        fail("Geometry must be numeric.")
    if not math.isfinite(v) or not low <= v <= high:
        fail(f"Geometry must be between {low} and {high}.")
    return v


def declarations(text):
    result = []
    for d in tinycss2.parse_declaration_list(text or "", skip_comments=True, skip_whitespace=True):
        if d.type != "declaration" or d.lower_name not in CSS_PROPERTIES or d.important:
            fail("Unsupported CSS declaration. Use scoped card styling only.")
        value = tinycss2.serialize(d.value)
        if re.search(r"url|expression|@|\\|[<>]|image-set|var\(", value, re.I):
            fail("CSS resource loading and expressions are disabled.")
        result.append(f"{d.lower_name}:{value}")
    return ";".join(result)


def validate_css(css):
    if len(css or "") > 30000:
        fail("CSS is too large.")
    for rule in tinycss2.parse_stylesheet(css or "", skip_comments=True, skip_whitespace=True):
        if rule.type != "qualified-rule":
            fail("CSS at-rules are disabled.")
        selector = tinycss2.serialize(rule.prelude).strip()
        if not re.fullmatch(r"[.\w\s,#>:+*\-]+", selector) or re.search(
            r"\b(html|body|page)\b", selector
        ):
            fail("Use card element and class selectors only.")
        declarations(tinycss2.serialize(rule.content))


def validate_html(source):
    if len(source or "") > 50000:
        fail("HTML is too large.")
    stripped = PLACEHOLDER.sub("", source or "")
    if any(x in stripped for x in ("{{", "}}", "{%", "{#")):
        fail("Only {{ allowed_field }} placeholders are supported.")
    if any(f not in SAFE_FIELDS for f in PLACEHOLDER.findall(source or "")):
        fail("Unknown or sensitive field binding.")
    soup = BeautifulSoup(source or "", "html.parser")
    tags = soup.find_all(True)
    if len(tags) > 300:
        fail("HTML may contain at most 300 elements.")
    for tag in tags:
        if len(list(tag.parents)) > 16:
            fail("HTML nesting is too deep.")
        if tag.name not in {
            "div",
            "span",
            "p",
            "b",
            "strong",
            "em",
            "i",
            "br",
            "h1",
            "h2",
            "h3",
            "small",
            "img",
        }:
            fail("Unsupported HTML element: " + tag.name)
        for k, v in tag.attrs.items():
            if k not in {"class", "style", "src", "alt"}:
                fail("Unsupported HTML attribute: " + k)
            if k == "style":
                declarations(v)
            if k == "src" and not (
                v == "{{ user_image }}" or re.fullmatch(r"/(private/)?files/[^?#]+", v)
            ):
                fail("Images must reference an uploaded Frappe file or {{ user_image }}.")


def scene(raw, w, h, bleed=0):
    if isinstance(raw, str) and len(raw) > 100000:
        fail("Layout JSON is too large.")
    try:
        items = json.loads(raw or "[]") if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        fail("Layout must be valid JSON.")
    if not isinstance(items, list) or len(items) > 100:
        fail("A side must contain at most 100 elements.")
    for e in items:
        if not isinstance(e, dict) or e.get("type") not in TYPES:
            fail("Unsupported element type.")
        for key, maxval in [("x", w), ("y", h), ("width", w), ("height", h)]:
            e[key] = number(
                e.get(key),
                -bleed if key in ("x", "y") else 0.1,
                maxval + bleed * (1 if key in ("x", "y") else 2),
            )
        if e["x"] + e["width"] > w + bleed + 0.01 or e["y"] + e["height"] > h + bleed + 0.01:
            fail("Element extends beyond the trim / bleed bounds.")
        number(e.get("rotation", 0), -360, 360)
        if e.get("field") and e["field"] not in SAFE_FIELDS:
            fail("Unknown field binding.")
        if e["type"] == "image" and e.get("field") and e["field"] != "user_image":
            fail("Image bindings must use the approved User image field.")
        if e.get("visible_if") and e["visible_if"] not in SAFE_FIELDS:
            fail("Unknown visibility field.")
        for k in ("text", "fallback", "src"):
            if not isinstance(e.get(k, ""), str) or len(e.get(k, "")) > 2000:
                fail("Element text is too large.")
        if not isinstance(e.get("style", {}), dict):
            fail("Element style must be an object.")
        for k, v in e.get("style", {}).items():
            if k not in STYLE_KEYS:
                fail("Unsupported element style.")
            declarations(f"{k}:{v}")
        if e.get("date_format") not in (None, "", "%Y-%m-%d", "%d %b %Y", "%d/%m/%Y"):
            fail("Unsupported date format.")
    return items


def validate(s):
    w = number(s.get("width_mm"), 20, 200)
    h = number(s.get("height_mm"), 20, 150)
    s.update(width_mm=w, height_mm=h, bleed_mm=number(s.get("bleed_mm") or 0, 0, 10))
    if s.get("editor_mode") not in ("Visual", "Code"):
        fail("Choose Visual or Code mode.")
    for side in ("front", "back"):
        scene(s.get(side + "_layout"), w, h, s["bleed_mm"])
        validate_html(s.get(side + "_html"))
    validate_css(s.get("shared_css"))
    return s


def snapshot(doc):
    return validate({k: doc.get(k) for k in FIELDS})


def asset(url):
    if not url:
        return ""
    if not re.fullmatch(r"/(private/)?files/[^?#]+", url):
        fail("Only local uploaded image files are allowed.")
    names = frappe.get_all("File", filters={"file_url": url}, pluck="name")
    if not names:
        fail("Image file is missing. Upload it again.")
    file = frappe.get_doc("File", names[0])
    file.check_permission("read")
    content = file.get_content()
    if isinstance(content, str):
        content = content.encode()
    if len(content) > 5 * 1024 * 1024:
        fail("Images may be at most 5 MB.")
    try:
        im = Image.open(io.BytesIO(content))
        im.verify()
        im = Image.open(io.BytesIO(content))
        if im.format not in ("PNG", "JPEG", "WEBP") or im.width * im.height > 24000000:
            fail("Use PNG, JPEG or WebP under 24 megapixels.")
        out = io.BytesIO()
        ImageOps.exif_transpose(im).convert("RGBA").save(out, format="PNG")
    except (OSError, ValueError):
        fail("Invalid image content.")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def text_value(e, data):
    value = str(data.get(e.get("field"), "") or e.get("fallback") or e.get("text") or "")
    if e.get("date_format"):
        try:
            value = datetime.fromisoformat(value).strftime(e["date_format"])
        except ValueError:
            pass
    return value


def side_html(s, side, data):
    if s["editor_mode"] == "Code":
        source = s.get(side + "_html") or ""
        # Replace text nodes and image sources independently; bindings never become markup or attributes.
        soup = BeautifulSoup(source, "html.parser")
        for node in list(soup.find_all(string=True)):
            node.replace_with(PLACEHOLDER.sub(lambda m: str(data.get(m[1]) or ""), str(node)))
        for img in soup.find_all("img"):
            src = img.get("src", "")
            img["src"] = (
                asset(data.get("user_image", "") if src == "{{ user_image }}" else src)
                if src
                else ""
            )
        return str(soup)
    output = []
    for e in scene(s.get(side + "_layout"), s["width_mm"], s["height_mm"], s.get("bleed_mm") or 0):
        if e.get("visible_if") and not data.get(e["visible_if"]):
            continue
        style = f"position:absolute;left:{e['x']}mm;top:{e['y']}mm;width:{e['width']}mm;height:{e['height']}mm;transform:rotate({e.get('rotation', 0)}deg);overflow:hidden;box-sizing:border-box;overflow-wrap:anywhere;"
        style += declarations(";".join(f"{k}:{v}" for k, v in e.get("style", {}).items()))
        content = html.escape(text_value(e, data))
        if e["type"] == "image":
            src = data.get(e.get("field"), "") or e.get("src", "")
            content = (
                f'<img style="width:100%;height:100%;object-fit:{html.escape(str(e.get("style", {}).get("object-fit", "cover")), quote=True)}" src="{asset(src)}">'
                if src
                else html.escape(e.get("fallback") or "No photo")
            )
        output.append(f'<div style="{html.escape(style, quote=True)}">{content}</div>')
    return "".join(output)


@lru_cache(maxsize=1)
def font_css():
    raw = (Path(__file__).parent / "public/fonts/FreeSerif.ttf").read_bytes()
    return (
        "@font-face{font-family:FreeSerif;src:url(data:font/ttf;base64,"
        + base64.b64encode(raw).decode()
        + ")}"
    )


def document_html(s, data):
    validate(s)
    w = s["width_mm"]
    h = s["height_mm"]
    b = s.get("bleed_mm") or 0
    # Render each face separately, then merge: arbitrary content can never introduce a third page.
    faces = []
    for side in ("front", "back"):
        faces.append(
            '<!doctype html><html><head><meta charset="utf-8"><style>'
            + font_css()
            + f"@page{{size:{w + 2 * b}mm {h + 2 * b}mm;margin:0}}html,body{{margin:0;padding:0}}body{{font-family:FreeSerif,serif;font-size:9pt;line-height:1.2}}.sheet{{position:relative;width:{w + 2 * b}mm;height:{h + 2 * b}mm;overflow:hidden;background:#f5f3e7}}.card{{position:absolute;left:{b}mm;top:{b}mm;width:{w}mm;height:{h}mm;overflow:visible;background:#f5f3e7;print-color-adjust:exact;box-sizing:border-box}}"
            + (s.get("shared_css") or "")
            + '</style></head><body><div class="sheet"><div class="card">'
            + side_html(s, side, data)
            + "</div></div></body></html>"
        )
    return faces


def pdf(s, data):
    from pypdf import PdfReader, PdfWriter
    from weasyprint import HTML

    def fetch(url, **kwargs):
        if url.startswith(("data:image/png;base64,", "data:font/ttf;base64,")):
            header, encoded = url.split(",", 1)
            return dict(string=base64.b64decode(encoded), mime_type=header[5:].split(";")[0])
        raise ValueError("External resources are disabled")

    writer = PdfWriter()
    for face in document_html(s, data):
        raw = HTML(string=face, url_fetcher=fetch).write_pdf()
        reader = PdfReader(io.BytesIO(raw))
        if len(reader.pages) != 1:
            fail("Content overflowed the card page. Reduce content or dimensions.")
        writer.add_page(reader.pages[0])
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def thumbnail(s):
    """Fictional/static scene thumbnail, never a real User photo."""
    parts = []
    if s.get("editor_mode") == "Visual":
        for e in scene(
            s.get("front_layout"), s["width_mm"], s["height_mm"], s.get("bleed_mm") or 0
        ):
            style = e.get("style", {})
            color = html.escape(style.get("color", "#244b47"), quote=True)
            background = html.escape(style.get("background", "transparent"), quote=True)
            if e["type"] in ("shape", "line", "image"):
                parts.append(
                    f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["width"]}" height="{e["height"]}" fill="{background if background != "transparent" else "#dbe3dd"}"/>'
                )
            else:
                value = html.escape(
                    (e.get("text") or e.get("fallback") or "[" + e.get("field", "text") + "]")[:100]
                )
                parts.append(
                    f'<text x="{e["x"]}" y="{e["y"] + 3}" fill="{color}" font-size="2.5">{value}</text>'
                )
    else:
        parts.append('<text x="5" y="25" font-size="6" fill="#244b47">HTML / CSS template</text>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s["width_mm"]} {s["height_mm"]}"><rect width="100%" height="100%" fill="#f5f3e7"/>'
        + "".join(parts)
        + "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def preflight(s, data):
    validate(s)
    warnings = []
    for side in ("front", "back"):
        for index, e in enumerate(
            scene(s.get(side + "_layout"), s["width_mm"], s["height_mm"], s.get("bleed_mm") or 0)
        ):
            label = f"{side} element {index + 1}"
            if (
                min(
                    e["x"],
                    e["y"],
                    s["width_mm"] - e["x"] - e["width"],
                    s["height_mm"] - e["y"] - e["height"],
                )
                < 3
            ):
                warnings.append(label + ": touches the 3 mm safety margin.")
            if e.get("field") and not data.get(e["field"]) and not e.get("fallback"):
                warnings.append(label + ": bound value is empty; add fallback text.")
            if e["type"] == "text":
                # Conservative estimate only; the final PDF remains the proof for variable glyph widths.
                size = re.fullmatch(
                    r"([0-9.]+)(pt|px|mm|cm)", str(e.get("style", {}).get("font-size", "9pt"))
                )
                font_mm = (
                    float(size[1]) * {"pt": 25.4 / 72, "px": 25.4 / 96, "mm": 1, "cm": 10}[size[2]]
                    if size
                    else 9 * 25.4 / 72
                )
                lines = max(1, int(e["height"] / max(font_mm * 1.2, 0.1)))
                capacity = max(8, int(e["width"] / max(font_mm * 0.5, 0.1)) * lines)
                if len(text_value(e, data)) > capacity:
                    warnings.append(label + ": long text may be clipped; inspect the PDF.")
            if e["type"] == "image":
                src = data.get(e.get("field"), "") or e.get("src")
                if src:
                    encoded = asset(src).split(",", 1)[1]
                    im = Image.open(io.BytesIO(base64.b64decode(encoded)))
                    dpi = (
                        min(im.width / max(e["width"], 0.1), im.height / max(e["height"], 0.1))
                        * 25.4
                    )
                    if dpi < 300:
                        warnings.append(
                            label + f": image is approximately {dpi:.0f} DPI; prefer 300 DPI."
                        )
    return dict(
        width_mm=s["width_mm"],
        height_mm=s["height_mm"],
        media_width_mm=s["width_mm"] + 2 * (s.get("bleed_mm") or 0),
        media_height_mm=s["height_mm"] + 2 * (s.get("bleed_mm") or 0),
        pages=2,
        warnings=warnings,
        font="Bundled GNU FreeSerif (Latin / Ethiopic); other fonts require local installation.",
    )
