"""Disposable-site test bootstrap only; never called by install/migrate or public APIs."""

import frappe


def bootstrap():
    if not frappe.conf.allow_tests:
        frappe.throw("Enable tests only on a disposable development site.")
    for key, value in {"language": "en", "time_zone": "UTC"}.items():
        if not frappe.db.get_single_value("System Settings", key):
            frappe.db.set_single_value("System Settings", key, value)


def save_file(filename, content, doctype, name, is_private=1):
    """Fixture using the public File document API, preserving binary content before insert.

    The v16 legacy file_manager helper writes then re-reads some PNGs as Windows
    text. Supplying bytes to File directly exercises its normal, strict lifecycle.
    """
    return frappe.get_doc(
        dict(
            doctype="File",
            file_name=filename,
            content=content,
            is_private=is_private,
            attached_to_doctype=doctype,
            attached_to_name=name,
        )
    ).insert()
