#!/usr/bin/env python3
"""Lay out a solved network as a riser diagram: an orthogonal schematic on a grid of ranks and lanes.

Pure. Nodes and edges in, grid coordinates and routed polylines out. Nothing here knows about SVG,
pixels or fonts, which is what lets it be tested on its own and drawn by anything.

The picture engineers draw by hand, and the only layout family in which a branch line can never
collide with another one:

- A spanning tree from the supply, grown by flow: at every step the untaken edge carrying the most
  flow is added (Prim). On a ring or a grid the edges left out are the ones carrying the least, which
  is where the flow divides, so the drawing opens each loop at the one place a ring is meant to be
  read open. The left-out edges are drawn as routed closers.
- Lanes. Walking the tree, the child with the largest subtree continues straight in its parent's
  lane, the others branch off into lanes of their own, and every leaf gets a lane to itself. A run
  and its branches therefore never share a row with anything from another branch.
- Ranks. x is depth in the tree, one step per node, so a run reads left to right.
- Elevation bands. Nodes at a higher elevation are lifted above everything at a lower one, with the
  tree edge into them drawn as a vertical, so elevation is still up the page without flattening a
  whole floor onto one row. With no elevations, or one, the tree alone is the picture.
- Closers are routed orthogonally: out of the node on the side where no tree run lies along its
  lane, up or down a free track between ranks, along a free half-lane channel, and in the same way
  into the other node. Tracks and channels are booked, so two closers never lie on one line and a
  closer never lies on a tree bus.

Standard library only, Python 3.9.
"""

from __future__ import annotations

import heapq
import math
from typing import Any, Optional

Point = tuple[float, float]


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def supply_id(nodes: list[dict], edges: list[dict]) -> Optional[str]:
    """The node the network is fed from: an explicit flag, then a pressure boundary, then any node."""
    for node in nodes:
        if node.get("isSupply"):
            return _text(node.get("id"))
    for node in nodes:
        if "PRESSURE" in _text(node.get("kind")).upper():
            return _text(node.get("id"))
    if nodes:
        return _text(nodes[0].get("id"))
    if edges:
        return _text(edges[0].get("from"))
    return None


class Layout:
    """The result: everything in grid units (ranks across, lanes up).

    positions   node id -> (rank, lane)
    routes      edge id -> polyline from the edge's `from` to its `to`
    tree_edges  ids of the edges in the spanning forest; the rest are closers
    bands       (elevation, lowest lane, highest lane) per elevation, ascending; empty without elevations
    ranks, lanes  grid extent
    use_elevation  whether bands mean anything
    """

    def __init__(self) -> None:
        self.positions: dict[str, tuple[int, int]] = {}
        self.routes: dict[str, list[Point]] = {}
        self.tree_edges: set[str] = set()
        self.bands: list[tuple[float, int, int]] = []
        self.ranks = 0
        self.lanes = 0
        self.use_elevation = False


def _spanning_forest(ids: list[str], edges: list[dict], supply: Optional[str]) -> tuple[dict, dict, set]:
    """Prim from the supply, heaviest flow first. Returns parent, children, tree edge ids."""
    adjacency: dict[str, list[tuple[float, int, str, str]]] = {i: [] for i in ids}
    for order, edge in enumerate(edges):
        a, b, eid = _text(edge.get("from")), _text(edge.get("to")), _text(edge.get("id"))
        if a in adjacency and b in adjacency and a != b:
            weight = abs(_num(edge.get("flow_kg_s")) or 0.0)
            adjacency[a].append((weight, order, b, eid))
            adjacency[b].append((weight, order, a, eid))

    parent: dict[str, Optional[str]] = {}
    children: dict[str, list[str]] = {i: [] for i in ids}
    tree: set[str] = set()
    roots = ([supply] if supply in adjacency else []) + [i for i in ids if i != supply]
    for root in roots:
        if root in parent:
            continue
        parent[root] = None
        heap: list[tuple[float, int, str, str, str]] = []
        for weight, order, other, eid in adjacency[root]:
            heapq.heappush(heap, (-weight, order, root, other, eid))
        while heap:
            _, _, u, v, eid = heapq.heappop(heap)
            if v in parent:
                continue
            parent[v] = u
            children[u].append(v)
            tree.add(eid)
            for weight, order, other, other_eid in adjacency[v]:
                if other not in parent:
                    heapq.heappush(heap, (-weight, order, v, other, other_eid))
    return parent, children, tree


def _place(children: dict[str, list[str]], roots: list[str]) -> dict[str, tuple[int, int]]:
    """Ranks and lanes. The largest subtree continues straight; a leaf takes the next free lane."""
    size: dict[str, int] = {}
    order: list[str] = []
    for root in roots:
        stack = [root]
        while stack:
            u = stack.pop()
            order.append(u)
            stack.extend(children[u])
    for u in reversed(order):
        size[u] = 1 + sum(size[c] for c in children[u])

    positions: dict[str, tuple[int, int]] = {}
    lane = 0
    for root in roots:
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            u, rank = stack.pop()
            # The first leaf reached below u is reached through the main child, so u's lane is the
            # lane counter as it stands on entry.
            positions[u] = (rank, lane)
            kids = sorted(children[u], key=lambda c: (-size[c], c))
            if not kids:
                lane += 1
            for c in reversed(kids):
                stack.append((c, rank + 1))
    return positions


def _lift_bands(nodes: list[dict], positions: dict[str, tuple[int, int]]) -> tuple[list, bool]:
    """Lift each elevation band above the ones below it, then close the gaps in the lane numbering."""
    elevation = {_text(n.get("id")): _num(n.get("elevation_m")) for n in nodes}
    known = sorted({z for z in elevation.values() if z is not None})
    use_elevation = len(known) > 1
    if not use_elevation:
        return [], False
    low = known[0]
    top = 0
    band_of: dict[str, float] = {}
    for z in known:
        ids = [i for i in positions if (elevation.get(i) if elevation.get(i) is not None else low) == z]
        if not ids:
            continue
        shift = max(0, top - min(positions[i][1] for i in ids))
        for i in ids:
            positions[i] = (positions[i][0], positions[i][1] + shift)
            band_of[i] = z
        top = max(positions[i][1] for i in ids) + 1
    used = sorted({y for _, y in positions.values()})
    renumber = {y: k for k, y in enumerate(used)}
    for i, (x, y) in positions.items():
        positions[i] = (x, renumber[y])
    bands = []
    for z in known:
        lanes = [positions[i][1] for i in positions if band_of.get(i) == z]
        if lanes:
            bands.append((z, min(lanes), max(lanes)))
    return bands, True


def _tree_route(parent_pos: tuple[int, int], child_pos: tuple[int, int], track: float) -> list[Point]:
    """Straight along a shared lane; otherwise out to the parent's bus track, up or down it, then along.

    The bus sits about half a rank past the parent, where no label is: a node's id is above the node
    and its call-out below it, both narrower than half a rank. A riser (a change of elevation band)
    is the same shape, and its vertical is what reads as the riser."""
    (xp, yp), (xc, yc) = parent_pos, child_pos
    if yp == yc:
        return [(xp, yp), (xc, yc)]
    return [(xp, yp), (track, yp), (track, yc), (xc, yc)]


_TRACK_OFFSETS = (0.5, 0.56, 0.44, 0.62, 0.38)


class _Occupancy:
    """What the vertical tracks between ranks and the horizontal channels between lanes carry, so a
    closer never lies on a tree bus or on another closer."""

    def __init__(self) -> None:
        self.vertical: dict[float, list[tuple[float, float]]] = {}
        self.horizontal: dict[float, list[tuple[float, float]]] = {}

    @staticmethod
    def _free(spans: list[tuple[float, float]], lo: float, hi: float) -> bool:
        return all(hi < a or lo > b for a, b in spans)

    def reserve_vertical(self, x: float, y0: float, y1: float) -> None:
        self.vertical.setdefault(x, []).append((min(y0, y1), max(y0, y1)))

    def track(self, rank: int, side: int, y0: float, y1: float) -> float:
        """A free vertical track beside a node, on the side asked for, nearest the mid-rank first."""
        lo, hi = min(y0, y1), max(y0, y1)
        for offset in _TRACK_OFFSETS:
            x = rank + side * offset
            if self._free(self.vertical.get(x, []), lo, hi):
                self.reserve_vertical(x, lo, hi)
                return x
        x = rank + side * _TRACK_OFFSETS[0]
        self.reserve_vertical(x, lo, hi)
        return x

    def channel(self, first: float, x0: float, x1: float) -> float:
        """The first free half-lane channel at or above `first` over this x span."""
        lo, hi = min(x0, x1), max(x0, x1)
        y = first
        while not self._free(self.horizontal.get(y, []), lo, hi):
            y += 1.0
        self.horizontal.setdefault(y, []).append((lo, hi))
        return y


def _free_side(node: str, parent: dict, children: dict, positions: dict) -> int:
    """+1 (right) when nothing runs along the node's lane to its right, else -1 when nothing runs to
    its left, else +1. A closer arriving on the free side does not lie on a tree run."""
    x, y = positions[node]
    straight_child = any(positions[c][1] == y for c in children.get(node, []))
    p = parent.get(node)
    straight_parent = p is not None and positions[p][1] == y
    if not straight_child:
        return 1
    if not straight_parent:
        return -1
    return 1


def layout(nodes: list[dict], edges: list[dict], supply: Optional[str] = None) -> Layout:
    result = Layout()
    ids: list[str] = []
    for node in nodes:
        i = _text(node.get("id"))
        if i and i not in ids:
            ids.append(i)
    if not ids:
        return result
    supply = supply or supply_id(nodes, edges)
    parent, children, tree = _spanning_forest(ids, edges, supply)
    roots = [i for i in ids if parent.get(i) is None]
    positions = _place(children, roots)
    bands, use_elevation = _lift_bands(nodes, positions)

    occupancy = _Occupancy()
    # One bus per parent, booked so two parents at the same rank do not draw their branches on one
    # line. A parent's own branches share its bus, which is how a header reads.
    bus: dict[str, float] = {}
    for p in ids:
        branches = [c for c in children[p] if positions[c][1] != positions[p][1]]
        if branches:
            lanes = [positions[p][1]] + [positions[c][1] for c in branches]
            bus[p] = occupancy.track(positions[p][0], 1, min(lanes), max(lanes))
    routes: dict[str, list[Point]] = {}
    closers: list[tuple[str, str, str]] = []
    for edge in edges:
        a, b, eid = _text(edge.get("from")), _text(edge.get("to")), _text(edge.get("id"))
        if a not in positions or b not in positions or a == b:
            continue
        if eid in tree:
            p, c = (a, b) if parent.get(b) == a else (b, a)
            points = _tree_route(positions[p], positions[c], bus.get(p, positions[p][0] + 0.5))
            routes[eid] = points if p == a else list(reversed(points))
        else:
            closers.append((eid, a, b))
    for eid, a, b in closers:
        (xa, ya), (xb, yb) = positions[a], positions[b]
        y = min(ya, yb) + 0.5
        ta = occupancy.track(xa, _free_side(a, parent, children, positions), ya, y)
        tb = occupancy.track(xb, _free_side(b, parent, children, positions), yb, y)
        y = occupancy.channel(y, ta, tb)
        routes[eid] = [(xa, ya), (ta, ya), (ta, y), (tb, y), (tb, yb), (xb, yb)]

    result.positions = positions
    result.routes = routes
    result.tree_edges = tree
    result.bands = bands
    result.use_elevation = use_elevation
    result.ranks = max(x for x, _ in positions.values()) + 1
    result.lanes = max(max(y for _, y in positions.values()) + 1,
                       int(math.ceil(max([max(y for _, y in r) for r in routes.values()] + [0]))) + 1)
    return result


def longest_segment(points: list[Point]) -> tuple[Point, Point]:
    """The segment a label and an arrow go on."""
    return max(zip(points, points[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
