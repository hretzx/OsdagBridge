"""pythonOCC geometry of the pier: a circular column and its cage."""
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

from ..rebar_builder import bars_compound


def build_pier_shapes(part):
    """(concrete solid, rebar compound) for a pier Part from pier.geometry."""
    s = part.solid                                   # Cylinder
    axis = gp_Ax2(gp_Pnt(s.cx, s.cy, s.z0), gp_Dir(0, 0, 1))
    concrete = BRepPrimAPI_MakeCylinder(axis, s.r, s.h).Shape()
    return concrete, bars_compound(part.bars)
