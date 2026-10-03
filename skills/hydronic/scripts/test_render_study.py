#!/usr/bin/env python3
"""Invariants of the study renderer.

Run: python3 scripts/test_render_study.py

These are not style checks. Each one is a property of the page that someone downstream relies on, and
each would fail silently if it broke: a missing qualifications section looks like a clean study, a
withdrawn result that still reads "Solved" looks like an answer, and a dash rendered as 0.00 looks like
a measurement.

Standard library only, so the skill's own tests run anywhere the skill does.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_study import render  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
        FAILURES.append(name)


def base(**overrides) -> dict:
    study = {
        "title": "Test study",
        "converged": True,
        "iterations": 4,
        "nodes": [
            {"id": "src", "kind": "FIXED_PRESSURE", "elevation_m": 0, "pressure_kPa": 400,
             "flow_kg_s": -2.0, "isSupply": True},
            {"id": "far", "kind": "FIXED_DEMAND", "elevation_m": 6, "pressure_kPa": 330,
             "flow_kg_s": 2.0},
        ],
        "edges": [
            {"id": "run", "from": "src", "to": "far", "size": "DN50", "length_m": 40,
             "flow_kg_s": 2.0, "velocity_m_s": 1.02, "dp_kPa": 24.8},
        ],
    }
    study.update(overrides)
    return study


def test_qualifications_are_always_present() -> None:
    print("qualifications are never dropped")
    clean = render(base())
    check("a clean run still shows the section", "Qualifications" in clean)
    check("and says nothing was raised, rather than staying silent", "raised none" in clean,
          "a heading that only appears with bad news teaches readers that its absence means nothing")

    noticed = render(base(qualifications=[{
        "element": "P1", "code": "PUMP_OUTSIDE_RATED_RANGE", "finding": "Pump outside rated range",
        "what": "Pump 'P1' settled at 6.000 kg/s, past the 4.000 kg/s runout its curve describes.",
    }]))
    check("the engine's sentence is carried through verbatim",
          "past the 4.000 kg/s runout" in noticed,
          "the numbers in it are what let a reviewer judge whether it matters")
    check("the element is named so it can be found on the drawing", ">P1<" in noticed)


def test_a_non_physical_pressure_withdraws_the_study() -> None:
    print("an impossible pressure withdraws the results")
    page = render(base(qualifications=[{
        "element": "far", "code": "NON_PHYSICAL_PRESSURE", "finding": "Impossible pressure",
        "what": "Node 'far' settled at -28.80 kPa absolute.",
    }]))
    check("the verdict says the results are withdrawn", "withdrawn" in page.lower())
    check("and does not say 'Solved, with qualifications'",
          "Solved, with qualifications" not in page,
          "this is not a caveat on a usable number, it is the absence of one")
    check("the reader is told not to quote anything", "should be quoted" in page)


def test_a_failed_run_is_not_presented_as_an_answer() -> None:
    print("a run that did not converge")
    page = render(base(converged=False))
    check("says the numbers are a last iterate", "last iterate" in page)
    check("and does not read as solved", ">Solved<" not in page)


def test_missing_values_are_dashes_not_zeros() -> None:
    print("nothing is not zero")
    page = render(base(nodes=[{"id": "a", "kind": "JUNCTION"}, {"id": "b"}],
                       edges=[{"id": "e", "from": "a", "to": "b"}]))
    check("an absent number renders as a dash", "&mdash;" in page)
    check("and never as 0.00", ">0.00<" not in page,
          "a zero reads as a measurement; a dash reads as 'not reported', which is the truth")


def test_the_diagram_is_honest_about_what_it_is() -> None:
    print("the diagram")
    with_elevation = render(base())
    check("says it is a schematic and not a P&ID", "not a P&amp;ID" in with_elevation)
    check("names its axes when elevations are given", "Elevation up the page" in with_elevation)

    flat = render(base(nodes=[{"id": "a", "kind": "FIXED_PRESSURE"}, {"id": "b", "kind": "FIXED_DEMAND"}],
                       edges=[{"id": "e", "from": "a", "to": "b", "flow_kg_s": 1.0}]))
    check("and admits when it is only topology", "topology sketch" in flat,
          "a vertical axis that means nothing is worse than one that says so")


def test_flow_direction_survives() -> None:
    print("signs, which is where the flow divide lives")
    page = render(base(edges=[
        {"id": "f", "from": "a", "to": "b", "flow_kg_s": 2.0},
        {"id": "r", "from": "b", "to": "c", "flow_kg_s": -0.58},
    ], nodes=[{"id": "a", "kind": "FIXED_PRESSURE"}, {"id": "b"}, {"id": "c", "kind": "FIXED_DEMAND"}]))
    check("a reversed run keeps its negative sign in the schedule", "-0.58" in page)
    check("both runs get an arrow", page.count('class="arrow"') == 2,
          "the arrow is the only place direction is visible on the diagram")
    check("the page explains what a negative flow means", "against the direction" in page)


def test_a_broken_input_does_not_crash() -> None:
    print("degenerate inputs")
    for name, study in {
        "empty": {"title": "x", "nodes": [], "edges": []},
        "edge pointing at a node that does not exist":
            {"title": "x", "nodes": [{"id": "a"}], "edges": [{"id": "e", "from": "a", "to": "ghost"}]},
        "nulls everywhere":
            {"title": "x", "nodes": [{"id": "a", "kind": None, "pressure_kPa": None}],
             "edges": [{"id": "e", "from": "a", "to": "a", "flow_kg_s": None}]},
        "no title at all": {"nodes": [{"id": "a"}], "edges": []},
    }.items():
        try:
            page = render(study)
            check(f"renders: {name}", page.startswith("<!DOCTYPE html>") and len(page) > 500)
        except Exception as error:  # noqa: BLE001 - the point is that nothing escapes
            check(f"renders: {name}", False, f"{type(error).__name__}: {error}")


def test_user_text_cannot_break_the_page() -> None:
    print("escaping")
    page = render(base(title='Block <script>alert(1)</script> "C"',
                       notes="a & b < c",
                       qualifications=[{"element": "<b>x</b>", "finding": "f", "what": "w & w"}]))
    check("markup in user text is escaped", "<script>alert(1)</script>" not in page)
    check("and the text itself survives", "alert(1)" in page)
    check("ampersands are escaped", "a &amp; b &lt; c" in page)


def test_equipment_and_a_run_over_time_render_as_the_solve_returns_them() -> None:
    print("equipment and a run over time")
    study = base(
        devices=[{"id": "comp", "type": "COMPRESSOR", "electricalPower_kW": 34.3, "recoveredEnergy_kWh": 8.137,
                  "starts": 7}],
        transient={
            "simulated_s": 1200, "timeStep_s": 10, "stopReason": "Reached time horizon (1200.0 s).",
            "vessels": [{"id": "receiver", "start_kPa": 800, "end_kPa": 910.4, "min_kPa": 719.4, "min_at_s": 120,
                         "max_kPa": 910.4, "max_at_s": 1200}],
            "events": [{"t_s": 10, "device": "comp", "command": 1.0}, {"t_s": 120, "device": "comp", "command": 0.0}],
            "series": [{"t_s": 0, "receiver_kPa": 800, "tank_C": 10.0, "comp_cmd": 1.0},
                       {"t_s": 600, "receiver_kPa": 850, "tank_C": 13.5, "comp_cmd": 0.0},
                       {"t_s": 1200, "receiver_kPa": 910.4, "tank_C": 16.96, "comp_cmd": 1.0}],
        },
    )
    page = render(study)
    check("the equipment table labels each figure with the unit its field name carries",
          "Electrical power <strong>34.30</strong> kW" in page and "Recovered energy" in page and "kWh" in page)
    check("a vessel's lowest pressure comes with when", "719.4 at 120 s" in page)
    check("every command change is listed", page.count("<td>comp</td>") >= 2)
    check("a chart per unit, pressure and temperature apart", page.count("class='chart'") == 3)
    check("and the page says what a run over time is not", "water hammer are not part of it" in page)
    steady = render(base())
    check("a steady study shows neither section", "Over time" not in steady and "Equipment" not in steady)


def plant() -> dict:
    """The compressor heat-recovery recipe's shape: air in, a compressor, a receiver and a tool on one
    system, and the compressor's oil-cooler heat pumped into a store on the other, both runs reaching the
    compressor through its ports as authored."""
    return {
        "title": "Compressor room", "converged": True,
        "nodes": [
            {"id": "intake", "kind": "FIXED_PRESSURE", "pressure_kPa": 100.0, "flow_kg_s": -0.12},
            {"id": "receiver", "kind": "PRESSURE_TANK", "pressure_kPa": 800.0},
            {"id": "tool", "kind": "FIXED_DEMAND", "pressure_kPa": 760.0, "flow_kg_s": 0.12},
            {"id": "water", "kind": "FIXED_PRESSURE", "pressure_kPa": 250.0},
        ],
        "edges": [
            {"id": "a1", "from": "intake", "to": "comp.airIn", "size": "DN80", "flow_kg_s": 0.12},
            {"id": "a2", "from": "comp.airOut", "to": "receiver", "size": "DN50", "flow_kg_s": 0.12},
            {"id": "a3", "from": "receiver", "to": "tool", "size": "DN40", "flow_kg_s": 0.12},
            {"id": "w1", "from": "water", "to": "p1.inlet", "size": "DN25", "flow_kg_s": 0.3},
            {"id": "w2", "from": "p1.outlet", "to": "comp.waterIn", "size": "DN25", "flow_kg_s": 0.3},
            {"id": "w3", "from": "comp.waterOut", "to": "store.in", "size": "DN25", "flow_kg_s": 0.3},
        ],
        "devices": [
            {"id": "comp", "type": "COMPRESSOR", "electricalPower_kW": 34.3, "recoveredHeat_kW": 24.4},
            {"id": "p1", "type": "PUMP", "massFlow_kgps": 0.3, "rise_kPa": 45.0},
            {"id": "store", "type": "STORAGE_TANK", "stored_C": 41.2},
        ],
    }


def test_equipment_is_drawn_as_its_symbol() -> None:
    print("equipment and boundaries as P&ID symbols")
    page = render(plant())
    for name in ("compressor-screw-recovery", "pump-horizontal", "storage-tank", "fixed-pressure",
                 "fixed-demand", "pressure-tank"):
        check(f"{name} is drawn and defined once", page.count(f'href="#efx-sym-{name}"') >= 1
              and page.count(f'<symbol id="efx-sym-{name}"') == 1)
    check("a symbol nobody uses is not shipped in the page", 'id="efx-sym-wtr-hx-plate"' not in page)
    check("each device is one node on the drawing, whatever its ports",
          page.count('class="node device"') == 3,
          "three devices, so three plates; a plate per port would draw the compressor twice")
    check("a run to a port ends on its device", "comp.airIn" not in page.split("<svg", 1)[1].split("</svg>", 1)[0])
    check("the schedule still shows the run as authored, port and all", "comp.airIn" in page)
    check("the key names every symbol drawn", all(label in page for label in (
        "Compressor with heat recovery", "Pump", "Storage tank", "Pressure boundary", "Demand",
        "Receiver or expansion vessel")))
    check("a device carries its own figures on the drawing", "34.3 kW electric" in page and "24.4 kW recovered" in page)
    check("the caption says what the orange frame is", "Equipment is drawn in an orange frame" in page)
    check("the symbols are defined after the drawing, so the network is the first picture on the page",
          page.index('<svg class="sprite"') > page.index('class="schematic"'))


def test_a_symbol_faces_the_way_its_pipe_runs() -> None:
    print("symbols face their pipework")
    from study_glyphs import mirrored
    check("a boundary whose runs all leave left is mirrored", mirrored("out", [-1, -1], []))
    check("a boundary feeding right is not", not mirrored("out", [1], []))
    check("a demand fed from the right is mirrored", mirrored("in", [1], [1]))
    check("a pump whose fluid arrives from the right is mirrored", mirrored("through", [1, -1], [1]))
    check("a pump fed from the left is not", not mirrored("through", [-1, 1], [-1]))
    check("a vertical connection says nothing about left and right", not mirrored("in", [0], [0]))
    check("a symbol with no handedness is never mirrored", not mirrored(None, [1], [1]))
    def pump_mirrored(study: dict) -> bool:
        use = re.search(r'<use class="glyph" href="#efx-sym-pump-horizontal"[^>]*>', render(study))
        return use is not None and "matrix(-1" in use.group(0)

    forward, backward = plant(), plant()
    for edge in backward["edges"]:
        if edge["id"] in ("w1", "w2"):
            edge["flow_kg_s"] = -edge["flow_kg_s"]
    # Where the pump lands depends on the layout; which way it points must depend only on the flow.
    check("reversing the flow through a pump turns its symbol round",
          pump_mirrored(forward) != pump_mirrored(backward),
          "the triangle is the pump's direction, and it must agree with the arrows on its runs")


def test_an_unfinished_run_is_never_called_solved() -> None:
    print("a run over time that stopped at its limit")
    sentence = ("This transient run is INCOMPLETE. It stopped after 1200 steps, at 600 s of the 3600 s asked for, "
                "because it reached its step limit.")
    for name, study in {
        "by its completed flag": base(transient={"completed": False, "steps": 1200, "simulated_s": 600}),
        "by its code": base(qualifications=[{"code": "RUN_LIMIT_REACHED", "what": sentence}]),
        "by the engine's sentence alone": base(qualifications=[{"finding": "Stopped early", "what": sentence}]),
    }.items():
        page = render(study)
        check(f"the verdict says it stopped early, {name}", "The run stopped early, before its end" in page)
        check(f"and never 'Solved', {name}", ">Solved" not in page)
    page = render(base(transient={"completed": False, "steps": 1200, "simulated_s": 600}))
    check("it says how far the run got", "1,200 steps and 600 s of the run" in page)
    check("the run section says it did not complete", "no, stopped early" in page)
    finished = render(base(transient={"completed": True, "steps": 120, "simulated_s": 1200}))
    check("a finished run is not called unfinished", "stopped early" not in finished)


def test_an_impossible_pressure_is_caught_without_its_code() -> None:
    print("the engine's sentence withdraws the results when the code is missing")
    page = render(base(qualifications=[{"finding": "Pressure", "what": "Node 'far' settled at -28.80 kPa absolute."}]))
    check("withdrawn on the sentence alone", "These results are withdrawn" in page,
          "over MCP a notice is a sentence, so the code is the agent's; a wrong one must not read as Solved")
    huge = render(base(qualifications=[{"what": "Node 'far' settled at -1.234e+04 kPa absolute."}]))
    check("and when the engine writes the pressure in exponent form", "These results are withdrawn" in huge,
          "the engine formats it with %.4g, so a large pressure arrives as -1.234e+04")
    pump = render(base(qualifications=[{"finding": "Pump", "what": "Pump 'P1' settled at 6.000 kg/s, past its runout."}]))
    check("a pump that 'settled at' a flow does not withdraw anything", "withdrawn" not in pump.lower())


def main() -> int:
    for test in [
        test_equipment_is_drawn_as_its_symbol,
        test_a_symbol_faces_the_way_its_pipe_runs,
        test_an_unfinished_run_is_never_called_solved,
        test_an_impossible_pressure_is_caught_without_its_code,
        test_qualifications_are_always_present,
        test_a_non_physical_pressure_withdraws_the_study,
        test_a_failed_run_is_not_presented_as_an_answer,
        test_missing_values_are_dashes_not_zeros,
        test_the_diagram_is_honest_about_what_it_is,
        test_flow_direction_survives,
        test_a_broken_input_does_not_crash,
        test_user_text_cannot_break_the_page,
        test_equipment_and_a_run_over_time_render_as_the_solve_returns_them,
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
