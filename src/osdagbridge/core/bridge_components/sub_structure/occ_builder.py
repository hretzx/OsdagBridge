"""OpenCASCADE (pythonocc) shapes for the substructure, for the Osdag 3D view.

The same model objects that feed the IFC export are turned into TopoDS shapes
here, so the viewer and the IFC file can never disagree. pythonocc is
imported lazily: the IFC export and the self-check do not need it.
"""
from __future__ import annotations

from .solids import Box, Cylinder, PrismX


def _occ():
    from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                         BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire)
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCC.Core.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder,
                                      BRepPrimAPI_MakePrism)
    from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
    return locals()


def solid_shape(solid):
    o = _occ()
    if isinstance(solid, Box):
        return o["BRepPrimAPI_MakeBox"](o["gp_Pnt"](solid.x0, solid.y0, solid.z0),
                                        solid.dx, solid.dy, solid.dz).Shape()
    if isinstance(solid, Cylinder):
        axis = o["gp_Ax2"](o["gp_Pnt"](solid.cx, solid.cy, solid.z0), o["gp_Dir"](0, 0, 1))
        return o["BRepPrimAPI_MakeCylinder"](axis, solid.r, solid.h).Shape()
    if isinstance(solid, PrismX):
        poly = o["BRepBuilderAPI_MakePolygon"]()
        for y, z in solid.yz:
            poly.Add(o["gp_Pnt"](solid.x0, y, z))
        poly.Close()
        face = o["BRepBuilderAPI_MakeFace"](poly.Wire()).Face()
        return o["BRepPrimAPI_MakePrism"](face, o["gp_Vec"](solid.length, 0, 0)).Shape()
    raise TypeError(type(solid).__name__)


def bar_shape(bar):
    """A bar as a circle swept along its (already bent) axis."""
    o = _occ()
    spine = o["BRepBuilderAPI_MakePolygon"]()
    for p in bar.points:
        spine.Add(o["gp_Pnt"](*p))
    p0, p1 = bar.points[0], bar.points[1]
    d = o["gp_Dir"](p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    circle = o["gp_Circ"](o["gp_Ax2"](o["gp_Pnt"](*p0), d), bar.d / 2.0)
    edge = o["BRepBuilderAPI_MakeEdge"](circle).Edge()
    profile = o["BRepBuilderAPI_MakeFace"](o["BRepBuilderAPI_MakeWire"](edge).Wire()).Face()
    return o["BRepOffsetAPI_MakePipe"](spine.Wire(), profile).Shape()


def build_shapes(support_lines, with_bars=True):
    """{"concrete": [(name, shape)], "rebar": [(name, shape)]} for display."""
    out = {"concrete": [], "rebar": []}
    for line in support_lines:
        for part in line.parts:
            out["concrete"].append((part.name, solid_shape(part.solid)))
            if with_bars:
                out["rebar"] += [(b.name, bar_shape(b)) for b in part.bars]
    return out


def shape_volume(shape):
    """Volume of a TopoDS shape (handles old and new pythonocc spellings)."""
    from OCC.Core.GProp import GProp_GProps
    props = GProp_GProps()
    try:
        from OCC.Core.BRepGProp import brepgprop
        brepgprop.VolumeProperties(shape, props)
    except ImportError:                      # pythonocc < 7.7
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties
        brepgprop_VolumeProperties(shape, props)
    return props.Mass()
