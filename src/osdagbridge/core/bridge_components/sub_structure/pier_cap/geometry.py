"""Pier cap: trapezoidal section (wide on top, narrow below) across the deck.

The section lies in the X-Z plane, ``pier_cap_top_width`` wide at the top and
``pier_cap_bottom_width`` at the bottom, ``pier_cap_depth`` deep, and runs
along Y for the cap length (the deck width by default).
"""
from __future__ import annotations

from ..solids import Bar, Part, PrismY, fillet_polyline


def build_pier_cap(name, x_centre, y_centre, length, z_top, p) -> Part:
    tw, bw, d = p.pier_cap_top_width, p.pier_cap_bottom_width, p.pier_cap_depth
    xz = [(x_centre - tw / 2, z_top), (x_centre + tw / 2, z_top),
          (x_centre + bw / 2, z_top - d), (x_centre - bw / 2, z_top - d)]
    y0 = y_centre - length / 2
    solid = PrismY(y0, length, xz)

    c, dm, dt = p.rebar_cover, p.rebar_main_diameter, p.rebar_transverse_diameter
    s_l, s_t = p.rebar_spacing_longitudinal, p.rebar_spacing_transverse
    bars = []
    # Longitudinal bars run across the deck (Y), inside the stirrups. The
    # sides slope, so the outermost bar of each layer is placed from the side
    # face's position at that bar's height, offset along the face normal.
    off = c + dt + dm / 2
    k = (1 + ((tw - bw) / 2 / d) ** 2) ** 0.5     # normal offset -> horizontal shift
    y_a, y_b = y0 + c, y0 + length - c

    def face_half_width(z):
        return tw / 2 - (tw - bw) / 2 * (z_top - z) / d

    for layer, z in (("top", z_top - off), ("bottom", z_top - d + off)):
        half = face_half_width(z) - off * k
        n = max(2, int(2 * half // s_l) + 1)
        for i in range(n):
            x = x_centre - half + i * 2 * half / (n - 1)
            bars.append(Bar(f"{name} {layer} bar {i+1}", [(x, y_a, z), (x, y_b, z)], dm))
    # Trapezoidal stirrups every s_t along Y, at cover from every face. The
    # sloped faces are offset along their normal, so the cover there is exact.
    zt, zb = z_top - c - dt / 2, z_top - d + c + dt / 2
    slope = (tw - bw) / 2 / d                    # horizontal run per unit depth
    k = (1 + slope ** 2) ** 0.5                  # normal offset -> horizontal shift
    shift = (c + dt / 2) * k
    def x_at(z, sign):                           # sloped face, moved inwards
        frac = (z_top - z) / d
        half = tw / 2 - (tw - bw) / 2 * frac
        return x_centre + sign * (half - shift)
    r_bend = (dt + dm) / 2
    n_st = max(2, int((length - 2 * c - dt) // s_t) + 1)
    for i in range(n_st):
        y = y0 + c + dt / 2 + i * (length - 2 * c - dt) / (n_st - 1)
        x_mid = x_centre
        pts = [(x_mid + dt, y, zt), (x_at(zt, 1), y, zt), (x_at(zb, 1), y, zb),
               (x_at(zb, -1), y, zb), (x_at(zt, -1), y, zt), (x_mid - dt, y, zt)]
        bars.append(Bar(f"{name} stirrup {i+1}", fillet_polyline(pts, r_bend), dt,
                        "LIGATURE", bend_radius=r_bend))
    return Part("PIER_CAP", name, solid, p.grade, c, bars,
                {"TopWidth": tw, "BottomWidth": bw, "Depth": d, "Length": length})
