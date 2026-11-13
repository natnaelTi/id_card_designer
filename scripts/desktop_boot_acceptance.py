"""Regression for the early-v16 crash, on an explicitly marked disposable site."""

import os
from pathlib import Path

import frappe

from id_card_designer.navigation import seed_navigation, supports_desktop_icons

bench = Path(os.environ["ID_CARD_BENCH_ROOT"])
site = os.environ["ID_CARD_TEST_SITE"]
assert site.startswith("id-card-") and site.endswith("-test.localhost")
os.chdir(bench / "sites")
frappe.init(site=site)
frappe.connect()
frappe.set_user("Administrator")
assert frappe.conf.id_card_test_fixture
from frappe.boot import get_bootinfo  # noqa: E402

if not supports_desktop_icons():
    # Reproduce a previously installed app icon, then exercise its real boot failure.
    if not frappe.db.exists("Desktop Icon", "ID Card Designer"):
        frappe.get_doc(
            dict(
                doctype="Desktop Icon",
                label="ID Card Designer",
                icon_type="Link",
                link_type="Workspace Sidebar",
                link_to="ID Card Designer",
                sidebar="ID Card Designer",
                icon="printer",
            )
        ).insert()
    frappe.cache().delete_key("desktop_icons")
    try:
        get_bootinfo()
    except frappe.DoesNotExistError as error:
        assert "Desktop Icon" in str(error)
        print("REPRODUCED: early-v16 Desktop Icon row interpreted as a document name")
    else:
        raise AssertionError("Expected the unmodified old framework to reproduce the boot failure")
seed_navigation()
seed_navigation()
frappe.cache().delete_key("desktop_icons")
boot = get_bootinfo()
assert boot.user.name == "Administrator"
assert frappe.db.exists("Workspace Sidebar", "ID Card Designer")
assert bool(frappe.db.exists("Desktop Icon", "ID Card Designer")) == supports_desktop_icons()
frappe.db.commit()
frappe.destroy()
print("PASS: idempotent app navigation repair, real Desk boot and retained workspace/sidebar")
