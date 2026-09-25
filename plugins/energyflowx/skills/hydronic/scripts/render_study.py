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
from collections import deque
from pathlib import Path
from typing import Any, Iterable

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
# Laying out the diagram
# ---------------------------------------------------------------------------------------------
#
# There are no coordinates in a solve result, so a layout has to come from somewhere. Inventing one
# (a force-directed blob, a circle) would put the reader in front of a picture whose shape means
# nothing, which is worse than no picture: they will read meaning into it anyway.
#
# So the layout is derived from physics and from the graph:
#
#   y = elevation          the one spatial fact a hydraulic model actually carries, and the one that
#                          explains most of the pressure field in any building
#   x = graph distance     hops from the supply, so the far end of the network is at the far end of
#                          the page and a ring closes back on itself
#
# When no elevations are given, y falls back to a spread within each depth column so nodes do not
# overlap. That is honest — it is a topology sketch and the page says so — and it is still the right
# shape for reading a branch structure.


def _supply_id(nodes: list[dict], edges: list[dict]) -> str | None:
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


def _depths(nodes: list[dict], edges: list[dict], supply: str | None) -> dict[str, int]:
    """Hops from the supply, breadth first. Anything unreachable is parked past the deepest column."""
    adjacency: dict[str, set[str]] = {_text(n.get("id")): set() for n in nodes}
    for edge in edges:
        a, b = _text(edge.get("from")), _text(edge.get("to"))
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)

    depths: dict[str, int] = {}
    if supply and supply in adjacency:
        depths[supply] = 0
        queue = deque([supply])
        while queue:
            current = queue.popleft()
            for neighbour in sorted(adjacency[current]):
                if neighbour not in depths:
                    depths[neighbour] = depths[current] + 1
                    queue.append(neighbour)

    orphan_depth = (max(depths.values()) + 1) if depths else 0
    for node_id in adjacency:
        depths.setdefault(node_id, orphan_depth)
    return depths


def _layout(nodes: list[dict], edges: list[dict], width: int, height: int) -> dict[str, tuple[float, float]]:
    if not nodes:
        return {}

    supply = _supply_id(nodes, edges)
    depths = _depths(nodes, edges, supply)
    max_depth = max(depths.values()) if depths else 0

    elevations = {_text(n.get("id")): _num(n.get("elevation_m")) for n in nodes}
    known = [e for e in elevations.values() if e is not None]
    use_elevation = len(known) > 1 and (max(known) - min(known)) > 1e-9

    pad_x, pad_y = 90.0, 58.0
    span_x = max(width - 2 * pad_x, 1.0)
    span_y = max(height - 2 * pad_y, 1.0)

    positions: dict[str, tuple[float, float]] = {}

    if use_elevation:
        low, high = min(known), max(known)
        # Nodes with no stated elevation sit at the datum, which is what the model means by omitting it.
        for node in nodes:
            node_id = _text(node.get("id"))
            elevation = elevations.get(node_id)
            elevation = low if elevation is None else elevation
            x = pad_x + (span_x * (depths[node_id] / max_depth) if max_depth else span_x / 2.0)
            y = height - pad_y - span_y * ((elevation - low) / (high - low))
            positions[node_id] = (x, y)
    else:
        # Topology only: spread each depth column vertically so nothing overlaps.
        columns: dict[int, list[str]] = {}
        for node in nodes:
            columns.setdefault(depths[_text(node.get("id"))], []).append(_text(node.get("id")))
        for depth, column in columns.items():
            x = pad_x + (span_x * (depth / max_depth) if max_depth else span_x / 2.0)
            for index, node_id in enumerate(sorted(column)):
                offset = (index + 1) / (len(column) + 1)
                positions[node_id] = (x, pad_y + span_y * offset)

    # Nudge apart any pair that landed on the same point: two nodes at one elevation and one depth is
    # ordinary (a symmetrical branch), and overlapping labels make the picture useless.
    seen: dict[tuple[int, int], int] = {}
    for node_id, (x, y) in list(positions.items()):
        key = (round(x / 18), round(y / 18))
        count = seen.get(key, 0)
        seen[key] = count + 1
        if count:
            positions[node_id] = (x, y + count * 26.0)

    return positions, use_elevation


# ---------------------------------------------------------------------------------------------
# The diagram
# ---------------------------------------------------------------------------------------------


def _arrow(x1: float, y1: float, x2: float, y2: float, reverse: bool) -> str:
    """A small arrowhead at the midpoint, pointing the way the fluid actually goes."""
    if reverse:
        x1, y1, x2, y2 = x2, y2, x1, y1
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    size = 7.0
    px, py = -uy, ux
    points = [
        (mx + ux * size, my + uy * size),
        (mx - ux * size * 0.6 + px * size * 0.55, my - uy * size * 0.6 + py * size * 0.55),
        (mx - ux * size * 0.6 - px * size * 0.55, my - uy * size * 0.6 - py * size * 0.55),
    ]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon class="arrow" points="{path}" />'


def _diagram(nodes: list[dict], edges: list[dict]) -> str:
    if not nodes:
        return '<p class="empty">No nodes to draw.</p>'

    width, height = 960, 520
    positions, used_elevation = _layout(nodes, edges, width, height)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Schematic of the solved network" class="schematic">'
    ]

    flows = [abs(_num(e.get("flow_kg_s")) or 0.0) for e in edges]
    peak = max(flows) if flows else 0.0

    for edge in edges:
        a, b = _text(edge.get("from")), _text(edge.get("to"))
        if a not in positions or b not in positions:
            continue
        (x1, y1), (x2, y2) = positions[a], positions[b]
        flow = _num(edge.get("flow_kg_s"))
        # Line weight carries magnitude, the arrow carries direction. A negative flow means the fluid
        # runs against the declared from/to, which around a ring is where the flow divide shows up.
        share = (abs(flow) / peak) if (flow is not None and peak > 0) else 0.0
        stroke = 1.6 + 4.6 * share
        parts.append(
            f'<line class="run" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke-width="{stroke:.2f}" />'
        )
        if flow is not None and abs(flow) > 1e-12:
            parts.append(_arrow(x1, y1, x2, y2, reverse=flow < 0))

        label_bits = [_text(edge.get("id"))]
        if _num(edge.get("flow_kg_s")) is not None:
            label_bits.append(f"{abs(_num(edge['flow_kg_s'])):.3g} kg/s")
        if _num(edge.get("velocity_m_s")) is not None:
            label_bits.append(f"{_num(edge['velocity_m_s']):.2f} m/s")
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        parts.append(
            f'<text class="edge-label" x="{mx:.1f}" y="{my - 11:.1f}" text-anchor="middle">'
            f"{_esc('  '.join(label_bits))}</text>"
        )

    for node in nodes:
        node_id = _text(node.get("id"))
        if node_id not in positions:
            continue
        x, y = positions[node_id]
        kind = _text(node.get("kind")).upper()
        shape_class = "boundary" if ("PRESSURE" in kind or "OUTLET" in kind) else (
            "demand" if "DEMAND" in kind else "junction"
        )
        parts.append(f'<circle class="node {shape_class}" cx="{x:.1f}" cy="{y:.1f}" r="8" />')
        parts.append(
            f'<text class="node-label" x="{x:.1f}" y="{y - 15:.1f}" text-anchor="middle">'
            f"{_esc(node_id)}</text>"
        )
        readout = []
        if _num(node.get("pressure_kPa")) is not None:
            readout.append(f"{_num(node['pressure_kPa']):.1f} kPa")
        if _num(node.get("elevation_m")) is not None:
            readout.append(f"z {_num(node['elevation_m']):.1f} m")
        if readout:
            parts.append(
                f'<text class="node-readout" x="{x:.1f}" y="{y + 24:.1f}" text-anchor="middle">'
                f"{_esc('  ')}{_esc('  '.join(readout))}</text>"
            )

    parts.append("</svg>")

    axis = (
        "Elevation up the page, distance from the supply across it."
        if used_elevation
        else "No elevations were given, so this is a topology sketch: distance from the supply across "
        "the page, nodes spread to keep them apart."
    )
    parts.append(
        '<p class="caption">Schematic, not a P&amp;ID, and not to scale. '
        f"{html.escape(axis)} Line weight is flow magnitude; the arrow is the direction the fluid "
        "actually runs, which around a ring is where the flow divide shows.</p>"
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
.schematic { width: 100%; height: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
.schematic .run { stroke: var(--accent); stroke-linecap: round; opacity: 0.85; }
.schematic .arrow { fill: var(--accent); }
.schematic .node { fill: var(--bg); stroke: var(--fg); stroke-width: 2; }
.schematic .node.boundary { fill: var(--accent); stroke: var(--accent); }
.schematic .node.demand { fill: var(--warn); stroke: var(--warn); }
.schematic .node-label { fill: var(--fg); font-size: 12px; font-weight: 600; }
.schematic .node-readout, .schematic .edge-label { fill: var(--muted); font-size: 10.5px; font-variant-numeric: tabular-nums; }
footer { margin-top: 44px; padding-top: 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
@media print { body { background: #fff; } .schematic { break-inside: avoid; } section { break-inside: avoid; } }
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
            f"<section><h2>The network</h2>{_diagram(study.get('nodes') or [], study.get('edges') or [])}</section>",
            _critical_path(study),
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
