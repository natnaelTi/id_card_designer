import frappe


def seed_navigation():
    if not frappe.db.exists("DocType", "Workspace Sidebar"):
        return
    title = "ID Card Designer"
    if not frappe.db.exists("Workspace Sidebar", title):
        items = [dict(type="Link", label=title, link_type="Workspace", link_to=title)]
        items += [
            dict(type="Link", label=label, link_type=kind, link_to=target)
            for label, kind, target in [
                ("ID Card Templates", "DocType", "ID Card Template"),
                ("Create Template", "Page", "id-card-builder"),
                ("Shared Assets", "DocType", "ID Card Asset"),
                ("Settings", "DocType", "ID Card Settings"),
                ("Profiles", "DocType", "ID Card Profile"),
                ("Print Audit", "DocType", "ID Card Print Log"),
            ]
        ]
        frappe.get_doc(
            dict(
                doctype="Workspace Sidebar",
                title=title,
                module=title,
                header_icon="printer",
                items=items,
            )
        ).insert()
    if frappe.get_meta("Desktop Icon").has_field("sidebar") and not frappe.db.exists(
        "Desktop Icon", title
    ):
        frappe.get_doc(
            dict(
                doctype="Desktop Icon",
                label=title,
                icon_type="Link",
                link_type="Workspace Sidebar",
                link_to=title,
                sidebar=title,
                icon="printer",
                roles=[
                    dict(role=x)
                    for x in [
                        "ID Card Manager",
                        "ID Card Designer",
                        "ID Card Printer",
                        "System Manager",
                    ]
                ],
            )
        ).insert()
