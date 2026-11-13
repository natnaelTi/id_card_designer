"""Exact transformed physical bounds and actual WeasyPrint line/glyph layout, no character estimates."""

import math

from weasyprint.formatting_structure.boxes import LineBox, TextBox

from id_card_designer.geometry import bounds, walk

MM = 25.4 / 96


def descendants(box):
    # AbsolutePlaceholder is a proxy, not a ParentBox; WeasyPrint's descendants()
    # intentionally stops at it. Unwrap it to inspect the actual laid-out content.
    box = getattr(box, "_box", box)
    yield box
    for child in box.all_children():
        yield from descendants(child)


def inspect(s, data, documents=None):
    from id_card_designer.rendering import render_pages, validate

    validate(s)
    issues = []

    def add(code, severity, side, path, message, box=None):
        issues.append(
            dict(code=code, severity=severity, side=side, path=path, message=message, bounds_mm=box)
        )

    w, h, b = s["width_mm"], s["height_mm"], s["bleed_mm"]
    margin = s["safe_margin_mm"]
    for side in ("front", "back"):
        elements = active_scene(s, side, w, h, b)
        masks = set()
        for path, e, m in walk(elements):
            box = bounds(e, m)
            left, t, r, d = box
            clipped = e.get("allow_clip") or any(path.startswith(p + ".") for p in masks)
            if e.get("clip"):
                masks.add(path)
            if min(left + b, t + b, w + b - r, h + b - d) < -0.02:
                add(
                    "outside_media",
                    "info" if clipped else "error",
                    side,
                    path,
                    "Transformed artwork extends outside the MediaBox"
                    + (" (intentional mask)." if clipped else "."),
                    box,
                )
            elif min(left, t, w - r, h - d) < -0.02:
                add(
                    "bleed",
                    "info" if e.get("allow_bleed") or clipped else "warning",
                    side,
                    path,
                    "Artwork extends into bleed; extend background deliberately.",
                    box,
                )
            elif min(left - margin, t - margin, w - margin - r, h - margin - d) < -0.02 and e[
                "type"
            ] not in ("shape", "line", "group"):
                add(
                    "safe_zone",
                    "warning",
                    side,
                    path,
                    "Element touches the configured safe zone.",
                    box,
                )
            if e.get("field") and not data.get(e["field"]) and not e.get("fallback"):
                add("empty", "warning", side, path, "Bound value is empty; add fallback text.")
            if e["type"] == "qr":
                import segno

                from id_card_designer.qr import options, payload

                correction, quiet, _ = options(e)
                modules = segno.make_qr(
                    payload(e, data), error=correction, boost_error=False
                ).symbol_size(border=quiet)[0]
                sx, sy = math.hypot(m[0], m[1]), math.hypot(m[2], m[3])
                if (
                    min(e["width"] * sx, e["height"] * sy) / modules < 0.25
                    or abs(e["width"] * sx - e["height"] * sy) > 0.02
                    or abs(m[0] * m[2] + m[1] * m[3]) > 0.001
                ):
                    add(
                        "qr_geometry",
                        "error",
                        side,
                        path,
                        "QR must be square, unskewed, with modules at least 0.25 mm.",
                    )
                if e.get("style", {}).get("opacity", "1") not in ("1", 1):
                    add("qr_opacity", "error", side, path, "QR opacity must be 1.")
    documents = documents or render_pages(s, data)
    used_fonts = set()
    for side, document in zip(("front", "back"), documents):
        if len(document.pages) != 1:
            add("pagination", "error", side, "", "Each face must fit exactly one physical page.")
            continue
        document._id_card_pdf = document.write_pdf()
        fonts = list(document.fonts.values())
        used_fonts.update(
            font.family.decode("utf-8", errors="replace")
            if isinstance(font.family, bytes)
            else str(font.family)
            for font in fonts
        )
        # The renderer records actual missing glyphs during PDF generation. This
        # includes shaping/fallback and avoids false positives from subset cmaps
        # where a rendered ligature replaces its individual Unicode characters.
        missing_glyphs = set().union(*(set(getattr(font, "missing", {})) for font in fonts))
        boxes = list(descendants(document.pages[0]._page_box))
        if fonts and not all(hasattr(font, "missing") for font in fonts):
            # WeasyPrint 66 skips unknown Pango glyphs rather than recording them.
            # Its rendered Unicode maps include expanded ligature strings.
            rendered = {
                ord(c)
                for font in fonts
                for text in getattr(font, "cmap", {}).values()
                for c in text
            }
            missing_glyphs = {
                ord(c)
                for box in boxes
                if isinstance(box, TextBox)
                for c in box.text
                if not c.isspace() and ord(c) not in rendered
            }

        owners = {}
        for box in boxes:
            element = getattr(box, "element", None)
            path = element.get("data-ic-path") if element is not None else None
            if path is not None and not isinstance(box, (TextBox, LineBox)):
                old = owners.get(path)
                if old is None or box.width * box.height > old.width * old.height:
                    owners[path] = box
        clipped_paths = set()
        any_text = False

        def visit(box, path=None, matrix=None, opacity=1):
            nonlocal any_text
            box = getattr(box, "_box", box)
            el = getattr(box, "element", None)
            if el is not None:
                path = el.get("data-ic-path", path)
            from weasyprint.anchors import rectangle_aabb

            local = getattr(box, "transformation_matrix", None)
            matrix = (
                (local @ matrix if matrix is not None else local) if local is not None else matrix
            )
            opacity *= float(box.style.get("opacity", 1))
            if (
                s["editor_mode"] == "Code"
                and getattr(box, "element_tag", None) not in (None, "html", "body")
                and not isinstance(box, (TextBox, LineBox))
            ):
                classes = (el.get("class", "") if el is not None else "").split()
                if not set(classes) & {"sheet", "card"}:
                    rect = tuple(
                        v * MM
                        for v in rectangle_aabb(
                            matrix,
                            box.border_box_x(),
                            box.border_box_y(),
                            box.border_width(),
                            box.border_height(),
                        )
                    )
                    if min(rect[0], rect[1], w + 2 * b - rect[2], h + 2 * b - rect[3]) < -0.02:
                        add(
                            "outside_media",
                            "info" if "allow-clip" in classes else "error",
                            side,
                            path or "code",
                            "Code element extends outside the measured PDF MediaBox.",
                            rect,
                        )
                    if el is not None and el.get("data-ic-qr"):
                        sx = math.hypot(*(matrix.values[:2])) if matrix is not None else 1
                        sy = math.hypot(*(matrix.values[2:4])) if matrix is not None else 1
                        width, height = box.width * sx * MM, box.height * sy * MM
                        if (
                            abs(width - height) > 0.02
                            or min(width, height) / int(el.get("data-ic-qr")) < 0.25
                        ):
                            add(
                                "qr_geometry",
                                "error",
                                side,
                                path or "code",
                                "Code QR is distorted or has modules below 0.25 mm.",
                            )
                        if opacity < 0.999:
                            add(
                                "qr_opacity", "error", side, path or "code", "QR opacity must be 1."
                            )
            if isinstance(box, TextBox) and box.text.strip() and opacity > 0:
                any_text = True
                missing = {ord(c) for c in box.text if not c.isspace() and ord(c) in missing_glyphs}
                if missing:
                    add(
                        "missing_glyph",
                        "error",
                        side,
                        path or "code",
                        f"Embedded fonts lack {len(missing)} rendered glyphs.",
                    )
                owner = owners.get(path)
                if owner:
                    left, top = owner.content_box_x(), owner.content_box_y()
                    if (
                        box.position_x < left - 0.2
                        or box.position_y < top - 0.2
                        or box.position_x + box.width > left + owner.width + 0.2
                        or box.position_y + box.height > top + owner.height + 0.2
                    ):
                        clipped_paths.add(path)
                elif (
                    box.position_x < 0
                    or box.position_y < 0
                    or box.position_x + box.width > (w + 2 * b) / MM + 0.2
                    or box.position_y + box.height > (h + 2 * b) / MM + 0.2
                ):
                    clipped_paths.add("code")
            for child in box.all_children():
                visit(child, path, matrix, opacity)

        visit(document.pages[0]._page_box)
        layout = {path: e for path, e, _ in walk(active_scene(s, side, w, h, b))}
        for path in sorted(clipped_paths):
            intentional = layout.get(path, {}).get("allow_clip", False)
            add(
                "text_clipped",
                "info" if intentional else "error",
                side,
                path,
                "Measured long text exceeds its content box"
                + (
                    " (intentional clipping)."
                    if intentional
                    else "; enlarge the element or reduce typography."
                ),
            )
        # Code mode uses measured boxes too, including fixed-size overflow:hidden containers.
        if s["editor_mode"] == "Code":
            for box in boxes:
                if isinstance(box, (TextBox, LineBox)) or not getattr(box, "children", None):
                    continue
                if box.style.get("overflow") == "hidden":
                    for child in descendants(box):
                        if isinstance(child, TextBox) and (
                            child.position_y + child.height > box.content_box_y() + box.height + 0.2
                            or child.position_x + child.width
                            > box.content_box_x() + box.width + 0.2
                        ):
                            add(
                                "text_clipped",
                                "error",
                                side,
                                "code",
                                "Code text exceeds its measured clipping container.",
                            )
                            break
        if not any_text and not any(getattr(box, "element_tag", None) == "img" for box in boxes):
            add("blank_face", "error", side, "", "No readable text or image on this face.")
    warnings = [
        f"{x['side']} element {x['path']}: {x['message']}"
        for x in issues
        if x["severity"] != "info"
    ]
    return dict(
        width_mm=w,
        height_mm=h,
        media_width_mm=w + 2 * b,
        media_height_mm=h + 2 * b,
        pages=2,
        issues=issues,
        warnings=warnings,
        errors=[x for x in issues if x["severity"] == "error"],
        fonts_used=sorted(used_fonts),
        font="Embedded fonts: "
        + ", ".join(sorted(used_fonts))
        + "; actual layout measured by WeasyPrint.",
    )


def active_scene(s, side, w, h, b):
    from id_card_designer.rendering import scene

    if s["editor_mode"] == "Visual":
        return scene(s.get(side + "_layout"), w, h, b)
    import base64

    from bs4 import BeautifulSoup

    tag = BeautifulSoup(s.get(side + "_html") or "", "html.parser").find("ic-scene")
    return scene(base64.b64decode(tag["source"]).decode(), w, h, b) if tag else []
