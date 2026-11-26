"""Bounded text fitting using actual WeasyPrint line boxes, never character counts."""

from bs4 import BeautifulSoup
from weasyprint.formatting_structure.boxes import LineBox, TextBox

from id_card_designer.preflight import descendants


def render_fitted(source, fetch):
    from weasyprint import HTML

    if "data-ic-fit-min=" not in source:
        return HTML(string=source, url_fetcher=fetch).render()
    soup = BeautifulSoup(source, "html.parser")
    tags = {x["data-ic-path"]: x for x in soup.select("[data-ic-fit-min]")}
    states = {}
    for _ in range(12):
        doc = HTML(string=str(soup), url_fetcher=fetch).render()
        if not tags or len(doc.pages) != 1:
            return doc
        owners = {}
        for box in descendants(doc.pages[0]._page_box):
            el = getattr(box, "element", None)
            path = el.get("data-ic-path") if el is not None else None
            if path in tags and not isinstance(box, (LineBox, TextBox)):
                old = owners.get(path)
                if old is None or box.width * box.height > old.width * old.height:
                    owners[path] = box
        changed = False
        for path, tag in tags.items():
            owner = owners.get(path)
            if owner is None:
                continue
            lines = [x for x in descendants(owner) if isinstance(x, LineBox)]
            if not lines:
                continue
            width = max(x.width for x in lines)
            height = max(x.position_y + x.height for x in lines) - owner.content_box_y()
            fits = width <= owner.width + 0.15 and height <= owner.height + 0.15
            current = round(owner.style["font_size"] * 72 / 96, 4)
            if path not in states:
                if fits:
                    continue
                minimum = float(tag["data-ic-fit-min"])
                maximum = min(current, 24)
                values = sorted(
                    {
                        minimum,
                        *[
                            round(maximum - 0.25 * n, 4)
                            for n in range(81)
                            if maximum - 0.25 * n >= minimum
                        ],
                    }
                )
                states[path] = dict(values=values, low=0, high=len(values) - 1, best=minimum)
            state = states[path]
            values = state["values"]
            index = min(range(len(values)), key=lambda i: abs(values[i] - current))
            if fits:
                state["best"] = max(state["best"], current)
                state["low"] = index + 1
            else:
                state["high"] = index - 1
            if state["low"] <= state["high"]:
                size = values[(state["low"] + state["high"]) // 2]
            else:
                size = state["best"]
            if abs(size - current) > 0.01:
                tag["style"] += f";font-size:{size:.4f}pt"
                changed = True
        if not changed:
            return doc
    # Always return the layout corresponding to the final chosen source.
    return HTML(string=str(soup), url_fetcher=fetch).render()
