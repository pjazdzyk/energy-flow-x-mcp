#!/usr/bin/env python3
"""Invariants of the riser-diagram layout and of the drawing made from it.

Run: python3 scripts/test_study_layout.py

The first picture the renderer produced of a real sprinkler network put 22 nodes on one row and 80
labels on top of each other. Nothing here is a style check: each property below is one that, broken,
gives a picture that cannot be read, and the last group parses the SVG the renderer emits and fails on
any two labels that touch, on any run that crosses a label, on any two nodes that share a spot.

Standard library only, so the skill's own tests run anywhere the skill does.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_study import render  # noqa: E402
from study_layout import layout  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
        FAILURES.append(name)


# ---------------------------------------------------------------------------------------------
# Fixtures: the shapes that broke the old picture and the shapes a ring main has
# ---------------------------------------------------------------------------------------------


def sprinkler(grid: bool = False, branches: int = 3, heads: int = 6) -> dict:
    """A pumped tree at floor level feeding branch lines on a ceiling, optionally closed into a grid."""
    nodes = [
        {"id": "tank", "kind": "FIXED_PRESSURE", "elevation_m": 0.5, "pressure_kPa": 101.3, "flow_kg_s": -30, "isSupply": True},
        {"id": "pump.in", "kind": "PUMP inlet", "elevation_m": 0.0, "pressure_kPa": 100.0},
        {"id": "pump.out", "kind": "PUMP outlet", "elevation_m": 0.0, "pressure_kPa": 460.0},
        {"id": "riserBase", "kind": "JUNCTION", "elevation_m": 0.5, "pressure_kPa": 455.0},
        {"id": "riserTop", "kind": "JUNCTION", "elevation_m": 6.0, "pressure_kPa": 392.0},
    ]
    edges = [
        {"id": "suction", "from": "tank", "to": "pump.in", "size": "DN150", "flow_kg_s": 30, "velocity_m_s": 1.5, "dp_kPa": 1.3},
        {"id": "pump", "from": "pump.in", "to": "pump.out", "size": "fire pump", "flow_kg_s": 30, "dp_kPa": -360},
        {"id": "feed", "from": "pump.out", "to": "riserBase", "size": "DN150", "flow_kg_s": 30, "velocity_m_s": 1.5, "dp_kPa": 5},
        {"id": "riser", "from": "riserBase", "to": "riserTop", "size": "DN100", "flow_kg_s": 30, "velocity_m_s": 3.3, "dp_kPa": 63},
    ]
    previous = "riserTop"
    for b in range(1, branches + 1):
        cm = f"cm{b}"
        nodes.append({"id": cm, "kind": "JUNCTION", "elevation_m": 6.0, "pressure_kPa": 380 - 10 * b})
        edges.append({"id": f"cross{b}", "from": previous, "to": cm, "size": "DN80", "flow_kg_s": 30 - 10 * (b - 1), "dp_kPa": 8})
        previous = cm
        upstream = cm
        for h in range(1, heads + 1):
            head = f"h{b}{h}"
            nodes.append({"id": head, "kind": "K80 head", "elevation_m": 6.0, "pressure_kPa": 340 - 10 * h - 5 * b, "flow_kg_s": 1.3})
            edges.append({"id": f"b{b}s{h}", "from": upstream, "to": head, "size": "DN40" if h < 4 else "DN25",
                          "flow_kg_s": 1.3 * (heads - h + 1), "velocity_m_s": 2.0, "dp_kPa": 9})
            upstream = head
    if grid:
        nodes.append({"id": "cmB", "kind": "JUNCTION", "elevation_m": 6.0, "pressure_kPa": 360})
        edges.append({"id": "feedB", "from": "riserTop", "to": "cmB", "size": "DN80", "flow_kg_s": 9, "dp_kPa": 20})
        previous = "cmB"
        for b in range(1, branches + 1):
            far = f"h{b}{heads}"
            edges.append({"id": f"closer{b}", "from": previous, "to": far, "size": "DN50", "flow_kg_s": 3 if b == 1 else -0.4, "dp_kPa": 2})
            previous = far
    return {"title": "sprinkler", "converged": True, "iterations": 6, "nodes": nodes, "edges": edges,
            "criticalPath": {"from": "riserBase", "to": f"h{branches}{heads}", "totalDrop_kPa": 200, "residual_kPa": 190,
                             "elements": ["riser", "cross1", "b1s1"]}}


def ring(size: int = 8) -> dict:
    """A ring main with a divide: the flow runs clockwise into one half and anticlockwise into the other."""
    # Long ids on purpose: a label must stay clear of the tracks however long the name is.
    nodes = [{"id": "plant-room", "kind": "FIXED_PRESSURE", "elevation_m": 0, "pressure_kPa": 500, "flow_kg_s": -12, "isSupply": True}]
    edges = []
    previous = "plant-room"
    for k in range(1, size + 1):
        nodes.append({"id": f"building-{k}", "kind": "FIXED_DEMAND", "elevation_m": 3.0 * (k % 3), "pressure_kPa": 480 - 8 * min(k, size - k + 1), "flow_kg_s": 1.5})
        # Clockwise into the first half, anticlockwise into the second: the divide is the middle run.
        flow = 1.5 * (size // 2 - k + 1) if k <= size // 2 else -1.5 * (k - size // 2 - 1)
        edges.append({"id": f"r{k}", "from": previous, "to": f"building-{k}", "size": "DN100", "flow_kg_s": flow, "dp_kPa": 3})
        previous = f"building-{k}"
    edges.append({"id": "rclose", "from": previous, "to": "plant-room", "size": "DN100", "flow_kg_s": -1.5 * (size - size // 2), "dp_kPa": 3})
    return {"title": "ring", "converged": True, "nodes": nodes, "edges": edges}


def flat() -> dict:
    study = sprinkler()
    for node in study["nodes"]:
        node.pop("elevation_m", None)
    return study


# ---------------------------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------------------------


def test_every_branch_has_its_own_lane() -> None:
    print("lanes")
    study = sprinkler()
    grid = layout(study["nodes"], study["edges"])
    spots = list(grid.positions.values())
    check("no two nodes share a spot", len(spots) == len(set(spots)))
    leaves = {f"h{b}6" for b in (1, 2, 3)}
    leaf_lanes = [grid.positions[i][1] for i in leaves]
    check("each branch line ends in a lane of its own", len(set(leaf_lanes)) == len(leaves))
    for b in (1, 2, 3):
        lanes = {grid.positions[f"h{b}{h}"][1] for h in range(1, 7)}
        check(f"branch {b} runs along one lane", len(lanes) == 1, f"lanes {sorted(lanes)}")
    ranks = [grid.positions[f"h1{h}"][0] for h in range(1, 7)]
    check("and reads left to right, one step per head", ranks == sorted(ranks) and len(set(ranks)) == 6)
    check("the pump ports are not pushed off the drawing", "pump.in" in grid.positions and "pump.out" in grid.positions)


def test_elevation_is_up_the_page_without_flattening_a_floor() -> None:
    print("elevation bands")
    grid = layout(sprinkler()["nodes"], sprinkler()["edges"])
    check("bands are used when elevations differ", grid.use_elevation)
    z = {n["id"]: n["elevation_m"] for n in sprinkler()["nodes"]}
    below = [grid.positions[i][1] for i in grid.positions if z[i] < 6.0]
    above = [grid.positions[i][1] for i in grid.positions if z[i] == 6.0]
    check("every node on the ceiling is above every node on the floor", min(above) > max(below))
    check("the ceiling is not one row", len(set(above)) > 1, "that is the picture this replaces")
    riser = grid.routes["riser"]
    check("the riser is drawn as a vertical", any(a[0] == b[0] and a[1] != b[1] for a, b in zip(riser, riser[1:])))
    check("bands are reported lowest first", [b[0] for b in grid.bands] == sorted(b[0] for b in grid.bands))
    no_z = layout(flat()["nodes"], flat()["edges"])
    check("without elevations it is a topology sketch and says so", not no_z.use_elevation and not no_z.bands)


def test_a_ring_opens_where_the_flow_divides() -> None:
    print("rings and grids")
    study = ring()
    grid = layout(study["nodes"], study["edges"])
    closers = [e["id"] for e in study["edges"] if e["id"] not in grid.tree_edges]
    check("exactly one edge of a ring is a closer", len(closers) == 1, str(closers))
    lightest = min(study["edges"], key=lambda e: abs(e["flow_kg_s"]))["id"]
    check("and it is the one carrying the least flow, which is the divide", closers == [lightest], f"{closers} vs {lightest}")
    check("the closer is routed, not drawn straight through the drawing", len(grid.routes[closers[0]]) > 2)
    for eid, points in grid.routes.items():
        check(f"{eid} is orthogonal", all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:])))
    sprinkler_grid = layout(sprinkler(grid=True)["nodes"], sprinkler(grid=True)["edges"])
    channels = {}
    for eid in ("closer1", "closer2", "closer3"):
        if eid not in sprinkler_grid.tree_edges:
            horizontal = [seg for seg in zip(sprinkler_grid.routes[eid], sprinkler_grid.routes[eid][1:]) if seg[0][1] == seg[1][1] and seg[0][1] % 1 == 0.5]
            for (x0, y), (x1, _) in horizontal:
                channels.setdefault(y, []).append((min(x0, x1), max(x0, x1)))
    overlapping = any(not (b1 < a2 or b2 < a1) for spans in channels.values() for (a1, b1) in spans for (a2, b2) in spans if (a1, b1) != (a2, b2))
    check("two closers never share a channel over the same span", not overlapping)


def test_direction_is_kept_from_the_edge_not_the_tree() -> None:
    print("direction")
    study = sprinkler(grid=True)
    grid = layout(study["nodes"], study["edges"])
    for edge in study["edges"]:
        route = grid.routes[edge["id"]]
        check(f"{edge['id']} starts at its from and ends at its to",
              route[0] == tuple(grid.positions[edge["from"]]) and route[-1] == tuple(grid.positions[edge["to"]]))
        if FAILURES:
            break


def test_degenerate_graphs_still_lay_out() -> None:
    print("degenerate graphs")
    lone = layout([{"id": "a"}], [])
    check("one node", lone.positions == {"a": (0, 0)} and lone.ranks == 1 and lone.lanes == 1)
    two = layout([{"id": "a"}, {"id": "b"}], [])
    check("two islands get their own lanes", two.positions["a"] != two.positions["b"])
    loop = layout([{"id": "a"}], [{"id": "self", "from": "a", "to": "a"}])
    check("a self loop is ignored rather than routed", "self" not in loop.routes)
    ghost = layout([{"id": "a"}], [{"id": "e", "from": "a", "to": "ghost"}])
    check("an edge to a missing node is skipped", "e" not in ghost.routes and "a" in ghost.positions)
    check("nothing to draw is nothing, not a crash", layout([], []).positions == {})


# ---------------------------------------------------------------------------------------------
# The drawing: parse the SVG the renderer emits and check that it can be read
# ---------------------------------------------------------------------------------------------

_TEXT = re.compile(r'<text class="([^"]+)" x="([-\d.]+)" y="([-\d.]+)"(?: text-anchor="middle")?>([^<]*)</text>')
_POLY = re.compile(r'<polyline class="([^"]+)" points="([^"]+)"')
_NODE = re.compile(r'<(?:circle|rect|polygon) class="node[^"]*"[^>]*?(?:cx="([-\d.]+)" cy="([-\d.]+)"|x="([-\d.]+)" y="([-\d.]+)"|points="([-\d.]+),([-\d.]+))')
_CALLOUT = re.compile(r'<rect class="callout" x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" height="([-\d.]+)"')
_FONT = {"node-label": 12.0, "edge-label": 10.5, "datum-label": 11.0, "callout-label": 11.0}


def _svg(page: str) -> str:
    return page[page.index("<svg"):page.index("</svg>")]


def boxes(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Text boxes (name, x0, y0, x1, y1), a character-width estimate that errs on the wide side."""
    out = []
    for match in _TEXT.finditer(svg):
        cls, x, y, text = match.group(1), float(match.group(2)), float(match.group(3)), match.group(4)
        size = _FONT.get(cls, 12.0)
        width = len(text) * 0.6 * size
        middle = 'text-anchor="middle"' in match.group(0)
        x0 = x - width / 2 if middle else x
        out.append((f"{cls} {text}", x0, y - size * 0.8, x0 + width, y + size * 0.25))
    return out


def segments(svg: str) -> list[tuple[str, float, float, float, float]]:
    out = []
    for match in _POLY.finditer(svg):
        points = [tuple(float(v) for v in p.split(",")) for p in match.group(2).split()]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            out.append((match.group(1), min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return out


def overlaps(a: tuple, b: tuple, slack: float = 1.0) -> bool:
    return not (a[3] < b[1] + slack or b[3] < a[1] + slack or a[4] < b[2] + slack or b[4] < a[2] + slack)


def test_the_drawing_can_be_read() -> None:
    for name, study in (("the sprinkler tree", sprinkler()), ("the sprinkler grid", sprinkler(grid=True)),
                        ("a ring main", ring()), ("a wide tree", sprinkler(branches=5, heads=9)), ("no elevations", flat())):
        print(f"the drawing of {name}")
        svg = _svg(render(study))
        labels = boxes(svg)
        clashes = [(a[0], b[0]) for i, a in enumerate(labels) for b in labels[i + 1:] if overlaps(a, b)]
        check("no two labels touch", not clashes, f"{len(clashes)} pairs, first {clashes[:3]}")
        runs = segments(svg)
        crossed = [(l[0], r[0]) for l in labels for r in runs if overlaps(l, r, slack=0.0)]
        check("no run crosses a label", not crossed, f"{len(crossed)}, first {crossed[:3]}")
        callout_boxes = [("callout", float(m.group(1)), float(m.group(2)), float(m.group(1)) + float(m.group(3)),
                          float(m.group(2)) + float(m.group(4))) for m in _CALLOUT.finditer(svg)]
        crossed = [(c, r[0]) for c in callout_boxes for r in runs if overlaps(c, r, slack=0.0)]
        check("no run crosses a call-out box", not crossed, f"{len(crossed)}, first {crossed[:2]}")
        width = float(re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).group(1))
        height = float(re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).group(2))
        inside = all(0 <= b[1] and b[3] <= width and 0 <= b[2] and b[4] <= height for b in labels + callout_boxes)
        check("everything is inside the canvas", inside)
        check("the canvas grew with the network rather than squeezing it", width >= 96 * (len(study["nodes"]) ** 0.5))
        check("every node is drawn", len(_NODE.findall(svg)) == len(study["nodes"]))
        check("every edge is drawn", len(_POLY.findall(svg)) == len(study["edges"]))


def test_the_page_says_what_the_picture_means() -> None:
    print("the caption")
    page = render(sprinkler(grid=True))
    check("names the bands", "Elevation up the page in bands" in page)
    check("says what a dashed run is", "closes a ring or a grid" in page)
    check("says what the fill is", "Node fill is pressure" in page)
    check("names the critical path when there is one", "critical path" in page)
    check("tells the reader the figures are on hover and in the schedules", "Hover a node or a run" in page)
    check("still calls it a schematic", "not a P&amp;ID" in page)
    check("a closer is drawn dashed", 'class="run closer"' in page)
    check("the critical path is marked", 'class="run critical"' in page)
    check("the supply and the far end carry call-outs", page.count('class="callout"') >= 2)


def main() -> int:
    for test in [
        test_every_branch_has_its_own_lane,
        test_elevation_is_up_the_page_without_flattening_a_floor,
        test_a_ring_opens_where_the_flow_divides,
        test_direction_is_kept_from_the_edge_not_the_tree,
        test_degenerate_graphs_still_lay_out,
        test_the_drawing_can_be_read,
        test_the_page_says_what_the_picture_means,
    ]:
        test()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed: " + ", ".join(FAILURES))
        return 1
    print("all invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
