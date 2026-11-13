"""Decode and normalize only authorized local raster images, bounded before pixel allocation."""

import io
from pathlib import Path

import frappe
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024


def read_file(file):
    file.check_permission("read")
    root = Path(
        frappe.get_site_path("private/files" if file.is_private else "public/files")
    ).resolve()
    path = Path(file.get_full_path()).resolve()
    if not path.is_relative_to(root):
        frappe.throw("Image path escapes the site files directory.")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError:
        frappe.throw("Image file is missing or unreadable. Upload it again.")
    if len(raw) > MAX_BYTES:
        frappe.throw("Images may be at most 5 MB.")
    return raw


def normalize(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        frappe.throw("Upload a raster image under 5 MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 24000000:
            frappe.throw("Use PNG, JPEG or WebP under 24 megapixels.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGBA")
        out = io.BytesIO()
        image.save(out, format="PNG")
        if out.tell() > MAX_BYTES:
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format="PNG")
        return out.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        frappe.throw("Invalid or excessively large image content.")
