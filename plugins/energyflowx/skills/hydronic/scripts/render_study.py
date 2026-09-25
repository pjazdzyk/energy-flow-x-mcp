#!/usr/bin/env python3
"""Render a solved hydraulic network as a single self-contained HTML study.

Why this exists as a script rather than as "ask the model to write some HTML": a study is handed to
somebody who was not in the conversation, and the parts that matter most are the ones a summary
written from memory quietly drops. The qualifications page is the clearest case. Here it is emitted
by code, from data, every time.

Input is one JSON file. Run:

    python3 render_study.py study.json -o study.html

Units live in the FIELD NAMES (pressure_kPa, flow_kg_s). That is not a style choice. A unit mistake is
the cheapest error to make in this domain and the most expensive to find, so the schema makes it
impossible to write a number without saying what it is. See references/report.md for the full schema.

No third-party dependencies: Python 3.9 and the standard library.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study_layout import layout, longest_segment, supply_id  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Reading the input
# ---------------------------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    """A finite number, or None. A string that happens to parse counts; anything else does not."""
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


def _fmt(value: Any, places: int = 2) -> str:
    """A number for a table cell. An em dash for nothing, because a blank reads as a zero."""
    number = _num(value)
    if number is None:
        return "&mdash;"
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.{places}f}"


def _esc(value: Any) -> str:
    return html.escape(_text(value), quote=True)


# ---------------------------------------------------------------------------------------------
# The diagram
# ---------------------------------------------------------------------------------------------
#
# There are no coordinates in a solve result, so a layout has to come from somewhere. Inventing one
# (a force-directed blob, a circle) would put the reader in front of a picture whose shape means
# nothing, which is worse than no picture: they will read meaning into it anyway.
#
# So it is drawn as a riser diagram, the schematic engineers sketch by hand: study_layout.py grows a
# spanning tree from the supply by flow, gives every branch its own lane, lifts each elevation above
# the ones below it and routes what is left of a ring or a grid as dashed closers. This file only
# turns that grid into SVG. The canvas grows with the network, labels are rationed (an id beside each
# node, a size along each run, every number on hover and in the schedules), and pressure is the fill
# of each node so the eye finds where it runs out without reading a figure.

_STEP_Y = 80.0          # one lane: a label above the node, a call-out below it, a closer channel between
_CHAR = 6.6             # px per character of a 12 px label, for spacing ranks by the longest id
_MAX_CALLOUTS = 6


def _label_width(text: str, size: float = 12.0) -> float:
    return len(text) * _CHAR * size / 12.0


Box = tuple[float, float, float, float]


def _touches(a: Box, b: Box, gap: float = 2.0) -> bool:
    return not (a[2] < b[0] - gap or b[2] < a[0] - gap or a[3] < b[1] - gap or b[3] < a[1] - gap)


class _Placer:
    """Label placement. Node ids and call-outs go down first as fixed obstacles, every run is an
    obstacle, and each run label then takes the first of its candidate spots that touches nothing.
    A label with no free spot is left off: its figure is on hover and in the schedule, and a label
    on top of another is worse than none."""

    def __init__(self) -> None:
        self.boxes: list[Box] = []
        self.runs: list[Box] = []

    def reserve(self, box: Box) -> None:
        self.boxes.append(box)

    def run(self, points: list[tuple[float, float]]) -> None:
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            self.runs.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def place(self, candidates: list[tuple[float, float, str]], width: float, size: float) -> tuple[float, float, str] | None:
        """candidates are (x, baseline y, anchor). Returns the first that is clear, or None."""
        for x, y, anchor in candidates:
            x0 = x - width / 2.0 if anchor == "middle" else (x - width if anchor == "end" else x)
            box = (x0, y - size * 0.8, x0 + width, y + size * 0.25)
            if any(_touches(box, other) for other in self.boxes) or any(_touches(box, r, 1.0) for r in self.runs):
                continue
            self.boxes.append(box)
            return x, y, anchor
        return None


def _arrow(x1: float, y1: float, x2: float, y2: float, reverse: bool) -> str:
    """A small arrowhead at the midpoint, pointing the way the fluid actually goes."""
    if reverse:
        x1, y1, x2, y2 = x2, y2, x1, y1
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    size = 6.5
    px, py = -uy, ux
    points = [
        (mx + ux * size, my + uy * size),
        (mx - ux * size * 0.7 + px * size * 0.6, my - uy * size * 0.7 + py * size * 0.6),
        (mx - ux * size * 0.7 - px * size * 0.6, my - uy * size * 0.7 - py * size * 0.6),
    ]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon class="arrow" points="{path}" />'


def _pressure_fill(share: float | None) -> str:
    """Deep blue where pressure is plentiful, pale where it runs out. Inline, so it holds in print."""
    if share is None:
        return "var(--bg)"
    return f"hsl(208 62% {78 - 48 * share:.0f}%)"


def _node_shape(kind: str, x: float, y: float, fill: str, title: str) -> str:
    k = kind.upper()
    t = f"<title>{_esc(title)}</title>"
    if "PRESSURE" in k:
        return f'<rect class="node boundary" x="{x - 7:.1f}" y="{y - 7:.1f}" width="14" height="14" rx="2" fill="{fill}">{t}</rect>'
    if "OUTLET" in k or "HEAD" in k or "SPRINKLER" in k:
        return f'<polygon class="node outlet" points="{x - 7:.1f},{y - 6:.1f} {x + 7:.1f},{y - 6:.1f} {x:.1f},{y + 7:.1f}" fill="{fill}">{t}</polygon>'
    if "DEMAND" in k:
        return f'<polygon class="node demand" points="{x:.1f},{y - 8:.1f} {x + 8:.1f},{y:.1f} {x:.1f},{y + 8:.1f} {x - 8:.1f},{y:.1f}" fill="{fill}">{t}</polygon>'
    if "PUMP" in k or "COMPRESSOR" in k or "DEVICE" in k:
        return f'<circle class="node device" cx="{x:.1f}" cy="{y:.1f}" r="7" fill="var(--warn)">{t}</circle>'
    return f'<circle class="node junction" cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{fill}">{t}</circle>'


def _callouts(study: dict, nodes: list[dict], edges: list[dict]) -> dict[str, list[str]]:
    """The few elements whose numbers belong on the drawing: the supply, the devices, the far end of the
    critical path and the lowest-pressure node. Everything else is on hover and in the schedules."""
    by_node: dict[str, list[str]] = {}
    supply = _text(study.get("_supply"))
    critical = study.get("criticalPath") or {}
    wanted: list[str] = []
    if supply:
        wanted.append(supply)
    if _text(critical.get("to")):
        wanted.append(_text(critical.get("to")))
    pressured = [n for n in nodes if _num(n.get("pressure_kPa")) is not None]
    if pressured:
        wanted.append(_text(min(pressured, key=lambda n: _num(n.get("pressure_kPa")))["id"]))
    for edge in edges:
        if any(word in _text(edge.get("size")).upper() for word in ("PUMP", "COMPRESSOR", "FAN")):
            wanted.append(_text(edge.get("to")))
    for node in nodes:
        node_id = _text(node.get("id"))
        if node_id not in wanted or node_id in by_node or len(by_node) >= _MAX_CALLOUTS:
            continue
        bits = []
        if _num(node.get("pressure_kPa")) is not None:
            bits.append(f"{_num(node['pressure_kPa']):.1f} kPa")
        if _num(node.get("flow_kg_s")) is not None:
            bits.append(f"{abs(_num(node['flow_kg_s'])):.3g} kg/s")
        if bits:
            by_node[node_id] = bits
    return by_node


def _diagram(nodes: list[dict], edges: list[dict], study: dict | None = None) -> str:
    if not nodes:
        return '<p class="empty">No nodes to draw.</p>'
    study = study or {}
    supply = supply_id(nodes, edges)
    grid = layout(nodes, edges, supply)
    if not grid.positions:
        return '<p class="empty">No nodes to draw.</p>'

    ids = [_text(n.get("id")) for n in nodes]
    critical = set(_text(e) for e in ((study.get("criticalPath") or {}).get("elements") or []))
    callouts = _callouts({**study, "_supply": supply}, nodes, edges)
    callout_widths = [_label_width("  ".join(c), 11.0) + 14.0 for c in callouts.values()]
    # A label is centred on its node and must stay clear of the tracks half a rank away on either side.
    step_x = max(110.0, max(_label_width(i) for i in ids) + 40.0, max(callout_widths + [0.0]) + 36.0)
    widest = max([_label_width(i) for i in ids] + callout_widths)
    # The datum labels sit at the left edge, so with elevations the first rank keeps clear of them.
    pad_left = max(78.0, widest / 2.0 + 60.0) if grid.use_elevation else max(40.0, widest / 2.0 + 16.0)
    pad_right = max(40.0, widest / 2.0 + 16.0)
    if len(grid.tree_edges) < len(grid.routes):
        # A closer leaves a node on a track up to 0.62 of a rank out, past the first or last rank too.
        pad_left, pad_right = max(pad_left, 0.75 * step_x), max(pad_right, 0.75 * step_x)
    width = pad_left + (grid.ranks - 1) * step_x + pad_right
    pad_top, pad_bottom = 34.0, 60.0
    height = pad_top + (grid.lanes - 1) * _STEP_Y + pad_bottom

    def sx(x: float) -> float:
        return pad_left + x * step_x

    def sy(y: float) -> float:
        return height - pad_bottom - y * _STEP_Y

    flows = [abs(_num(e.get("flow_kg_s")) or 0.0) for e in edges]
    peak = max(flows) if flows else 0.0
    pressures = [_num(n.get("pressure_kPa")) for n in nodes if _num(n.get("pressure_kPa")) is not None]
    p_low, p_high = (min(pressures), max(pressures)) if pressures else (None, None)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="Schematic of the solved network" '
        f'class="schematic" style="min-width:{0.75 * width:.0f}px">'
    ]

    # Elevation datums: a dashed line under each band with its level on the left.
    for z, lane_low, _ in grid.bands:
        yy = sy(lane_low) + _STEP_Y * 0.5
        parts.append(f'<line class="datum" x1="8" y1="{yy:.1f}" x2="{width - 12:.1f}" y2="{yy:.1f}" />')
        parts.append(f'<text class="datum-label" x="8" y="{yy - 5:.1f}">{z:+.1f} m</text>')

    placer = _Placer()
    node_parts: list[str] = []
    for node in nodes:
        node_id = _text(node.get("id"))
        if node_id not in grid.positions:
            continue
        gx, gy = grid.positions[node_id]
        x, y = sx(gx), sy(gy)
        pressure = _num(node.get("pressure_kPa"))
        share = None
        if pressure is not None and p_low is not None:
            share = (pressure - p_low) / (p_high - p_low) if p_high > p_low else 1.0
        hover = [node_id, _text(node.get("kind"))]
        if _num(node.get("elevation_m")) is not None:
            hover.append(f"z {_num(node['elevation_m']):.2f} m")
        if pressure is not None:
            hover.append(f"{pressure:.1f} kPa")
        if _num(node.get("flow_kg_s")) is not None:
            hover.append(f"{_num(node['flow_kg_s']):.3f} kg/s net")
        node_parts.append(_node_shape(_text(node.get("kind")), x, y, _pressure_fill(share), ", ".join(b for b in hover if b)))
        node_parts.append(f'<text class="node-label" x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle">{_esc(node_id)}</text>')
        half_w = _label_width(node_id) / 2.0
        placer.reserve((x - half_w, y - 12 - 9.6, x + half_w, y - 12 + 3))
        placer.reserve((x - 8, y - 8, x + 8, y + 8))
        if node_id in callouts:
            text = "  ".join(callouts[node_id])
            box_w = _label_width(text, 11.0) + 14.0
            node_parts.append(
                f'<rect class="callout" x="{x - box_w / 2:.1f}" y="{y + 20:.1f}" width="{box_w:.1f}" height="18" rx="4" />'
                f'<text class="callout-label" x="{x:.1f}" y="{y + 33:.1f}" text-anchor="middle">{_esc(text)}</text>'
            )
            placer.reserve((x - box_w / 2, y + 20, x + box_w / 2, y + 38))

    labelled: list[tuple[str, list[tuple[float, float]], float | None, bool]] = []
    for edge in edges:
        eid = _text(edge.get("id"))
        route = grid.routes.get(eid)
        if not route:
            continue
        points = [(sx(x), sy(y)) for x, y in route]
        placer.run(points)
        flow = _num(edge.get("flow_kg_s"))
        share = (abs(flow) / peak) if (flow is not None and peak > 0) else 0.0
        stroke = 1.6 + 4.6 * share
        classes = ["run"]
        if eid not in grid.tree_edges:
            classes.append("closer")
        if eid in critical:
            classes.append("critical")
        hover = [eid]
        for key, unit, places in (("size", "", None), ("length_m", "m", 1), ("flow_kg_s", "kg/s", 3),
                                  ("velocity_m_s", "m/s", 2), ("dp_kPa", "kPa drop", 2)):
            value = edge.get(key)
            if places is None and _text(value):
                hover.append(_text(value))
            elif places is not None and _num(value) is not None:
                hover.append(f"{_num(value):.{places}f} {unit}")
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        parts.append(
            f'<polyline class="{" ".join(classes)}" points="{path}" stroke-width="{stroke:.2f}">'
            f"<title>{_esc(', '.join(hover))}</title></polyline>"
        )
        (x1, y1), (x2, y2) = longest_segment(points)
        if flow is not None and abs(flow) > 1e-12:
            parts.append(_arrow(x1, y1, x2, y2, reverse=flow < 0))
        labelled.append((_text(edge.get("size")) or eid, points, eid in grid.tree_edges))

    # Run labels last, so every run and every fixed label is already an obstacle. Candidates, in
    # order: along the longest segment, under it a fifth of the way in (clear of the mid-rank tracks)
    # or beside it just under the half-lane nearest its middle; then the other spots on that segment;
    # then the same on the next longest.
    for size, points, is_tree in labelled:
        candidates: list[tuple[float, float, str]] = []
        segments = sorted(zip(points, points[1:]), key=lambda s: -(abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1])))
        for (x1, y1), (x2, y2) in segments[:3]:
            if y1 == y2:
                fractions = (0.2, 0.8, 0.35, 0.65, 0.5) if is_tree else (0.5, 0.3, 0.7)
                for f in fractions:
                    candidates.append((x1 + f * (x2 - x1), y1 + 14.0, "middle"))
                for f in fractions:
                    candidates.append((x1 + f * (x2 - x1), y1 - 6.0, "middle"))
            else:
                low, high = min(y1, y2), max(y1, y2)
                halves = sorted(
                    (y for y in (sy(k + 0.5) for k in range(int(grid.lanes) + 1)) if low + 1 < y < high - 1),
                    key=lambda y: abs(y - (low + high) / 2.0))
                for hy in halves:
                    candidates.append((x1 + 8.0, hy + 14.0, "start"))
                    candidates.append((x1 - 8.0, hy + 14.0, "end"))
                    candidates.append((x1 + 8.0, hy - 4.0, "start"))
                    candidates.append((x1 - 8.0, hy - 4.0, "end"))
        spot = placer.place(candidates, _label_width(size, 10.5), 10.5)
        if spot:
            x, y, anchor = spot
            parts.append(f'<text class="edge-label" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{_esc(size)}</text>')

    parts.extend(node_parts)

    parts.append("</svg>")
    parts.insert(0, '<div class="figure">')
    parts.append("</div>")

    axis = (
        "Elevation up the page in bands, each drawn above the levels below it; distance from the supply "
        "across it, one step per node."
        if grid.use_elevation
        else "No elevations were given, so this is a topology sketch: distance from the supply across the "
        "page, one step per node, each branch in a lane of its own."
    )
    legend = (
        "Line weight is flow magnitude and the arrow is the direction the fluid actually runs. Node fill "
        "is pressure, deep where it is plentiful and pale where it runs out"
        + (f" ({p_high:.0f} down to {p_low:.0f} kPa)" if pressures else "")
        + ". A dashed run closes a ring or a grid outside the spanning tree, opened where the flow divides."
        + (" The lighter runs are the critical path." if critical else "")
        + " Hover a node or a run for its figures; the schedules below have them all."
    )
    parts.append(
        f'<p class="caption">Schematic, not a P&amp;ID, and not to scale. {html.escape(axis)} {html.escape(legend)}</p>'
    )
    return "".join(parts)


# ---------------------------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------------------------


def _verdict(study: dict) -> str:
    converged = study.get("converged")
    iterations = study.get("iterations")
    notices = study.get("qualifications") or []
    withdrawn = any("NON_PHYSICAL" in _text(q.get("code")).upper() for q in notices)

    if withdrawn:
        tone, headline = "bad", "These results are withdrawn"
        detail = (
            "The solve reached a pressure no fluid can be at, which means the network cannot deliver "
            "the flow being asked of it. Nothing in the schedules below should be quoted."
        )
    elif converged is False:
        tone, headline = "bad", "The solve did not converge"
        detail = (
            "The numbers below are the last iterate, not a solution. They are worth reading for where "
            "the solve got stuck, and worth nothing as an answer."
        )
    elif notices:
        tone, headline = "warn", "Solved, with qualifications"
        detail = (
            f"{len(notices)} qualification{'s' if len(notices) != 1 else ''} apply to these results. "
            "Read them before quoting any number."
        )
    else:
        tone, headline = "good", "Solved"
        detail = "The solve converged and raised nothing worth qualifying."

    meta = f" in {iterations} iterations" if _num(iterations) is not None else ""
    return (
        f'<section class="verdict {tone}"><h2>Verdict</h2>'
        f"<p class=\"headline\">{html.escape(headline)}{html.escape(meta)}</p>"
        f"<p>{html.escape(detail)}</p></section>"
    )


def _qualifications(study: dict) -> str:
    """Never omitted. When there is nothing to say, the page says that rather than staying silent."""
    rows = study.get("qualifications") or []
    if not rows:
        return (
            '<section id="qualifications"><h2>Qualifications</h2>'
            '<p class="empty">The solve raised none. Every number in this study was computed '
            "in the ordinary way from the design as drawn.</p></section>"
        )

    body = "".join(
        "<tr>"
        f"<td>{_esc(row.get('element'))}</td>"
        f"<td>{_esc(row.get('finding') or row.get('code'))}</td>"
        f"<td>{_esc(row.get('what'))}</td>"
        "</tr>"
        for row in rows
    )
    return (
        '<section id="qualifications" class="flagged"><h2>Qualifications</h2>'
        "<p>These do not stop a solve and do not affect convergence. Each one means a number "
        "elsewhere in this study was produced by something other than ordinary evaluation of the "
        "design as drawn, and should be read as such.</p>"
        '<table><thead><tr><th>Element</th><th>Finding</th><th>What the solve did</th></tr></thead>'
        f"<tbody>{body}</tbody></table></section>"
    )


def _critical_path(study: dict) -> str:
    path = study.get("criticalPath")
    if not isinstance(path, dict) or not path:
        return ""
    facts = []
    if _text(path.get("to")):
        facts.append(("Worst node", _esc(path.get("to"))))
    if _num(path.get("totalDrop_kPa")) is not None:
        facts.append(("Total drop", f"{_fmt(path.get('totalDrop_kPa'), 1)} kPa"))
    if _num(path.get("residual_kPa")) is not None:
        facts.append(("Left at the end", f"{_fmt(path.get('residual_kPa'), 1)} kPa"))
    elements = path.get("elements") or []
    if elements:
        facts.append(("Route", _esc(" &rarr; ".join(_text(e) for e in elements)).replace("&amp;rarr;", "&rarr;")))

    items = "".join(f"<div><dt>{html.escape(k)}</dt><dd>{v}</dd></div>" for k, v in facts)
    return (
        '<section><h2>Critical path</h2>'
        "<p>The route that costs the most pressure. In most designs this, rather than any single "
        "pipe's velocity, is what decides whether the system works.</p>"
        f"<dl class='facts'>{items}</dl></section>"
    )


def _node_table(study: dict) -> str:
    nodes = study.get("nodes") or []
    if not nodes:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{_esc(n.get('id'))}</td>"
        f"<td>{_esc(n.get('kind'))}</td>"
        f"<td class='n'>{_fmt(n.get('elevation_m'), 2)}</td>"
        f"<td class='n'>{_fmt(n.get('pressure_kPa'), 1)}</td>"
        f"<td class='n'>{_fmt(n.get('flow_kg_s'), 3)}</td>"
        "</tr>"
        for n in nodes
    )
    return (
        "<section><h2>Nodes</h2><table><thead><tr>"
        "<th>Id</th><th>Kind</th><th class='n'>Elevation [m]</th>"
        "<th class='n'>Pressure [kPa]</th><th class='n'>Net flow [kg/s]</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></section>"
    )


def _edge_table(study: dict) -> str:
    edges = study.get("edges") or []
    if not edges:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{_esc(e.get('id'))}</td>"
        f"<td>{_esc(e.get('from'))} &rarr; {_esc(e.get('to'))}</td>"
        f"<td>{_esc(e.get('size'))}</td>"
        f"<td class='n'>{_fmt(e.get('length_m'), 1)}</td>"
        f"<td class='n'>{_fmt(e.get('flow_kg_s'), 3)}</td>"
        f"<td class='n'>{_fmt(e.get('velocity_m_s'), 2)}</td>"
        f"<td class='n'>{_fmt(e.get('dp_kPa'), 1)}</td>"
        "</tr>"
        for e in edges
    )
    return (
        "<section><h2>Runs</h2><table><thead><tr>"
        "<th>Id</th><th>From &rarr; to</th><th>Size</th><th class='n'>Length [m]</th>"
        "<th class='n'>Flow [kg/s]</th><th class='n'>Velocity [m/s]</th><th class='n'>&Delta;p [kPa]</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
        "<p class='caption'>A negative flow runs against the direction the run was declared in. "
        "Around a ring, the place the sign changes is the flow divide.</p></section>"
    )


_UNITS = {"kW": "kW", "kWh": "kWh", "kPa": "kPa", "C": "°C", "kgps": "kg/s", "W": "W", "s": "s",
          "m": "m", "mps": "m/s"}


def _label(key: str) -> tuple[str, str]:
    """A figure's field name as a label and its unit: "electricalPower_kW" -> ("Electrical power", "kW")."""
    name, _, unit = key.partition("_")
    words = "".join(" " + c.lower() if c.isupper() else c for c in name).strip()
    return words[:1].upper() + words[1:], _UNITS.get(unit, unit)


def _devices(study: dict) -> str:
    """Equipment, one row per device, its figures read straight off the solve's `devices` rows."""
    devices = study.get("devices") or []
    if not devices:
        return ""
    rows = []
    for device in devices:
        figures = []
        for key, value in device.items():
            if key in ("id", "type") or _num(value) is None:
                continue
            label, unit = _label(key)
            figures.append(f"{_esc(label)} <strong>{_fmt(value, 2)}</strong> {_esc(unit)}".rstrip())
        shown = "; ".join(figures) if figures else "&mdash;"
        rows.append(f"<tr><td>{_esc(device.get('id'))}</td><td>{_esc(device.get('type'))}</td><td>{shown}</td></tr>")
    return ("<section><h2>Equipment</h2><table><thead><tr><th>Id</th><th>Type</th><th>What it did</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
            "<p class='caption'>After a run over time, a machine's power and recovered heat are averages over "
            "the run, and a store's temperature is the one it ended at.</p></section>")


def _chart(rows: list[dict], columns: list[str], unit: str) -> str:
    """A small line chart of some series columns against time, its range printed on it."""
    points = []
    for row in rows:
        time = _num(row.get("t_s"))
        if time is not None:
            points.append((time, {c: _num(row.get(c)) for c in columns}))
    values = [x for _, v in points for x in v.values() if x is not None]
    if len(points) < 2 or not values:
        return ""
    w, h, pad = 640, 170, 34
    t0, t1 = points[0][0], points[-1][0]
    lo, hi = min(values), max(values)
    if hi == lo:
        hi, lo = hi + 1.0, lo - 1.0

    def sx(time: float) -> float:
        return pad + (w - 2 * pad) * (time - t0) / ((t1 - t0) or 1.0)

    def sy(value: float) -> float:
        return h - pad + (2 * pad - h) * (value - lo) / (hi - lo)

    lines = []
    for index, column in enumerate(columns):
        pts = " ".join(f"{sx(tm):.1f},{sy(v[column]):.1f}" for tm, v in points if v[column] is not None)
        lines.append(f"<polyline class='series s{index % 4}' points='{pts}' fill='none'/>")
    legend = ", ".join(_esc(c.rsplit("_", 1)[0]) for c in columns)
    return (f"<figure><svg class='chart' viewBox='0 0 {w} {h}' role='img' aria-label='{legend} over time'>"
            f"<line class='axis' x1='{pad}' y1='{h - pad}' x2='{w - pad}' y2='{h - pad}'/>"
            f"{''.join(lines)}"
            f"<text class='tick' x='{pad}' y='{pad - 10}'>{_fmt(hi, 1)} {_esc(unit)}</text>"
            f"<text class='tick' x='{pad}' y='{h - pad + 16}'>{_fmt(lo, 1)} {_esc(unit)}</text>"
            f"<text class='tick' x='{w - pad}' y='{h - pad + 16}' text-anchor='end'>{_fmt(t1, 0)} s</text>"
            f"</svg><figcaption class='caption'>{legend}, sampled over the run.</figcaption></figure>")


def _run(study: dict) -> str:
    """A run over time: how long, each vessel's swing, every command change, and the sampled curve."""
    run = study.get("transient")
    if not isinstance(run, dict):
        return ""
    facts = []
    if _num(run.get("simulated_s")) is not None:
        facts.append(("Simulated", f"{_fmt(run.get('simulated_s'), 0)} s"))
    if _num(run.get("timeStep_s")) is not None:
        facts.append(("Step", f"{_fmt(run.get('timeStep_s'), 1)} s"))
    if _text(run.get("stopReason")):
        facts.append(("Stopped because", _esc(run.get("stopReason"))))
    parts = ["<section><h2>Over time</h2>"]
    if facts:
        parts.append("<dl class='facts'>" + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)
                     + "</dl>")
    vessels = run.get("vessels") or []
    if vessels:
        body = "".join(
            f"<tr><td>{_esc(v.get('id'))}</td><td class='n'>{_fmt(v.get('start_kPa'), 1)}</td>"
            f"<td class='n'>{_fmt(v.get('min_kPa'), 1)} at {_fmt(v.get('min_at_s'), 0)} s</td>"
            f"<td class='n'>{_fmt(v.get('max_kPa'), 1)} at {_fmt(v.get('max_at_s'), 0)} s</td>"
            f"<td class='n'>{_fmt(v.get('end_kPa'), 1)}</td></tr>" for v in vessels)
        parts.append("<h3>Vessels</h3><table><thead><tr><th>Id</th><th class='n'>Start [kPa]</th>"
                     "<th class='n'>Lowest [kPa]</th><th class='n'>Highest [kPa]</th><th class='n'>End [kPa]</th>"
                     f"</tr></thead><tbody>{body}</tbody></table>")
    series = run.get("series") or []
    if series:
        columns = [c for c in series[0].keys() if c != "t_s"]
        for suffix, unit in (("_kPa", "kPa"), ("_C", "°C"), ("_cmd", "command")):
            group = [c for c in columns if c.endswith(suffix)]
            if group:
                parts.append(_chart(series, group, unit))
    events = run.get("events") or []
    if events:
        body = "".join(f"<tr><td class='n'>{_fmt(e.get('t_s'), 0)}</td><td>{_esc(e.get('device'))}</td>"
                       f"<td class='n'>{_fmt(e.get('command'), 2)}</td></tr>" for e in events)
        parts.append("<h3>Command changes</h3><table><thead><tr><th class='n'>Time [s]</th><th>Device</th>"
                     f"<th class='n'>Command</th></tr></thead><tbody>{body}</tbody></table>"
                     "<p class='caption'>1 is loaded or full speed, 0 unloaded or stopped.</p>")
    parts.append("<p class='caption'>Each step of the run is a steady network solve, so pressure waves and "
                 "water hammer are not part of it.</p></section>")
    return "".join(parts)


def _assumptions(study: dict) -> str:
    items: list[str] = []
    if _text(study.get("fluid")):
        items.append(f"Fluid: {_esc(study.get('fluid'))}")
    for line in study.get("assumptions") or []:
        items.append(_esc(line))
    if not items:
        return ""
    body = "".join(f"<li>{item}</li>" for item in items)
    return f"<section><h2>Assumptions</h2><ul>{body}</ul></section>"


def _notes(study: dict) -> str:
    note = _text(study.get("notes"))
    if not note:
        return ""
    return f"<section><h2>Notes</h2><p>{_esc(note)}</p></section>"


# ---------------------------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------------------------

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #161a1d; --muted: #5a6470; --line: #d8dee6; --panel: #f6f8fa;
  --good: #1a7f4b; --warn: #9a6400; --bad: #b3261e; --accent: #1f5c8b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14171a; --fg: #e8ecef; --muted: #9aa5b1; --line: #2c3238; --panel: #1b1f24;
    --good: #5ec98b; --warn: #e0a72a; --bad: #f0857c; --accent: #6db3e8;
  }
}
:root[data-theme="dark"] {
  --bg: #14171a; --fg: #e8ecef; --muted: #9aa5b1; --line: #2c3238; --panel: #1b1f24;
  --good: #5ec98b; --warn: #e0a72a; --bad: #f0857c; --accent: #6db3e8;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 72px; }
header.study { border-bottom: 2px solid var(--line); padding-bottom: 14px; margin-bottom: 26px; }
header.study h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: -0.01em; }
header.study .meta { color: var(--muted); font-size: 13px; }
header.study .meta span + span::before { content: " · "; }
section { margin: 30px 0; }
h2 { font-size: 17px; margin: 0 0 10px; letter-spacing: 0.01em; }
p { margin: 0 0 10px; }
.caption, .empty { color: var(--muted); font-size: 13px; }
.verdict { border-left: 0; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.verdict .headline { font-weight: 650; font-size: 17px; margin-bottom: 4px; }
.verdict.good .headline { color: var(--good); }
.verdict.warn .headline { color: var(--warn); }
.verdict.bad .headline { color: var(--bad); }
section.flagged { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-weight: 620; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
dl.facts { display: flex; flex-wrap: wrap; gap: 10px 28px; margin: 0; }
dl.facts dt { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
dl.facts dd { margin: 2px 0 0; font-size: 16px; font-variant-numeric: tabular-nums; }
ul { margin: 0; padding-left: 20px; }
.figure { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.schematic { display: block; width: 100%; height: auto; }
.schematic .run { fill: none; stroke: var(--accent); stroke-linecap: round; stroke-linejoin: round; opacity: 0.85; }
.schematic .run.closer { stroke: var(--warn); stroke-dasharray: 6 4; }
.schematic .run.critical { opacity: 1; filter: brightness(1.25); }
.schematic .arrow { fill: var(--fg); }
.schematic .node { stroke: var(--fg); stroke-width: 1.6; }
.schematic .datum { stroke: var(--line); stroke-dasharray: 2 6; }
.schematic .datum-label { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.schematic .node-label { fill: var(--fg); font-size: 12px; font-weight: 600; }
.schematic .edge-label { fill: var(--muted); font-size: 10.5px; }
.schematic .callout { fill: var(--bg); stroke: var(--line); }
.schematic .callout-label { fill: var(--fg); font-size: 11px; font-variant-numeric: tabular-nums; }
h3 { font-size: 14px; margin: 18px 0 8px; }
figure { margin: 14px 0; }
.chart { width: 100%; height: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
.chart .axis { stroke: var(--line); }
.chart .tick { fill: var(--muted); font-size: 11px; }
.chart .series { stroke-width: 2; }
.chart .s0 { stroke: var(--accent); } .chart .s1 { stroke: var(--warn); }
.chart .s2 { stroke: var(--good); } .chart .s3 { stroke: var(--bad); }
footer { margin-top: 44px; padding-top: 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
@media print { body { background: #fff; } .figure { overflow: visible; } .schematic { width: 100%; height: auto; break-inside: avoid; } section { break-inside: avoid; } }
@media (max-width: 640px) {
  main { padding: 20px 16px 48px; }
  table { font-size: 13px; }
  th, td { padding: 6px 7px; }
}
"""


def render(study: dict) -> str:
    title = _text(study.get("title")) or "Hydraulic study"
    meta_bits = [
        _text(study.get("project")),
        f"Rev {_text(study.get('revision'))}" if _text(study.get("revision")) else "",
        _text(study.get("date")),
        _text(study.get("author")),
        _text(study.get("scenario")),
    ]
    meta = "".join(f"<span>{_esc(bit)}</span>" for bit in meta_bits if bit)

    body = "".join(
        [
            _verdict(study),
            _qualifications(study),
            f"<section><h2>The network</h2>{_diagram(study.get('nodes') or [], study.get('edges') or [], study)}</section>",
            _critical_path(study),
            _devices(study),
            _run(study),
            _edge_table(study),
            _node_table(study),
            _assumptions(study),
            _notes(study),
        ]
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body><main>"
        f'<header class="study"><h1>{_esc(title)}</h1><p class="meta">{meta}</p></header>'
        f"{body}"
        "<footer>Computed with the EnergyFlowX hydraulic engine. Every figure here comes from the "
        "solve; nothing on this page was estimated by hand. Read the qualifications before quoting "
        "any number.</footer>"
        "</main></body></html>\n"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a solved hydraulic network as an HTML study.")
    parser.add_argument("study", type=Path, help="the study JSON (see references/report.md)")
    parser.add_argument("-o", "--output", type=Path, default=Path("study.html"), help="where to write")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        data = json.loads(args.study.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"No such study file: {args.study}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"{args.study} is not valid JSON: {error}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("The study file must contain a JSON object.", file=sys.stderr)
        return 2

    args.output.write_text(render(data), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
