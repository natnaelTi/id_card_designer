"""Manage only this app's disposable runtime. Never migrates an existing site."""

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[3]
RUNTIME = Path("/tmp/id-card-runtime")
SITE = "id-card-designer-test.localhost"
DB = "id_card_designer_dev"


def owned_pid(kind):
    file = RUNTIME / (kind + ".pid")
    if not file.exists():
        return None
    pid = int(file.read_text().strip())
    try:
        cmd = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode()
    except FileNotFoundError:
        return None
    expected = {
        "db": "--datadir=" + str(RUNTIME / "db"),
        "redis": "redis-server 127.0.0.1:13328",
        "web": "dev_wsgi:application",
    }[kind]
    if expected not in cmd:
        raise RuntimeError("PID belongs to another process; no action taken: " + kind)
    return pid


def start():
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    RUNTIME.chmod(0o700)
    if not (RUNTIME / "db/mysql").exists():
        subprocess.run(
            [
                "mariadb-install-db",
                "--datadir=" + str(RUNTIME / "db"),
                "--auth-root-authentication-method=normal",
                "--skip-test-db",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    if not owned_pid("db"):
        subprocess.Popen(
            [
                "mariadbd",
                "--datadir=" + str(RUNTIME / "db"),
                "--socket=" + str(RUNTIME / "db.sock"),
                "--pid-file=" + str(RUNTIME / "db.pid"),
                "--skip-networking",
                "--log-error=" + str(RUNTIME / "db.log"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    for _ in range(50):
        try:
            import pymysql

            c = pymysql.connect(unix_socket=str(RUNTIME / "db.sock"), user="root")
            c.close()
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("Temporary MariaDB unavailable; inspect " + str(RUNTIME / "db.log"))
    if not owned_pid("redis"):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 13328)) == 0:
                raise RuntimeError("Port 13328 belongs to another process.")
        subprocess.run(
            [
                "redis-server",
                "--port",
                "13328",
                "--bind",
                "127.0.0.1",
                "--daemonize",
                "yes",
                "--pidfile",
                str(RUNTIME / "redis.pid"),
                "--logfile",
                str(RUNTIME / "redis.log"),
                "--dir",
                str(RUNTIME),
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            check=True,
        )
    if not (BENCH / "sites" / SITE / "site_config.json").exists():
        print("Services ready. Run this script with create to create the disposable site.")
        return
    if not owned_pid("web"):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 8028)) == 0:
                raise RuntimeError(
                    "Port 8028 belongs to another process; stop the previous test web server first."
                )
        subprocess.run(
            [
                str(BENCH / "env/bin/gunicorn"),
                "--daemon",
                "--bind",
                "127.0.0.1:8028",
                "--workers",
                "2",
                "--timeout",
                "90",
                "--pid",
                str(RUNTIME / "web.pid"),
                "--chdir",
                str(BENCH / "sites"),
                "--pythonpath",
                str(Path(__file__).parent),
                "--error-logfile",
                str(RUNTIME / "web.log"),
                "--access-logfile",
                str(RUNTIME / "access.log"),
                "dev_wsgi:application",
            ],
            check=True,
        )
    print("Disposable preview: http://localhost:8028/app/id-card-builder/national-id-inspired-demo")


def create():
    if (BENCH / "sites" / SITE).exists():
        raise RuntimeError("Test site already exists; create will not overwrite it.")
    import pymysql

    c = pymysql.connect(unix_socket=str(RUNTIME / "db.sock"), user="root")
    if c.cursor().execute("SHOW DATABASES LIKE %s", (DB,)):
        raise RuntimeError("Test database already exists; create will not overwrite it.")
    c.close()
    apps = BENCH / "sites/apps.txt"
    lines = apps.read_text().splitlines()
    if "id_card_designer" not in lines:
        apps.write_text("\n".join(lines + ["id_card_designer"]) + "\n")
    os.environ["FRAPPE_REDIS_CACHE"] = "redis://127.0.0.1:13328"
    os.environ["FRAPPE_REDIS_QUEUE"] = "redis://127.0.0.1:13328"
    from unittest.mock import patch

    from frappe.commands.site import new_site

    os.chdir(BENCH / "sites")
    with patch("getpass.getpass", return_value=""):
        new_site.callback(
            site=SITE,
            db_name=DB,
            db_type="mariadb",
            db_root_username="root",
            db_root_password="",
            db_socket=str(RUNTIME / "db.sock"),
            admin_password=secrets.token_urlsafe(32),
            db_password=secrets.token_urlsafe(32),
            mariadb_user_host_login_scope="localhost",
            install_app=["id_card_designer"],
        )
    config = BENCH / "sites" / SITE / "site_config.json"
    d = json.loads(config.read_text())
    d.update(
        redis_cache="redis://127.0.0.1:13328",
        redis_queue="redis://127.0.0.1:13328",
        allow_tests=True,
        developer_mode=1,
    )
    config.write_text(json.dumps(d, indent=2))
    print("Created only " + SITE + ". Run prepare_browser_test.py for its local login fixture.")


def stop():
    for kind in ("web", "redis", "db"):
        pid = owned_pid(kind)
        if pid:
            os.kill(pid, signal.SIGTERM)
    print("Sent shutdown only to this app’s owned test services. Test data retained.")


def status():
    for kind in ("db", "redis", "web"):
        print(kind, owned_pid(kind) or "stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "create", "stop", "status"))
    args = parser.parse_args()
    {"start": start, "create": create, "stop": stop, "status": status}[args.action]()
