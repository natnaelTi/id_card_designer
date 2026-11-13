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
        if self.qr_application_origin:
            from urllib.parse import urlsplit

            url = urlsplit(self.qr_application_origin)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.path not in ("", "/")
                or url.query
                or url.fragment
            ):
                frappe.throw(
                    "QR application origin must be an HTTPS origin without credentials, path, query or fragment."
                )
        if (
            self.audit_retention_days is not None
            and not 1 <= int(self.audit_retention_days or 90) <= 3650
        ):
            frappe.throw("Audit retention must be 1–3650 days.")
        old = self.get_doc_before_save()
        if (
            old
            and old.default_template != self.default_template
            and not frappe.flags.id_card_default_update
        ):
            frappe.throw("Use Set Default on a published template.")
