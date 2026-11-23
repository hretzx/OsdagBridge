"""pythonOCC geometry of the pile cap: a rectangular block and two bar mats."""
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.gp import gp_Pnt

from ...sub_structure.rebar_builder import bars_compound


def build_pile_cap_shapes(part):
    """(concrete solid, rebar compound) for a pile cap Part from pile_cap.geometry."""
    s = part.solid                                   # Box
    concrete = BRepPrimAPI_MakeBox(gp_Pnt(s.x0, s.y0, s.z0), s.dx, s.dy, s.dz).Shape()
    return concrete, bars_compound(part.bars)
