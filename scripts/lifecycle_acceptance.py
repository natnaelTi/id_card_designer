"""Lifecycle gates on an explicitly marked disposable site, never on an operator site."""

import io
import os
import subprocess
import sys
from pathlib import Path

import frappe
from pypdf import PdfReader

from id_card_designer import api
from id_card_designer.install import DEMO_NAME

bench = Path(os.environ.get("ID_CARD_BENCH_ROOT", Path(__file__).resolve().parents[3])).resolve()
site = os.environ.get("ID_CARD_TEST_SITE", "id-card-designer-test.localhost")
assert site.startswith("id-card-") and site.endswith("-test.localhost")
os.chdir(bench / "sites")


def connect():
    frappe.init(site=site)
    frappe.connect()
    frappe.set_user("Administrator")
    assert frappe.conf.get("id_card_test_fixture"), "Refusing an unmarked site"


def command(*args):
    subprocess.run(
        [sys.executable, "-m", "frappe.utils.bench_helper", "frappe", "--site", site, *args],
        check=True,
    )


connect()

mode = sys.argv[1]
if mode == "preserve":
    assert frappe.db.count("ID Card Template", {"builtin": 1}) == 1
    user = "migration-fixture@org.example.invalid"
    if not frappe.db.exists("User", user):
        frappe.get_doc(
            dict(
                doctype="User",
                email=user,
                first_name="Migration",
                last_name="Fixture",
                send_welcome_email=0,
            )
        ).insert()
        frappe.get_doc(
            dict(
                doctype="ID Card Profile",
                user=user,
                department="Synthetic Research",
                card_number="ORG-DEMO-001",
            )
        ).insert()
    draft = api.duplicate_template(DEMO_NAME)
    draft["title"] = "Customer migration preservation fixture"
    draft = api.save_draft(draft)
    api.publish_template(draft["name"])
    api.set_default_template(draft["name"])
    original = frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot
    design = frappe.get_doc("ID Card Template", draft["name"]).published_snapshot
    profile = frappe.get_doc("ID Card Profile", user).as_dict()
    frappe.db.commit()
    frappe.destroy()
    command("migrate")
    command("migrate")
    connect()
    assert frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot == original
    assert frappe.get_doc("ID Card Template", draft["name"]).published_snapshot == design
    assert frappe.get_single("ID Card Settings").default_template == draft["name"]
    assert frappe.get_doc("ID Card Profile", user).department == profile.department
    api.print_user_id(draft["name"], user)
    raw = frappe.local.response.filecontent
    pages = PdfReader(io.BytesIO(raw)).pages
    assert len(pages) == 2 and "Migration Fixture" in pages[0].extract_text()
    assert user in "\n".join(p.extract_text() for p in pages)
    for page in pages:
        assert abs(float(page.mediabox.width) * 25.4 / 72 - 85.60) < 0.01
        assert abs(float(page.mediabox.height) * 25.4 / 72 - 53.98) < 0.01
    api.set_default_template(DEMO_NAME)
    frappe.db.commit()
    print(
        "PASS lifecycle: fresh default, two migrations preserve custom publication/default/profile, real User PDF two pages and correct dimensions"
    )
elif mode == "reinstall":
    users = set(frappe.get_all("User", pluck="name"))
    frappe.destroy()
    command("uninstall-app", "id_card_designer", "--yes", "--no-backup")
    command("install-app", "id_card_designer")
    connect()
    assert set(frappe.get_all("User", pluck="name")) == users
    assert frappe.db.count("ID Card Template", {"builtin": 1}) == 1
    assert frappe.get_single("ID Card Settings").default_template == DEMO_NAME
    print(
        "PASS lifecycle: uninstall/reinstall restores one default and preserves all framework Users"
    )
else:
    raise ValueError("Choose preserve or reinstall")
frappe.destroy()
