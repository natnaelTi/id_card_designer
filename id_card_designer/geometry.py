"""Millimetre affine transforms, shared contract for legacy leaves and nested groups."""

import math

IDENTITY = [1, 0, 0, 1, 0, 0]


def multiply(a, b):
    return [
        a[0] * b[0] + a[2] * b[1],
        a[1] * b[0] + a[3] * b[1],
        a[0] * b[2] + a[2] * b[3],
        a[1] * b[2] + a[3] * b[3],
        a[0] * b[4] + a[2] * b[5] + a[4],
        a[1] * b[4] + a[3] * b[5] + a[5],
    ]


def transform(e):
    w, h = e["width"], e["height"]
    angle = math.radians(float(e.get("rotation", 0)))
    c, s = math.cos(angle), math.sin(angle)
    rotate = [c, s, -s, c, (w - c * w + s * h) / 2, (h - s * w - c * h) / 2]
    return multiply([1, 0, 0, 1, e["x"], e["y"]], multiply(e.get("affine", IDENTITY), rotate))


def child_transform(e):
    return multiply(
        transform(e),
        [
            e["width"] / e.get("base_width", e["width"]),
            0,
            0,
            e["height"] / e.get("base_height", e["height"]),
            0,
            0,
        ],
    )


def point(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def bounds(e, m=None):
    m = m or transform(e)
    points = [
        point(m, x, y)
        for x, y in [(0, 0), (e["width"], 0), (e["width"], e["height"]), (0, e["height"])]
    ]
    return (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def walk(items, parent=None, prefix=""):
    parent = parent or IDENTITY
    for i, e in enumerate(items):
        path = f"{prefix}.{i}" if prefix else str(i)
        m = multiply(parent, transform(e))
        yield path, e, m
        if e["type"] == "group":
            yield from walk(e["children"], multiply(parent, child_transform(e)), path)


def css_matrix(m):
    return (
        "matrix("
        + ",".join(str(round(v * (96 / 25.4 if i > 3 else 1), 10)) for i, v in enumerate(m))
        + ")"
    )
