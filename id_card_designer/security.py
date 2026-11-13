"""Explicit capabilities and a deliberately small User binding schema."""

import frappe

USER_FIELDS = (
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "email",
    "user_image",
    "phone",
    "mobile_no",
    "language",
    "location",
)
PROFILE_FIELDS = (
    "local_name",
    "department",
    "role_title",
    "card_number",
    "issue_date",
    "expiry_date",
)
SAFE_FIELDS = USER_FIELDS + tuple("profile_" + f for f in PROFILE_FIELDS)
MANAGERS = {"ID Card Manager", "System Manager"}


def can(capability):
    if frappe.session.user == "Guest":
        return False
    roles = set(frappe.get_roles())
    allowed = MANAGERS.copy()
    if capability == "design":
        allowed.add("ID Card Designer")
    if capability == "print":
        settings = frappe.get_single("ID Card Settings")
        allowed.update((settings.printing_roles or "ID Card Printer").splitlines())
    return frappe.session.user == "Administrator" or bool(roles.intersection(allowed))


def require(capability):
    if not can(capability):
        frappe.throw("Your role does not permit this ID card action.", frappe.PermissionError)


def schema():
    meta = frappe.get_meta("User")
    fields = [
        dict(fieldname=f.fieldname, label=f.label, source="User", fieldtype=f.fieldtype)
        for f in meta.fields
        if f.fieldname in USER_FIELDS and not f.permlevel
    ]
    fields += [
        dict(
            fieldname="profile_" + f,
            label=f.replace("_", " ").title(),
            source="ID Card Profile",
            fieldtype="Date" if f.endswith("_date") else "Data",
        )
        for f in PROFILE_FIELDS
    ]
    return fields


def user_data(name, printing=False):
    doc = frappe.get_doc("User", name)
    doc.check_permission("read")
    if printing:
        doc.check_permission("print")
    permitted = doc.as_dict()
    doc.apply_fieldlevel_read_permissions()
    readable = doc.as_dict()
    result = {
        f["fieldname"]: readable.get(f["fieldname"]) or ""
        for f in schema()
        if f["source"] == "User" and f["fieldname"] in permitted
    }
    profile_name = frappe.db.get_value("ID Card Profile", {"user": name}, "name")
    if profile_name:
        profile = frappe.get_doc("ID Card Profile", profile_name)
        if profile.has_permission("read"):
            profile.apply_fieldlevel_read_permissions()
            result.update({"profile_" + f: str(profile.get(f) or "") for f in PROFILE_FIELDS})
    return result


def audience_allowed(template, user=None):
    allowed = set((template.allowed_roles or "").splitlines()) - {""}
    return (
        not allowed
        or bool(allowed.intersection(frappe.get_roles(user)))
        or (user or frappe.session.user) == "Administrator"
    )


def audience(template):
    if not audience_allowed(template):
        frappe.throw("This template is restricted to its audience roles.", frappe.PermissionError)
