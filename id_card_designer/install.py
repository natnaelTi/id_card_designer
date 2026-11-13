import json

import frappe

from id_card_designer.rendering import snapshot

DEMO_NAME = "national-id-inspired-demo"


def sample():
    def text(x, y, w, h, text="", field="", size="8pt", **extra):
        return dict(
            type="text",
            x=x,
            y=y,
            width=w,
            height=h,
            text=text,
            field=field,
            style={"font-size": size, "color": "#244b47", **extra},
        )

    front = [
        dict(type="shape", x=0, y=0, width=85.6, height=10, style={"background": "#dae7df"}),
        text(4, 1, 77, 5, "EXAMPLE INSTITUTION · የተቋም መታወቂያ", size="9pt"),
        text(4, 6, 77, 3, "Institutional ID · Unofficial demonstration", size="6pt"),
        dict(
            type="image",
            x=4,
            y=13,
            width=21,
            height=28,
            field="user_image",
            fallback="No photo",
            style={"background": "#dbe3dd", "object-fit": "cover", "padding": "1mm"},
        ),
        text(29, 11, 52, 3, "FULL NAME / ሙሉ ስም", size="5pt"),
        text(29, 14, 52, 9, field="full_name", size="10pt"),
        text(29, 23, 52, 4, field="profile_local_name", size="8pt"),
        text(29, 28, 52, 3, field="profile_department", size="6.5pt"),
        text(29, 31.5, 52, 3, field="profile_role_title", size="6.5pt"),
        text(29, 35, 52, 3, "ISSUED                         EXPIRES", size="5pt"),
        text(29, 38, 25, 3, field="profile_issue_date", size="6.5pt"),
        text(57, 38, 25, 3, field="profile_expiry_date", size="6.5pt"),
        text(4, 42, 77, 4, field="profile_card_number", size="7pt"),
        text(
            4,
            47,
            78,
            5,
            "SAMPLE / NOT VALID ID",
            size="10pt",
            **{"font-weight": "bold", "color": "#835d23"},
        ),
    ]
    for e in front:
        if e.get("field", "").startswith("profile_"):
            e["fallback"] = "—"

    back = [
        dict(
            type="shape",
            x=54,
            y=7,
            width=27,
            height=34,
            style={"background": "#d6e6de", "border-radius": "8mm"},
        ),
        dict(
            type="shape",
            x=61,
            y=13,
            width=14,
            height=22,
            rotation=20,
            style={"background": "#b6c9bc", "border-radius": "4mm"},
        ),
        text(5, 5, 47, 6, "EXAMPLE INSTITUTION", size="10pt"),
        text(
            5,
            15,
            45,
            13,
            "If found, return to your institution.\nContact: office@example.invalid",
            size="8pt",
        ),
        text(5, 30, 45, 8, field="email", size="7pt"),
        text(5, 42, 75, 4, "Issued by the configured institution only.", size="6pt"),
        text(
            5,
            47,
            76,
            5,
            "SAMPLE / NOT VALID ID",
            size="10pt",
            **{"font-weight": "bold", "color": "#835d23"},
        ),
    ]
    return dict(
        title="National-ID-Inspired Demo — NOT VALID ID",
        description="Unofficial, institution-neutral sample. No government verification.",
        enabled=1,
        builtin=1,
        is_default=1,
        status="Published",
        source_doctype="User",
        editor_mode="Visual",
        width_mm=85.6,
        height_mm=53.98,
        bleed_mm=0,
        front_layout=json.dumps(front),
        back_layout=json.dumps(back),
        revision=1,
    )


def seed():
    frappe.flags.in_id_card_seed = True
    try:
        for role in ("ID Card Manager", "ID Card Designer", "ID Card Printer"):
            if not frappe.db.exists("Role", role):
                frappe.get_doc(dict(doctype="Role", role_name=role, desk_access=1)).insert()
        if not frappe.db.exists("ID Card Template", DEMO_NAME):
            doc = frappe.get_doc(dict(doctype="ID Card Template", name=DEMO_NAME, **sample()))
            doc.published_snapshot = json.dumps(snapshot(doc))
            doc.insert(set_name=DEMO_NAME)
        settings = frappe.get_single("ID Card Settings")
        if not settings.default_template:
            settings.default_template = DEMO_NAME
            settings.save()
            frappe.db.set_value("ID Card Template", DEMO_NAME, "is_default", 1)
        if not frappe.db.exists("Workspace", "ID Card Designer"):
            links = [
                dict(
                    type="Link",
                    label="ID Card Templates",
                    link_type="DocType",
                    link_to="ID Card Template",
                ),
                dict(
                    type="Link",
                    label="Create Template",
                    link_type="Page",
                    link_to="id-card-builder",
                ),
                dict(
                    type="Link",
                    label="ID Card Settings",
                    link_type="DocType",
                    link_to="ID Card Settings",
                ),
                dict(
                    type="Link",
                    label="ID Card Profiles",
                    link_type="DocType",
                    link_to="ID Card Profile",
                ),
                dict(
                    type="Link",
                    label="Print Audit Log",
                    link_type="DocType",
                    link_to="ID Card Print Log",
                ),
            ]
            frappe.get_doc(
                dict(
                    doctype="Workspace",
                    name="ID Card Designer",
                    title="ID Card Designer",
                    label="ID Card Designer",
                    module="ID Card Designer",
                    public=1,
                    icon="printer",
                    links=[dict(type="Card Break", label="ID Cards")] + links,
                    content=json.dumps(
                        [
                            dict(
                                id="id-card-header",
                                type="header",
                                data=dict(text="<b>ID Card Designer</b>", col=12),
                            ),
                            dict(
                                id="id-card-links",
                                type="card",
                                data=dict(card_name="ID Cards", col=12),
                            ),
                        ]
                    ),
                    roles=[
                        dict(role=r)
                        for r in (
                            "ID Card Manager",
                            "ID Card Designer",
                            "ID Card Printer",
                            "System Manager",
                        )
                    ],
                )
            ).insert()
    finally:
        frappe.flags.in_id_card_seed = False
    from id_card_designer.navigation import seed_navigation

    seed_navigation()
