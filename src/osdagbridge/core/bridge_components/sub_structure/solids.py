"""Plain solids and bars used by the substructure model (all lengths in mm).

These are deliberately simple, library-free descriptions. The same object is
turned into an IFC solid (``ifc_export_bridge.substructure_ifc``) and into an
OpenCASCADE shape (``sub_structure.occ_builder``), and its exact volume is
known from a formula, which the IFC self-check compares against.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Box:
    """Axis-aligned box from its minimum corner."""
    x0: float
    y0: float
    z0: float
    dx: float
    dy: float
    dz: float

    @property
    def volume(self) -> float:
        return self.dx * self.dy * self.dz

    def bounds(self):
        return ((self.x0, self.y0, self.z0),
                (self.x0 + self.dx, self.y0 + self.dy, self.z0 + self.dz))


@dataclass
class Cylinder:
    """Vertical cylinder: centre of the bottom face, radius, height."""
    cx: float
    cy: float
    z0: float
    r: float
    h: float

    @property
    def volume(self) -> float:
        return math.pi * self.r ** 2 * self.h

    def bounds(self):
        return ((self.cx - self.r, self.cy - self.r, self.z0),
                (self.cx + self.r, self.cy + self.r, self.z0 + self.h))


@dataclass
class PrismX:
    """A polygon in the Y-Z plane extruded along +X from x0 by length.

    Used for the hammerhead pier cap, whose elevation is a trapezoid.
    """
    x0: float
    length: float
    yz: list[tuple[float, float]]

    @property
    def area(self) -> float:
        pts = self.yz
        return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                       - pts[(i + 1) % len(pts)][0] * pts[i][1]
                       for i in range(len(pts)))) / 2.0

    @property
    def volume(self) -> float:
        return self.area * self.length

    def bounds(self):
        ys = [p[0] for p in self.yz]
        zs = [p[1] for p in self.yz]
        return ((self.x0, min(ys), min(zs)),
                (self.x0 + self.length, max(ys), max(zs)))


def fillet_polyline(points, r, segments=6):
    """Round every interior corner of a polyline with an arc of radius ``r``.

    Rebar is bent, never kinked; a sharp corner also makes the swept solid
    self-intersect. The arc is approximated by ``segments`` straight pieces.
    """
    if r <= 0 or len(points) < 3:
        return list(points)
    out = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - b[i] for i in range(3)]
        lu, lv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(x * x for x in v))
        u = [x / lu for x in u]
        v = [x / lv for x in v]
        cos_t = max(-1.0, min(1.0, -sum(u[i] * v[i] for i in range(3))))
        theta = math.acos(cos_t)                  # interior angle at b
        if abs(math.pi - theta) < 1e-9:           # straight through
            out.append(b)
            continue
        t = r / math.tan(theta / 2)               # tangent length
        p1 = [b[i] - u[i] * t for i in range(3)]
        p2 = [b[i] + v[i] * t for i in range(3)]
        bis = [v[i] - u[i] for i in range(3)]
        lb = math.sqrt(sum(x * x for x in bis))
        centre = [b[i] + bis[i] / lb * r / math.sin(theta / 2) for i in range(3)]
        a1 = [p1[i] - centre[i] for i in range(3)]
        a2 = [p2[i] - centre[i] for i in range(3)]
        for k in range(segments + 1):
            f = k / segments
            # spherical interpolation between the two radius vectors
            omega = math.acos(max(-1.0, min(1.0, sum(a1[i] * a2[i] for i in range(3)) / (r * r))))
            w1 = math.sin((1 - f) * omega) / math.sin(omega)
            w2 = math.sin(f * omega) / math.sin(omega)
            out.append(tuple(centre[i] + w1 * a1[i] + w2 * a2[i] for i in range(3)))
    out.append(points[-1])
    return out


@dataclass
class PrismY:
    """A polygon in the X-Z plane extruded along +Y from y0 by length.

    Used for the pier cap: a trapezoid in section (wide at the top, narrow at
    the bottom) running across the deck.
    """
    y0: float
    length: float
    xz: list[tuple[float, float]]

    @property
    def area(self) -> float:
        pts = self.xz
        return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                       - pts[(i + 1) % len(pts)][0] * pts[i][1]
                       for i in range(len(pts)))) / 2.0

    @property
    def volume(self) -> float:
        return self.area * self.length

    def bounds(self):
        xs = [p[0] for p in self.xz]
        zs = [p[1] for p in self.xz]
        return ((min(xs), self.y0, min(zs)), (max(xs), self.y0 + self.length, max(zs)))


def circle_points(cx, cy, z, r, n=24, gap=0.0):
    """Points of a horizontal circle (a hoop). ``gap`` leaves the ends apart
    by that arc length, as a real hoop is a lapped bar, not a closed ring."""
    a_gap = gap / r if r > 0 else 0.0
    span = 2 * math.pi - a_gap
    return [(cx + r * math.cos(a_gap / 2 + span * k / n),
             cy + r * math.sin(a_gap / 2 + span * k / n), z) for k in range(n + 1)]


@dataclass
class Bar:
    """A reinforcing bar: a polyline axis swept by a circle of diameter d."""
    name: str
    points: list[tuple[float, float, float]]
    d: float
    role: str = "MAIN"            # MAIN or LIGATURE (IFC predefined types)
    bend_radius: float = 0.0      # fillet radius of the axis at each corner

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))

    @property
    def volume(self) -> float:
        """Swept-disk volume ignoring the tiny overlap at bends."""
        return math.pi * (self.d / 2) ** 2 * self.length


@dataclass
class Part:
    """One concrete member of the substructure."""
    kind: str                      # PIER, PIER_CAP, PILE_CAP, PILE
    name: str
    solid: object                  # Box | Cylinder | PrismX
    grade: str = "M35"
    cover: float = 50.0
    bars: list[Bar] = field(default_factory=list)
    props: dict = field(default_factory=dict)

    @property
    def volume(self) -> float:
        return self.solid.volume
