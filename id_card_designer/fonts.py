"""Local licensed font registry shared by PDF generation and Desk CSS."""

import base64
from functools import lru_cache
from pathlib import Path

FONTS = [
    ("FreeSerif", "FreeSerif.ttf", 400),
    ("Open Sans", "OpenSans-Regular.ttf", 400),
    ("Open Sans", "OpenSans-Semibold.ttf", 600),
    ("Open Sans", "OpenSans-Bold.ttf", 700),
    ("Noto Sans Ethiopic", "NotoSansEthiopic-Regular.ttf", 400),
]


@lru_cache(maxsize=1)
def embedded_css():
    root = Path(__file__).parent / "public/fonts"
    return "".join(
        '@font-face{font-family:"'
        + family
        + '";font-weight:'
        + str(weight)
        + ";src:url(data:font/ttf;base64,"
        + base64.b64encode((root / name).read_bytes()).decode()
        + ")}"
        for family, name, weight in FONTS
    )
