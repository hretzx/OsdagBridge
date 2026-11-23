"""Pile cap: a block that covers every pile plus an edge distance."""
from __future__ import annotations

from ...sub_structure.solids import Bar, Box, Part


def build_pile_cap(name, pile_xy, z_top, p) -> Part:
    r, e = p.pile_dia / 2.0, p.pile_cap_edge
    xs = [x for x, _ in pile_xy]
    ys = [y for _, y in pile_xy]
    x0, x1 = min(xs) - r - e, max(xs) + r + e
    y0, y1 = min(ys) - r - e, max(ys) + r + e
    t = p.pile_cap_depth
    solid = Box(x0, y0, z_top - t, x1 - x0, y1 - y0, t)
    # Bottom mat: X bars in the lower layer, Y bars resting on them, so the
    # two layers touch but never pass through each other.
    c, db, s = p.cover, p.pile_cap_bar_dia, p.pile_cap_bar_spacing
    z_x = solid.z0 + c + db / 2.0
    z_y = z_x + db
    bars = []
    ny = max(2, int((solid.dy - 2 * c - db) // s) + 1)
    for i in range(ny):
        y = y0 + c + db / 2 + i * (solid.dy - 2 * c - db) / (ny - 1)
        bars.append(Bar(f"{name} bottom X bar {i+1}", [(x0 + c, y, z_x), (x1 - c, y, z_x)], db))
    nx = max(2, int((solid.dx - 2 * c - db) // s) + 1)
    for i in range(nx):
        x = x0 + c + db / 2 + i * (solid.dx - 2 * c - db) / (nx - 1)
        bars.append(Bar(f"{name} bottom Y bar {i+1}", [(x, y0 + c, z_y), (x, y1 - c, z_y)], db))
    return Part("PILE_CAP", name, solid, p.grade, c, bars,
                {"Length": solid.dx, "Width": solid.dy, "Depth": t})
