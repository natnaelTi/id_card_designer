"""Loopback-only acceptance server for the disposable ID Card Designer site."""

from pathlib import Path

import frappe.app

bench = Path(__file__).resolve().parents[3]
frappe.app._site = "id-card-designer-test.localhost"
frappe.app._sites_path = str(bench / "sites")
application = frappe.app.application_with_statics()
