"""Bored piles in a rectangular group, each with a cage of longitudinal bars."""
from __future__ import annotations

import math

from ...sub_structure.solids import Bar, Cylinder, Part


def pile_positions(x_centre, y_centre, p) -> list[tuple[float, float]]:
    """Centres of a rows x cols group at ``p.pile_spacing`` both ways."""
    s = p.pile_spacing
    xs = [x_centre + (i - (p.pile_rows - 1) / 2) * s for i in range(p.pile_rows)]
    ys = [y_centre + (j - (p.pile_cols - 1) / 2) * s for j in range(p.pile_cols)]
    return [(x, y) for x in xs for y in ys]


def build_pile(name, cx, cy, z_top, p) -> Part:
    r = p.pile_dia / 2.0
    solid = Cylinder(cx, cy, z_top - p.pile_length, r, p.pile_length)
    c, db = p.cover, p.pile_bar_dia
    rb = r - c - db / 2.0                     # radius of the bar centres
    z0, z1 = solid.z0 + c, z_top - c
    bars = []
    for k in range(p.pile_bars):
        a = 2 * math.pi * k / p.pile_bars
        x, y = cx + rb * math.cos(a), cy + rb * math.sin(a)
        bars.append(Bar(f"{name} main bar {k+1}", [(x, y, z0), (x, y, z1)], db))
    return Part("PILE", name, solid, p.grade, c, bars,
                {"Diameter": p.pile_dia, "Length": p.pile_length})
