"""pythonOCC geometry of the pier cap: a trapezoidal section swept across the deck."""
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.gp import gp_Pnt, gp_Vec

from ..rebar_builder import bars_compound


def build_pier_cap_shapes(part):
    """(concrete solid, rebar compound) for a pier cap Part from pier_cap.geometry."""
    s = part.solid                                   # PrismY
    section = BRepBuilderAPI_MakePolygon()
    for x, z in s.xz:
        section.Add(gp_Pnt(x, s.y0, z))
    section.Close()
    face = BRepBuilderAPI_MakeFace(section.Wire()).Face()
    concrete = BRepPrimAPI_MakePrism(face, gp_Vec(0, s.length, 0)).Shape()
    return concrete, bars_compound(part.bars)
