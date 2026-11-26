"""Explicit synthetic BAIC workflow fixture, restricted to marked disposable sites."""

import argparse
import json
import os
from pathlib import Path

import frappe

from id_card_designer import api
from id_card_designer.presets import baic

parser = argparse.ArgumentParser()
parser.add_argument("--bundle", required=True)
parser.add_argument("--output", required=True, type=Path)
a = parser.parse_args()
bench = Path(os.environ["ID_CARD_BENCH_ROOT"])
site = os.environ["ID_CARD_TEST_SITE"]
assert site.startswith("id-card-") and site.endswith("-test.localhost")
os.chdir(bench / "sites")
frappe.init(site=site)
frappe.connect()
frappe.set_user("Administrator")
assert frappe.conf.id_card_test_fixture
baic.setup(a.bundle)
d = api.get_template_for_builder(baic.NAME)
assert d["status"] == "Draft", "Use a fresh disposable fixture for acceptance"
assets = {
    k: frappe.get_doc("ID Card Asset", "baic-vision-" + k).image
    for k in ("background", "logo", "seal", "signature")
}
f, b = baic.scenes(assets)
d.update(
    front_layout=json.dumps(f, ensure_ascii=False), back_layout=json.dumps(b, ensure_ascii=False)
)
api.save_draft(d)
user = "baic-workflow@org.example.invalid"
if not frappe.db.exists("User", user):
    frappe.get_doc(
        dict(
            doctype="User",
            email=user,
            first_name="Synthetic",
            last_name="BAIC Partner",
            phone="+251 900 000 001",
            send_welcome_email=0,
            user_type="System User",
        )
    ).insert()
portrait = frappe.get_doc(
    dict(
        doctype="File",
        file_name="baic-workflow-portrait.png",
        content=(Path(a.bundle) / "demo_portrait.png").read_bytes(),
        is_private=1,
        attached_to_doctype="User",
        attached_to_name=user,
    )
).insert()
u = frappe.get_doc("User", user)
u.user_image = portrait.file_url
u.save()
if not frappe.db.exists("ID Card Profile", user):
    frappe.get_doc(
        dict(
            doctype="ID Card Profile",
            user=user,
            chapel="Bole Chapel",
            anointment_date="2025-10-22",
            role_title="Member",
            department="Media & Communications",
            card_number="BAIC-TEST-0001",
            address_line_1="Synthetic address line 1",
            address_line_2="Addis Ababa, Ethiopia",
        )
    ).insert()
settings = frappe.get_single("ID Card Settings")
default = settings.default_template
settings.baic_office_contact = "Chapel office / chapel-office@example.invalid"
settings.save()
assert frappe.get_single("ID Card Settings").default_template == default
frappe.db.commit()
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(dict(template=baic.NAME, user=user, default_template=default)))
a.output.chmod(0o600)
frappe.destroy()
print("Prepared explicit synthetic BAIC workflow fixture; no default/publication changed.")
