"""Assemble the substructure under each support line of the bridge.

A support line is the row of bearings at one end of the span. Under it we
place, top to bottom: a pier cap whose top meets the bearings and which runs
the full deck width, a circular pier, a pile cap and a 2 x 2 group of piles.
Members touch face to face and never overlap, which the IFC self-check
verifies.

The default dimensions are the ones given in the FOSSEE screening task
("Parametric 3D CAD Modeling of Bridge Substructure"); every one of them is a
field of ``SubstructureParams`` and can be changed.

All lengths are millimetres, in the global frame of the Osdag CAD model:
X along the span, Y across the deck, Z up.
"""
from __future__ import annotations

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
    """Default dimensions from the task document (mm)."""
    grade: str = "M35"
    rebar_grade: str = "Fe500"
    # Piers (circular columns)
    pier_diameter: float = 800.0
    pier_height: float = 3000.0
    # Pier cap (hammerhead / trapezoidal section)
    pier_cap_top_width: float = 3000.0       # along the span (X), at the top
    pier_cap_bottom_width: float = 1200.0    # along the span (X), at the bottom
    pier_cap_depth: float = 600.0
    pier_cap_length: float | None = None     # across the deck (Y); None = deck width
    # Pile cap (rectangular prism)
    pile_cap_length: float = 2200.0          # across the deck (Y)
    pile_cap_width: float = 1200.0           # along the span (X)
    pile_cap_depth: float = 600.0
    # Piles (circular, 2 x 2 grid)
    n_piles_per_cap: int = 4
    pile_diameter: float = 400.0
    pile_length: float = 5000.0
    pile_spacing: float = 600.0              # centre to centre
    # Reinforcement
    rebar_main_diameter: float = 16.0
    rebar_spacing_longitudinal: float = 150.0
    rebar_transverse_diameter: float = 8.0
    rebar_spacing_transverse: float = 200.0
    rebar_cover: float = 40.0


@dataclass
class SupportLine:
    name: str
    x: float                       # where the pier cap is centred along the span
    bearing_ys: list[float]
    bearing_z: float
    bearing_xs: list[float] = field(default_factory=list)  # each bearing's own x
    deck_centre_y: float = 0.0
    deck_width: float = 0.0
    parts: list[Part] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def build_support_line(name, x, bearing_ys, bearing_z, p=None,
                       deck_width=None, deck_centre_y=None) -> SupportLine:
    """Everything under one row of bearings.

    ``x`` is one longitudinal position, or a list with each bearing's own x (a
    skewed deck); the pier is centred on their average, and every bearing's
    real position is kept for the self-check. The pier cap runs the deck
    width (or ``p.pier_cap_length``), centred on the deck.
    """
    p = p or SubstructureParams()
    xs = list(x) if isinstance(x, (list, tuple)) else [x] * len(bearing_ys)
    x = sum(xs) / len(xs)
    yc = deck_centre_y if deck_centre_y is not None else (min(bearing_ys) + max(bearing_ys)) / 2
    width = deck_width or (max(bearing_ys) - min(bearing_ys) + 2 * p.pier_cap_top_width / 2)
    cap_length = p.pier_cap_length or width
    line = SupportLine(name, x, list(bearing_ys), bearing_z, xs, yc, width)

    cap = build_pier_cap(f"{name} pier cap", x, yc, cap_length, bearing_z, p)
    z_cap_soffit = bearing_z - p.pier_cap_depth
    z_pile_cap_top = z_cap_soffit - p.pier_height
    z_pile_top = z_pile_cap_top - p.pile_cap_depth
    pier = build_pier(f"{name} pier", x, yc, z_pile_cap_top, z_cap_soffit, p)
    xy = pile_positions(x, yc, p)
    pile_cap = build_pile_cap(f"{name} pile cap", x, yc, z_pile_cap_top, p)
    piles = [build_pile(f"{name} pile {i+1}", px, py, z_pile_top, p)
             for i, (px, py) in enumerate(xy)]
    line.parts = [cap, pier, pile_cap, *piles]
    line.issues = check_pier(pier, p) + check_pile_group(xy, p)
    return line


def bearing_lines(span, girder_d, girder_tf_b, bearing_ys, skew_offset=lambda y: 0.0):
    """Bearing positions at both ends of the span.

    Mirrors the support geometry of PlateGirderIFCExtractor._extract_supports:
    a support of height base_dim / 1.5 under the bottom flange, at w_supp
    from the left end and r_cyl from the right end.
    Returns [(name, [x of each bearing], [y...], z of the bearing underside)].
    """
    z_contact = -(girder_d / 2.0 + girder_tf_b)
    base_dim = min(0.10 * span, 0.75 * girder_d)
    h_supp = base_dim / 1.5
    w_supp = base_dim / 2.0
    r_cyl = h_supp / 2.0
    xs_left = [skew_offset(y) + w_supp for y in bearing_ys]
    xs_right = [skew_offset(y) + span - r_cyl for y in bearing_ys]
    z = z_contact - h_supp
    return [("A", xs_left, list(bearing_ys), z), ("B", xs_right, list(bearing_ys), z)]


def build_substructure(lines, p=None, deck_width=None, deck_centre_y=0.0) -> list[SupportLine]:
    """``lines``: [(name, x or [x...], [bearing y...], underside z), ...]."""
    p = p or SubstructureParams()
    return [build_support_line(n, x, ys, z, p, deck_width, deck_centre_y)
            for n, x, ys, z in lines]
