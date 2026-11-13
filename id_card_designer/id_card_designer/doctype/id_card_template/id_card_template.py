import frappe
from frappe.model.document import Document

from id_card_designer.rendering import snapshot
from id_card_designer.security import require


class IDCardTemplate(Document):
    def validate(self):
        if frappe.flags.in_id_card_seed:
            return
        require("design")
        old = self.get_doc_before_save()
        if self.builtin or (old and old.builtin):
            frappe.throw(
                "The bundled sample is protected. Duplicate it to customize.",
                frappe.PermissionError,
            )
        if old and (old.allowed_roles != self.allowed_roles or old.enabled != self.enabled):
            require("manage")
        if not old and self.allowed_roles:
            require("manage")
        for key in ("published_snapshot", "revisions", "revision", "status", "is_default"):
            if (
                self.get(key) != (old.get(key) if old else self.meta.get_field(key).default)
                and not frappe.flags.id_card_publishing
            ):
                # New drafts may use empty values rather than default values.
                if old or self.get(key) not in (None, "", 0, "Draft"):
                    frappe.throw(
                        "Use the publication/default APIs to change protected fields.",
                        frappe.PermissionError,
                    )
        if old and old.is_default and not self.enabled:
            frappe.throw("Choose another default before disabling this template.")
        if self.source_doctype != "User":
            frappe.throw("Only User source records are supported.")
        for role in (self.allowed_roles or "").splitlines():
            if not frappe.db.exists("Role", role):
                frappe.throw("Unknown template audience role: " + role)
        snapshot(self)

    def on_trash(self):
        require("manage")
        if self.builtin or self.is_default:
            frappe.throw("The bundled or default template cannot be deleted.")


def has_permission(doc, ptype=None, user=None, **kwargs):
    from id_card_designer.security import audience_allowed

    return bool(audience_allowed(doc, user=user))
