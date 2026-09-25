---
name: hydronic-network-design
description: >-
  Design and solve piped and ducted networks with the EnergyFlowX Hydronic MCP server, then present the
  result as an engineering study with a diagram and schedules. Use it whenever the work is a network
  rather than a single run: heating, chilled-water and glycol circuits, ring mains, risers, compressed-air
  rings and compressor rooms, gas distribution, ducts, steam mains, refrigerant lines, several fluids in
  one plant. Use it for plant with equipment: a pump's duty point, a compressor with heat recovery into a
  hot-water tank, a receiver, a heat exchanger between circuits. Use it for questions over time: how often
  a compressor cycles, how long the air lasts after a trip, how fast a tank heats. Use it for questions
  that sound simpler but are not: sizing a branch in a loop, whether the far end has enough pressure.
  Use it at the START of such a job, while the request is still vague: it covers what is being asked and
  what may be assumed. Reach for it even when the user never says "hydraulic" or "MCP".
---

# Hydronic network design

You are being asked to size, solve or diagnose a **network**: pipes joined at nodes, with something
holding the pressure and something making the fluid move. This skill covers the whole job: building
the network on the server, solving it, reading the answer like an engineer, and handing it over as a
study somebody can check.

## The single most important habit

**A converged solve is not a correct answer.** The solver will happily return a clean, ordinary-looking
result for a network that is physically impossible, because a fixed demand is a promise it keeps
whatever it costs. Always read the solve's `warnings` before you quote a number. The engine's run
notices arrive there as complete sentences, beside the validation warnings and the assumptions it
made. They say what computing the answer actually involved: a substituted fluid property, a value
held at a physical limit, a node at a pressure no fluid can be at. Numbers with a notice against them are not the same
kind of fact as numbers without one, and the difference is invisible on screen.

## Before you build anything

Most hydraulic jobs arrive underspecified, and the work starts well before the first tool call.
`references/gathering-inputs.md` is the long version. Two things from it apply almost every time:

**Work out what the unknown is.** "Size my system" is five different jobs. Are the diameters unknown
(sizing), the pressure at some point (checking), the head the plant must supply or a pump's duty point
(selection), the location of a problem (diagnosis), which of two options (comparison), or how the plant
behaves over time (a transient run: a trip, a cycling compressor, a tank charging)? They need different data and different answers, and
getting this wrong costs more than any arithmetic error, because you will produce a confident, correct answer
to a question nobody asked.

**Then build what you can and let the server say what is missing.** A half-built design is a normal
state. `hydronic_inspect(handle, what="readiness")` answers "what do I still need", split into what
would make the answer meaningless and what merely gets assumed. Ask the user once, for the blocking
group only, in their words rather than the API's. That beats a twenty-question intake, and it means you
are never guessing at what is missing.

Some things are never yours to assume, because each produces a complete and fictional study: a
**glycol or brine concentration**, **elevations** in anything with more than one floor, the **ΔT**
behind a duty in kW, and for a gas **what its volume flow was measured at** (free air, normal cubic
metres or line conditions differ by up to a factor of eight at 7 bar), **the humidity** of humid air
and **the composition** of a natural gas. The server refuses each of them rather than guessing. Two more
need a stated assumption rather than silence: whether a given pressure is **gauge or absolute** (the
API takes absolute, users almost always mean gauge, and a bar is a large fraction of most systems),
and the **acceptance criterion**, because "is it OK" has no answer until somebody says what OK is.

Duties in kW become flows through `ṁ = Q / (cp·ΔT)`. Get `cp` from `get_fluid_properties` on the free
endpoint rather than from memory, and state the ΔT in the same sentence as the answer: doubling it
halves the flow and changes every pipe size. A burner's input in kW becomes a gas flow through the
gas's calorific value, which `get_natural_gas_properties` gives for the same preset or composition.

## Which networks it solves

Hydronic MCP solves networks of **liquids, gases and steam**, in steady state or over time: water and glycol
circuits, water mains, compressed air, natural gas and other fuel and industrial gases, ventilation
ducts of dry or humid air, steam mains, and refrigerant liquid or vapour lines. Pipes and ducts may be
round, rectangular or elliptic. `hydronic://vocabulary/fluids` lists the fluids and what each needs;
`hydronic_inspect(what="fluids")` gives the same list to a client that cannot read resources.

**A design can hold several fluids**, one per **system**. The gas supply to a boiler house and the
heating circuit it fires are two systems in one session: `set_fluid` with `system: "gas"` creates the
second, and its pipes carry `system: "gas"`. Each system is solved on its own, at its own temperature
and fill pressure, which is exact because two fluids never share a pipe. A node joining two systems is
refused, since fluids meet only inside a device. A compressor's air and its heat-recovery water, or the
two sides of a heat exchanger, are the systems a device joins, and those are solved together.

**Equipment.** `add_device` adds a pump (liquids), an air compressor with heat recovery, a heater or
boiler, a heat exchanger between two systems, or a storage tank, and pipes reach its ports as
`"device.port"`. A receiver or an expansion vessel is a `PRESSURE_TANK` node. Read
`hydronic://vocabulary/devices` before adding one: it lists each type's ports and settings, and a
setting the type does not take is refused by name.

**Over time.** `add_schedule` drives a pump, a compressor, a demand or a boundary pressure through a
profile, `add_controller` adds a pressure or flow switch or a PI loop, and `set_transient` states the
run's duration and step. `hydronic_solve(mode="transient")` then answers what a plant does over time:
how far a receiver swings, how often a compressor starts, how long the air lasts after a trip, how far
a store charges. Water hammer and surge are not modelled: each step is a steady network solve.

What changes for a gas:

- **Demands need their state.** Give a mass flow, a normal or standard volume in the unit
  (`"450Nm3/h"`, `"120Sm3/h"`, `"80scfm"`), or a plain volume with `flowBasis`: `FAD` for compressed-air
  consumers rated in free air delivery (dry air only), `ACTUAL` for a volume at the line pressure, such
  as ventilation air in m³/h. A plain gas volume with no basis is refused.
- **The density follows the pressure** along every pipe, and the solve reports velocity and Mach
  number, because for a gas the velocity limit usually decides the size before the pressure drop does.
- **One phase per system.** A steam main must stay above its saturation temperature everywhere, a
  refrigerant liquid line above its bubble point pressure, humid air below saturation. The solve checks
  every node and reports a crossing as a `PHASE` warning. Model steam superheated by a few kelvin at the
  highest pressure in the system, and condensate as `WATER` in a system of its own.

For a single run or a straight series path with known flows, the free `size_conduit` and
`select_conduit_size` are still the quicker answer. See "When the network is one pipe" below.

## The two servers

| | address | plugin server name | tools | key |
| --- | --- | --- | --- | --- |
| Networks | `/mcp/hydronic` | `energy-flow-x-hydronic` | `hydronic_session`, `hydronic_edit`, `hydronic_solve`, `hydronic_inspect` | **required** |
| Fluids and single conduits | `/mcp` | `energy-flow-x` | property, saturation, unit-conversion and conduit-sizing tools | none |

They are separate MCP servers, and the plugin connects both under the names above. A client that
needs both connects to both. If a hydronic call comes
back saying it needs an API key, relay that to the user along with the access terms it states:
network solving is free while it is being tested, that is temporary, and it can change at any time.

## The loop

Read `references/workflow.md` for the call-by-call detail. In outline:

1. **Read the vocabulary once.** `hydronic://vocabulary/ops`, `/fittings`, `/materials`, `/fluids`,
   `/devices` when there is equipment, and a recipe from `hydronic://recipes/riser`, `/ring-main`,
   `/compressed-air-ring` or `/compressor-heat-recovery` (equipment and a run over time). These are MCP *resources*, not tools,
   so they cost nothing per turn and most clients will not fetch them unless you ask. Pace them about a
   second apart: a burst trips the rate limiter, and although a throttled call comes back as a
   JSON-RPC error carrying `retryAfterSeconds`, waiting is cheaper than retrying.
2. **Open a session.** `hydronic_session(action="create")` returns a handle. The network lives on the
   server, and you never pass it as an argument. That is deliberate: a network is far too large to sit in
   a tool call, and an incremental edit is how you keep the design and the conversation in step.
3. **Edit in batches.** One `hydronic_edit` call carries many ops and is all-or-nothing. Build the
   whole topology in one or two calls rather than one node at a time.
4. **Solve.** `hydronic_solve(handle)` for one operating state. For behaviour over time, add the
   schedules and controllers, state the run with `set_transient`, and solve with `mode="transient"`.
   Solve steady first even then: it is a quick check that the plant works at all before you spend a run
   on it.
5. **Read the rest of the result.** `hydronic_solve(handle, detail=50)` returns up to 50 rows of the
   worst edges, the fastest pipes and the pressure extremes, which is every element of a network that
   size.
   `hydronic_inspect` reads the design back as you authored it, which is how you check what you built.
   It does not return solved values.
6. **Report.** See "Handing it over" below.

Quantities are strings that carry their units: `"150mm"`, `"2.5bar"`, `"70oC"`, `"1.2kg/s"`,
`"12m3/h"`, `"450Nm3/h"`. This is not decoration. A bare number is the single most common way an answer comes out
wrong by three orders of magnitude, and the server refuses a field that does not belong to its op, by
name, so a typo fails loudly instead of being ignored.

## Reading the answer

`references/reading-results.md` is the long version, and it is worth reading before you interpret a
solve for someone. The short version is five things, in this order:

1. **`warnings`.** Anything here changes what the rest of the result means. A warning that a node
   "settled at" a pressure at or below zero absolute, or a `PHASE` warning, withdraws the answer: do not
   quote numbers from that run as a design. `NEAR CHOKING` says a gas run is undersized by a wide
   margin. In a design with several systems every warning starts with its system's name.
2. **`converged`.** False means the numbers are a last iterate, not a solution. They are still worth
   looking at for *where* it got stuck, and worth nothing as an answer.
3. **`lowestPressureNodes` and `worstEdges`.** The lowest node is where the design works or fails,
   far more often than any single pipe's velocity. The worst edges rank where the head goes, with
   friction, local and static parts split apart, so they name the run to change.
4. **Signs on edge flows.** In a loop, the sign is the direction, and the place where it flips is the
   **flow divide**, the point the ring feeds from both sides. Nothing about a single pipe can tell
   you where it is, which is exactly why the network had to be solved.
5. **`fastestEdges`.** Each pipe's velocity, and for a gas its Mach number, at the faster end. Around
   0.5 to 1.5 m/s in liquid distribution pipework is unremarkable, compressed-air mains are commonly
   designed for 6 to 10 m/s, and saturated steam mains for 25 to 40 m/s. An order of magnitude out
   usually means a unit went in wrong or a demand is on the wrong node.

### A run over time

A transient comes back as answers, not a time series. Read it in this order:

1. **`completed` and `stopReason`**, then `converged`. A run that stopped early or an instant that did
   not converge qualifies everything after it.
2. **`vessels`**: each receiver's or expansion vessel's lowest and highest pressure, with when. The
   lowest is what the far end saw at its worst, so compare it with what the tools need there. A vessel
   "held at the floor" ran empty: after that the demand shown is a promise, not delivery.
3. **`events` and each machine's `starts`**: the pressure switch cutting in and out, a trip. Many starts
   in a short run is short-cycling, which a larger receiver or a wider band cures.
4. **`devices`**: average power, energy, recovered heat, how far each store charged. Check the energy:
   the heat a compressor or heater put in should reappear in the store, within a few per cent. If it
   does not, something is leaking heat you did not intend, or the run is too short to say.
5. **`lowestPressureNodes`** with `at_s`, and the sampled **`series`** for the shape of the curve.

A switch acts at step boundaries, so a vessel dips below its cut-in by up to one step's worth of draw.
That is the step, not the plant: a shorter step tightens it.

## What goes wrong, and what it means

These are the failures that actually happen, and each one looks like something else at first glance.

**"Nothing drives flow."** No node draws flow and there are not two boundaries at different
pressures. The server refuses rather than returning the zero-flow answer it could compute, because a
confident zero is indistinguishable from a real result when you cannot see a drawing. Add a
`FIXED_DEMAND` to draw flow, or a second pressure boundary at a different pressure.

**"Nothing anchors the pressure."** A refusal. Without a `FIXED_PRESSURE` or `OUTLET` node, or a
`fillPressure`, the pressure field is fixed only up to a constant, so every absolute reading would be
arbitrary. For a sealed loop, set `fillPressure` and say in the answer that the absolute pressures
rest on it.

**A node at or below zero absolute.** The network cannot deliver what is being asked of it. A fixed
demand is delivered whatever it costs, so the solver drives the pressure through zero to keep the
promise. Reduce the demand, open up the run, or raise the supply pressure. Do not report the numbers.

**A request for a control valve, balancing or regulation.** This release has none of them. A pump is
available as a device with its datasheet curve, and its duty point is the solve's answer. A pump on a
gas is refused, because a fixed curve does not follow a gas's density: a gas network is driven by a
compressor or by its boundary pressures.

**A glycol or brine with no concentration.** Refused, and rightly. A 30% ethylene glycol is about 6%
denser and roughly twice as viscous as water at 20 °C, so a defaulted concentration is a wrong
friction loss presented as a real one. Humid air without its humidity and natural gas without its
composition are refused for the same reason.

**"The network cannot carry the demanded flow."** A gas network refused before any numbers: to
deliver its demands the pressure would have to fall below what the gas can be evaluated at, which in a
real line means it chokes. Enlarge the runs carrying the most flow, shorten them, raise the supply
pressure or lower the demand.

**A gas volume "means nothing without the state it was measured at".** A plain `"10m3/min"` on a gas,
refused until you say what it is. Ask the user if you do not know: a compressor or tool rating is free
air delivery, a gas-meter or boiler figure is normally in normal or standard cubic metres, a
ventilation airflow is the volume at the duct.

**"This run was NOT started".** A transient predicted to take over a minute is refused, with the step
that would fit. Use it, or shorten the duration. For a pressure switch the step should stay at or below
a tenth of the shortest time the compressor spends loaded or unloaded, or the switching instants blur.

**"device ... has ports with no pipe".** Every port of a device needs a pipe, or the network has an
unknown with no equation. A compressor is the one exception: leave both of its water ports open and its
heat is rejected rather than recovered, and the solve says so.

**A compressor refused for missing settings.** Its free air delivery, discharge pressure, power (or
isentropic efficiency), recoverable heat and aftercooler outlet temperature are all on its datasheet,
and each changes the answer. Ask for them. Never fill them in from a typical value.

**"schedules and controllers were not applied".** A steady solve holds every machine at its stated
command. The run over time is `mode="transient"`.

**A `PHASE` warning.** The fluid left its phase somewhere: steam condensing, a liquid line flashing,
water boiling at a high point, humid air reaching its dew point. The warning names the nodes and the
saturation temperature there. Change the design, not the reading: raise the steam temperature or the
pressure, lower a high point, dry the air.

## Handing it over

When the work is for someone else (a client, a reviewer, a colleague who will act on it), produce an
**HTML study**, not a wall of numbers in chat. A network result is spatial: which way the flow goes,
where the pressure runs out, which branch is the problem. A table alone makes the reader rebuild the
picture in their head, and they will rebuild it wrong.

Use the bundled renderer rather than writing HTML by hand:

```bash
python3 scripts/render_study.py study.json -o study.html
```

It takes one plain JSON file and emits a single self-contained page: the verdict, the qualifications,
a riser diagram of the network (**every branch in a lane of its own, elevation in bands up the page,
distance from the supply across it**), what each device did, a run over time with its vessels, command changes and charts, and the node
and edge schedules. The `devices` rows and the transient blocks go in exactly as the solve returns them. `references/report.md` has the input schema and an example.

Three things about that page are not stylistic preferences:

- **The qualifications section is never dropped.** It is the one part a hand-written summary always
  loses, and losing it is how a bounded number gets handed over as a computed one. The renderer emits
  it whenever there is anything to say and the page states plainly when there is not.
- **The diagram is schematic and says so.** There are no coordinates in a solve result, so the layout
  is derived from the graph and from elevation rather than invented: a spanning tree grown by flow
  from the supply, one lane per branch, elevation bands, and a ring or grid opened where the flow
  divides. It is not a P&ID and it is not to scale. The renderer labels it accordingly, so leave that
  label alone. Only ids and pipe sizes are printed on it; the figures are on hover, in a few
  call-outs (supply, devices, the far end of the critical path, the lowest pressure) and in the
  schedules, which is what keeps it readable at any size.
- **Units are in the field names** (`pressure_kPa`, `flow_kg_s`). Getting a unit wrong is the easiest
  and most expensive mistake in this whole domain, so the schema makes it impossible to write a number
  without saying what it is.

If the user only wants a quick answer in chat, give them the answer and offer the study. If they are
going to send it to anyone, build the study.

## When the network is one pipe

Not every question needs a network. A single run with a known flow, "what size for 2 kg/s over 40 m",
is answered by `size_conduit` or `select_conduit_size` on the free `/mcp` endpoint, with no key and
no session.

The line between them is worth being precise about: **sizing one pipe assumes its flow is already
known.** The moment the flow through a pipe depends on the rest of the system (anything in a loop,
anything downstream of a branch, anything where two routes compete), that assumption fails and only a
network solve can answer it. If you catch yourself guessing how a flow splits, stop and build the
network.

## Files

- `references/gathering-inputs.md`: deciding what to solve, and getting the data to solve it.
- `references/workflow.md`: every call, its arguments, and the order to make them in.
- `references/reading-results.md`: how to interpret a solve, and the traps in detail.
- `references/report.md`: the study JSON schema, with a worked example.
- `scripts/render_study.py`: the HTML study renderer. No dependencies beyond Python 3.9.
- `scripts/study_layout.py`: the riser-diagram layout the renderer draws from, pure and tested on its own.
