import frappe
from frappe.model.document import Document

from id_card_designer.security import require


class IDCardProfile(Document):
    def validate(self):
        require("manage")
        frappe.get_doc("User", self.user).check_permission("read")
        old = self.get_doc_before_save()
        if old and old.user != self.user:
            frappe.throw("Create a separate profile to change the linked User.")
        if self.issue_date and self.expiry_date and str(self.expiry_date) < str(self.issue_date):
            frappe.throw("Expiry date must be on or after the issue date.")


def has_permission(doc, ptype=None, user=None, **kwargs):
    return bool(frappe.has_permission("User", "read", doc=doc.user, user=user))


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    # Conservative lists: direct access is still possible with profile AND source-User access.
    return "`tabID Card Profile`.`user`=" + frappe.db.escape(user)
