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


def main() -> int:
    for test in [
        test_qualifications_are_always_present,
        test_a_non_physical_pressure_withdraws_the_study,
        test_a_failed_run_is_not_presented_as_an_answer,
        test_missing_values_are_dashes_not_zeros,
        test_the_diagram_is_honest_about_what_it_is,
        test_flow_direction_survives,
        test_a_broken_input_does_not_crash,
        test_user_text_cannot_break_the_page,
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
