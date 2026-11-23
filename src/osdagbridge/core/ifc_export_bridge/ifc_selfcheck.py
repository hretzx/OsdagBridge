"""Re-open an exported IFC and check the substructure geometry against its design.

    python -m osdagbridge.core.ifc_export_bridge.ifc_selfcheck bridge.ifc

The check reads only the IFC file. Every member carries its design intent in
``Pset_OsdagSubstructure`` (shape, dimensions, design volume, bearing
positions), and the geometry is rebuilt by IfcOpenShell's OpenCASCADE kernel,
so the two are independent. Checks:

1. volume    geometry volume = design volume (and = pi r^2 L for piles)
2. stacking  cap soffit meets pier top, pier bottom meets pile cap top,
             pile tops meet pile cap underside; footprints sit inside
3. bearings  every bearing lands on its pier cap, at the cap's top level
4. cover     every bar stays inside its member with at least the stated cover
5. clashes   members do not interpenetrate; bars in a member never cross
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.shape as us

TOL = 0.002          # 2 mm, in metres
VOL_TOL = 0.005      # 0.5 % for flat-faced members
CURVED_VOL_TOL = 0.01  # 1 % for cylinders, which the kernel tessellates


@dataclass
class Check:
    name: str
    passed: int = 0
    failures: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self):
        return not self.failures


@dataclass
class Report:
    path: str
    members: int
    bars: int
    checks: list[Check]

    @property
    def ok(self):
        return all(c.ok for c in self.checks)

    def text(self) -> str:
        lines = [f"Self-check of {self.path}",
                 f"{self.members} concrete members, {self.bars} reinforcing bars", ""]
        for c in self.checks:
            mark = "PASS" if c.ok else "FAIL"
            lines.append(f"[{mark}] {c.name}: {c.passed} passed, {len(c.failures)} failed"
                         + (f"  ({c.detail})" if c.detail else ""))
            lines += [f"       - {f}" for f in c.failures[:10]]
            if len(c.failures) > 10:
                lines.append(f"       ... and {len(c.failures) - 10} more")
        lines += ["", "RESULT: " + ("ALL CHECKS PASSED" if self.ok else "CHECKS FAILED")]
        return "\n".join(lines)

    def as_dict(self):
        return {"path": self.path, "members": self.members, "bars": self.bars,
                "ok": self.ok,
                "checks": [{"name": c.name, "ok": c.ok, "passed": c.passed,
                            "failures": c.failures, "detail": c.detail} for c in self.checks]}


class _Geo:
    def __init__(self, el, shape):
        self.el = el
        v = shape.geometry.verts
        self.xyz = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
        self.lo = tuple(min(p[k] for p in self.xyz) for k in range(3))
        self.hi = tuple(max(p[k] for p in self.xyz) for k in range(3))
        self.volume = us.get_volume(shape.geometry)


class _BarAxis:
    """A bar read straight from its IfcSweptDiskSolid: axis polyline + radius."""

    def __init__(self, bar):
        sweep = bar.Representation.Representations[0].Items[0]
        self.r = sweep.Radius
        self.xyz = [tuple(p.Coordinates) for p in sweep.Directrix.Points]
        # Exact extent of the swept disk: along each axis a segment reaches
        # r * sqrt(1 - d_k^2) beyond its end points (0 along its own direction).
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for p, q in zip(self.xyz, self.xyz[1:]):
            length = math.dist(p, q) or 1.0
            for k in range(3):
                d = (q[k] - p[k]) / length
                ext = self.r * math.sqrt(max(0.0, 1 - d * d))
                lo[k] = min(lo[k], p[k] - ext, q[k] - ext)
                hi[k] = max(hi[k], p[k] + ext, q[k] + ext)
        self.lo, self.hi = tuple(lo), tuple(hi)
        self.name = bar.Name

    def radial_extent(self, cx, cy):
        """Largest horizontal distance of the bar's surface from (cx, cy)."""
        best = 0.0
        for p, q in zip(self.xyz, self.xyz[1:]):
            length = math.dist(p, q) or 1.0
            dz = (q[2] - p[2]) / length
            for pt in (p, q):
                best = max(best, math.hypot(pt[0] - cx, pt[1] - cy)
                           + self.r * math.sqrt(max(0.0, 1 - dz * dz)))
        return best


def _seg_dist(p1, q1, p2, q2):
    """Shortest distance between segments p1-q1 and p2-q2 (3D)."""
    d1 = [q1[i] - p1[i] for i in range(3)]
    d2 = [q2[i] - p2[i] for i in range(3)]
    r = [p1[i] - p2[i] for i in range(3)]
    a = sum(x * x for x in d1)
    e = sum(x * x for x in d2)
    f = sum(d2[i] * r[i] for i in range(3))
    if a <= 1e-15 and e <= 1e-15:
        return math.dist(p1, p2)
    if a <= 1e-15:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = sum(d1[i] * r[i] for i in range(3))
        if e <= 1e-15:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = sum(d1[i] * d2[i] for i in range(3))
            denom = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / denom)) if denom > 1e-15 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    c1 = [p1[i] + d1[i] * s for i in range(3)]
    c2 = [p2[i] + d2[i] * t for i in range(3)]
    return math.dist(c1, c2)


def _boxes_overlap(a, b, depth):
    return all(min(a.hi[k], b.hi[k]) - max(a.lo[k], b.lo[k]) > depth for k in range(3))


def _pset(el):
    return ue.get_psets(el).get("Pset_OsdagSubstructure", {})


def run(path: str) -> Report:
    f = ifcopenshell.open(path)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    members = [e for e in f.by_type("IfcElement") if _pset(e).get("Kind")]
    geo = {e.id(): _Geo(e, ifcopenshell.geom.create_shape(settings, e)) for e in members}
    bars_of = {}
    for e in members:
        bars_of[e.id()] = [b for b in ue.get_decomposition(e) if b.is_a("IfcReinforcingBar")]
    all_bars = [b for bl in bars_of.values() for b in bl]
    bar_geo = {b.id(): _BarAxis(b) for b in all_bars}

    checks = [_check_volumes(members, geo), _check_stacking(f, members, geo),
              _check_bearings(f, members, geo), _check_cover(members, geo, bars_of, bar_geo),
              _check_clashes(f, members, bars_of, bar_geo, geo)]
    return Report(path, len(members), len(all_bars), checks)


def _check_volumes(members, geo) -> Check:
    c = Check("1. volume matches design")
    worst = 0.0
    for e in members:
        ps = _pset(e)
        design = ps["DesignVolume"]
        got = geo[e.id()].volume
        tol = CURVED_VOL_TOL if ps.get("Shape") == "CYLINDER" else VOL_TOL
        err = abs(got - design) / design
        worst = max(worst, err)
        if ps.get("Shape") == "CYLINDER":
            formula = math.pi * ps["Radius"] ** 2 * ps["Height"]
            if abs(formula - design) / design > 1e-9:
                c.failures.append(f"{e.Name}: design volume {design:.4f} m3 is not pi r^2 L "
                                  f"= {formula:.4f} m3")
                continue
        if err > tol:
            c.failures.append(f"{e.Name}: geometry {got:.4f} m3 vs design {design:.4f} m3 "
                              f"({err:.2%})")
        else:
            c.passed += 1
    c.detail = f"largest difference {worst:.3%}"
    return c


def _assemblies(f):
    return [a for a in f.by_type("IfcElementAssembly") if _pset(a).get("SupportLine")]


def _parts(assembly, kind):
    return [e for e in ue.get_decomposition(assembly)
            if _pset(e).get("Kind") == kind]


def _inside_xy(inner, outer, tol=TOL):
    return (inner.lo[0] >= outer.lo[0] - tol and inner.hi[0] <= outer.hi[0] + tol
            and inner.lo[1] >= outer.lo[1] - tol and inner.hi[1] <= outer.hi[1] + tol)


def _check_stacking(f, members, geo) -> Check:
    c = Check("2. members stack face to face")
    for a in _assemblies(f):
        cap = _parts(a, "PIER_CAP")[0]
        g_cap = geo[cap.id()]
        cap_soffit = g_cap.lo[2]
        for pier in _parts(a, "PIER"):
            gp = geo[pier.id()]
            # The soffit is lowest over the columns, so the pier top meets it.
            if abs(gp.hi[2] - cap_soffit) > TOL:
                c.failures.append(f"{pier.Name}: top {gp.hi[2]:.3f} m, cap soffit {cap_soffit:.3f} m")
            else:
                c.passed += 1
            caps = [pc for pc in _parts(a, "PILE_CAP") if _inside_xy(gp, geo[pc.id()])]
            if len(caps) != 1:
                c.failures.append(f"{pier.Name}: sits on {len(caps)} pile caps, expected 1")
                continue
            g_pc = geo[caps[0].id()]
            if abs(gp.lo[2] - g_pc.hi[2]) > TOL:
                c.failures.append(f"{pier.Name}: bottom {gp.lo[2]:.3f} m, pile cap top {g_pc.hi[2]:.3f} m")
            else:
                c.passed += 1
        for pile in _parts(a, "PILE"):
            g = geo[pile.id()]
            caps = [pc for pc in _parts(a, "PILE_CAP") if _inside_xy(g, geo[pc.id()])]
            if len(caps) != 1:
                c.failures.append(f"{pile.Name}: under {len(caps)} pile caps, expected 1")
            elif abs(g.hi[2] - geo[caps[0].id()].lo[2]) > TOL:
                c.failures.append(f"{pile.Name}: top {g.hi[2]:.3f} m, pile cap underside "
                                  f"{geo[caps[0].id()].lo[2]:.3f} m")
            else:
                c.passed += 1
    return c


def _check_bearings(f, members, geo) -> Check:
    c = Check("3. every bearing lands on a pier cap")
    for a in _assemblies(f):
        ps = _pset(a)
        z, points = ps["BearingUndersideZ"], json.loads(ps["BearingPoints"])
        g = geo[_parts(a, "PIER_CAP")[0].id()]
        for x, y in points:
            on_plan = g.lo[0] - TOL <= x <= g.hi[0] + TOL and g.lo[1] - TOL <= y <= g.hi[1] + TOL
            if not on_plan:
                c.failures.append(f"line {ps['SupportLine']}: bearing at x={x:.3f}, y={y:.3f} m "
                                  f"is off the cap")
            elif abs(g.hi[2] - z) > TOL:
                c.failures.append(f"line {ps['SupportLine']}: bearing at y={y:.3f} m is "
                                  f"{(z - g.hi[2]) * 1000:.0f} mm from the cap top")
            else:
                c.passed += 1
    return c


def _check_cover(members, geo, bars_of, bar_geo) -> Check:
    c = Check("4. bars keep their concrete cover")
    least = math.inf
    for e in members:
        ps = _pset(e)
        cover = ue.get_psets(e).get("Pset_ConcreteElementGeneral", {}).get("ConcreteCover", 0.05)
        host = geo[e.id()]
        for b in bars_of[e.id()]:
            bg = bar_geo[b.id()]
            if ps["Shape"] == "CYLINDER":
                cx = (host.lo[0] + host.hi[0]) / 2
                cy = (host.lo[1] + host.hi[1]) / 2
                margin = min(ps["Radius"] - bg.radial_extent(cx, cy),
                             bg.lo[2] - host.lo[2], host.hi[2] - bg.hi[2])
            else:
                margin = min(min(bg.lo[k] - host.lo[k], host.hi[k] - bg.hi[k])
                             for k in range(3))
            least = min(least, margin)
            if margin < cover - TOL:
                c.failures.append(f"{b.Name}: {margin * 1000:.0f} mm from the surface, "
                                  f"cover is {cover * 1000:.0f} mm")
            else:
                c.passed += 1
    if least < math.inf:
        c.detail = f"least cover found {least * 1000:.1f} mm"
    return c


def _check_clashes(f, members, bars_of, bar_geo, geo) -> Check:
    """Members: bounding boxes may touch but not interpenetrate by more than 2 mm.
    Bars: two bars clash when their axes come closer than the sum of radii."""
    c = Check("5. no clashes")
    for i, a in enumerate(members):
        for b in members[i + 1:]:
            if _boxes_overlap(geo[a.id()], geo[b.id()], TOL):
                c.failures.append(f"{a.Name} overlaps {b.Name}")
            else:
                c.passed += 1
    n_bar_pairs = 0
    for host, bars in bars_of.items():
        axes = [bar_geo[b.id()] for b in bars]
        for i, a in enumerate(axes):
            for b in axes[i + 1:]:
                n_bar_pairs += 1
                if not _boxes_overlap(a, b, 0.0):
                    c.passed += 1
                    continue
                gap = min(_seg_dist(p, q, u, v)
                          for p, q in zip(a.xyz, a.xyz[1:])
                          for u, v in zip(b.xyz, b.xyz[1:])) - a.r - b.r
                if gap < -TOL:
                    c.failures.append(f"bar {a.name} passes through {b.name} "
                                      f"({-gap * 1000:.1f} mm)")
                else:
                    c.passed += 1
    n_bars = sum(len(b) for b in bars_of.values())
    c.detail = (f"{len(members)} members (bounding boxes), "
                f"{n_bars} bars in {n_bar_pairs} pairs (exact axis distance)")
    return c


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    report = run(argv[0])
    print(report.text())
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as fh:
            json.dump(report.as_dict(), fh, indent=2)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
