#!/usr/bin/env python3
"""Which P&ID symbol draws which node kind or device type on the study diagram.

Pure: strings in, strings out. Nothing here knows about SVG or the page, so the map can be read by the
renderer, by the tool that embeds the symbols (tools/sync_symbols.py) and by the tests alike.

The symbols are the ones the EnergyFlowX Hydronic builder draws, authored in CAD and embedded here as
data (study_symbols.py), so a study and the builder show the same plant the same way. Only the kinds and
device types the Hydronic MCP server can actually produce are mapped. A JUNCTION is deliberately absent:
it is a connection, and a connection is a dot. Anything this file does not know keeps the renderer's
plain shapes, because a wrong symbol on a drawing is read as a statement about the plant, and is worse
than no symbol at all.

Standard library only, Python 3.9.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


class Glyph(NamedTuple):
    symbol: str             # the symbol's name, the builder's file name without .svg
    label: str              # what the key under the diagram calls it
    facing: Optional[str]   # which way its connections point when drawn unmirrored, see `mirrored`
    device: bool            # equipment rather than a node of the network


# Facing, as the symbols are drawn:
#   "out"      one connection, on the right: a boundary that feeds the network
#   "in"       one connection, on the left: a terminal the network feeds
#   "through"  in on the left, out on the right: a machine the flow passes through
#   None       no handedness worth correcting
GLYPHS = {
    "FIXED_PRESSURE": Glyph("fixed-pressure", "Pressure boundary", "out", False),
    "FIXED_DEMAND": Glyph("fixed-demand", "Demand", "in", False),
    "OUTLET": Glyph("outlet", "Outlet to a stated pressure", "in", False),
    "PRESSURE_TANK": Glyph("pressure-tank", "Receiver or expansion vessel", None, False),
    "PUMP": Glyph("pump-horizontal", "Pump", "through", True),
    "COMPRESSOR": Glyph("compressor-screw-recovery", "Compressor with heat recovery", "through", True),
    "HEATER": Glyph("wtr-boiler", "Heater or boiler", "through", True),
    "HEAT_EXCHANGER": Glyph("wtr-hx-plate", "Heat exchanger", None, True),
    "STORAGE_TANK": Glyph("storage-tank", "Storage tank", None, True),
}


def glyph_for(kind: object) -> Optional[Glyph]:
    """The glyph for a node kind or device type, matched exactly, or None."""
    if not isinstance(kind, str):
        return None
    return GLYPHS.get(kind.strip().upper())


def symbol_names() -> list[str]:
    """Every symbol the map names, once each, in a stable order."""
    seen: list[str] = []
    for glyph in GLYPHS.values():
        if glyph.symbol not in seen:
            seen.append(glyph.symbol)
    return seen


def mirrored(facing: Optional[str], sides: list[int], inflow_sides: list[int]) -> bool:
    """Whether a glyph should be drawn mirrored left to right.

    `sides` is the side each run touches the node from: -1 left, +1 right, 0 above or below.
    `inflow_sides` is the same for the runs whose fluid arrives at the node.

    A boundary whose runs all leave to its left, or a terminal fed only from its right, would otherwise
    point its connection away from the pipe it is connected to, and a pump whose fluid arrives from the
    right would show its triangle pointing against the flow the arrows show. A vertical connection says
    nothing about left and right, so it never mirrors anything.
    """
    if facing == "out":
        return bool(sides) and all(side < 0 for side in sides)
    if facing == "in":
        return bool(sides) and all(side > 0 for side in sides)
    if facing == "through":
        return bool(inflow_sides) and all(side > 0 for side in inflow_sides)
    return False
