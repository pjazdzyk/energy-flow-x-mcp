# The report

```
hydronic_report(handle, mode?, labels?, title?)
```

The server solves the design behind the handle, the same solve `hydronic_solve` runs, and builds a report from
the engine's own numbers: every node, every run, every device. It returns the verdict, an image of the network,
and links to a study page and a DXF. Nothing runs on the user's machine and nothing is copied by hand, so a
figure on the page is the figure the engine computed.

| Argument | Values |
| --- | --- |
| `handle` | the session to report |
| `mode` | `steady` (default) or `transient`, as `hydronic_solve` |
| `labels` | `data` (default): each run's size, velocity, flow and pressure drop, each node's pressure. `minimal`: ids and sizes |
| `title` | the page's title, the session's name when left out |

A design that fails validation is refused exactly as `hydronic_solve` refuses it, with every error listed, and no
report is made.

## What comes back

**First, the verdict, as JSON.** Read it before you show anything.

| Field | What it is |
| --- | --- |
| `data.verdict` | the page's headline: `Solved`, `Solved, and meets every stated criterion`, `Solved, with qualifications`, `The design fails its criteria`, `The run stopped early, before its end`, `The solve did not converge`, `The design point did not converge`, `The run over time did not converge at every instant` or `These results are withdrawn`, and may end with the iteration count |
| `data.verdictDetail` | the sentence under it, which also says whether anything was judged against criteria |
| `data.failedChecks` | when the design fails its criteria: each failed check in words, e.g. `branch_a: velocity 1.80 m/s is over its limit` (at most 20, then a count) |
| `data.criticalPath` | per figure: `from`, `to`, `lostInItsRuns_kPa` and the `runs` in flow order, at the design point |
| `data.parts` | with `mode="transient"`: the two parts the page has, the design point and the run over time |
| `data.runConverged` | with `mode="transient"`: whether every instant of the run converged |
| `data.qualifications` | each as `element: finding`. The engine's own sentences are in `warnings` |
| `data.files` | each file's `name`, what it is, its `url` (HTTPS), its `resource` (`hydronic://reports/...`) and size |
| `data.expiresAt` | when the links stop working |
| `warnings` | every sentence the solve said, verbatim: the qualifications first, then assumptions and validation warnings, then anything about the files |

**Then an image of each figure** (up to three), `image/png`, at most 1,600 px on its long side. Show it: it is
the network the user asked about, in the symbols the EnergyFlowX Hydronic builder draws. A large plant arrives
scaled down. The page and the DXF have every label at full size.

**Then a resource link per file**: `study.html`, `network.dxf` and `figure-N.png`. A client that reads MCP
resources opens them as `hydronic://reports/{token}/{file}`, and a browser opens the HTTPS `url`.

## Relaying the verdict

Two headlines change everything else and are said first, in words, before the picture:

- **These results are withdrawn.** A node solved at or below zero absolute pressure: the network cannot deliver
  what is asked of it. Nothing in the report should be quoted. Say which node and what to change.
- **The run stopped early, before its end.** A run over time met its compute limit. Every step shown is a real
  solve, but its last state is not the outcome, so do not quote it as the outcome. Say how far it got.

`The solve did not converge` means the numbers are a last iterate. `Solved, with qualifications` means a number was
produced by something other than ordinary evaluation of the design, and you say which.

**`The design fails its criteria`** is a converged, valid solve of a design that does not meet what `set_criteria`
stated for it: a run too fast or too steep, a draw point short of its least pressure, a peak over the rating, or,
for a run over time, a draw point that falls below its least pressure at some instant of the run (that check says
when). Never
call that design solved or fine. Say what fails, from `failedChecks`, and what would cure it. Plain `Solved` means
no criteria were stated, so nothing was judged a pass: say so rather than imply one.

## Qualifications

The engine's run notices, each with its code, the element it names, and its sentence, verbatim. The page shows
them in a section that is always there and says so when there are none.

| Code | Finding |
| --- | --- |
| `NON_PHYSICAL_PRESSURE` | Impossible pressure: withdraws the results |
| `RUN_LIMIT_REACHED` | Stopped at its compute limit: heads the run as unfinished |
| `PUMP_OUTSIDE_RATED_RANGE` | Pump outside rated range |
| `FLUID_PROPERTY_SUBSTITUTED` | Fluid property substituted |
| `VALUE_CLAMPED` | Value held at a limit |
| any other engine notice | Run notice |

Relay a qualification's sentence unchanged. It carries the numbers that let a reviewer decide whether it matters,
and "past the 3.50 kg/s runout" rewritten as "outside its range" loses the only figure on the line.

## The drawing

A riser diagram: the orthogonal schematic engineers sketch by hand, laid out from the network rather than from
coordinates.

- **A spanning tree grown by flow** from the supply. On a ring or a grid the runs left out are the ones carrying
  the least, which is where the flow divides, so each loop is opened at the one place a ring is meant to be read
  open. Those runs are drawn dashed, routed around the tree.
- **One lane per branch**, one step across per node, so a run reads left to right and the far end of the network
  lands at the far end of the page.
- **Elevation in bands**, each above the levels below it, each level a thin solid grey line with its height at the
  left. The 0.0 m datum is the only dotted line on the drawing, and a dashed line is only ever a run closing a ring.
  With no elevations it is a topology sketch and the page says so.
- **P&ID symbols** for pressure boundaries, demands, outlets, receivers and every device, each on a plate.
  Equipment has an orange frame and turns to face the way its fluid runs. A junction is a dot. A device is drawn
  once, with every run to any of its ports ending on it. **A dot on a line is a tee**: where a branch leaves a line
  it was drawn along, away from any node, so the reader sees where the flow splits.
- **Valves, strainers and Kv elements** in their runs: a `VALVE` or `STRAINER` fitting on a pipe, and a lumped
  resistance given by its Kv, which is drawn as a balancing valve. The run's label sits at the valve.
- **Line weight is mass flow**, relative to the largest. **The arrow is the way the fluid runs**, from the sign of
  the solved flow. **A faint tint is pressure**, strongest where it is plentiful.
- **What flows where**: a demand "draws", a boundary "feeds" or "takes", a receiver is "charging" or
  "discharging", from the exact balance of the solved runs.
- **The critical path**, highlighted, ends at the most disadvantaged draw point. With a `minPressure` stated it is
  the one with the least to spare above it, static head and all, as a water supply's top tap is. With none it is
  the index circuit: the draw point that has lost the most head reaching it, its height set aside, so a high floor
  is not chosen merely for being high. From there it runs upstream along the run bringing the most flow, through
  any pump or compressor, to a pressure boundary or a receiver. Its total is what its runs lose to friction and
  fittings, never start pressure minus end pressure, which across a pump is a gain.
- **A plant of separate systems** is one figure per connected group, each system in one colour throughout.
- **A legend in every figure**, naming every symbol, colour and line style that figure uses, so a saved image
  explains itself.
- **Labels never touch.** A label with no clear spot is left off: every figure is on hover on the page and in its
  schedules.

It is a schematic, not a P&ID, and not to scale. A report of a run over time draws the design point, the steady
state, never an instant of the run.

## The study page

One self-contained HTML file that works offline, in light and dark, and prints: the verdict, the qualifications,
the drawing, the critical path, the equipment and what each device did, a bill of materials, every run and every
node, and the assumptions and warnings.

A report with `mode="transient"` comes in two parts, so no table mixes two states of the plant. Part 1 is the
design point: the plant solved steady, every machine at its stated command and every vessel at its stated pressure,
and the drawing, the design checks, the critical path, the equipment and the schedules are all this state. Part 2 is
the run over time: whether it completed and every instant converged, each vessel's swing, each machine over the run
(a compressor's averages, energy and starts), the lowest pressure each point reached and when, judged at a draw
point against the least its system must keep, a mass and energy balance per fluid circuit, charts with their ticks
(one per range, a command drawn as the step it is) and every command change. The balance counts what a gas
receiver kept twice, from its flows and from its own state, and the two agree when the run conserved mass; an energy
residual near zero says the same of energy. Quote both before trusting a run's energy figures. A draw point that keeps
its pressure at the design point but falls below it at the bottom of a receiver's swing fails the verdict. The bill of materials aggregates like items: pipe and duct by material, size and system
with their total length, fittings by type and the size of the run carrying them, valves, equipment and vessels by
type, each line naming its members. Tees and crosses are counted from the network, one wherever three or four
connections meet, because a tee's loss is entered once for each path through it; an entry or exit loss at a vessel
is not a part, and an enlargement is billed as a reducer. It lists only what the design states: a run with no
length is counted as unstated, never given one, and allowances (waste, supports, insulation) are left to whoever
orders from it. A small plant's page carries its DXF inside it as a download, so the page alone can be sent on.

Each pump is drawn on the curve the engine solved on, at the speed it actually ran (a controller or schedule may
have changed it): capped at its shut-off rise, and past the datasheet's last flow the engine's steep runout, drawn
thin, which is not the pump's curve. The system curve through the duty counts the drop across any equipment on the
route as flow loss, and is left out, with the reason, when a second pump drives the same route. NPSH available is
judged at the temperature the liquid reaches the pump at. An expansion vessel given a `precharge` shows the water it
holds; without one it shows none, because the volume is then only its gas cushion.

## The DXF

The page's drawing as R12 (AC1009), the version every CAD opens, in millimetres at one per page pixel. Each symbol is
a block, inserted wherever it appears and mirrored by its insert, so a CAD user can select every pump at once or
swap a symbol for their house standard. Layers: `PIPE-<SYSTEM>` per fluid system (a run closing a ring dashed on
its own system's layer), `FLOW-ARROW`, `VALVE`, `CRITICAL-PATH`, `SYMBOL`, `EQUIPMENT-FRAME`, `NODE`, `TEXT-ID`,
`TEXT-DATA`, `CALLOUT`, `DATUM`, `TITLE` and `LEGEND`.

## Links, and how long they last

A report is kept at most 24 hours, then deleted. Its links are capabilities: anyone holding one can open the
report until then, with no sign-in, so a link goes only to whoever should see the design. A report holds the
design's figures and the names its author gave it, and nothing from the account.

An account keeps at most 10 reports at once, each at most 4 MB. At that limit a new report still returns its verdict and its images,
says so, and has no links. Nothing already kept is removed for it. A report is a copy of a solve: after the design
changes, report again.

## Sign conventions

A run's flow is signed against its declared `from` to `to`, and the arrow follows the sign. Around a ring the
place the sign changes is the flow divide. A node's net flow is what leaves the network there, negative where fluid
enters. Pressures are absolute.
