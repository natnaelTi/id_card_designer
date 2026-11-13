from frappe.model.document import Document

from id_card_designer.security import require


class IDCardAsset(Document):
    def validate(self):
        require("manage")
        if self.image:
            from id_card_designer.rendering import asset

            asset(self.image)

    def on_trash(self):
        require("manage")
