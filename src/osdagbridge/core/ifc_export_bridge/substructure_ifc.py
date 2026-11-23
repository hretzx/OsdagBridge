"""Write the substructure (pier caps, piers, pile caps, piles, rebar) into IFC4.

Each concrete member becomes the IFC class an engineer would expect, with its
material, a concrete property set and its design volume, so that BIM tools can
schedule it and ``ifc_selfcheck`` can verify the geometry against the design:

    pier cap  -> IfcBeam      (ObjectType "PIERCAP")
    pier      -> IfcColumn    (ObjectType "PIER")
    pile cap  -> IfcFooting   (PredefinedType PILE_CAP)
    pile      -> IfcPile      (PredefinedType BORED)
    bar       -> IfcReinforcingBar (MAIN or LIGATURE), aggregated by its member

The members under one bearing line are aggregated into an IfcElementAssembly
placed in a "Substructure" storey next to the existing "Superstructure" one.
"""
from __future__ import annotations

import json

from osdagbridge.core.bridge_components.sub_structure.solids import Box, Cylinder, PrismX
from osdagbridge.core.ifc_export_bridge.bridge_geometry_mapper import create_ifc_guid

S = 0.001                     # mm -> m
CONCRETE_RGB = (0.72, 0.72, 0.70)
REBAR_RGB = (0.55, 0.12, 0.10)


class SubstructureIfcWriter:
    def __init__(self, ifc_file, mapper, owner_history, building):
        self.f = ifc_file
        self.m = mapper
        self.oh = owner_history
        place = self.f.createIfcLocalPlacement(
            building.ObjectPlacement, self.m.create_axis2placement_3d((0., 0., 0.)))
        self.storey = self.f.createIfcBuildingStorey(
            create_ifc_guid(), self.oh, Name="Substructure", ObjectPlacement=place)
        self.f.createIfcRelAggregates(create_ifc_guid(), self.oh,
                                      RelatingObject=building, RelatedObjects=[self.storey])
        self._materials = {}
        self._contained = []

    # ---------------------------------------------------------------- helpers
    def _material(self, name, category):
        if name not in self._materials:
            self._materials[name] = (self.f.createIfcMaterial(name, None, category), [])
        return self._materials[name]

    def _placement(self, origin, z_dir=(0., 0., 1.), x_dir=(1., 0., 0.)):
        return self.f.createIfcLocalPlacement(
            self.storey.ObjectPlacement,
            self.m.create_axis2placement_3d([v * S for v in origin], z_dir, x_dir))

    def _shape(self, items, rgb, kind="SweptSolid"):
        rep = self.f.createIfcShapeRepresentation(self.m._context3d, "Body", kind, items)
        self.m.apply_color(rep, rgb)
        return self.f.createIfcProductDefinitionShape(None, None, [rep])

    def _identity(self):
        return self.m.create_axis2placement_3d((0., 0., 0.))

    def _pset(self, element, name, values):
        props = []
        for key, val in values.items():
            if isinstance(val, bool):
                nv = self.f.createIfcBoolean(val)
            elif isinstance(val, (int, float)):
                nv = self.f.createIfcReal(float(val))
            else:
                nv = self.f.createIfcLabel(str(val))
            props.append(self.f.createIfcPropertySingleValue(key, None, nv, None))
        pset = self.f.createIfcPropertySet(create_ifc_guid(), self.oh, name, None, props)
        self.f.createIfcRelDefinesByProperties(create_ifc_guid(), self.oh, None, None,
                                               [element], pset)

    def _volume_qto(self, element, qto_name, volume_m3):
        q = self.f.createIfcQuantityVolume("NetVolume", None, None, volume_m3)
        eq = self.f.createIfcElementQuantity(create_ifc_guid(), self.oh, qto_name,
                                             None, None, [q])
        self.f.createIfcRelDefinesByProperties(create_ifc_guid(), self.oh, None, None,
                                               [element], eq)

    # ------------------------------------------------------------- geometry
    def _solid(self, solid):
        """(placement, swept solid, shape descriptor) for a model solid."""
        if isinstance(solid, Box):
            prof = self.f.createIfcRectangleProfileDef(
                "AREA", None, self.m.create_axis2placement_2d((solid.dx * S / 2, solid.dy * S / 2)),
                solid.dx * S, solid.dy * S)
            body = self.m.create_extruded_solid(prof, solid.dz * S, self._identity())
            return self._placement((solid.x0, solid.y0, solid.z0)), body, {
                "Shape": "BOX", "SizeX": solid.dx * S, "SizeY": solid.dy * S, "SizeZ": solid.dz * S}
        if isinstance(solid, Cylinder):
            prof = self.f.createIfcCircleProfileDef("AREA", None,
                                                    self.m.create_axis2placement_2d((0., 0.)),
                                                    solid.r * S)
            body = self.m.create_extruded_solid(prof, solid.h * S, self._identity())
            return self._placement((solid.cx, solid.cy, solid.z0)), body, {
                "Shape": "CYLINDER", "Radius": solid.r * S, "Height": solid.h * S}
        if isinstance(solid, PrismX):
            pts = [self.f.createIfcCartesianPoint((y * S, z * S)) for y, z in solid.yz]
            poly = self.f.createIfcPolyline(pts + [pts[0]])
            prof = self.f.createIfcArbitraryClosedProfileDef("AREA", "PierCapElevation", poly)
            body = self.m.create_extruded_solid(prof, solid.length * S, self._identity())
            # Local Z (extrusion) = global X, local X = global Y, so local Y = global Z.
            place = self._placement((solid.x0, 0., 0.), z_dir=(1., 0., 0.), x_dir=(0., 1., 0.))
            return place, body, {"Shape": "PRISM_X", "Length": solid.length * S,
                                 "ElevationArea": solid.area * S * S}
        raise TypeError(f"unknown solid {type(solid).__name__}")

    # -------------------------------------------------------------- members
    def _member(self, part):
        place, body, shape_info = self._solid(part.solid)
        rep = self._shape([body], CONCRETE_RGB)
        common = dict(GlobalId=create_ifc_guid(), OwnerHistory=self.oh, Name=part.name,
                      ObjectPlacement=place, Representation=rep)
        if part.kind == "PILE":
            el = self.f.createIfcPile(**common, PredefinedType="BORED")
            qto = "Qto_PileBaseQuantities"
        elif part.kind == "PILE_CAP":
            el = self.f.createIfcFooting(**common, PredefinedType="PILE_CAP")
            qto = "Qto_FootingBaseQuantities"
        elif part.kind == "PIER":
            el = self.f.createIfcColumn(**common, ObjectType="PIER", PredefinedType="USERDEFINED")
            qto = "Qto_ColumnBaseQuantities"
        elif part.kind == "PIER_CAP":
            el = self.f.createIfcBeam(**common, ObjectType="PIERCAP", PredefinedType="USERDEFINED")
            qto = "Qto_BeamBaseQuantities"
        else:
            raise ValueError(part.kind)
        self._material(f"Concrete {part.grade}", "concrete")[1].append(el)
        self._pset(el, "Pset_ConcreteElementGeneral",
                   {"StrengthClass": part.grade, "ConcreteCover": part.cover * S})
        info = {"Kind": part.kind, "DesignVolume": part.volume * S ** 3, **shape_info}
        info.update({k: v * S for k, v in part.props.items()})
        self._pset(el, "Pset_OsdagSubstructure", info)
        self._volume_qto(el, qto, part.volume * S ** 3)
        return el

    def _bar(self, bar, rebar_grade):
        pts = [self.f.createIfcCartesianPoint(tuple(v * S for v in p)) for p in bar.points]
        # Bends are already rounded in the bar's axis (see fillet_polyline);
        # IfcSweptDiskSolid is the most widely supported rebar geometry.
        sweep = self.f.createIfcSweptDiskSolid(self.f.createIfcPolyline(pts),
                                               bar.d / 2 * S, None, None, None)
        rep = self._shape([sweep], REBAR_RGB, "AdvancedSweptSolid")
        el = self.f.createIfcReinforcingBar(
            GlobalId=create_ifc_guid(), OwnerHistory=self.oh, Name=bar.name,
            ObjectPlacement=self._placement((0., 0., 0.)), Representation=rep,
            SteelGrade=rebar_grade, NominalDiameter=bar.d * S,
            CrossSectionArea=3.141592653589793 * (bar.d / 2 * S) ** 2,
            BarLength=bar.length * S, PredefinedType=bar.role)
        self._material(f"Steel {rebar_grade}", "steel")[1].append(el)
        return el

    # ---------------------------------------------------------------- write
    def write(self, support_lines, rebar_grade="Fe500"):
        for line in support_lines:
            assembly = self.f.createIfcElementAssembly(
                create_ifc_guid(), self.oh, f"Substructure {line.name}", None, "PIER",
                self._placement((0., 0., 0.)), None, None, None, "USERDEFINED")
            self._pset(assembly, "Pset_OsdagSubstructure", {
                "SupportLine": line.name, "CapCentreX": line.x * S,
                "BearingUndersideZ": line.bearing_z * S,
                "BearingPoints": json.dumps([[round(x * S, 6), round(y * S, 6)] for x, y
                                             in zip(line.bearing_xs, line.bearing_ys)]),
                "Issues": "; ".join(line.issues) or "none"})
            members = []
            for part in line.parts:
                el = self._member(part)
                members.append(el)
                if part.bars:
                    bars = [self._bar(b, rebar_grade) for b in part.bars]
                    self.f.createIfcRelAggregates(create_ifc_guid(), self.oh,
                                                  RelatingObject=el, RelatedObjects=bars)
            self.f.createIfcRelAggregates(create_ifc_guid(), self.oh,
                                          RelatingObject=assembly, RelatedObjects=members)
            self._contained.append(assembly)
        if self._contained:
            self.f.createIfcRelContainedInSpatialStructure(
                create_ifc_guid(), self.oh, None, None, self._contained, self.storey)
        for mat, elements in self._materials.values():
            if elements:
                self.f.createIfcRelAssociatesMaterial(create_ifc_guid(), self.oh, None,
                                                      None, elements, mat)
