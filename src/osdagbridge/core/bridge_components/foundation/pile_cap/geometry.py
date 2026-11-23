"""Pile cap: rectangular block with a top and a bottom mat of bars."""
from __future__ import annotations

from ...sub_structure.solids import Bar, Box, Part


def build_pile_cap(name, x_centre, y_centre, z_top, p) -> Part:
    w, ln, t = p.pile_cap_width, p.pile_cap_length, p.pile_cap_depth   # X, Y, Z
    solid = Box(x_centre - w / 2, y_centre - ln / 2, z_top - t, w, ln, t)
    c, dm, s = p.rebar_cover, p.rebar_main_diameter, p.rebar_spacing_longitudinal
    x0, x1, y0, y1 = solid.x0, solid.x0 + w, solid.y0, solid.y0 + ln
    bars = []
    # Each mat has two layers that rest on each other: X bars, then Y bars.
    mats = (("bottom", solid.z0 + c + dm / 2, +1), ("top", z_top - c - dm / 2, -1))
    for mat, z_outer, inward in mats:
        z_inner = z_outer + inward * dm
        ny = max(2, int((ln - 2 * c - dm) // s) + 1)
        for i in range(ny):
            y = y0 + c + dm / 2 + i * (ln - 2 * c - dm) / (ny - 1)
            bars.append(Bar(f"{name} {mat} X bar {i+1}",
                            [(x0 + c, y, z_outer), (x1 - c, y, z_outer)], dm))
        nx = max(2, int((w - 2 * c - dm) // s) + 1)
        for i in range(nx):
            x = x0 + c + dm / 2 + i * (w - 2 * c - dm) / (nx - 1)
            bars.append(Bar(f"{name} {mat} Y bar {i+1}",
                            [(x, y0 + c, z_inner), (x, y1 - c, z_inner)], dm))
    return Part("PILE_CAP", name, solid, p.grade, c, bars,
                {"Length": ln, "Width": w, "Depth": t})
