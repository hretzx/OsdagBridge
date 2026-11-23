"""Show the substructure in a pythonocc window and check volumes with OpenCASCADE.

Run inside the Osdag conda environment (it has pythonocc):

    python tools/view_substructure_occ.py            # concrete + rebar
    python tools/view_substructure_occ.py --no-bars  # faster, concrete only
    python tools/view_substructure_occ.py --check    # no window, volumes only
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from substructure_demo import sample_bridge  # noqa: E402

from osdagbridge.core.bridge_components.sub_structure import occ_builder  # noqa: E402
from osdagbridge.core.ifc_export_bridge.bridge_cad_extraction import (  # noqa: E402
    PlateGirderIFCExtractor)


def main():
    with_bars = "--no-bars" not in sys.argv
    ex = PlateGirderIFCExtractor(sample_bridge())
    lines = ex.extract()["substructure"]
    shapes = occ_builder.build_shapes(lines, with_bars=with_bars)

    parts = {p.name: p for line in lines for p in line.parts}
    worst = 0.0
    for name, shape in shapes["concrete"]:
        v, design = occ_builder.shape_volume(shape), parts[name].volume
        worst = max(worst, abs(v - design) / design)
    print(f"{len(shapes['concrete'])} members, {len(shapes['rebar'])} bars; "
          f"largest OpenCASCADE vs design volume difference: {worst:.4%}")
    if "--check" in sys.argv:
        return

    from OCC.Display.SimpleGui import init_display
    display, start_display, _, _ = init_display()
    for _, shape in shapes["concrete"]:
        display.DisplayShape(shape, color="GRAY", transparency=0.55, update=False)
    for _, shape in shapes["rebar"]:
        display.DisplayShape(shape, color="RED", update=False)
    display.FitAll()
    start_display()


if __name__ == "__main__":
    main()
