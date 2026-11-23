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
    SubstructureParams, build_support_line)
from osdagbridge.core.ifc_export_bridge import ifc_selfcheck
from substructure_demo import export, sample_bridge


# ----------------------------------------------------------------- geometry
def test_defaults_are_the_task_dimensions():
    p = SubstructureParams()
    assert (p.pier_diameter, p.pier_height) == (800, 3000)
    assert (p.pier_cap_top_width, p.pier_cap_bottom_width, p.pier_cap_depth) == (3000, 1200, 600)
    assert (p.pile_cap_length, p.pile_cap_width, p.pile_cap_depth) == (2200, 1200, 600)
    assert (p.n_piles_per_cap, p.pile_diameter, p.pile_length, p.pile_spacing) == (4, 400, 5000, 600)
    assert (p.rebar_main_diameter, p.rebar_spacing_longitudinal) == (16, 150)
    assert (p.rebar_transverse_diameter, p.rebar_spacing_transverse, p.rebar_cover) == (8, 200, 40)


def _line(**kw):
    return build_support_line("A", 0, [-2750, 0, 2750], -1000, SubstructureParams(**kw),
                              deck_width=8000, deck_centre_y=0)


def test_pile_volume_is_pi_r2_l():
    pile = next(p for p in _line().parts if p.kind == "PILE")
    assert pile.volume == pytest.approx(math.pi * 200 ** 2 * 5000)


def test_pier_cap_is_the_trapezoid_across_the_deck():
    cap = _line().parts[0]
    assert cap.solid.area == pytest.approx((3000 + 1200) / 2 * 600)
    assert cap.solid.length == 8000                         # deck width
    assert cap.volume == pytest.approx((3000 + 1200) / 2 * 600 * 8000)


def test_members_stack_from_the_bearings_down():
    cap, pier, pile_cap, *piles = _line().parts
    assert cap.solid.bounds()[1][2] == -1000                # cap top = bearing underside
    assert pier.solid.z0 + pier.solid.h == pytest.approx(-1000 - 600)
    assert pile_cap.solid.z0 + pile_cap.solid.dz == pytest.approx(pier.solid.z0)
    assert all(p.solid.z0 + p.solid.h == pytest.approx(pile_cap.solid.z0) for p in piles)
    assert len(piles) == 4


def test_pile_grid_is_2x2_at_600():
    piles = [p for p in _line().parts if p.kind == "PILE"]
    xs = sorted({round(p.solid.cx) for p in piles})
    ys = sorted({round(p.solid.cy) for p in piles})
    assert xs == [-300, 300] and ys == [-300, 300]


def test_tie_corners_are_bent_not_kinked():
    square = [(0, 0, 0), (100, 0, 0), (100, 100, 0)]
    pts = fillet_polyline(square, 20)
    arc = pts[1:-1]
    assert all(math.dist(p[:2], (80, 20)) == pytest.approx(20) for p in arc)
    assert arc[0][:2] == pytest.approx((80, 0)) and arc[-1][:2] == pytest.approx((100, 20))


def test_close_piles_are_reported():
    line = _line()
    assert any("below the usual 3 x diameter" in i for i in line.issues)


def test_cad_generator_plumbing_returns_every_component():
    """The pythonOCC builders run on the stand-in here; this checks the routing
    (one concrete shape per member, one rebar compound per member)."""
    from osdagbridge.core.bridge_components.sub_structure.builder import build_substructure_cad
    out = build_substructure_cad([_line(), _line()])
    assert {k: len(v) for k, v in out.items()} == {
        "pier_caps": 2, "piers": 2, "pile_caps": 2, "piles": 8, "substructure_rebar": 14}


# ------------------------------------------------------------- full export
@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    return export(str(tmp_path_factory.mktemp("ifc") / "bridge.ifc"))


def test_export_contains_the_substructure_classes(exported):
    f = ifcopenshell.open(exported)
    assert len(f.by_type("IfcPile")) == 8            # 2 support lines x 4 piles
    assert len(f.by_type("IfcFooting")) == 2
    assert len(f.by_type("IfcColumn")) == 2
    assert all(x.PredefinedType == "PILE_CAP" for x in f.by_type("IfcFooting"))
    assert len([b for b in f.by_type("IfcBeam") if b.ObjectType == "PIERCAP"]) == 2
    assert len(f.by_type("IfcReinforcingBar")) == 750   # 375 per support line
    storeys = {s.Name for s in f.by_type("IfcBuildingStorey")}
    assert storeys == {"Superstructure", "Substructure"}
    assert len(f.by_type("IfcPlate")) > 0            # superstructure still exported


def test_selfcheck_passes_on_clean_export(exported):
    report = ifc_selfcheck.run(exported)
    assert report.ok, report.text()


def test_narrow_bridge_also_passes(tmp_path):
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
            p.Coordinates = (x, y, z - 0.012)       # 12 mm down into the X layer
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


def test_export_is_schema_valid(exported):
    """Strict importers such as Revit reject files that break the IFC4 schema."""
    import ifcopenshell.validate
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(ifcopenshell.open(exported), logger, express_rules=False)
    assert logger.statements == []
