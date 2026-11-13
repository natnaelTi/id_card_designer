"""Loopback-only acceptance server for the disposable ID Card Designer site."""

import os
from pathlib import Path

import frappe.app

bench = Path(os.environ.get("ID_CARD_BENCH_ROOT", Path(__file__).resolve().parents[3]))
frappe.app._site = os.environ.get("ID_CARD_TEST_SITE", "id-card-designer-test.localhost")
frappe.app._sites_path = str(bench / "sites")
application = frappe.app.application_with_statics()
