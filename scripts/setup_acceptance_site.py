"""Create only an explicitly named disposable acceptance site; works in CI and local v15/v16."""

# ruff: noqa: E402 -- establish the test Bench cwd before site initialization.
import json
import os
import secrets
from pathlib import Path

import frappe
from frappe.commands.site import new_site

bench = Path(os.environ.get("ID_CARD_BENCH_ROOT", Path(__file__).resolve().parents[3])).resolve()
site = os.environ.get("ID_CARD_TEST_SITE", "id-card-designer-test.localhost")
assert site.startswith("id-card-") and site.endswith("-test.localhost"), (
    "Disposable acceptance site required"
)
os.chdir(bench / "sites")
assert not (bench / "sites" / site).exists(), "Refusing to overwrite an existing site"
from unittest.mock import patch

root_password = os.environ.get("ID_CARD_DB_ROOT_PASSWORD", "")
redis = os.environ.get("ID_CARD_REDIS", "redis://127.0.0.1:13328")
os.environ["FRAPPE_REDIS_CACHE"] = os.environ["FRAPPE_REDIS_QUEUE"] = redis
with patch("getpass.getpass", return_value=root_password):
    new_site.callback(
        site=site,
        db_name=os.environ.get("ID_CARD_DB_NAME", site.replace("-", "_").replace(".", "_")),
        db_type="mariadb",
        db_root_username="root",
        db_root_password=root_password or None,
        db_socket=os.environ.get("ID_CARD_DB_SOCKET"),
        db_host=os.environ.get("ID_CARD_DB_HOST"),
        admin_password=secrets.token_urlsafe(32),
        db_password=secrets.token_urlsafe(32),
        mariadb_user_host_login_scope=os.environ.get("ID_CARD_DB_SCOPE", "localhost"),
        install_app=["id_card_designer"],
    )
frappe.destroy()
path = bench / "sites" / site / "site_config.json"
config = json.loads(path.read_text())
config.update(redis_cache=redis, redis_queue=redis, allow_tests=True, id_card_test_fixture=1)
path.write_text(json.dumps(config, indent=2))
path.chmod(0o600)
frappe.init(site=site)
frappe.connect()
frappe.set_user("Administrator")
from id_card_designer.testing import bootstrap

bootstrap()
frappe.db.commit()
frappe.destroy()
print("Created isolated acceptance site:", site)
