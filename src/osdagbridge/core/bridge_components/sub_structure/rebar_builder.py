"""pythonOCC helpers shared by the substructure builders: reinforcing bars.

A bar is a circle of the bar diameter swept along the bar's axis. Corners are
already bent in the model (see solids.fillet_polyline), so the sweep never
self-intersects.
"""
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                     BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire)
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCC.Core.TopoDS import TopoDS_Compound


def bar_shape(bar):
    """TopoDS solid of one reinforcing bar."""
    spine = BRepBuilderAPI_MakePolygon()
    for p in bar.points:
        spine.Add(gp_Pnt(*p))
    p0, p1 = bar.points[0], bar.points[1]
    direction = gp_Dir(p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    circle = gp_Circ(gp_Ax2(gp_Pnt(*p0), direction), bar.d / 2.0)
    edge = BRepBuilderAPI_MakeEdge(circle).Edge()
    profile = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(edge).Wire()).Face()
    return BRepOffsetAPI_MakePipe(spine.Wire(), profile).Shape()


def bars_compound(bars):
    """All bars of a member in one compound (one display object, fast to draw)."""
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for bar in bars:
        builder.Add(compound, bar_shape(bar))
    return compound
