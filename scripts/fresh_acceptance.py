"""Fresh install + two migrations, limited to a new named disposable site."""

# ruff: noqa: E402 -- bootstrap the Bench cwd/environment before importing its commands.

import io
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

BENCH = Path(__file__).resolve().parents[3]
SITE = "id-card-designer-fresh.localhost"
DB = "id_card_designer_fresh"
SOCKET = "/tmp/id-card-runtime/db.sock"
assert not (BENCH / "sites" / SITE).exists(), "Refusing to overwrite an existing site."
os.environ["FRAPPE_REDIS_CACHE"] = "redis://127.0.0.1:13328"
os.environ["FRAPPE_REDIS_QUEUE"] = "redis://127.0.0.1:13328"
os.chdir(BENCH / "sites")
import pymysql

c = pymysql.connect(unix_socket=SOCKET, user="root")
assert not c.cursor().execute("SHOW DATABASES LIKE %s", (DB,))
c.close()
from frappe.commands.site import new_site

with patch("getpass.getpass", return_value=""):
    new_site.callback(
        site=SITE,
        db_name=DB,
        db_type="mariadb",
        db_root_username="root",
        db_root_password="",
        db_socket=SOCKET,
        admin_password=secrets.token_urlsafe(32),
        db_password=secrets.token_urlsafe(32),
        mariadb_user_host_login_scope="localhost",
        install_app=["id_card_designer"],
    )
import frappe

config_file = BENCH / "sites" / SITE / "site_config.json"
config = json.loads(config_file.read_text())
config.update(redis_cache="redis://127.0.0.1:13328", redis_queue="redis://127.0.0.1:13328")
config_file.write_text(json.dumps(config, indent=2))
frappe.destroy()
frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")
from id_card_designer import api
from id_card_designer.install import DEMO_NAME

assert frappe.db.count("ID Card Template") == 1
assert (
    frappe.db.count(
        "ID Card Template", {"builtin": 1, "is_default": 1, "enabled": 1, "status": "Published"}
    )
    == 1
)
assert frappe.db.exists("Workspace", "ID Card Designer")
assert all(
    frappe.db.exists("Role", role)
    for role in ("ID Card Manager", "ID Card Designer", "ID Card Printer")
)
assert frappe.db.exists("DocType", "ID Card Profile")
original = frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot
copy = api.duplicate_template(DEMO_NAME)
copy["title"] = "Customer design — preserve through migrations"
copy = api.save_draft(copy)
api.publish_template(copy["name"])
api.set_default_template(copy["name"])
frappe.db.commit()
frappe.destroy()
for _ in range(2):
    subprocess.run(
        [sys.executable, "-m", "frappe.utils.bench_helper", "frappe", "--site", SITE, "migrate"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")
assert frappe.db.count("ID Card Template") == 2
assert frappe.get_doc("ID Card Template", DEMO_NAME).published_snapshot == original
assert frappe.get_doc("ID Card Template", copy["name"]).title == copy["title"]
assert frappe.get_single("ID Card Settings").default_template == copy["name"]
user = frappe.get_doc(
    dict(
        doctype="User",
        email="card-fixture@example.invalid",
        first_name="Live",
        last_name="Fixture",
        send_welcome_email=0,
    )
).insert()
frappe.get_doc(
    dict(
        doctype="ID Card Profile",
        user=user.name,
        department="Applied Sciences",
        role_title="Library Member",
        card_number="INSTITUTION-017",
        local_name="ሰላም",
        issue_date="2026-01-01",
        expiry_date="2027-01-01",
    )
).insert()
api.print_user_id(copy["name"], user.name)
from pypdf import PdfReader

raw = frappe.local.response.filecontent
r = PdfReader(io.BytesIO(raw))
assert len(r.pages) == 2
assert "Live Fixture" in r.pages[0].extract_text()
assert "Applied Sciences" in r.pages[0].extract_text()
assert "card-fixture@example.invalid" in r.pages[1].extract_text()
assert "Selam Example" not in r.pages[0].extract_text()
out = BENCH / "apps/id_card_designer/artifacts"
(out / "fresh-live-fixture.pdf").write_bytes(raw)
frappe.db.commit()
frappe.destroy()
print(
    "PASS: fresh install; one protected default; all roles/workspace/profile; two migrations preserve customer design, default and demo snapshot; real User/Profile bindings in two-page PDF."
)
