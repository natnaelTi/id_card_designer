import json
import secrets

import frappe

from id_card_designer.compat import list_limit
from id_card_designer.rendering import FIELDS, pdf, snapshot, thumbnail
from id_card_designer.security import audience, audience_allowed, can, require, schema, user_data

DEMO = dict(
    full_name="Selam Example",
    first_name="Selam",
    last_name="Example",
    email="selam@example.invalid",
    phone="+000 000 000",
    mobile_no="",
    user_image="",
    location="Learning Centre",
    language="አማርኛ",
    profile_local_name="ሰላም ምሳሌ",
    profile_department="Learning & Research",
    profile_role_title="Member",
    profile_card_number="DEMO-0001",
    profile_issue_date="2026-01-01",
    profile_expiry_date="2027-01-01",
)


def template(name, live=False):
    doc = frappe.get_doc("ID Card Template", name)
    doc.check_permission("read")
    audience(doc)
    if live and (not doc.enabled or doc.status != "Published" or not doc.published_snapshot):
        frappe.throw("This template is unavailable. Choose an active published template.")
    return doc


def lock():
    # Serialize publication and default changes across templates; row exists after install.
    frappe.db.sql("SELECT name FROM `tabDocType` WHERE name=%s FOR UPDATE", ("ID Card Settings",))


@frappe.whitelist()
def capabilities(user=None):
    result = {cap: can(cap) for cap in ("design", "manage", "print")}
    if user and result["print"]:
        if not frappe.db.exists("User", user):
            result["print"] = False
        else:
            source = frappe.get_doc("User", user)
            result["print"] = bool(source.has_permission("read") and source.has_permission("print"))
    return result


@frappe.whitelist()
def list_usable_templates():
    require("print")
    result = []
    for name in frappe.get_list(
        "ID Card Template",
        filters={"enabled": 1, "status": "Published"},
        pluck="name",
        **list_limit(200),
    ):
        doc = frappe.get_doc("ID Card Template", name)
        if not audience_allowed(doc) or not doc.published_snapshot:
            continue
        doc.check_permission("read")
        s = json.loads(doc.published_snapshot)
        result.append(
            dict(
                name=doc.name,
                title=doc.title,
                is_default=doc.is_default,
                width_mm=s["width_mm"],
                height_mm=s["height_mm"],
                revision=doc.revision,
                thumbnail=thumbnail(s),
            )
        )
    return sorted(result, key=lambda d: not d["is_default"])


@frappe.whitelist()
def get_template_for_builder(name):
    require("design")
    doc = template(name)
    return {
        "draft_unpublished": bool(
            doc.published_snapshot and snapshot(doc) != json.loads(doc.published_snapshot)
        ),
        **{f: doc.get(f) for f in FIELDS},
        **{
            f: doc.get(f)
            for f in (
                "name",
                "title",
                "description",
                "status",
                "builtin",
                "revision",
                "modified",
                "enabled",
                "allowed_roles",
            )
        },
    }


get_template = get_template_for_builder


@frappe.whitelist(methods=["POST"])
def save_draft(payload):
    require("design")
    p = frappe.parse_json(payload)
    if not isinstance(p, dict):
        frappe.throw("Draft must be a JSON object.")
    if p.get("name"):
        # Lock before reading the optimistic version: two HTTP editors cannot both pass a stale check.
        frappe.db.sql(
            "SELECT name FROM `tabID Card Template` WHERE name=%s FOR UPDATE", (p["name"],)
        )
        doc = template(p["name"])
        doc.check_permission("write")
        if str(doc.modified) != str(p.get("modified")):
            frappe.throw("Template changed. Reload before saving.", frappe.TimestampMismatchError)
    else:
        doc = frappe.new_doc("ID Card Template")
        doc.check_permission("create")
    for k in FIELDS + ("title", "description", "enabled"):
        if k in p:
            doc.set(k, p[k])
    doc.save()
    return get_template_for_builder(doc.name)


@frappe.whitelist(methods=["POST"])
def publish_template(name, modified=None):
    require("manage")
    lock()
    frappe.db.sql("SELECT name FROM `tabID Card Template` WHERE name=%s FOR UPDATE", (name,))
    doc = template(name)
    doc.check_permission("write")
    if modified and str(doc.modified) != str(modified):
        frappe.throw(
            "Draft changed before publication; compare again.", frappe.TimestampMismatchError
        )
    if doc.builtin:
        frappe.throw("Duplicate the protected sample first.")
    s = snapshot(doc)
    from id_card_designer.rendering import side_html

    for side in ("front", "back"):
        side_html(s, side, DEMO)
    checked_pdf(s, DEMO, render=False)
    revisions = json.loads(doc.revisions or "[]")
    if doc.published_snapshot:
        revisions.append(dict(revision=doc.revision, snapshot=json.loads(doc.published_snapshot)))
    frappe.flags.id_card_publishing = True
    doc.update(
        dict(
            published_snapshot=json.dumps(s),
            revisions=json.dumps(revisions[-30:]),
            revision=(doc.revision or 0) + 1,
            status="Published",
        )
    )
    try:
        doc.save()
    finally:
        frappe.flags.id_card_publishing = False
    return get_template_for_builder(name)


@frappe.whitelist(methods=["POST"])
def duplicate_template(name):
    require("design")
    source = template(name)
    doc = frappe.new_doc("ID Card Template")
    for k in FIELDS:
        doc.set(k, source.get(k))
    doc.title = source.title + " (copy)"
    doc.enabled = 1
    doc.save()
    return get_template_for_builder(doc.name)


@frappe.whitelist(methods=["POST"])
def set_default_template(name):
    require("manage")
    lock()
    frappe.db.sql("SELECT name FROM `tabID Card Template` WHERE name=%s FOR UPDATE", (name,))
    doc = template(name, True)
    doc.check_permission("write")
    # Authority checked above. Direct DB update avoids editing protected demo content.
    frappe.db.sql("UPDATE `tabID Card Template` SET is_default=0 WHERE is_default=1")
    frappe.db.set_value("ID Card Template", name, "is_default", 1)
    settings = frappe.get_single("ID Card Settings")
    settings.default_template = name
    frappe.flags.id_card_default_update = True
    try:
        settings.save()
    finally:
        frappe.flags.id_card_default_update = False
    return name


@frappe.whitelist()
def get_field_schema():
    require("design")
    return schema()


@frappe.whitelist()
def get_preview_data(user=None):
    require("design")
    return user_data(user) if user else DEMO


@frappe.whitelist()
def list_revisions(name):
    require("design")
    return json.loads(template(name).revisions or "[]")


@frappe.whitelist(methods=["POST"])
def restore_revision(name, revision):
    require("manage")
    lock()
    frappe.db.sql("SELECT name FROM `tabID Card Template` WHERE name=%s FOR UPDATE", (name,))
    doc = template(name)
    doc.check_permission("write")
    match = next(
        (r for r in json.loads(doc.revisions or "[]") if r["revision"] == int(revision)), None
    )
    if not match:
        frappe.throw("Revision no longer available.")
    doc.update(match["snapshot"])
    doc.save()
    return get_template_for_builder(name)


@frappe.whitelist(methods=["POST"])
def prepare_pdf(name, user=None, preview=0):
    preview = bool(int(preview))
    require("design" if preview else "print")
    doc = template(name, not preview)
    if user:
        user_data(user, not preview)
    elif not preview:
        frappe.throw("Choose a saved User.")
    token = secrets.token_urlsafe(32)
    frappe.cache().set_value(
        "id-card:" + token,
        dict(
            owner=frappe.session.user,
            owner_session=frappe.session.sid,
            name=name,
            user=user,
            preview=preview,
            snapshot=doc.published_snapshot if not preview else None,
            revision=doc.revision,
        ),
        expires_in_sec=60,
    )
    return dict(url="/api/method/id_card_designer.api.deliver_pdf", token=token)


def respond(raw):
    frappe.local.id_card_pdf = True
    frappe.local.response.update(
        type="pdf", filename="institutional-id.pdf", filecontent=raw, display_content_as="inline"
    )
    if hasattr(frappe.local, "response_headers"):
        frappe.local.response_headers.update(
            {
                "Cache-Control": "no-store, private",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            }
        )


@frappe.whitelist(methods=["POST"])
def deliver_pdf(token):
    entry = frappe.cache().get_value("id-card:" + token)
    if not entry or (
        entry["owner"] != frappe.session.user or entry.get("owner_session") != frappe.session.sid
    ):
        frappe.throw("PDF link expired. Open the print dialog again.", frappe.PermissionError)
    if entry["preview"]:
        return render_preview_pdf(entry["name"], entry["user"])
    return _print_user_id(entry["name"], entry["user"], entry)


@frappe.whitelist(methods=["POST"])
def render_preview_pdf(name, user=None):
    require("design")
    doc = template(name)
    data = user_data(user) if user else DEMO
    respond(checked_pdf(snapshot(doc), data))


@frappe.whitelist(methods=["POST"])
def print_user_id(name, user):
    return _print_user_id(name, user)


def _print_user_id(name, user, prepared=None):
    require("print")
    doc = template(name, True)
    data = user_data(user, True)
    raw = checked_pdf(
        json.loads(prepared["snapshot"] if prepared else doc.published_snapshot), data
    )
    # Internal append-only audit event; no create permission granted to callers.
    log = frappe.get_doc(
        dict(
            doctype="ID Card Print Log",
            printed_by=frappe.session.user,
            source_user=user,
            template=name,
            revision=prepared["revision"] if prepared else doc.revision,
            result="Generated",
        )
    )
    log.db_insert()
    respond(raw)


def secure_pdf_headers(response, request=None):
    if getattr(frappe.local, "id_card_pdf", False):
        response.headers.update(
            {
                "Cache-Control": "no-store, private, max-age=0",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "frame-ancestors 'self'",
                "Content-Disposition": 'inline; filename="institutional-id.pdf"',
            }
        )


@frappe.whitelist()
def preflight_template(name, user=None):
    require("design")
    from id_card_designer.rendering import preflight

    return preflight(snapshot(template(name)), user_data(user) if user else DEMO)


@frappe.whitelist()
def get_builder_defaults():
    require("design")
    settings = frappe.get_single("ID Card Settings")
    return dict(
        width_mm=settings.default_width_mm or 85.6,
        height_mm=settings.default_height_mm or 53.98,
        bleed_mm=settings.default_bleed_mm or 0,
    )


@frappe.whitelist()
def list_assets(name):
    require("design")
    template(name)
    files = frappe.get_list(
        "File",
        filters={
            "attached_to_doctype": "ID Card Template",
            "attached_to_name": name,
            "is_folder": 0,
        },
        fields=["name", "file_name", "file_url"],
        **list_limit(50),
    )
    return [
        f for f in files if (f.file_url or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]


def checked_pdf(s, data, render=True):
    from id_card_designer.preflight import inspect
    from id_card_designer.rendering import render_pages

    pages = render_pages(s, data)
    report = inspect(s, data, pages)
    if (s.get("block_severe") and report["errors"]) or any(
        e["code"] in ("qr_geometry", "qr_opacity", "pagination") for e in report["errors"]
    ):
        frappe.throw(
            "Preflight blocked: "
            + "; ".join(e["code"] + " on " + e["side"] for e in report["errors"])
        )
    return pdf(s, data, pages) if render else report


@frappe.whitelist(methods=["POST"])
def revoke_pdf(token):
    entry = frappe.cache().get_value("id-card:" + token)
    if not entry:
        return
    if entry["owner"] != frappe.session.user:
        require("manage")
    frappe.cache().delete_value("id-card:" + token)


@frappe.whitelist()
def qr_preview(element, user=None):
    require("design")
    from id_card_designer.qr import make
    from id_card_designer.rendering import scene

    e = frappe.parse_json(element)
    if not isinstance(e, dict) or e.get("type") != "qr":
        frappe.throw("Choose a QR element.")
    scene([e], 200, 150, 10)
    try:
        return make(e, user_data(user) if user else DEMO)
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist(methods=["POST"])
def convert_to_code(name):
    require("design")
    doc = template(name)

    s = snapshot(doc)
    if s["editor_mode"] != "Visual":
        frappe.throw("Template is already in code mode.")
    # The generated source retains the exact visual scene in a safe, declarative element.
    # Explicit rendering contract preserves groups, bindings, conditions, QR and fallbacks.
    copy = duplicate_template(name)
    payload = {**copy, "editor_mode": "Code"}
    for side in ("front", "back"):
        import base64

        encoded = base64.b64encode((s.get(side + "_layout") or "[]").encode()).decode()
        payload[side + "_html"] = f'<ic-scene source="{encoded}"></ic-scene>'
    return save_draft(payload)


@frappe.whitelist(methods=["POST"])
def draft_key():
    """Per-login encryption key: not stored in the browser; other sessions cannot recover drafts."""
    require("design")
    import base64
    import hashlib

    scope = hashlib.sha256((frappe.session.user + str(frappe.session.sid)).encode()).hexdigest()
    cache = frappe.cache()
    key = cache.make_key("id-card-draft-key:" + scope)
    # Atomic initialization across parallel tabs; bypass request-local cached misses.
    cache.set(key, base64.b64encode(secrets.token_bytes(32)), ex=86400, nx=True)
    value = cache.get(key)
    return value.decode() if isinstance(value, bytes) else value


@frappe.whitelist()
def list_global_assets():
    require("design")
    from id_card_designer.rendering import asset

    result = []
    for row in frappe.get_list(
        "ID Card Asset", fields=["name", "title", "image"], **list_limit(100)
    ):
        if row.image:
            asset(row.image)
            result.append(row)
    return result


@frappe.whitelist(methods=["POST"])
def upload_asset():
    """Frappe FileUploader method hook; decode before v16 can strip JPEG orientation."""
    import re
    from pathlib import Path

    from id_card_designer.images import normalize, read_file

    doctype, name = frappe.form_dict.doctype, frappe.form_dict.docname
    if doctype not in ("ID Card Template", "ID Card Asset"):
        frappe.throw("Choose a saved template or managed global asset.")
    require("manage" if doctype == "ID Card Asset" else "design")
    parent = frappe.get_doc(doctype, name)
    parent.check_permission("write")
    if doctype == "ID Card Template":
        audience(parent)
        if parent.builtin:
            frappe.throw("Duplicate the protected sample before uploading assets.")
    raw = getattr(frappe.local, "uploaded_file", None)
    if raw is None:
        source = frappe.form_dict.library_file_name
        if not source:
            frappe.throw("Remote image URLs are disabled. Upload a local image.")
        raw = read_file(frappe.get_doc("File", source))
    content = normalize(raw)
    filename = (
        re.sub(
            r"[^\w.-]",
            "_",
            Path(getattr(frappe.local, "uploaded_filename", "image") or "image").stem,
        )
        + ".png"
    )
    file = frappe.get_doc(
        dict(
            doctype="File",
            file_name=filename,
            content=content,
            is_private=1,
            attached_to_doctype=doctype,
            attached_to_name=name,
        )
    )
    file.insert()
    return file
