"""Circular pier column with longitudinal bars and hoops."""
from __future__ import annotations

import math

from ..solids import Bar, Cylinder, Part, circle_points


def build_pier(name, x_centre, y_centre, z_bottom, z_top, p) -> Part:
    r = p.pier_diameter / 2.0
    h = z_top - z_bottom
    solid = Cylinder(x_centre, y_centre, z_bottom, r, h)
    return Part("PIER", name, solid, p.grade, p.rebar_cover,
                column_cage(name, x_centre, y_centre, z_bottom, z_top, r, p),
                {"Diameter": p.pier_diameter, "Height": h})


def column_cage(name, cx, cy, z_bottom, z_top, r, p):
    """Longitudinal bars on a circle inside hoops; shared by piers and piles."""
    c, dm, dt = p.rebar_cover, p.rebar_main_diameter, p.rebar_transverse_diameter
    r_main = r - c - dt - dm / 2            # bar centres sit inside the hoops
    n_main = max(6, int(2 * math.pi * r_main // p.rebar_spacing_longitudinal))
    bars = []
    z0, z1 = z_bottom + c, z_top - c
    for k in range(n_main):
        a = 2 * math.pi * k / n_main
        x, y = cx + r_main * math.cos(a), cy + r_main * math.sin(a)
        bars.append(Bar(f"{name} main bar {k+1}", [(x, y, z0), (x, y, z1)], dm))
    r_hoop = r - c - dt / 2
    n_hoops = max(2, int((z1 - z0 - dt) // p.rebar_spacing_transverse) + 1)
    for k in range(n_hoops):
        z = z0 + dt / 2 + k * (z1 - z0 - dt) / (n_hoops - 1)
        bars.append(Bar(f"{name} hoop {k+1}", circle_points(cx, cy, z, r_hoop, 32, gap=2 * dt),
                        dt, "LIGATURE"))
    return bars
