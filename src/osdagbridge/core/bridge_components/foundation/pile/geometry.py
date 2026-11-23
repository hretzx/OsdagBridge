"""Bored piles in a 2 x 2 group, each with a cage of bars and hoops."""
from __future__ import annotations

import math

from ...sub_structure.pier.geometry import column_cage
from ...sub_structure.solids import Cylinder, Part


def pile_positions(x_centre, y_centre, p) -> list[tuple[float, float]]:
    """Centres of a square-ish grid of ``n_piles_per_cap`` at ``pile_spacing``."""
    cols = max(1, round(math.sqrt(p.n_piles_per_cap)))
    rows = math.ceil(p.n_piles_per_cap / cols)
    s = p.pile_spacing
    pts = []
    for i in range(rows):
        for j in range(cols):
            if len(pts) < p.n_piles_per_cap:
                pts.append((x_centre + (i - (rows - 1) / 2) * s,
                            y_centre + (j - (cols - 1) / 2) * s))
    return pts


def build_pile(name, cx, cy, z_top, p) -> Part:
    r = p.pile_diameter / 2.0
    solid = Cylinder(cx, cy, z_top - p.pile_length, r, p.pile_length)
    bars = column_cage(name, cx, cy, solid.z0, z_top, r, p)
    return Part("PILE", name, solid, p.grade, p.rebar_cover, bars,
                {"Diameter": p.pile_diameter, "Length": p.pile_length})
