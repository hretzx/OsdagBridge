"""Export the sample plate girder bridge with its substructure to IFC.

    python tools/substructure_demo.py out/bridge_with_substructure.ifc

Uses the same sample bridge as ``desktop/ui/cad_3d.py`` (25 m span, five
girders) and the real Osdag IFC export path: PlateGirderIFCExtractor ->
BridgeIfcGenerator. Runs without the GUI; pythonocc is only needed by modules
that the export path imports, and a stand-in is used when it is missing.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "tests", "substructure"))

import occ_stub  # noqa: E402

occ_stub.install()

from osdagbridge.core.bridge_types.plate_girder.dto import (  # noqa: E402
    BridgeParametersDTO, ISectionDimsDTO, SectionDimsDTO)
from osdagbridge.core.ifc_export_bridge.export_ifc_handler import (  # noqa: E402
    PlateGirderIfcExportHandler)


def sample_bridge(**overrides) -> BridgeParametersDTO:
    angle = SectionDimsDTO(leg_h=100, leg_w=50, connection_type="LONGER_LEG")
    small = SectionDimsDTO(leg_h=80, leg_w=40, connection_type="LONGER_LEG")
    params = dict(
        steel_grade="E250", concrete_grade="M35",
        span_length_L=25_000, girder_section_d=900, girder_section_bf=500,
        girder_section_bf_b=500, girder_section_tf=260, girder_section_tf_b=260,
        girder_section_tw=100, num_girders=5, girder_spacing=2_750, skew_angle=0,
        carriageway_width=12_000, deck_thickness=400, footpath_config="BOTH",
        footpath_width=1_500, railing_width=300, barrier_type="Semi-Rigid",
        crash_barrier_subtype="Double W-beam", enable_median=True,
        median_type="Metallic Crash Barrier", rail_count=3, railing_type="rcc",
        include_intermediate_stiffeners=True, intermediate_stiffener_spacing=2_000,
        intermediate_stiffener_thickness=20, intermediate_stiffener_outstand=None,
        num_end_stiffener_pairs=4, end_stiffener_thickness=30, end_stiffener_outstand=None,
        include_longitudinal_stiffeners=True, num_longitudinal_stiffeners=2,
        longitudinal_stiffener_thickness=20, longitudinal_stiffener_outstand=None,
        cross_bracing_spacing=4_000, bracing_type="X", x_bracket_option="BOTH",
        k_top_bracket=True,
        diagonal_section_type="ANGLE", diagonal_section_dims=angle, diagonal_thickness=5,
        top_chord_section_type="DOUBLE_CHANNEL", top_chord_section_dims=small,
        top_chord_thickness=5,
        bottom_chord_section_type="ANGLE", bottom_chord_section_dims=small,
        bottom_chord_thickness=5,
        end_diaphragm_type="Cross Bracing", end_diaphragm_spacing=100,
        end_diaphragm_bracing_type="K",
        end_diaphragm_diagonal_section_type="ANGLE",
        end_diaphragm_diagonal_section_dims=angle, end_diaphragm_diagonal_thickness=5,
        end_diaphragm_top_chord_section_type="CHANNEL",
        end_diaphragm_top_chord_section_dims=small, end_diaphragm_top_chord_thickness=5,
        end_diaphragm_bottom_chord_section_type="ANGLE",
        end_diaphragm_bottom_chord_section_dims=small,
        end_diaphragm_bottom_chord_thickness=5,
        end_diaphragm_section="I_SECTION",
        end_diaphragm_dims=ISectionDimsDTO(depth=800, flange_width=250,
                                           web_thickness=12, flange_thickness=100),
    )
    params.update(overrides)
    return BridgeParametersDTO(**params)


def export(path, dto=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    result = {}
    handler = PlateGirderIfcExportHandler(dto or sample_bridge(), path,
                                          lambda ok, msg: result.update(ok=ok, msg=msg))
    handler.export()
    if not result.get("ok"):
        raise RuntimeError(result.get("msg"))
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out/bridge_with_substructure.ifc"
    print(export(out))
