"""Assemble the substructure under each support line of the bridge.

A support line is the row of bearings at one end of a span. Under it we
place, top to bottom: a hammerhead pier cap whose top meets the bearings, a
pier column, a pile cap and a group of bored piles. Parts touch face to face
and never overlap, which the IFC self-check verifies.

All lengths are millimetres, in the same global frame as the Osdag CAD model
(X along the span, Y across it, Z up).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..foundation.pile.checks import check_pile_group
from ..foundation.pile.geometry import build_pile, pile_positions
from ..foundation.pile_cap.geometry import build_pile_cap
from .pier.checks import check_pier
from .pier.geometry import build_pier
from .pier_cap.geometry import build_pier_cap
from .solids import Part


@dataclass
class SubstructureParams:
    """Default proportions for a short-span highway bridge pier (editable)."""
    grade: str = "M35"
    rebar_grade: str = "Fe500"
    cover: float = 50.0
    # pier cap
    cap_width: float = 1800.0            # along the span
    cap_edge: float = 600.0              # beyond the outer bearings
    cap_depth_mid: float = 1500.0
    cap_depth_tip: float = 800.0
    cap_bar_dia: float = 25.0
    cap_bar_spacing: float = 150.0
    # pier column
    pier_height: float = 6000.0          # cap soffit to pile cap top
    max_column_spacing: float = 7000.0   # wider decks get more columns
    pier_breadth: float = 2500.0         # across the bridge
    pier_thickness: float = 1200.0       # along the span
    pier_bar_dia: float = 25.0
    pier_bar_spacing: float = 150.0
    pier_tie_dia: float = 10.0
    pier_tie_spacing: float = 300.0
    # pile cap and piles
    pile_cap_depth: float = 1500.0
    pile_cap_edge: float = 150.0         # pile face to cap edge
    pile_cap_bar_dia: float = 25.0
    pile_cap_bar_spacing: float = 150.0
    pile_rows: int = 2                   # along the span
    pile_cols: int = 2                   # across the bridge
    pile_dia: float = 1000.0
    pile_spacing: float = 3000.0         # 3 x diameter
    pile_length: float = 15000.0
    pile_bars: int = 12
    pile_bar_dia: float = 20.0


@dataclass
class SupportLine:
    name: str
    x: float                       # where the pier cap is centred along the span
    bearing_ys: list[float]
    bearing_z: float
    bearing_xs: list[float] = field(default_factory=list)  # each bearing's own x
    parts: list[Part] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def column_positions(bearing_ys, p) -> list[float]:
    """Y of each pier column: one under a narrow deck, more under a wide one."""
    y_lo, y_hi = min(bearing_ys), max(bearing_ys)
    width = y_hi - y_lo
    n = max(1, math.ceil(width / p.max_column_spacing))
    if n == 1:
        return [(y_lo + y_hi) / 2.0]
    step = width / n
    return [y_lo + step * (i + 0.5) for i in range(n)]


def build_support_line(name, x, bearing_ys, bearing_z, p=None) -> SupportLine:
    """Everything under one row of bearings.

    ``x`` is either one longitudinal position, or a list with each bearing's
    own x (a skewed deck); the cap is centred on their average and laid
    square, and every bearing's real position is kept for the self-check.
    """
    p = p or SubstructureParams()
    xs = list(x) if isinstance(x, (list, tuple)) else [x] * len(bearing_ys)
    x = sum(xs) / len(xs)
    line = SupportLine(name, x, list(bearing_ys), bearing_z, xs)
    cols = column_positions(bearing_ys, p)

    cap = build_pier_cap(f"{name} pier cap", x, bearing_ys, cols, bearing_z, p)
    z_cap_soffit = bearing_z - p.cap_depth_mid
    z_pile_cap_top = z_cap_soffit - p.pier_height
    z_pile_top = z_pile_cap_top - p.pile_cap_depth
    line.parts.append(cap)

    for k, yc in enumerate(cols, start=1):
        tag = f"{name}{k}" if len(cols) > 1 else name
        pier = build_pier(f"{tag} pier", x, yc, z_pile_cap_top, z_cap_soffit, p)
        xy = pile_positions(x, yc, p)
        pile_cap = build_pile_cap(f"{tag} pile cap", xy, z_pile_cap_top, p)
        piles = [build_pile(f"{tag} pile {i+1}", px, py, z_pile_top, p)
                 for i, (px, py) in enumerate(xy)]
        line.parts += [pier, pile_cap, *piles]
        line.issues += check_pier(pier, p) + check_pile_group(xy, p)
    return line


def build_substructure(bearing_lines, p=None) -> list[SupportLine]:
    """``bearing_lines``: [(name, x or [x...], [bearing y...], underside z), ...]."""
    p = p or SubstructureParams()
    return [build_support_line(n, x, ys, z, p) for n, x, ys, z in bearing_lines]
