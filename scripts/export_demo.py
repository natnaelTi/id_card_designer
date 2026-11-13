"""Export fictional demo artifacts without a database or live User data."""

import json
from pathlib import Path

from pypdf import PdfReader

from id_card_designer.api import DEMO
from id_card_designer.install import sample
from id_card_designer.rendering import FIELDS, pdf

out = Path(__file__).resolve().parents[1] / "artifacts"
out.mkdir(exist_ok=True)
s = {key: sample().get(key) for key in FIELDS}
file = out / "demo.pdf"
file.write_bytes(pdf(s, DEMO))
r = PdfReader(file)
assert len(r.pages) == 2
print(
    json.dumps(
        dict(
            file=str(file),
            pages=len(r.pages),
            dimensions_mm=[
                dict(
                    width=round(float(p.mediabox.width) * 25.4 / 72, 4),
                    height=round(float(p.mediabox.height) * 25.4 / 72, 4),
                )
                for p in r.pages
            ],
        ),
        indent=2,
    )
)
