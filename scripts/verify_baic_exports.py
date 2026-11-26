"""Private 600-dpi export and matched-scale reference verification for BAIC proofs."""

import argparse
import json
from pathlib import Path

import pymupdf
import zxingcpp
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument("--demo", type=Path, required=True)
p.add_argument("--issued", type=Path, required=True)
p.add_argument("--blank", type=Path)
p.add_argument("--reference", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
root = a.output.resolve()
repo = Path(__file__).resolve().parents[1]
assert not root.is_relative_to(repo), "Supplied assets and personal evidence must stay private"
root.mkdir(parents=True, exist_ok=True)
root.chmod(0o700)
report = {"dpi": 600, "tolerance_mm": 0.01, "documents": {}, "baseline_deltas_mm": {}}
for kind, path, qr in [
    ("demo", a.demo, "BAIC|DEMO|BAIC-001248"),
    ("issued", a.issued, "BAIC-TEST-0001"),
] + ([("blank", a.blank, "BAIC|DEMO|BAIC-000000")] if a.blank else []):
    doc = pymupdf.open(path)
    assert len(doc) == 2
    dims = []
    fonts = set()
    texts = []
    for i, page in enumerate(doc):
        size = [page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72]
        assert abs(size[0] - 85.6) < 0.01 and abs(size[1] - 53.98) < 0.01
        dims.append(size)
        pix = page.get_pixmap(dpi=600, alpha=False)
        assert (pix.width, pix.height) == (2023, 1276)
        pix.save(root / f"{kind}-{['front', 'back'][i]}.png")
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        assert all(abs(v - t) <= 1 for v, t in zip(image.getpixel((1000, 0)), (176, 148, 85)))
        assert all(abs(v - t) <= 1 for v, t in zip(image.getpixel((1000, 1274)), (21, 76, 72)))
        if i == 1:
            decoded = zxingcpp.read_barcode(image)
            assert decoded is not None and decoded.text == qr
        texts.append(page.get_text())
        for f in page.get_fonts():
            assert doc.extract_font(f[0])[3], "Missing embedded font data"
            fonts.add(f[3])
    text = "\n".join(texts)
    assert "BAIC KINGDOM CHAPEL" in text and "VISION PARTNERSHIP CARD" in text
    assert "የራዕይ ተካፋይ" in text
    assert (
        "For BAIC Kingdom Chapel vision partnership identification only. Non-transferable." in text
    )
    assert "Not a government-issued ID. If found, return to the chapel office." in text
    if kind == "demo":
        for token in [
            "DAWIT SAMUEL TESFAYE",
            "Bole Chapel",
            "12 / 02 / 2018 E.C.",
            "Media & Communications",
            "BAIC-001248",
            "Bole Subcity, Woreda 03",
            "Addis Ababa, Ethiopia",
            "+251 912 480 736",
            "dawit.samuel@example.com",
            "Bole, Addis Ababa / office@example.com",
            "SAMPLE",
            "DEMO - NOT VALID",
            "DEMO QR",
        ]:
            assert token in text, token
    if kind == "issued":
        for token in ["SAMPLE", "DEMO", "None", "null", "Member", "Parish", "[Chapel"]:
            assert token not in text, token
        assert "SYNTHETIC BAIC PARTNER" in text
        assert (
            "baic-workflow@org.example.invalid" in text and "chapel-office@example.invalid" in text
        )
    if kind == "blank":
        assert "DESIGN SAMPLE" in text and "[Chapel name]" in text
    report["documents"][kind] = dict(
        pages=2, dimensions_mm=dims, fonts=sorted(fonts), qr_payload=qr
    )
reference = pymupdf.open(a.reference)
proof = pymupdf.open(a.demo)
for i in range(2):
    left = reference[i].get_pixmap(dpi=600, alpha=False)
    right = proof[i].get_pixmap(dpi=600, alpha=False)
    panel = Image.new("RGB", (left.width + right.width, max(left.height, right.height)), "white")
    panel.paste(Image.frombytes("RGB", (left.width, left.height), left.samples), (0, 0))
    panel.paste(Image.frombytes("RGB", (right.width, right.height), right.samples), (left.width, 0))
    panel.save(root / f"comparison-{i + 1}.png")

    def baselines(page):
        return {
            span["text"]: span["origin"]
            for b in page.get_text("dict")["blocks"]
            if b["type"] == 0
            for line in b["lines"]
            for span in line["spans"]
        }

    old, new = baselines(reference[i]), baselines(proof[i])
    report["baseline_deltas_mm"][str(i + 1)] = {
        t: [round((new[t][j] - old[t][j]) * 25.4 / 72, 4) for j in (0, 1)]
        for t in [
            "BAIC KINGDOM CHAPEL",
            "VISION PARTNERSHIP CARD",
            "FULL NAME",
            "CHAPEL",
            "CHAPEL ROLE",
            "DISCLAIMER",
            "CHAPEL OFFICE",
        ]
        if t in old and t in new
    }
(root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(
    "PASS: private exports, two trim pages, embedded fonts, exact demo/live wording, QR decoding, edge-to-edge colors and matched-scale comparisons."
)
