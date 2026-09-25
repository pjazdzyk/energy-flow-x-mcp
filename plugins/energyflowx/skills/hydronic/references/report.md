# The study report

```bash
python3 scripts/render_study.py study.json -o study.html
```

One JSON file in, one self-contained HTML page out. No dependencies beyond Python 3.9, no network,
nothing to install. The page carries its own CSS and SVG, works in light and dark, and prints.

## Why a renderer rather than writing the HTML yourself

Because the parts that matter most are the parts a summary written from memory drops. The
qualifications section is the clearest case: it is the least interesting-looking part of the page and
the one that stops a bounded number being handed over as a computed one. Emitted by code from data, it
cannot be forgotten.

The diagram is the second reason. A network result is spatial (which way the flow goes, where the
pressure runs out, which branch is the problem), and a table makes the reader rebuild that picture in
their head. They will rebuild it wrong.

## The schema

Everything is optional except what you want on the page. Nothing is invented: a field you leave out
produces an em dash or an omitted section, never a guess.

```json
{
  "title": "Campus ring main",
  "project": "North site",
  "revision": "A",
  "date": "2026-09-24",
  "author": "P. Jazdzyk",
  "scenario": "Peak",
  "fluid": "Water at 12 degC",

  "converged": true,
  "iterations": 5,

  "qualifications": [
    {
      "element": "P1",
      "code": "PUMP_OUTSIDE_RATED_RANGE",
      "finding": "Pump outside rated range",
      "what": "Pump 'P1' settled at 6.000 kg/s, outside the 1.000 to 4.000 kg/s range its curve describes."
    }
  ],

  "criticalPath": {
    "from": "plant", "to": "blockB",
    "totalDrop_kPa": 110.7, "residual_kPa": 389.3,
    "elements": ["r1", "r2"]
  },

  "nodes": [
    {"id": "plant", "kind": "FIXED_PRESSURE", "elevation_m": 0, "pressure_kPa": 500,
     "flow_kg_s": -15, "isSupply": true},
    {"id": "blockB", "kind": "FIXED_DEMAND", "elevation_m": 11, "pressure_kPa": 389.3, "flow_kg_s": 4.5}
  ],

  "edges": [
    {"id": "r1", "from": "plant", "to": "blockA", "size": "DN150", "length_m": 120,
     "flow_kg_s": 6.921, "velocity_m_s": 0.39, "dp_kPa": 1.3}
  ],

  "assumptions": ["Commercial steel, tabulated roughness, no ageing allowance."],
  "notes": "The ring feeds A and B clockwise, C and D anticlockwise. The divide sits on run r3."
}
```

### Equipment and a run over time

Copy the solve's `devices` rows in as they are, and for a run over time a `transient` object carrying
its `simulated_s`, `timeStep_s`, `stopReason`, `vessels`, `events` and `series`:

```json
{
  "devices": [
    {"id": "comp", "type": "COMPRESSOR", "electricalPower_kW": 34.3, "recoveredEnergy_kWh": 8.14, "starts": 7}
  ],
  "transient": {
    "simulated_s": 1200, "timeStep_s": 10, "stopReason": "Reached time horizon (1200.0 s).",
    "vessels": [{"id": "receiver", "start_kPa": 800, "min_kPa": 719.4, "min_at_s": 120,
                 "max_kPa": 910.4, "max_at_s": 1200, "end_kPa": 910.4}],
    "events": [{"t_s": 120, "device": "comp", "command": 1.0}],
    "series": [{"t_s": 0, "receiver_kPa": 800, "tank_C": 10.0, "comp_cmd": 1.0}]
  }
}
```

The page labels each device figure from the unit in its field name, charts the series one unit at a
time, and says that a run over time is steady solves in steps, so pressure waves are not in it.

### Units are in the field names

`pressure_kPa`, `flow_kg_s`, `velocity_m_s`, `elevation_m`, `length_m`, `dp_kPa`, `totalDrop_kPa`.

This is the one rule worth being rigid about. A unit mistake in hydraulics is trivially easy to make,
produces a number that looks entirely plausible, and can survive all the way to a purchase order. The
schema makes it impossible to write a number without saying what it is, and the page prints the unit in
every column header for the same reason.

Convert once, on the way in, and never again.

### `qualifications`

Map each entry from the engine's `runNotices`:

| study field | from |
| --- | --- |
| `element` | `elementId` |
| `code` | `code` |
| `finding` | a short human phrase for the code, e.g. "Pump outside rated range" |
| `what` | `message`, **verbatim** |

Relay the engine's sentence unchanged. It carries the numbers that let a reviewer decide whether it
matters, and rewriting "past the 3.50 kg/s runout" into "outside its range" deletes the only figure on
the line.

A `NON_PHYSICAL_PRESSURE` entry changes the whole page: the verdict becomes "These results are
withdrawn" and the reader is told not to quote anything. The renderer does that on the code, so get the
code right.

An empty list is fine and is not the same as omitting the field. Either way the section still appears,
saying the solve raised nothing. A heading that only shows up when there is bad news teaches readers
that its absence means nothing was checked.

### `isSupply`

Marks the node the diagram lays out from. If you omit it, the renderer takes the first pressure
boundary, then the first node. Set it on a real network: it decides which end of the page the far end
of the system ends up on.

### What a solve can fill in

A solve returns at most 50 edges and 50 nodes, ranked. For a network within that, ask
`hydronic_solve` with `detail=50` and every row is there. `velocity_m_s` comes from the solve's
`velocity_mps`, which for a gas is the velocity at the pipe's faster end; say so in `assumptions` when
the schedule is a gas one. For a larger network the schedules hold
the ranked rows only: say that in `notes` rather than leaving the reader to think the table is
complete. `criticalPath` is optional. Fill it only by tracing a route you can name from the edges
you have.

### Sign conventions

`flow_kg_s` on an edge is signed against the declared `from` → `to`. Keep the sign. The arrow on the
diagram follows it, and around a ring the place the sign changes is the flow divide, the single most
useful thing on the page, and invisible if you pass magnitudes.

`flow_kg_s` on a node is net: negative where fluid enters the network, positive where it leaves.

## The diagram

A riser diagram: the orthogonal schematic engineers sketch by hand, laid out from the model rather
than invented (`scripts/study_layout.py`, which has no idea what SVG is and is tested on its own):

- **A spanning tree grown by flow** from the supply. On a ring or a grid the edges left out are the
  ones carrying the least, which is where the flow divides, so each loop is opened at the one place a
  ring is meant to be read open. The left-out edges are drawn dashed, routed around the tree.
- **One lane per branch.** The child with the largest subtree continues straight in its parent's
  lane, the others branch off into lanes of their own, and every leaf gets one to itself. Two branch
  lines can therefore never share a row.
- **x = one step per node** along the tree, so a run reads left to right and the far end of the
  network lands at the far end of the page.
- **Elevation in bands.** Everything at a higher elevation is drawn above everything at a lower one,
  with a datum line and its level on the left, so elevation is still up the page without a whole
  floor collapsing onto one row. With no elevations anywhere it is a topology sketch and the caption
  says so.
- **Line weight = flow magnitude**, relative to the largest in the network. **Arrow = direction**,
  from the sign. **Node fill = pressure**, deep where it is plentiful and pale where it runs out, so
  the weak end is visible without reading a figure. The critical path, when the study names one, is
  drawn lighter.
- **Labels are rationed.** An id beside each node and a size along each run, nothing else. Every
  figure is on hover (the `<title>` of each node and run), in the schedules, and in at most six
  call-outs: the supply, each device's outlet, the far end of the critical path and the lowest
  pressure. A run label with no clear spot is left off rather than printed on top of something.
- **The canvas grows with the network** and scrolls when wider than the page. It never shrinks the
  drawing below three quarters of its natural size, so the text stays legible.

`scripts/test_study_layout.py` parses the SVG the renderer emits and fails on any two labels that
touch, any run that crosses a label or a call-out, and anything outside the canvas, on a sprinkler
tree, the same tree closed into a grid, a ring main with long names, a wide tree and a flat one.

The caption calls it a schematic, not a P&ID, and not to scale. Leave that in.

## Checking your work

```bash
python3 scripts/test_render_study.py
python3 scripts/test_study_layout.py
```

Covers the invariants that matter: the qualifications section is always emitted, a non-physical
pressure withdraws the results, a non-converged run says its numbers are a last iterate, missing values
render as dashes rather than zeros, and a network with no elevations still draws.
