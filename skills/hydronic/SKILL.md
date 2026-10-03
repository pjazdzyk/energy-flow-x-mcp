---
name: hydronic
description: >-
  Design and solve piped and ducted networks with the EnergyFlowX Hydronic MCP server, then present the
  result as an engineering study with a P&ID-symbol diagram and schedules. Use it whenever the work is a
  network rather than a single run: heating, chilled-water and glycol circuits, ring mains, risers,
  compressed-air rings and compressor rooms, gas distribution, ducts, steam mains, refrigerant lines,
  several fluids in one plant. Use it for plant with equipment: a pump's duty point, a compressor with
  heat recovery into a hot-water tank, a receiver, a heat exchanger between circuits. Use it for
  questions over time: how often a compressor cycles, how long the air lasts after a trip, how fast a
  tank heats. Use it for questions that sound simpler but are not: sizing a branch in a loop, whether the
  far end has enough pressure. Use it at the START of such a job, while the request is still vague and
  before anything is assumed. Reach for it even when the user never says "hydraulic" or "MCP".
---

# Hydronic network design

You are being asked to size, solve or diagnose a **network**: pipes joined at nodes, with something
holding the pressure and something making the fluid move. This skill covers the whole job: building
the network on the server, solving it, reading the answer like an engineer, and handing it over as a
study somebody can check. It is the decision layer. The references hold the detail and the figures.

## The single most important habit

**A converged solve is not a correct answer.** The solver will happily return a clean, ordinary-looking
result for a network that is physically impossible, because a fixed demand is a promise it keeps
whatever it costs. Always read the solve's `warnings` before you quote a number. The engine's run
notices arrive there as complete sentences, beside the validation warnings and the assumptions it
made. They say what computing the answer actually involved: a substituted fluid property, a value
held at a physical limit, a node at a pressure no fluid can be at, a run over time that stopped early.
Numbers with a notice against them are not the same kind of fact as numbers without one, and the
difference is invisible on screen.

## Before you build anything

Most hydraulic jobs arrive underspecified. `references/gathering-inputs.md` is the long version.

**Work out what the unknown is.** "Size my system" is several different jobs: the diameters (sizing),
the pressure at some point (checking), the plant pressure or a pump's duty point (selection), where
the pressure goes (diagnosis), which of two options (comparison), or how the plant behaves over time
(a transient run). Each needs different data, and the wrong one produces a confident, correct answer to
a question nobody asked.

**Then build what you can and let the server say what is missing.** A half-built design is a normal
state. `hydronic_inspect(handle, what="readiness")` splits what is missing into what would make the
answer meaningless and what merely gets assumed. Ask the user once, for the blocking group only, in
their words rather than the API's.

**Never assume these**, because each produces a complete and fictional study: a glycol or brine
concentration, elevations in anything with more than one floor, the ΔT behind a duty in kW, what a gas
volume was measured at (free air, normal or standard cubic metres, or line conditions), the humidity of
humid air, the composition of a natural gas, the demands themselves, and the acceptance criterion. The
server refuses the first group outright. The rest you ask for.

**Gauge or absolute.** The server takes absolute pressure and users almost always mean gauge. Unless
they say otherwise, add 101.325 kPa (1.013 bar) yourself and say so in the same sentence as the answer:
"I have taken your 4 bar as gauge, so 5.01 bar absolute". `convert_units` has no gauge unit, so this one
conversion is yours, and stating it is what makes it checkable.

**Duties in kW** become flows through `ṁ = Q / (cp·ΔT)`, with `cp` from `get_fluid_properties` at the
design temperature, never from memory. State the ΔT with the answer: doubling it halves the flow and
changes every pipe size. A burner's kW becomes a gas flow through the calorific value from
`get_natural_gas_properties`.

**Know the size limit before you plan.** One design holds up to 2,000 nodes, pipes and devices
together, one edit call carries up to 500 ops, and an account keeps up to 20 designs open. That is a
building, a plant room, a campus loop or a district branch, not a city. For anything larger, agree with
the user where to split it, model each part as its own design with the connection to its neighbour as
a fixed-pressure boundary at the pressure the other part delivers, and say in the study that it was
split. An export near the limit is about 250,000 characters: hand it over as a file, never paste it
into the chat. These limits apply to free use and may be lowered to match server capacity, so trust the
server's refusal over the numbers here, and tell the user when one comes.

## Which networks it solves

Liquids, gases and steam, in steady state or over time: water and glycol circuits, water mains,
compressed air, natural gas and other fuel and industrial gases, ventilation ducts of dry or humid air,
steam mains, and refrigerant liquid or vapour lines, in round, rectangular or elliptic pipes and ducts.
`hydronic://vocabulary/fluids` lists the fluids and what each needs; `hydronic_inspect(what="fluids")`
gives the same list to a client that cannot read resources.

**Several fluids, one per system.** The gas supply to a boiler house and the heating circuit it fires
are two systems in one session: `set_fluid` with `system: "gas"` creates the second, and its pipes carry
`system: "gas"`. Each system is solved at its own temperature and fill pressure. A node joining two
systems is refused, since fluids meet only inside a device, and the systems a device joins are solved
together.

**Equipment.** `add_device` adds a pump (liquids only), an air compressor with heat recovery, a heater
or boiler, a heat exchanger between two systems, or a storage tank, and pipes reach its ports as
`"device.port"`. A receiver or an expansion vessel is a `PRESSURE_TANK` node. Read
`hydronic://vocabulary/devices` first: a setting the type does not take is refused by name.

**Over time.** `add_schedule` drives a pump, a compressor, a demand or a boundary pressure through a
profile, `add_controller` adds a pressure or flow switch or a PI loop, and `set_transient` states the
duration and step. Each step is a steady network solve, so water hammer and surge are not modelled.

**What changes for a gas.** A demand needs its state: a mass flow, a normal or standard volume in the
unit (`"450Nm3/h"`, `"120Sm3/h"`, `"80scfm"`), or a plain volume with `flowBasis` (`FAD` for free air
delivery, dry air only, or `ACTUAL` for the volume at the line). A plain gas volume with no basis is
refused. The density follows the pressure along every pipe, and for a gas the velocity limit usually
decides the size before the pressure drop does. Each system stays in one phase: model steam superheated
by a few kelvin at the highest pressure in the system, and condensate as `WATER` in a system of its own.

## The two servers

| | address | plugin server name | tools | key |
| --- | --- | --- | --- | --- |
| Networks | `/mcp/hydronic` | `energy-flow-x-hydronic` | `hydronic_session`, `hydronic_edit`, `hydronic_solve`, `hydronic_inspect` | **required** |
| Fluids and single conduits | `/mcp` | `energy-flow-x` | property, saturation, unit-conversion and conduit-sizing tools | none |

They are separate MCP servers, and the plugin connects both. The hydronic server needs the user's free
EnergyFlowX account, and a client that supports MCP sign-in asks for it on its own: in Claude Code the
server shows as needing authentication, and the user runs `/mcp`, picks `energy-flow-x-hydronic` and
approves in the browser. A client that cannot sign in sends an API key instead. If a hydronic call comes
back saying it needs an account, relay that with the access terms it states:
network solving is free while it is being tested, that is temporary, and it can change at any time.
Never ask the user to paste a token or a key into the chat.

## The loop

`references/workflow.md` has every call and its arguments. In outline:

1. **Read the vocabulary once**, as MCP resources: the ops, fittings, materials and fluids, the devices
   when there is equipment, and the recipe nearest the problem. Most clients do not fetch resources
   unless asked, and a burst of reads trips the rate limiter, so pace them about a second apart.
2. **Open a session.** `hydronic_session(action="create")` returns a handle. The network lives on the
   server and is never passed as an argument.
3. **Edit in batches.** One `hydronic_edit` call carries many ops and is all-or-nothing. Build the whole
   topology in one or two calls.
4. **Solve.** `hydronic_solve(handle)` for one operating state. For behaviour over time, add the
   schedules and controllers, state the run with `set_transient`, solve steady first as a check that the
   plant works at all, then solve with `mode="transient"`.
5. **Read the rest.** `detail=50` returns every element of a network up to 50 elements.
   `hydronic_inspect` reads the design back as authored, never solved values.
6. **Report.** See "Handing it over".

Quantities are strings that carry their units: `"150mm"`, `"2.5bar"`, `"70oC"`, `"1.2kg/s"`,
`"12m3/h"`. A bare number is the most common way an answer comes out wrong by three orders of
magnitude, and a field that does not belong to its op is refused by name, so a typo fails loudly.

## Reading the answer

`references/reading-results.md` explains each item and gives the sanity ranges. Read in this order,
because each can invalidate the ones after it:

1. **`warnings`.** A node that "settled at" a pressure at or below zero absolute, or a `PHASE` warning,
   withdraws the answer: do not quote numbers from that run. `NEAR CHOKING` says a gas run is badly
   undersized. In a design with several systems every warning starts with its system's name.
2. **`converged`.** False means the numbers are a last iterate, worth reading only for where it got stuck.
3. **`lowestPressureNodes` and `worstEdges`.** The lowest node is where the design works or fails. The
   worst edges name the run to change, with friction, local and static parts apart.
4. **Signs on edge flows.** In a loop, where the sign flips is the **flow divide**, and it is usually the
   most useful sentence in a ring's report.
5. **`fastestEdges`.** An order of magnitude away from the usual range for the service usually means a
   unit went in wrong or a demand is on the wrong node.

### A run over time

A transient comes back as answers, not a time series:

1. **`completed` first.** A run that meets its compute limit is not refused. It returns the steps it
   computed with `completed: false`, and its first warning says it is INCOMPLETE, how far it got, and
   why it stopped. Then tell the user three things, in this order. The run is unfinished, and stopped at
   the time it names. Its last state is where the run stopped, not how the plant ends up, so you do
   not quote it as the outcome. It fits within the limit with a longer `timeStep` or a shorter duration.
   Longer runs are quoted individually by EnergyFlowX at the contact the warning gives. A run refused
   because another is in progress says when to retry: wait that long, then solve again.
2. **`vessels`**: each receiver's lowest and highest pressure, with when. A vessel "held at the floor"
   ran empty, and the demand shown after that is a promise, not delivery.
3. **`events` and each machine's `starts`**: many starts in a short run is short-cycling.
4. **`devices`**: power, energy, recovered heat, how far each store charged. The heat a compressor or
   heater put in should reappear in the store within a few per cent.
5. **`lowestPressureNodes`** with `at_s`, and the sampled **`series`** for the shape of the curve.

## What goes wrong, and what it means

Each of these looks like something else at first glance.

**"Nothing drives flow."** No node draws flow and there are not two boundaries at different pressures.
Add a `FIXED_DEMAND`, or a second pressure boundary at a different pressure.

**"Nothing anchors the pressure."** No `FIXED_PRESSURE` or `OUTLET` node and no `fillPressure`, so every
absolute reading would be arbitrary. For a sealed loop, set `fillPressure` and say that the absolute
pressures rest on it.

**A node at or below zero absolute.** The network cannot deliver what is asked of it: the solver drove
the pressure through zero to keep a fixed demand. Reduce the demand, open up the run, or raise the
supply pressure. Do not report the numbers.

**A request for a control valve, balancing or regulation.** This release has none of them. A pump on a
liquid is a device with its datasheet curve, and its duty point is the solve's answer. A pump on a gas is
refused: a gas network is driven by a compressor or by its boundary pressures.

**A missing concentration, humidity or composition.** Refused, and rightly: a defaulted value is a wrong
friction loss presented as a real one. Ask for it.

**"The network cannot carry the demanded flow."** A gas network whose pressure would have to fall below
what the gas can be evaluated at, which in a real line means it chokes. Enlarge the busiest runs,
shorten them, raise the supply pressure or lower the demand.

**A gas volume "means nothing without the state it was measured at".** Ask: a compressor or tool rating
is free air delivery, a gas meter or boiler figure is normal or standard cubic metres, a ventilation
airflow is the volume at the duct.

**"This transient run is INCOMPLETE."** It met its step or time limit and returned what it computed. See
"A run over time" for what to tell the user. For a pressure switch, keep the step at or below a tenth of
the shortest time the compressor spends loaded or unloaded, or the switching instants blur.

**"device ... has ports with no pipe".** Every port of a device needs a pipe. The one exception is a
compressor's water side: leave both water ports open and its heat is rejected rather than recovered.

**A compressor refused for missing settings.** Free air delivery, discharge pressure, power or
isentropic efficiency, recoverable heat and aftercooler outlet temperature are on its datasheet, and
each changes the answer. Ask for them. Never fill them in from a typical value.

**"schedules and controllers were not applied".** A steady solve holds every machine at its stated
command. The run over time is `mode="transient"`.

**A `PHASE` warning.** The fluid left its phase at the nodes named: steam condensing, a liquid flashing,
water boiling at a high point, humid air at its dew point. Change the design, not the reading.

## Handing it over

When the work is for someone else, produce an **HTML study**, not a wall of numbers in chat. A network
result is spatial, and a table alone makes the reader rebuild the picture in their head, wrongly. Use
the bundled renderer rather than writing HTML by hand:

```bash
python3 scripts/render_study.py study.json -o study.html
```

It takes one plain JSON file (`references/report.md` has the schema and an example) and emits one
self-contained page: the verdict, the qualifications, a riser diagram of the network drawn in the same
P&ID symbols as the EnergyFlowX Hydronic builder with a key beneath it, what each device did, a run over
time with its vessels and charts, and the node and edge schedules.

Four things about filling it in are not optional:

- **Copy every warning that is a run notice into `qualifications`**, the sentence verbatim, with the
  code its wording names (the table in `references/report.md`). That section is never dropped, and an
  impossible pressure or an incomplete run changes the whole page's verdict.
- **Copy run endpoints as authored**, `"comp.airOut"` included, and the solve's `devices` rows as they
  are. The renderer draws each device as its symbol, once, with every run to any of its ports.
- **Keep `completed` and `steps`** in the `transient` block. An unfinished run is then headed as one
  rather than as solved.
- **Units are in the field names** (`pressure_kPa`, `flow_kg_s`). Convert once, on the way in.

The diagram is a schematic and says so: it is laid out from the graph and the elevations, not from
coordinates, and it is not a P&ID or to scale. Leave that label alone.

If the user only wants a quick answer in chat, give them the answer and offer the study. If they are
going to send it to anyone, build the study.

## When the network is one pipe

A single run with a known flow, "what size for 2 kg/s over 40 m", is answered by `size_conduit` or
`select_conduit_size` on the free `/mcp` endpoint, with no account and no session.

The line between them: **sizing one pipe assumes its flow is already known.** The moment the flow
through a pipe depends on the rest of the system (anything in a loop, anything downstream of a branch,
anything where two routes compete), only a network solve can answer it. If you catch yourself guessing
how a flow splits, stop and build the network.

## Files

- `references/gathering-inputs.md`: deciding what to solve, and getting the data to solve it.
- `references/workflow.md`: every call, its arguments, and the order to make them in.
- `references/reading-results.md`: how to interpret a solve, the sanity ranges, and the traps in detail.
- `references/report.md`: the study JSON schema, with a worked example.
- `scripts/render_study.py`: the HTML study renderer. No dependencies beyond Python 3.9.
- `scripts/study_layout.py`: the riser-diagram layout, pure and tested on its own.
- `scripts/study_glyphs.py`: which P&ID symbol draws which node kind and device type.
