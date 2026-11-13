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
    "safe_margin_mm",
    "block_severe",
    "crop_marks",
)
TYPES = {"text", "richtext", "image", "shape", "line", "group", "qr"}
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

        def bounded(tokens, depth=0):
            if depth > 6:
                fail("CSS functions are nested too deeply.")
            for token in tokens:
                if token.type == "error":
                    fail("Malformed CSS value.")
                if token.type in ("number", "dimension", "percentage") and (
                    not math.isfinite(token.value) or abs(token.value) > 2000
                ):
                    fail("CSS numeric value is too large.")
                if token.type == "function":
                    bounded(token.arguments, depth + 1)

        bounded(d.value)
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


def validate_html(source, allow_scene=True):
    if len(source or "") > 200000:
        fail("HTML is too large.")
    stripped = PLACEHOLDER.sub("", source or "")
    if any(x in stripped for x in ("{{", "}}", "{%", "{#")):
        fail("Only {{ allowed_field }} placeholders are supported.")
    if any(f not in SAFE_FIELDS for f in PLACEHOLDER.findall(source or "")):
        fail("Unknown or sensitive field binding.")
    soup = BeautifulSoup(source or "", "html.parser")
    tags = soup.find_all(True)
    embedded = soup.find_all("ic-scene")
    if (
        len(embedded) > 1
        or len(source or "") - sum(len(t.get("source", "")) for t in embedded) > 50000
    ):
        fail("HTML is too large; use at most one bounded embedded scene.")
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
            "ic-qr",
            "ic-scene",
        }:
            fail("Unsupported HTML element: " + tag.name)
        if not allow_scene and tag.name in ("ic-scene", "ic-qr", "img"):
            fail("Rich text supports text markup; use the Image and QR palette for graphics.")
        if tag.name == "ic-scene":
            if not allow_scene:
                fail("Embedded scenes are not allowed in rich text.")
            if set(tag.attrs) != {"source"}:
                fail("Invalid scene attributes.")
            try:
                raw = base64.b64decode(tag["source"], validate=True).decode()
            except (ValueError, UnicodeError):
                fail("Invalid scene encoding.")
            if len(raw) > 100000:
                fail("Scene is too large.")
            scene(raw, 200, 150, 10)
            continue
        if tag.name == "ic-qr":
            if set(tag.attrs) - {"text", "field", "size", "error", "quiet", "dark", "light"}:
                fail("Invalid QR attributes.")
            if tag.get("field") and tag["field"] != "profile_card_number":
                fail("QR cannot bind personal fields.")
            continue
        for k, v in tag.attrs.items():
            if k not in {"class", "style", "src", "alt"}:
                fail("Unsupported HTML attribute: " + k)
            if k == "style":
                declarations(v)
            if k == "src" and not (
                v == "{{ user_image }}" or re.fullmatch(r"/(private/)?files/[^?#]+", v)
            ):
                fail("Images must reference an uploaded Frappe file or {{ user_image }}.")


def scene(raw, w, h, bleed=0, depth=0, budget=None):
    budget = budget if budget is not None else [0]
    if depth > 6:
        fail("Groups may nest at most six levels.")
    if isinstance(raw, str) and len(raw) > 100000:
        fail("Layout JSON is too large.")
    try:
        items = json.loads(raw or "[]") if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        fail("Layout must be valid JSON.")
    if not isinstance(items, list) or len(items) > 100:
        fail("A side must contain at most 100 elements.")
    for e in items:
        budget[0] += 1
        if budget[0] > 100:
            fail("A face may contain at most 100 objects including group children.")
        if not isinstance(e, dict) or e.get("type") not in TYPES:
            fail("Unsupported element type.")
        for key, maxval in [("x", w), ("y", h), ("width", w), ("height", h)]:
            e[key] = number(
                e.get(key),
                -bleed if key in ("x", "y") else 0.1,
                (220 if key == "width" else 170)
                if e.get("affine") and key in ("width", "height")
                else maxval + bleed * (1 if key in ("x", "y") else 2),
            )
        if not e.get("affine") and (
            e["x"] + e["width"] > w + bleed + 0.01 or e["y"] + e["height"] > h + bleed + 0.01
        ):
            fail("Element extends beyond the trim / bleed bounds.")
        e["rotation"] = number(e.get("rotation", 0), -360, 360)
        if e.get("affine") is not None:
            if not isinstance(e["affine"], list) or len(e["affine"]) != 6:
                fail("Invalid affine transform.")
            e["affine"] = [number(v, -1000, 1000) for v in e["affine"]]
            if abs(e["affine"][0] * e["affine"][3] - e["affine"][1] * e["affine"][2]) < 1e-8:
                fail("Singular transform.")
        if e["type"] == "group":
            e["base_width"] = number(e.get("base_width", e["width"]), 0.1, 220)
            e["base_height"] = number(e.get("base_height", e["height"]), 0.1, 170)
            e["children"] = scene(
                e.get("children"), e["base_width"], e["base_height"], 0, depth + 1, budget
            )
        if e["type"] == "qr":
            from id_card_designer.qr import ALLOWED_FIELDS, options

            try:
                options(e)
            except ValueError as exc:
                fail(str(exc))
            if e.get("field") and e["field"] not in ALLOWED_FIELDS:
                fail("QR cannot bind personal fields.")
        if e["type"] == "richtext":
            validate_html(e.get("text", ""), allow_scene=False)
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
        for flag in ("clip", "allow_clip", "allow_bleed", "locked"):
            if flag in e and not isinstance(e[flag], bool):
                fail("Element flags must be booleans.")
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
    s["safe_margin_mm"] = number(
        s.get("safe_margin_mm") if s.get("safe_margin_mm") is not None else 3, 0, 10
    )
    s["block_severe"] = int(bool(s.get("block_severe")))
    s["crop_marks"] = int(bool(s.get("crop_marks")))
    if s["crop_marks"] and s["bleed_mm"] < 3:
        fail("Crop marks require at least 3 mm bleed.")
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
    from id_card_designer.images import normalize, read_file

    content = normalize(read_file(file))
    return "data:image/png;base64," + base64.b64encode(content).decode()


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
        for tag in soup.find_all("ic-scene"):
            raw = base64.b64decode(tag["source"], validate=True).decode()
            content = render_elements(
                scene(raw, s.get("width_mm", 200), s.get("height_mm", 150), s.get("bleed_mm", 0)),
                data,
            )
            tag.replace_with(BeautifulSoup(content, "html.parser"))
        for tag in soup.find_all("ic-qr"):
            from id_card_designer.qr import make

            size = number(tag.get("size", 25), 10, 100)
            element = dict(
                type="qr",
                width=size,
                height=size,
                text=tag.get("text", ""),
                field=tag.get("field", ""),
                qr_error=tag.get("error", "M"),
                qr_quiet=int(tag.get("quiet", 4)),
                qr_dark=tag.get("dark", "#173b35"),
                qr_light=tag.get("light", "#ffffff"),
            )
            try:
                src, modules = make(element, data, metadata=True)
            except ValueError as exc:
                fail(str(exc))
            img = soup.new_tag("img", src=src, style=f"width:{size}mm;height:{size}mm")
            img["data-ic-qr"] = str(modules)
            tag.replace_with(img)
        return str(soup)
    return render_elements(
        scene(s.get(side + "_layout"), s["width_mm"], s["height_mm"], s.get("bleed_mm") or 0), data
    )


def render_elements(items, data, prefix=""):
    from id_card_designer.geometry import css_matrix, transform

    output = []
    for index, e in enumerate(items):
        path = f"{prefix}.{index}" if prefix else str(index)
        if e.get("visible_if") and not data.get(e["visible_if"]):
            continue
        style = f"position:absolute;left:0;top:0;width:{e['width']}mm;height:{e['height']}mm;transform-origin:0 0;transform:{css_matrix(transform(e))};overflow:{'hidden' if e.get('clip') or e['type'] != 'group' else 'visible'};box-sizing:border-box;overflow-wrap:anywhere;"
        style += declarations(";".join(f"{k}:{v}" for k, v in e.get("style", {}).items()))
        content = html.escape(text_value(e, data))
        if e["type"] == "richtext":
            temp = dict(editor_mode="Code", front_html=e.get("text", ""))
            content = side_html(temp, "front", data)
        if e["type"] == "image":
            src = data.get(e.get("field"), "") or e.get("src", "")
            fit = html.escape(str(e.get("style", {}).get("object-fit", "cover")), quote=True)
            content = (
                f'<img style="width:100%;height:100%;object-fit:{fit}" src="{asset(src)}">'
                if src
                else html.escape(e.get("fallback") or "No photo")
            )
        if e["type"] == "qr":
            from id_card_designer.qr import make

            try:
                src = make(e, data)
            except ValueError as exc:
                fail(str(exc))
            content = f'<img style="width:100%;height:100%;object-fit:contain" src="{src}">'
        if e["type"] == "group":
            sx = e["width"] / e["base_width"]
            sy = e["height"] / e["base_height"]
            content = (
                f'<div style="position:absolute;transform-origin:0 0;transform:scale({sx},{sy});width:{e["base_width"]}mm;height:{e["base_height"]}mm">'
                + render_elements(e["children"], data, path)
                + "</div>"
            )
        output.append(
            f'<div data-ic-path="{path}" style="{html.escape(style, quote=True)}">{content}</div>'
        )
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
    if s.get("crop_marks"):
        points = []
        for x in (b, w + b):
            for y in (b, h + b):
                dx = -1 if x == b else 1
                dy = -1 if y == b else 1
                points.append(
                    f'<path d="M {x + dx * 0.5} {y} L {x + dx * 2.5} {y} M {x} {y + dy * 0.5} L {x} {y + dy * 2.5}"/>'
                )
        marks = (
            f'<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;left:0;top:0;width:{w + 2 * b}mm;height:{h + 2 * b}mm" viewBox="0 0 {w + 2 * b} {h + 2 * b}" fill="none" stroke="black" stroke-width="0.1">'
            + "".join(points)
            + "</svg>"
        )
        faces = [face.replace("</body>", marks + "</body>") for face in faces]
    return faces


def render_pages(s, data):
    from weasyprint import HTML

    def fetch(url, **kwargs):
        if url.startswith(
            ("data:image/png;base64,", "data:font/ttf;base64,", "data:image/svg+xml;base64,")
        ):
            header, encoded = url.split(",", 1)
            return dict(string=base64.b64decode(encoded), mime_type=header[5:].split(";")[0])
        raise ValueError("External resources are disabled")

    return [HTML(string=face, url_fetcher=fetch).render() for face in document_html(s, data)]


def pdf(s, data, documents=None):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for document in documents or render_pages(s, data):
        reader = PdfReader(
            io.BytesIO(getattr(document, "_id_card_pdf", None) or document.write_pdf())
        )
        if len(reader.pages) != 1:
            fail("Content overflowed the card page. Reduce content or dimensions.")
        page = reader.pages[0]
        from pypdf.generic import RectangleObject

        b = s.get("bleed_mm") or 0
        page.trimbox = RectangleObject(
            [
                b * 72 / 25.4,
                b * 72 / 25.4,
                (b + s["width_mm"]) * 72 / 25.4,
                (b + s["height_mm"]) * 72 / 25.4,
            ]
        )
        writer.add_page(page)
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
    from id_card_designer.preflight import inspect

    return inspect(s, data)
