"""Pier cap: flat on top, sized to carry every bearing.

Over a single column it is a hammerhead (deep over the column, tapering to the
tips). Over several columns it keeps the full depth between the outer columns
and tapers only beyond them.
"""
from __future__ import annotations

from ..solids import Bar, Part, PrismX


def build_pier_cap(name, x_centre, bearing_ys, column_ys, z_top, p) -> Part:
    y_min = min(bearing_ys) - p.cap_edge
    y_max = max(bearing_ys) + p.cap_edge
    half_col = p.pier_breadth / 2.0
    d_mid, d_tip = p.cap_depth_mid, p.cap_depth_tip
    y_lo, y_hi = min(column_ys) - half_col, max(column_ys) + half_col
    yz = [(y_min, z_top), (y_max, z_top), (y_max, z_top - d_tip),
          (y_hi, z_top - d_mid), (y_lo, z_top - d_mid), (y_min, z_top - d_tip)]
    solid = PrismX(x_centre - p.cap_width / 2.0, p.cap_width, yz)

    # Top bars running across the bridge, spaced along the span.
    bars, c, db = [], p.cover, p.cap_bar_dia
    z_bar = z_top - c - db / 2.0
    usable = p.cap_width - 2 * c - db
    n = max(2, int(usable // p.cap_bar_spacing) + 1)
    for i in range(n):
        x = solid.x0 + c + db / 2.0 + i * usable / (n - 1)
        bars.append(Bar(f"{name} top bar {i+1}",
                        [(x, y_min + c, z_bar), (x, y_max - c, z_bar)], db))
    return Part("PIER_CAP", name, solid, p.grade, c, bars,
                {"Width": p.cap_width, "Length": y_max - y_min,
                 "DepthAtPier": d_mid, "DepthAtTip": d_tip})
