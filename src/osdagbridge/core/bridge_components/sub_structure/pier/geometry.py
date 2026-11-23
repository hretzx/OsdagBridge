"""Rectangular pier column with longitudinal bars and closed ties."""
from __future__ import annotations

from ..solids import Bar, Box, Part, fillet_polyline


def build_pier(name, x_centre, y_centre, z_bottom, z_top, p) -> Part:
    b, t = p.pier_breadth, p.pier_thickness      # b across the bridge (Y)
    solid = Box(x_centre - t / 2, y_centre - b / 2, z_bottom, t, b, z_top - z_bottom)
    c, db, dt = p.cover, p.pier_bar_dia, p.pier_tie_dia
    # Bar centres sit inside the ties: cover + tie + half a bar from the face.
    off = c + dt + db / 2.0
    xs = (solid.x0 + off, solid.x0 + t - off)
    ys_n = max(2, int((b - 2 * off) // p.pier_bar_spacing) + 1)
    xs_n = max(2, int((t - 2 * off) // p.pier_bar_spacing) + 1)
    ring = set()
    for i in range(ys_n):
        y = solid.y0 + off + i * (b - 2 * off) / (ys_n - 1)
        ring.add((round(xs[0], 3), round(y, 3)))
        ring.add((round(xs[1], 3), round(y, 3)))
    for i in range(xs_n):
        x = solid.x0 + off + i * (t - 2 * off) / (xs_n - 1)
        ring.add((round(x, 3), round(solid.y0 + off, 3)))
        ring.add((round(x, 3), round(solid.y0 + b - off, 3)))
    z0, z1 = z_bottom + c, z_top - c
    bars = [Bar(f"{name} main bar {k+1}", [(x, y, z0), (x, y, z1)], db)
            for k, (x, y) in enumerate(sorted(ring))]
    # Rectangular ties along the height. Each tie starts and ends near the
    # middle of one side, leaving a gap of two bar diameters, and its corners
    # are bent around the corner bars (bend radius = tie + bar radius).
    to = c + dt / 2.0
    x_lo, x_hi = solid.x0 + to, solid.x0 + t - to
    y_lo, y_hi = solid.y0 + to, solid.y0 + b - to
    x_mid = (x_lo + x_hi) / 2.0
    h = z_top - z_bottom
    n_ties = max(2, int((h - 2 * c - 2 * dt) // p.pier_tie_spacing) + 1)
    for k in range(n_ties):
        z = z_bottom + c + dt / 2 + k * (h - 2 * c - dt) / (n_ties - 1)
        pts = [(x_mid + dt, y_lo, z), (x_hi, y_lo, z), (x_hi, y_hi, z),
               (x_lo, y_hi, z), (x_lo, y_lo, z), (x_mid - dt, y_lo, z)]
        r_bend = (dt + db) / 2.0
        bars.append(Bar(f"{name} tie {k+1}", fillet_polyline(pts, r_bend), dt,
                        "LIGATURE", bend_radius=r_bend))
    return Part("PIER", name, solid, p.grade, c, bars,
                {"Breadth": b, "Thickness": t, "Height": h})
