import ast
import inspect
import textwrap

import frappe


def supports_desktop_icons():
    """Detect the early-v16 loader bug without patching or executing framework code.

    That loader passes an entire result row to get_doc("Desktop Icon", row),
    which Frappe interprets as a document name. Fixed loaders use explicit names
    or batch their permission checks. Unknown source fails closed to Workspace.
    """
    try:
        from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons

        return safe_loader(inspect.getsource(get_desktop_icons))
    except (ImportError, OSError, TypeError, SyntaxError):
        return False


def safe_loader(source):
    tree = ast.parse(textwrap.dedent(source))
    return not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_doc"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "Desktop Icon"
        and isinstance(node.args[1], ast.Name)
        for node in ast.walk(tree)
    )


def remove_incompatible_icon(title):
    # Only remove the exact icon linked to this app's sidebar. Never touch other
    # applications' icons, customer templates, publications, profiles or Files.
    icon = frappe.db.get_value("Desktop Icon", title, ["name", "sidebar", "link_to"], as_dict=True)
    if icon and icon.sidebar == title and icon.link_to == title:
        frappe.delete_doc("Desktop Icon", icon.name)
    frappe.cache().delete_key("desktop_icons")


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
    if not supports_desktop_icons():
        remove_incompatible_icon(title)
        return
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
