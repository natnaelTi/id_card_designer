"""Local acceptance fixture; refuses sites without the explicit test suffix."""

import json
import os
import secrets
from pathlib import Path

import frappe
from frappe.utils.password import update_password
from PIL import Image

site = os.environ.get("ID_CARD_TEST_SITE", "id-card-designer-test.localhost")
assert site.endswith("-test.localhost"), "Use a disposable test site only"
bench = Path(__file__).resolve().parents[3]
os.chdir(bench / "sites")
frappe.init(site=site, sites_path=str(bench / "sites"))
frappe.connect()
frappe.set_user("Administrator")
password = secrets.token_urlsafe(32)
update_password("Administrator", password)
frappe.db.set_single_value("System Settings", "setup_complete", 1)
frappe.db.sql("UPDATE `tabInstalled Application` SET is_setup_complete=1")
actors = []
for email, role in [
    ("printer-ui@id.example.invalid", "ID Card Printer"),
    ("plain-ui@id.example.invalid", "ID Card Designer"),
]:
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            dict(
                doctype="User",
                email=email,
                first_name=email.split("@")[0],
                send_welcome_email=0,
                user_type="System User",
            )
        ).insert()
    else:
        user = frappe.get_doc("User", email)
    if role:
        user.add_roles(role)
    actor_password = secrets.token_urlsafe(32)
    update_password(email, actor_password)
    frappe.share.add("User", email, user=email, read=1)
    actors.append(dict(usr=email, pwd=actor_password, can_print=role == "ID Card Printer"))
frappe.db.commit()
frappe.clear_cache()
p = Path("/tmp/id-card-runtime/browser-login.json")
p.write_text(json.dumps(dict(usr="Administrator", pwd=password, actors=actors)))
p.chmod(0o600)
Image.new("RGB", (700, 900), "#7d9d91").save("/tmp/id-card-runtime/test-logo.png")
frappe.destroy()
print("Disposable-site browser login fixture ready.")
