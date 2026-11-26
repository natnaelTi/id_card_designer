"""Extract original PDF assets and a private import bundle; never flatten a finished card.

Run with PyMuPDF installed (requirements-dev.txt). Output must be outside the repo.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

parser = argparse.ArgumentParser()
parser.add_argument("template_pdf", type=Path)
parser.add_argument("demo_pdf", type=Path)
parser.add_argument("output", type=Path)
a = parser.parse_args()
root = a.output.expanduser().resolve()
repo = Path(__file__).resolve().parents[1]
if root.is_relative_to(repo):
    raise SystemExit("Private asset bundles must be outside the public repository.")
root.mkdir(parents=True, exist_ok=True)
root.chmod(0o700)
docs = [pymupdf.open(a.template_pdf.expanduser()), pymupdf.open(a.demo_pdf.expanduser())]
assets = {}
report = {"pages": [], "sources": {}, "assets": {}}
for src, doc in zip([a.template_pdf, a.demo_pdf], docs):
    if len(doc) != 2:
        raise SystemExit("Each approved PDF must have front and back pages.")
    report["sources"][src.name] = hashlib.sha256(src.expanduser().read_bytes()).hexdigest()
    for i, page in enumerate(doc):
        report["pages"].append(
            dict(
                source=src.name,
                page=i + 1,
                size_mm=[page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72],
                fonts=page.get_fonts(),
                text=page.get_text(),
                colors=sorted(
                    {
                        s["color"]
                        for b in page.get_text("dict")["blocks"]
                        if b["type"] == 0
                        for line in b["lines"]
                        for s in line["spans"]
                    }
                ),
            )
        )
        for xref, smask, w, h, *_ in page.get_images(full=True):
            role = (
                "logo"
                if (w, h) == (640, 640)
                else "seal"
                if (w, h) == (1536, 1024)
                else "signature"
                if (w, h) == (1138, 441)
                else "background"
                if (w, h) == (1579, 996)
                else "demo_portrait"
                if src == a.demo_pdf and (w, h) == (1122, 1402)
                else None
            )
            if not role or role in assets:
                continue
            pix = pymupdf.Pixmap(doc, xref)
            if smask:
                pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, smask))
            name = role + ".png"
            pix.save(root / name)
            assets[role] = name
            report["assets"][role] = dict(
                xref=xref,
                soft_mask=smask,
                size=[w, h],
                sha256=hashlib.sha256((root / name).read_bytes()).hexdigest(),
            )
if set(assets) != {"logo", "seal", "signature", "background", "demo_portrait"}:
    raise SystemExit("Could not recover all original assets: " + str(set(assets)))
(root / "manifest.json").write_text(json.dumps(dict(version=1, assets=assets), indent=2))
(root / "reference-analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print("Extracted original, separate private assets:", ", ".join(assets))
