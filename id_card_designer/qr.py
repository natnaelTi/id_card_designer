"""Organizational QR only: no network fetches, unrestricted fields or issuer claims."""

import base64
import io
import re
from urllib.parse import urlsplit

import segno

ALLOWED_FIELDS = {"profile_card_number"}


def options(e):
    correction = e.get("qr_error", "M")
    if correction not in ("L", "M", "Q", "H"):
        raise ValueError("QR error correction must be L, M, Q or H.")
    quiet = e.get("qr_quiet", 4)
    if not isinstance(quiet, int) or not 4 <= quiet <= 12:
        raise ValueError("QR quiet zone must be 4–12 modules.")
    colors = [e.get("qr_dark", "#173b35"), e.get("qr_light", "#ffffff")]
    luminances = []
    for color in colors:
        if not isinstance(color, str) or not re.fullmatch("#[0-9a-fA-F]{6}", color):
            raise ValueError("Use six-digit QR colors.")
        rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        luminances.append(sum(a * b for a, b in zip(rgb, [0.2126, 0.7152, 0.0722])))
    if luminances[0] >= luminances[1] or (luminances[1] + 0.05) / (luminances[0] + 0.05) < 7:
        raise ValueError(
            "QR requires dark modules on a light background with at least 7:1 contrast."
        )
    return correction, quiet, colors


def payload(e, data):
    field = e.get("field")
    if field and field not in ALLOWED_FIELDS:
        raise ValueError(
            "QR bindings are limited to the institutional card reference; no personal fields."
        )
    value = (
        str(data.get(field) or e.get("fallback") or e.get("text") or "")
        if field
        else str(e.get("text") or "")
    )
    if not value or len(value.encode()) > 512 or any(ord(c) < 32 for c in value):
        raise ValueError("QR payload must contain 1–512 bytes of printable organizational text.")
    if re.search(r"(fayda|national.?id|\bFIN\b|\bFCN\b)", value, re.I):
        raise ValueError("Government credential/verification payloads are not supported.")
    if ":" in value or value.startswith(("/", "\\")):
        u = urlsplit(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.fragment:
            raise ValueError("QR URLs must be explicit HTTPS organizational application URLs.")
        import frappe

        origin = frappe.get_single("ID Card Settings").qr_application_origin or ""
        o = urlsplit(origin)
        if (u.scheme, u.netloc) != (o.scheme, o.netloc) or u.path.startswith("//"):
            raise ValueError(
                "QR URL origin must match the application origin approved by a manager."
            )
        if u.query:
            raise ValueError("Do not put personal data or verification tokens in QR query strings.")
    return value


def make(e, data, metadata=False):
    if abs(e["width"] - e["height"]) > 0.02:
        raise ValueError("QR elements must be square.")
    correction, quiet, colors = options(e)
    code = segno.make_qr(payload(e, data), error=correction, boost_error=False)
    modules = code.symbol_size(border=quiet)[0]
    if min(e["width"], e["height"]) < modules * 0.25:
        raise ValueError(
            "QR modules must be at least 0.25 mm including the quiet zone. Increase its size."
        )
    stream = io.BytesIO()
    code.save(
        stream, kind="svg", border=quiet, dark=colors[0], light=colors[1], xmldecl=False, svgid=None
    )
    uri = "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode()
    return (uri, modules) if metadata else uri
