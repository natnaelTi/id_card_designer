import unittest
from unittest.mock import patch

import frappe

from id_card_designer.navigation import remove_incompatible_icon, safe_loader

try:
    from frappe.tests import UnitTestCase
except ImportError:
    UnitTestCase = unittest.TestCase
if not getattr(frappe.local, "site", None):
    UnitTestCase = unittest.TestCase


class NavigationTests(UnitTestCase):
    def test_rejects_legacy_row_lookup_and_accepts_fixed_loaders(self):
        self.assertFalse(safe_loader('def load():\n    frappe.get_doc("Desktop Icon", s)'))
        self.assertTrue(safe_loader('def load():\n    frappe.get_doc("Desktop Icon", s.name)'))
        self.assertTrue(safe_loader("def load():\n    return batch_permission_checks()"))

    def test_cleanup_only_removes_exact_app_sidebar_icon(self):
        with patch("id_card_designer.navigation.frappe") as framework:
            framework.db.get_value.return_value = type(
                "Icon", (), dict(name="ID Card Designer", sidebar="Other App", link_to="Other App")
            )()
            remove_incompatible_icon("ID Card Designer")
            framework.delete_doc.assert_not_called()
            framework.cache.return_value.delete_key.assert_called_once_with("desktop_icons")
            framework.db.get_value.return_value = type(
                "Icon",
                (),
                dict(
                    name="ID Card Designer", sidebar="ID Card Designer", link_to="ID Card Designer"
                ),
            )()
            remove_incompatible_icon("ID Card Designer")
            framework.delete_doc.assert_called_once_with("Desktop Icon", "ID Card Designer")
