"""Substructure 3D CAD for the plate girder CAD generator (pythonOCC).

``build_substructure_cad`` turns the parametric model (substructure.py) into
display-ready shapes, using the builder of each component:

    pier_cap/builder.py   pier/builder.py   ../foundation/pile_cap/builder.py
    ../foundation/pile/builder.py           rebar_builder.py (bars)

The IFC export reads the same parametric model, so the CAD window and the
.ifc file always show the same substructure.
"""
from ..foundation.pile.builder import build_pile_shapes
from ..foundation.pile_cap.builder import build_pile_cap_shapes
from .pier.builder import build_pier_shapes
from .pier_cap.builder import build_pier_cap_shapes

_BUILDERS = {"PIER_CAP": build_pier_cap_shapes, "PIER": build_pier_shapes,
             "PILE_CAP": build_pile_cap_shapes, "PILE": build_pile_shapes}

# model_data keys, one per component, so each can be shown and hidden.
KEYS = {"PIER_CAP": "pier_caps", "PIER": "piers", "PILE_CAP": "pile_caps", "PILE": "piles"}


def build_substructure_cad(support_lines):
    """{"pier_caps": [...], "piers": [...], "pile_caps": [...], "piles": [...],
        "substructure_rebar": [...]} of TopoDS shapes."""
    out = {k: [] for k in KEYS.values()}
    out["substructure_rebar"] = []
    for line in support_lines:
        for part in line.parts:
            concrete, rebar = _BUILDERS[part.kind](part)
            out[KEYS[part.kind]].append(concrete)
            out["substructure_rebar"].append(rebar)
    return out
