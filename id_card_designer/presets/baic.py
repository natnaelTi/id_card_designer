"""Optional BAIC visual preset; supplied artwork is imported privately, never bundled."""

import json
from pathlib import Path

import frappe

from id_card_designer.calendar import format_ethiopian

KEY = "baic-vision-v1"
NAME = "baic-vision-partnership-card"
TITLE = "BAIC Vision Partnership Card"
TEAL, INK, MUTED, GOLD = "#154C48", "#183A36", "#526D62", "#B09455"
DISCLAIMER = "For BAIC Kingdom Chapel vision partnership identification only. Non-transferable.\nNot a government-issued ID. If found, return to the chapel office."
CARD_FIELDS = (
    "card_full_name",
    "card_chapel",
    "card_anointment",
    "card_role",
    "card_role_translation",
    "card_department",
    "card_number",
    "card_address_1",
    "card_address_2",
    "card_phone",
    "card_email",
    "card_office",
    "card_is_preview",
    "card_is_demo",
    "card_is_design",
    "card_is_live",
    "card_preview_badge",
)
DEMO = dict(
    full_name="Dawit Samuel Tesfaye",
    profile_chapel="Bole Chapel",
    profile_anointment_date="2025-10-22",
    profile_role_title="Vision Partner",
    profile_department="Media & Communications",
    profile_card_number="BAIC-001248",
    profile_address_line_1="Bole Subcity, Woreda 03",
    profile_address_line_2="Addis Ababa, Ethiopia",
    phone="+251 912 480 736",
    email="dawit.samuel@example.com",
)


def context(s, source=None, *, preview=False, variant="demo"):
    """Called only after the API has checked User/Profile access. Never accept a live-mode client flag."""
    design = preview and source is None and variant == "design"
    fictional = preview and source is None
    data = {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in dict(DEMO if fictional else source or {}).items()
    }
    role = str(data.get("profile_role_title") or "").strip()
    role = "Vision Partner" if not role or role.casefold() == "member" else role
    translation = (
        "የራዕይ ተካፋይ"
        if role.casefold() == "vision partner"
        else data.get("profile_role_translation", "")
    )
    office = (
        "Bole, Addis Ababa / office@example.com"
        if fictional
        else frappe.get_single("ID Card Settings").baic_office_contact or ""
    )
    import re

    data["profile_chapel"] = re.sub(
        r"\bParish(?:\s+Chapel)?\b", "Chapel", data.get("profile_chapel", ""), flags=re.I
    )
    number = data.get("profile_card_number", "")
    if fictional:
        data["user_image"] = s.get("demo_portrait") or ""
    data.update(
        card_full_name=str(data.get("full_name") or "").upper(),
        card_chapel=data.get("profile_chapel", ""),
        card_anointment=format_ethiopian(data.get("profile_anointment_date")),
        card_role=role,
        card_role_translation=translation,
        card_department=data.get("profile_department", ""),
        card_number=number,
        card_address_1=data.get("profile_address_line_1", ""),
        card_address_2=data.get("profile_address_line_2", ""),
        card_phone=data.get("mobile_no") or data.get("phone") or "",
        card_email=data.get("email") or "",
        card_office=office,
        card_is_preview=preview,
        card_is_demo=preview and not design,
        card_is_design=design,
        card_is_live=not preview,
        card_preview_badge="DESIGN SAMPLE" if design else "DEMO - NOT VALID" if preview else "",
    )
    if design:
        data.update(
            card_full_name="SAMPLE FULL NAME",
            card_chapel="[Chapel name]",
            card_anointment="DD / MM / YYYY E.C.",
            card_department="[Optional department]",
            card_number="BAIC-000000",
            card_address_1="[City / Subcity / Woreda]",
            card_address_2="",
            card_phone="+251 9XX XXX XXX",
            card_email="partner@example.com",
            card_office="[Address] / [Phone or email]",
            user_image="",
        )
    # The existing QR binding remains restricted to the organizational reference.
    data["profile_card_number"] = ("BAIC|DEMO|" + data["card_number"]) if preview else number
    return data


def required_issues(s, data):
    if s.get("preset_key") != KEY:
        return []
    issues = []
    for field, label in [
        ("card_full_name", "Full name"),
        ("user_image", "Portrait"),
        ("card_chapel", "Chapel"),
        ("card_anointment", "Date of anointment (Gregorian source required)"),
        ("card_number", "Vision partner number"),
        ("card_address_1", "Partner address"),
        ("card_office", "Chapel-office contact configuration"),
    ]:
        if not data.get(field) and not (field == "user_image" and data.get("card_is_design")):
            issues.append(
                dict(
                    code="baic_required",
                    severity="error",
                    side="front" if field not in ("card_address_1", "card_office") else "back",
                    path="",
                    message=label + " is required for this card.",
                    bounds_mm=None,
                )
            )
    return issues


def text(
    label,
    x,
    baseline,
    width,
    size,
    *,
    field="",
    weight=600,
    color=INK,
    height=None,
    visible="",
    family="Open Sans",
    fit=None,
):
    # Open Sans baseline with line-height 1.45, verified against the renderer's actual line boxes.
    e = dict(
        type="text",
        name=label or field,
        x=x,
        y=baseline - size * 25.4 / 72 * 1.1127,
        width=width,
        height=max(height or 0, size * 25.4 / 72 * 1.45),
        text=label,
        field=field,
        style={
            "font-family": family,
            "font-size": f"{size}pt",
            "font-weight": str(400 if family == "Noto Sans Ethiopic" else weight),
            "line-height": "1.45",
            "color": color,
            "white-space": "pre-wrap",
            "letter-spacing": "0.3pt",
        },
    )
    if visible:
        e["visible_if"] = visible
    if fit:
        e["fit_min_pt"] = fit
    return e


def shape(x, y, w, h, color, **kwargs):
    return dict(type="shape", x=x, y=y, width=w, height=h, style={"background": color, **kwargs})


def image(src, x, y, w, h, **kwargs):
    return dict(
        type="image",
        x=x,
        y=y,
        width=w,
        height=h,
        src=src,
        style={"object-fit": "contain", **kwargs},
    )


def scenes(assets):
    front, back = [], []
    for side in (front, back):
        bg = image(assets["background"], 0, 0, 85.6, 53.98, **{"object-fit": "fill"})
        bg.update(bleed_background=True, allow_bleed=True)
        side.append(bg)
        side.extend(
            [
                shape(0, 0, 85.6, 1, GOLD),
                shape(0, 47.9, 85.6, 0.5, GOLD),
                shape(0, 48.4, 85.6, 5.58, TEAL),
                image(assets["logo"], 3.8, 2.7, 8.7, 8.7),
                shape(14.4, 4, 0.15, 6.6, "#BECDB9"),
                shape(3.8, 12.3, 78, 0.15, "#C7D2C0"),
                text("BAIC KINGDOM CHAPEL", 17.2, 6.8, 54, 8.15, weight=700, color=TEAL),
                text("VISION PARTNERSHIP CARD", 17.3, 10.2, 39, 4.55, color=MUTED),
                text("የራዕይ ተካፋይ", 58.8, 10.2, 20, 4.75, color=MUTED, family="Noto Sans Ethiopic"),
            ]
        )
        badge = shape(71.8, 3.7, 9.7, 3.5, "#EAEAD9", **{"border-radius": ".6mm"})
        badge["visible_if"] = "card_is_preview"
        side.append(badge)
        side.append(
            text("SAMPLE", 73.5, 6.0, 7.5, 4.4, weight=700, color=TEAL, visible="card_is_preview")
        )
    frame = shape(
        3.8,
        15.5,
        21.3,
        27.3,
        "#DCE8DC",
        **{"border": ".15mm solid #ABC1AD", "border-radius": "1.2mm"},
    )
    frame["visible_if"] = "card_is_design"
    front.append(frame)
    head = shape(10.2, 20.1, 8.5, 8.5, "#9DB7A7", **{"border-radius": "50%"})
    head["visible_if"] = "card_is_design"
    front.append(head)
    shoulders = shape(5.3, 30.2, 18.3, 12.6, "#9DB7A7", **{"border-radius": "50%"})
    shoulders["visible_if"] = "card_is_design"
    front.append(shoulders)
    front.append(text("PHOTO", 7.25, 41.3, 15, 4.45, color=TEAL, visible="card_is_design"))
    portrait = image("", 3.8, 15.5, 21.3, 27.3, **{"object-fit": "cover", "border-radius": "1.2mm"})
    portrait.update(field="user_image", visible_if="user_image")
    front.append(portrait)
    front.extend(
        [
            text("FULL NAME", 29, 17, 52.8, 4.65, color=MUTED),
            text("", 29, 21.1, 52.8, 9, field="card_full_name", weight=700, height=4, fit=7),
            text("CHAPEL", 29, 25, 10, 4.65, color=MUTED),
            text("ራዕይ ተካፋይነት አጥቢያ", 39.4, 25, 28, 4.9, color=MUTED, family="Noto Sans Ethiopic"),
            text("", 29, 28.3, 52.8, 6.9, field="card_chapel", height=3.1, fit=6),
            text("DATE OF ANOINTMENT", 29, 32.3, 32, 4.65, color=MUTED),
            text("", 29, 35.6, 31, 6.4, field="card_anointment", height=3),
            text("CHAPEL ROLE", 61.8, 32.3, 20, 4.65, color=MUTED),
            text(
                "",
                61.8,
                35.6,
                20,
                6.7,
                field="card_role",
                weight=700,
                color=TEAL,
                height=3,
                fit=5.8,
            ),
            text(
                "",
                61.8,
                38.2,
                20,
                4.9,
                field="card_role_translation",
                color=MUTED,
                family="Noto Sans Ethiopic",
                visible="card_role_translation",
                height=2.5,
            ),
            text("DEPARTMENT", 29, 39.6, 51, 4.65, color=MUTED, visible="card_department"),
            text(
                "",
                29,
                43,
                52,
                6.7,
                field="card_department",
                visible="card_department",
                height=3.5,
                fit=6,
            ),
            image(assets["seal"], 17.15, 40, 11.6, 7.73),
            text("VISION PARTNER NO.", 3.8, 51.9, 21, 4, color="#D7E4D2"),
            text(
                "",
                24.3,
                51.9,
                36,
                6.7,
                field="card_number",
                weight=700,
                color="#FFFFFF",
                height=3,
                fit=5.5,
            ),
            text(
                "",
                64.5,
                51.9,
                18,
                4.7,
                field="card_preview_badge",
                color="#E6E5C9",
                visible="card_is_preview",
            ),
        ]
    )
    back.extend(
        [
            text("VISION PARTNER ADDRESS", 3.8, 16.9, 52, 4.65, color=MUTED),
            text("", 3.8, 20.3, 53, 6.9, field="card_address_1", height=3.1, fit=6),
            text(
                "",
                3.8,
                22.9,
                53,
                5.7,
                field="card_address_2",
                weight=400,
                color=MUTED,
                visible="card_address_2",
                height=2.5,
                fit=5.4,
            ),
            text("PHONE NUMBER", 3.8, 26, 34, 4.65, color=MUTED, visible="card_phone"),
            text(
                "", 3.8, 29.4, 34, 6.9, field="card_phone", visible="card_phone", height=3.1, fit=6
            ),
            text("EMAIL ADDRESS", 3.8, 33.1, 34, 4.65, color=MUTED, visible="card_email"),
            text(
                "",
                3.8,
                36.5,
                53,
                6.9,
                field="card_email",
                visible="card_email",
                height=3.1,
                fit=5.8,
            ),
            image(assets["signature"], 39.5, 26, 19.1, 7.4, opacity="0.29"),
            dict(
                type="qr",
                x=59.8,
                y=14.9,
                width=22,
                height=22,
                field="profile_card_number",
                qr_error="M",
                qr_quiet=4,
                qr_dark=TEAL,
                qr_light="#FFFFFF",
            ),
            text(
                "DEMO QR", 66.55, 38.9, 14, 4.45, weight=700, color=TEAL, visible="card_is_preview"
            ),
            text("DISCLAIMER", 3.8, 40.4, 78, 4.65, color=MUTED),
            text(DISCLAIMER, 3.8, 43.1, 78, 5.15, weight=400, height=5.5),
            text("CHAPEL OFFICE", 3.8, 51.9, 23, 4.6, color="#D7E4D2"),
            text(
                "",
                28,
                51.9,
                54,
                5.7,
                field="card_office",
                weight=400,
                color="#FFFFFF",
                height=3,
                fit=5.2,
            ),
        ]
    )
    for side in (front, back):
        for e in side:
            if e.get("text") == "BAIC KINGDOM CHAPEL":
                e["style"]["letter-spacing"] = "0.42pt"
            if e.get("text") in ("VISION PARTNERSHIP CARD", "የራዕይ ተካፋይ"):
                e["style"]["letter-spacing"] = "0.38pt"
            if e.get("text") == "SAMPLE":
                e["style"]["letter-spacing"] = "0.28pt"
            if e.get("text") == "VISION PARTNER NO.":
                e["style"]["letter-spacing"] = "0.12pt"
            if e.get("field") == "card_number":
                e["style"]["letter-spacing"] = "0.35pt"
            if e.get("field") == "card_preview_badge":
                e["style"].update({"letter-spacing": "0.42pt", "text-align": "right"})
                e.update(x=63.5, width=18.3)
            if e.get("text") == "DEMO QR":
                e["style"]["letter-spacing"] = "0.5pt"
            if e.get("field") == "card_office" or e.get("text") == "CHAPEL OFFICE":
                e["style"]["letter-spacing"] = "0.32pt"
    for side in (front, back):
        for e in side:
            if e["type"] == "shape" and e["x"] == 0 and e["width"] == 85.6:
                e.update(bleed_background=True, allow_bleed=True)
    return front, back


def setup(bundle_path):
    """Optional bench execute entry point; never called by generic install/migrate hooks."""
    from id_card_designer.images import normalize
    from id_card_designer.security import require

    require("manage")
    if not frappe.get_meta("ID Card Template").has_field("preset_key") or not frappe.get_meta("ID Card Profile").has_field("anointment_date"):
        frappe.throw("Run the site migration before importing the BAIC preset.")
    if frappe.db.exists("ID Card Template", NAME):
        return dict(name=NAME, created=False)
    folder = Path(bundle_path).expanduser().resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    content = {}
    for role in ("background", "logo", "seal", "signature", "demo_portrait"):
        path = (folder / manifest["assets"][role]).resolve()
        if not path.is_relative_to(folder):
            frappe.throw("Asset bundle path escapes its directory.")
        content[role] = normalize(path.read_bytes())
    doc = frappe.get_doc(
        dict(
            doctype="ID Card Template",
            title=TITLE,
            preset_key=KEY,
            editor_mode="Visual",
            source_doctype="User",
            width_mm=85.6,
            height_mm=53.98,
            bleed_mm=0,
            safe_margin_mm=0,
            block_severe=1,
            enabled=1,
            front_layout="[]",
            back_layout="[]",
        )
    )
    doc.insert(set_name=NAME)
    assets = {}
    for role, raw in content.items():
        shared = None
        if role != "demo_portrait":
            shared_name = "baic-vision-" + role
            if frappe.db.exists("ID Card Asset", shared_name):
                shared = frappe.get_doc("ID Card Asset", shared_name)
                if shared.image:
                    assets[role] = shared.image
                    continue
            else:
                shared = frappe.get_doc(
                    dict(doctype="ID Card Asset", title="BAIC " + role.title())
                ).insert(set_name=shared_name)
        f = frappe.get_doc(
            dict(
                doctype="File",
                file_name="baic-" + role + ".png",
                content=raw,
                is_private=1,
                attached_to_doctype="ID Card Asset" if shared else "ID Card Template",
                attached_to_name=shared.name if shared else doc.name,
            )
        ).insert()
        assets[role] = f.file_url
        if shared:
            shared.image = f.file_url
            shared.save()
    front, back = scenes(assets)
    doc.reload()
    doc.update(
        dict(
            front_layout=json.dumps(front, ensure_ascii=False),
            back_layout=json.dumps(back, ensure_ascii=False),
            demo_portrait=assets["demo_portrait"],
        )
    )
    doc.save()
    return dict(name=doc.name, created=True)
