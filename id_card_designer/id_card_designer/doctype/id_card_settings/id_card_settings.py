import frappe
from frappe.model.document import Document

from id_card_designer.security import require


class IDCardSettings(Document):
    def validate(self):
        if frappe.flags.in_id_card_seed:
            return
        require("manage")
        from id_card_designer.rendering import number

        number(self.default_width_mm or 85.6, 20, 200)
        number(self.default_height_mm or 53.98, 20, 150)
        number(self.default_bleed_mm or 0, 0, 10)
        for role in (self.printing_roles or "").splitlines():
            if not frappe.db.exists("Role", role):
                frappe.throw("Unknown printing role: " + role)
        old = self.get_doc_before_save()
        if (
            old
            and old.default_template != self.default_template
            and not frappe.flags.id_card_default_update
        ):
            frappe.throw("Use Set Default on a published template.")
