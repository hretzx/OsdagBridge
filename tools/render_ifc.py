"""Render the exported IFC to PNG pictures for the README (matplotlib, no GUI).

    python tools/render_ifc.py out/bridge_with_substructure.ifc docs/images
"""
import os
import sys

import ifcopenshell
import ifcopenshell.geom
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

SUB = ("IfcPile", "IfcFooting", "IfcColumn")


def meshes(f, elements):
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    out = []
    for e in elements:
        try:
            g = ifcopenshell.geom.create_shape(st, e).geometry
        except Exception:
            continue
        v, fa = g.verts, g.faces
        pts = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
        out.append((e, [[pts[fa[i]], pts[fa[i + 1]], pts[fa[i + 2]]] for i in range(0, len(fa), 3)]))
    return out


def is_sub(e):
    return e.is_a() in SUB or (e.is_a("IfcBeam") and e.ObjectType == "PIERCAP")


def draw(ax, tris, color, alpha, lw=0.0, edge=None):
    pc = Poly3DCollection(tris, facecolor=color, alpha=alpha, linewidths=lw,
                          edgecolor=edge or color)
    ax.add_collection3d(pc)


def frame(ax, tris_all, elev, azim):
    xs = [p[0] for t in tris_all for p in t]
    ys = [p[1] for t in tris_all for p in t]
    zs = [p[2] for t in tris_all for p in t]
    ax.set_xlim(min(xs), max(xs)); ax.set_ylim(min(ys), max(ys)); ax.set_zlim(min(zs), max(zs))
    ax.set_box_aspect((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)), zoom=0.85)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def main(path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    f = ifcopenshell.open(path)
    elements = [e for e in f.by_type("IfcElement") if e.Representation
                and not e.is_a("IfcReinforcingBar") and not e.is_a("IfcElementAssembly")]
    m = meshes(f, elements)

    # 1. whole bridge: superstructure blue-grey, substructure warm concrete
    fig = plt.figure(figsize=(14, 8), dpi=150)
    ax = fig.add_subplot(projection="3d")
    every = []
    for e, tris in m:
        sub = is_sub(e)
        draw(ax, tris, "#d9a679" if sub else "#8fa3b8", 1.0 if sub else 0.9,
             0.15, "#7a5233" if sub else "#4d5d6e")
        every += tris
    frame(ax, every, 18, -60)
    ax.set_title("OsdagBridge sample bridge with the new substructure (orange)", fontsize=13)
    fig.savefig(os.path.join(out_dir, "bridge_full.png"), bbox_inches="tight")
    plt.close(fig)

    # 2. one pier, see-through, with its reinforcement
    name = "A1"
    parts = [e for e, _ in m if is_sub(e) and (e.Name.startswith(name + " ") or
                                               (e.is_a("IfcBeam") and e.Name.startswith("A ")))]
    bars = [b for p in parts if not p.is_a("IfcBeam") for r in p.IsDecomposedBy for b in r.RelatedObjects
            if b.is_a("IfcReinforcingBar")]
    fig = plt.figure(figsize=(9, 15), dpi=150)
    ax = fig.add_subplot(projection="3d")
    every = []
    for e, tris in m:
        if e in parts and not e.is_a("IfcBeam"):
            draw(ax, tris, "#c9c9c4", 0.12, 0.3, "#8a8a85")
            every += tris
    for _, tris in meshes(f, bars):
        draw(ax, tris, "#b22a1f", 1.0)
    frame(ax, every, 12, -55)
    ax.set_title("Pier A1, its pile cap and four piles, with reinforcement", fontsize=12)
    fig.savefig(os.path.join(out_dir, "pier_rebar.png"), bbox_inches="tight")
    plt.close(fig)
    print("written to", out_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "docs/images")
