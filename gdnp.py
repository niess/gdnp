#!/usr/bin/env python
# -*- coding: utf-8 -*
#
# Copyright (c) 2018 Université Clermont Auvergne, CNRS/IN2P3, LPC
# Author: Valentin NIESS (niess@in2p3.fr)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import re
import sys
import textwrap
import xml.etree.ElementTree as ET


def load_gdml(path):
    """Load the content of a GDML file and sort the data by ownership"""

    # Parse the GDML file
    tree = ET.parse(path)
    gdml = tree.getroot()

    # Map solids
    solids = {}
    for solid in gdml.find("solids"):
        solids[solid.attrib["name"]] = solid

    # Map materials
    materials = {}
    for material in gdml.find("materials"):
        materials[material.attrib["name"]] = material

    # Map the cells
    cells = {}
    for structure in gdml.find("structure"):
        # Get the geometry
        solid_ref = structure.find("solidref").attrib["ref"]
        solid = solids[solid_ref]
        if solid.tag in ("intersection", "subtraction", "union"):
            # This is a logical volume
            first = solids[solid.find("first").attrib["ref"]]
            second = solids[solid.find("second").attrib["ref"]]
            solid = (solid.tag, (first.tag, first.attrib),
                     (second.tag, second.attrib), solid.find("position").attrib)
        else:
            # This is a base volume
            solid = (solid.tag, solid.attrib)

        # Get the material
        material_ref = structure.find("materialref").attrib["ref"]
        material = materials[material_ref]

        # Get any children
        children = structure.findall("physvol")

        # Add this cell
        ref = structure.attrib["name"]
        name = re.sub("0x.......", "", ref)
        cells[ref] = {"name": name, "volume": solid, "position": None,
                      "material": material, "children": children}

    # Set the children positions, w.r.t. their parent
    for name, cell in cells.iteritems():
        if not cell["children"]:
            continue
        c = []
        for child in children:
            child_ref = child.find("volumeref").attrib["ref"]
            sub_cell = cells[child_ref]
            position = child.find("position")
            if position is not None:
                sub_cell["position"] = position.attrib
            c.append(sub_cell)
        cell["children"] = c

    # Get the world cell
    world_ref = gdml.find("setup").find("world").attrib["ref"]
    world = cells[world_ref]

    return world


def dump_mcnp(gdml, world, path=None):
    """Dump sorted GDML data in MCNP format"""

    class MCNPSurface:
        # Global dictionary of all unique surfaces
        surfaces = {}

        # Fetch or register the surface
        def __init__(self, args):
            args = tuple(map(str, args))
            try:
                s = self.surfaces[args]
            except KeyError:
                self.surfaces[args] = self
                self.index = len(self.surfaces)
                self.args = args
            else:
                self.index = s.index
                self.args = s.args

    class MCNPCell:
        # Global list of all cells
        cells = []

        # Register a new cell
        def __init__(self, name, surfaces, material, density):
            self.name = name
            self.index = len(self.cells) + 1
            self.material = str(material)
            self.density = str(density)
            self.surfaces = " ".join(map(str, surfaces))
            self.cells.append(self)

    class MCNPMaterial:
        # Global dictionary of all materials
        materials = {}

        # Fetch or register the material
        def __init__(self, gdml):
            name = gdml.attrib["name"]
            try:
                m = self.materials[name]
            except KeyError:
                self.materials[name] = self
                self.index = len(self.materials)
                d = gdml.find("D").attrib
                self.density = float(d["value"]) * convert_gdml_unit(d["unit"])
                self.name = re.sub("0x.......", "", name)
            else:
                self.index = m.index
                self.density = m.density
                self.name = m.name

    # Convert GDML structures to MCNP cells, recursively
    def process_cell(cell):
        # Loop over child cells and get their reverted outer surface indices
        inner_surfaces = []
        for sub_cell in cell["children"]:
            inner_surfaces.append(process_cell(sub_cell))

        # Build the volume and register the cell outer surfaces
        surfaces = convert_gdml_volume(cell["volume"], cell["position"])
        outer_surfaces = [s[0] * MCNPSurface(s[1:]).index for s in surfaces]

        # Fetch or register the material
        material = MCNPMaterial(cell["material"])

        # Register the new cell
        surfaces = outer_surfaces + inner_surfaces
        MCNPCell(cell["name"], surfaces, material.index, material.density)

        return "".join(("(", ":".join([str(-i) for i in outer_surfaces]), ")"))

    process_cell(world)

    # Instanciate the writer
    if path is not None:
        outfile = open(path, "w+")

    wrapper = textwrap.TextWrapper(width=79, subsequent_indent=6 * " ")

    def write(*args):
        text = wrapper.fill(" ".join(args))
        if path is None:
            print text
        else:
            outfile.write(text)
            outfile.write("\n")

    def format_index(index):
        return "{:5d}".format(index)

    # Dump the header
    filename = os.path.basename(gdml).upper()
    write("----- CONVERTED BY GDNP.PY FROM", filename[:47])
    write("")

    # Dump the cell cards
    write("C", 77 * "-")
    write("C --- CELL CARDS")
    write("C", 77 * "-")
    for cell in MCNPCell.cells:
        write("C ---", cell.name)
        write(format_index(cell.index), cell.material, cell.density,
              cell.surfaces)
    write("")

    # Dump the surface cards
    write("C", 77 * "-")
    write("C --- SURFACE CARDS")
    write("C", 77 * "-")
    surfaces = [(s.index, s.args) for s in MCNPSurface.surfaces.values()]
    for surface in sorted(surfaces):
        write(format_index(surface[0]), " ".join(surface[1]))
    write("")

    # Dump the material headers
    write("C", 77 * "-")
    write("C --- DATA CARDS")
    write("C", 77 * "-")
    materials = [(m.index, m.name) for m in MCNPMaterial.materials.values()]
    for material in sorted(materials):
        write("C --- MATERIAL :", material[1])
        write("M{:<4d}".format(material[0]), "$ TODO: fill me")

    if path is not None:
        outfile.close()


def convert_gdml_unit(unit):
    """Convert a GDML unit to MCNP system"""
    units = {"m": 1E+02, "cm": 1., "mm": 1E-01, "g/cm3": 1.}
    return units[unit]


def convert_gdml_position(position):
    """Convert a GDML position to a 3-tuple"""
    unit = convert_gdml_unit(position["unit"])
    return map(lambda a: float(position[a]) * unit, ("x", "y", "z"))


class NotImplemented(Exception):
    pass


def convert_gdml_volume(volume, position):
    """Convert an arbitrary GDML volume to MCNP surfaces"""

    if position is not None:
        placement = convert_gdml_position(position)
    else:
        placement = 3 * (0.,)

    # Check for a binary volume
    tag = volume[0]
    if tag == "intersection":
        transform = convert_gdml_position(volume[3])
        t = {"x": str(placement[0] + transform[0]),
             "y": str(placement[1] + transform[1]),
             "z": str(placement[2] + transform[2]),
             "unit": "cm"}
        sections = convert_gdml_volume(volume[1], position)
        sections += convert_gdml_volume(volume[2], t)
        return sections

    # Fetch the converter and call it
    try:
        convert = globals()["convert_gdml_" + tag]
    except KeyError:
        raise NotImplemented(tag)
    else:
        return convert(volume[1], placement)


def convert_gdml_tube(volume, placement):
    """Convert a GDML tube to MCNP surfaces
    """
    if (float(volume["startphi"]) != 0) or (float(volume["deltaphi"]) < 360):
        raise NotImplemented("extruded tube")
    if (placement[0] != 0) or (placement[1] != 0):
        raise NotImplemented("offset tube")

    unit = convert_gdml_unit(volume["lunit"])
    r, dz = map(lambda a: float(volume[a]) * unit, ("rmax", "z"))
    return [
        (-1, "CZ", r),
        (+1, "PZ", -0.5 * dz + placement[2]),
        (-1, "PZ", +0.5 * dz + placement[2])
    ]


def convert_gdml_ellipsoid(volume, placement):
    """Convert a GDML ellipsoid to MCNP surfaces
    """
    ax, by, cz, z0, z1 = map(lambda s: float(volume[s]),
                             ("ax", "by", "cz", "zcut1", "zcut2"))
    sections = [(-1, "SQ", 1 / ax**2, 1 / by**2, 1 / cz**2, 0, 0, 0, 1,
                 placement[0], placement[1], placement[2])]

    if z0 > -cz:
        sections.append((+1, "PZ", z0 + placement[2]))
    if z1 < cz:
        sections.append((-1, "PZ", z1 + placement[2]))

    return sections


if __name__ == "__main__":
    if len(sys.argv) < 2:
        helper = ("Usage: gdnp.py [FILE.GDML] ([MCNP.CARD])",
                  "Convert a FILE.GDML geometry to an MCNP.CARD, or dump the "
                  "result to stdout.", "")
        sys.stderr.write("\n".join(helper))
        sys.exit(1)

    gdml = sys.argv[1]
    world = load_gdml(gdml)
    try:
        out = sys.argv[2]
    except IndexError:
        out = None
    dump_mcnp(gdml, world, out)
