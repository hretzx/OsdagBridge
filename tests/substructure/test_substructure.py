"""Substructure geometry, IFC export and self-check.

The export tests run the real Osdag path (PlateGirderIFCExtractor ->
BridgeIfcGenerator) on the sample bridge from desktop/ui/cad_3d.py. The
mutation tests then damage the exported file in one specific way each and
assert that the self-check reports exactly that damage.
"""
import json
import math

import ifcopenshell
import pytest

from osdagbridge.core.bridge_components.sub_structure.solids import fillet_polyline
from osdagbridge.core.bridge_components.sub_structure.substructure import (
    SubstructureParams, build_support_line, column_positions)
from osdagbridge.core.ifc_export_bridge import ifc_selfcheck
from substructure_demo import export, sample_bridge


# ----------------------------------------------------------------- geometry
def test_pile_volume_is_pi_r2_l():
    line = build_support_line("A", 0, [-1250, 1250], -1000)
    pile = next(p for p in line.parts if p.kind == "PILE")
    assert pile.volume == pytest.approx(math.pi * 500 ** 2 * 15000)


def test_hammerhead_area_by_hand():
    p = SubstructureParams()
    line = build_support_line("A", 0, [-1250, 1250], 0, p)
    cap = line.parts[0]
    length = 2500 + 2 * p.cap_edge                  # 3700
    # rectangle of tip depth + two trapezoids down to the column + column strip
    half_gap = (length - p.pier_breadth) / 2        # 600 each side
    extra = p.cap_depth_mid - p.cap_depth_tip       # 700
    area = length * p.cap_depth_tip + p.pier_breadth * extra + 2 * half_gap * extra / 2
    assert cap.solid.area == pytest.approx(area)


@pytest.mark.parametrize("width, columns", [(2500, 1), (7000, 1), (7001, 2), (27300, 4)])
def test_column_count_follows_deck_width(width, columns):
    ys = [-width / 2, width / 2]
    assert len(column_positions(ys, SubstructureParams())) == columns


def test_tie_corners_are_bent_not_kinked():
    square = [(0, 0, 0), (100, 0, 0), (100, 100, 0)]
    pts = fillet_polyline(square, 20)
    # every point of the arc is 20 from the arc centre (80, 20)
    arc = pts[1:-1]
    assert all(math.dist(p[:2], (80, 20)) == pytest.approx(20) for p in arc)
    assert arc[0][:2] == pytest.approx((80, 0)) and arc[-1][:2] == pytest.approx((100, 20))


def test_pile_spacing_rule_reported():
    line = build_support_line("A", 0, [0, 1], 0, SubstructureParams(pile_spacing=2000))
    assert any("less than 3 x diameter" in i for i in line.issues)


# ------------------------------------------------------------- full export
@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    return export(str(tmp_path_factory.mktemp("ifc") / "bridge.ifc"))


def test_export_contains_the_substructure_classes(exported):
    f = ifcopenshell.open(exported)
    assert len(f.by_type("IfcPile")) == 32           # 2 lines x 4 columns x 4 piles
    assert len(f.by_type("IfcFooting")) == 8
    assert all(x.PredefinedType == "PILE_CAP" for x in f.by_type("IfcFooting"))
    assert len([b for b in f.by_type("IfcBeam") if b.ObjectType == "PIERCAP"]) == 2
    assert len(f.by_type("IfcReinforcingBar")) > 1000
    storeys = {s.Name for s in f.by_type("IfcBuildingStorey")}
    assert storeys == {"Superstructure", "Substructure"}
    assert len(f.by_type("IfcPlate")) > 0            # superstructure still exported


def test_selfcheck_passes_on_clean_export(exported):
    report = ifc_selfcheck.run(exported)
    assert report.ok, report.text()


def test_narrow_bridge_gets_a_single_hammerhead(tmp_path):
    dto = sample_bridge(footpath_config="NONE", enable_median=False, carriageway_width=7_500,
                        num_girders=3)
    path = export(str(tmp_path / "narrow.ifc"), dto)
    f = ifcopenshell.open(path)
    assert len(f.by_type("IfcColumn")) == 2          # one pier per support line
    assert ifc_selfcheck.run(path).ok


# ----------------------------------------------------------- mutation tests
def _damage(src, tmp_path, fn):
    f = ifcopenshell.open(src)
    fn(f)
    out = str(tmp_path / "damaged.ifc")
    f.write(out)
    return {c.name: c for c in ifc_selfcheck.run(out).checks}


def _first(f, cls, pred=lambda e: True):
    return next(e for e in f.by_type(cls) if pred(e))


def test_selfcheck_catches_a_shrunk_pile(exported, tmp_path):
    def shrink(f):
        prof = _first(f, "IfcPile").Representation.Representations[0].Items[0].SweptArea
        prof.Radius *= 0.95
    checks = _damage(exported, tmp_path, shrink)
    assert not checks["1. volume matches design"].ok


def test_selfcheck_catches_a_sunken_pile(exported, tmp_path):
    def sink(f):
        loc = _first(f, "IfcPile").ObjectPlacement.RelativePlacement.Location
        x, y, z = loc.Coordinates
        loc.Coordinates = (x, y, z - 0.05)
    checks = _damage(exported, tmp_path, sink)
    assert not checks["2. members stack face to face"].ok


def test_selfcheck_catches_a_bar_without_cover(exported, tmp_path):
    def push_out(f):
        bar = _first(f, "IfcReinforcingBar", lambda b: "pile cap bottom" in b.Name)
        for p in bar.Representation.Representations[0].Items[0].Directrix.Points:
            x, y, z = p.Coordinates
            p.Coordinates = (x, y, z - 0.03)        # 30 mm closer to the soffit
    checks = _damage(exported, tmp_path, push_out)
    assert not checks["4. bars keep their concrete cover"].ok


def test_selfcheck_catches_crossing_bars(exported, tmp_path):
    def lower_layer(f):
        bar = _first(f, "IfcReinforcingBar", lambda b: "bottom Y bar 3" in b.Name)
        for p in bar.Representation.Representations[0].Items[0].Directrix.Points:
            x, y, z = p.Coordinates
            p.Coordinates = (x, y, z - 0.025)       # into the X layer below
    checks = _damage(exported, tmp_path, lower_layer)
    assert not checks["5. no clashes"].ok
    assert checks["4. bars keep their concrete cover"].ok   # still inside


def test_selfcheck_catches_a_bearing_off_the_cap(exported, tmp_path):
    def move_bearings(f):
        a = _first(f, "IfcElementAssembly")
        pset = next(r.RelatingPropertyDefinition for r in a.IsDefinedBy
                    if r.RelatingPropertyDefinition.Name == "Pset_OsdagSubstructure")
        prop = next(p for p in pset.HasProperties if p.Name == "BearingPoints")
        pts = json.loads(prop.NominalValue.wrappedValue)
        pts[0][0] += 2.0                            # first bearing 2 m along the span
        prop.NominalValue.wrappedValue = json.dumps(pts)
    checks = _damage(exported, tmp_path, move_bearings)
    assert not checks["3. every bearing lands on a pier cap"].ok


def test_skewed_deck_is_reported_not_hidden(tmp_path):
    """The cap is laid square; on a 20 degree skew the outer bearings miss it."""
    path = export(str(tmp_path / "skew.ifc"), sample_bridge(skew_angle=20))
    report = ifc_selfcheck.run(path)
    bearing = next(c for c in report.checks if c.name.startswith("3."))
    assert not bearing.ok
