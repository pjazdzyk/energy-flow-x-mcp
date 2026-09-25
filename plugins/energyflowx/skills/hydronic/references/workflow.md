# The workflow, call by call

This file is the mechanics. The vocabulary (which node kinds, which fittings, which materials, which
fluids, which edit ops and their fields) is **not** repeated here on purpose. It lives on the server
as MCP resources, it is the version that matches the server you are actually talking to, and a copy in
this file would drift the first time the server gained an op.

## Contents

- [Step 0: read the vocabulary](#step-0-read-the-vocabulary)
- [Step 1: open a session](#step-1-open-a-session)
- [Step 2: build the network](#step-2-build-the-network)
- [Step 3: solve](#step-3-solve)
- [Step 4: inspect](#step-4-inspect)
- [Step 5: keep or discard the session](#step-5-keep-or-discard-the-session)
- [The free endpoint](#the-free-endpoint)
- [Errors you will actually meet](#errors-you-will-actually-meet)

---

## Step 0: read the vocabulary

Nine resources, read once per session, then never again:

| uri | what it holds |
| --- | --- |
| `hydronic://vocabulary/ops` | every edit op, its required and optional fields |
| `hydronic://vocabulary/fittings` | fitting types and their loss coefficients |
| `hydronic://vocabulary/materials` | wall materials and their roughness |
| `hydronic://vocabulary/fluids` | fluid codes, what each needs, how a gas is solved, the phase checks |
| `hydronic://recipes/riser` | a complete, solvable plant riser |
| `hydronic://recipes/ring-main` | a campus ring main, and what a ring teaches you |
| `hydronic://recipes/compressed-air-ring` | a compressed-air ring in free air delivery, with a filter as a Kv |
| `hydronic://vocabulary/devices` | each device's ports and settings, schedules, controllers, and what a run returns |
| `hydronic://recipes/compressor-heat-recovery` | a compressor on a pressure switch charging a receiver, its heat into a store, run for twenty minutes |

They are **resources, not tools**, which is why they cost nothing on a turn where you do not need them.
Most MCP clients do not fetch resources unless asked, so ask.

**Pace them.** About a second between reads. The endpoint is rate limited, and reading six resources
back to back is enough to trip it. A throttled call comes back as a JSON-RPC error carrying a
`Retry-After` and the code `-32000`, so you will know what happened, but a second of patience beats a
round of retries.

Start with the recipe that matches the shape of the problem. A riser and a ring are the two topologies
almost everything else is a variation on, and reading one complete worked design teaches the op
vocabulary faster than reading the op list.

## Step 1: open a session

```
hydronic_session(action="create", name="Block C heating")
```

Returns a **handle**. Everything else takes it.

Why a session rather than passing the network: a real network is thousands of tokens of JSON, and
passing it on every call would mean re-sending the whole design to change one diameter. Worse, it would
mean the model holding the authoritative copy, so any transcription slip becomes the design. The server
holds it and you hold a handle.

Other actions:

| action | use |
| --- | --- |
| `create` | a new empty design |
| `open` | seed from a previously exported `document` |
| `export` | get the design back as JSON, `format` = `session` or `request` |
| `list` | the sessions you own |
| `close` | let it go |

`export(format="request")` gives the assembled `HydraulicDesignRequest`, which is what the REST API
takes. That is the bridge if someone wants to keep working outside MCP.

## Step 2: build the network

```
hydronic_edit(handle="...", ops=[ ... ])
```

**One call, many ops, all or nothing.** A batch that fails anywhere applies nothing, so you never end up
with half a network and no record of which half. Build the whole topology in one or two calls.

`dryRun=true` validates the batch and reports what it would do without changing anything. Worth using
when you have assembled a large batch programmatically and want the field names checked before you
commit.

A sensible order inside the batch, which is also the order the recipes use:

1. `set_fluid` for every system (with `system` for each one after the main), and `set_conditions` if a
   loop is sealed
2. `add_node` for every node, boundaries first
3. `add_pipe` for every run
4. `add_fitting` / `add_resistance` for the local losses
5. `set` / `remove` for later corrections

**Quantities are strings with units**: `"150mm"`, `"2.5bar"`, `"70oC"`, `"1.2kg/s"`, `"12m3/h"`,
`"450Nm3/h"`. A field
that does not belong to its op is refused **by name**, in both directions: an op that is missing a
field it needs and an op given a field it does not take both fail loudly. That is deliberate: a silently
ignored field is a design that is not what anyone thinks it is.

Two things that are easy to get wrong and expensive to miss:

- **`elevation` omitted means the datum, not "no elevation".** In a building that is the difference
  between a static head and none. 11 m of water is about 108 kPa, and on a 5 bar system that is a fifth of
  everything you have.
- **A volume-flow demand is converted using the fluid's density.** A liquid at the design temperature;
  a gas at the state its basis names (the unit for a normal or standard volume, `flowBasis` for free air
  or the line pressure). The conversion is stated in the solve response. Read it once to confirm it used
  the density you expected.
- **An edge in another system says so.** `add_pipe` and `add_resistance` take `system`, and a system
  must exist before an edge names it, so put the `set_fluid` ops first.
- **Devices first, then their pipes.** `add_device` before any pipe that names `"device.port"`, and every
  port piped. A compressor's air side and water side are two systems, so its water pipes carry the water
  system's name.
- **Schedules and controllers last.** Each names a device or node that must already exist, and a device
  takes its command from one source, a schedule or a controller. `set_transient` can go anywhere.

## Step 3: solve

```
hydronic_solve(handle="...", detail=<n>)
```

`mode` is `steady` (the default) or `transient`, which runs the duration `set_transient` states and
applies the design's schedules and controllers. A transient returns each receiver's swing with when, the
lowest pressures and when, each machine's starts, power, energy and recovered heat, how far each store
charged, every command change, and a sampled table. A run predicted to take longer than a minute is
refused with the step that would fit.
`detail` is the number of rows in each ranking: the worst edges by the head they consume, the fastest
pipes, and the lowest and highest pressure nodes. The default is 5 and the maximum is 50, so a network
of up to 50 elements can be read in full. The solve returns no critical path. A design with several
systems returns one entry per system under `systems`, and each warning starts with its system's name.

Everything else the solve has to say is in `warnings`: the run notices, the validation warnings and
the assumptions it made, each a complete sentence.

The solve **refuses to report numbers for a design that failed validation**. That is not an obstacle to
route around: a design that cannot be validated cannot be solved meaningfully, and a plausible answer
would be worse than no answer.

## Step 4: inspect

```
hydronic_inspect(handle="...", what="...", id="...", limit=<n>)
```

| what | returns |
| --- | --- |
| `readiness` | what is still missing, split into blocking and advisory, and the validator's verdict |
| `design` | the whole document as currently authored |
| `nodes` / `edges` | the authored tables, up to `limit` rows (default 50) |
| `node` / `edge` | one authored element, with `id` |
| `fluids` | the fluids this server carries |

Inspect reads the design, never the solution. Computed flows and pressures come from the solve.

`readiness` is the one to reach for while building. It answers "what do I still need" in the vocabulary
you are editing in, and it distinguishes what would make the answer meaningless from what merely gets
assumed.

## Step 5: keep or discard the session

Sessions belong to the API key that made them. `export` before `close` if the design is worth keeping;
hand the exported document back to the user, because it is the only copy they control.

## The free endpoint

`/mcp` is a separate server, no key, eleven tools. Relevant here:

- `get_fluid_properties`, `get_saturation_properties`, `list_fluids`: density, viscosity, saturation
  state for 29 fluids and solids.
- `size_conduit`, `select_conduit_size`, `search_conduit_catalog`, `get_conduit_dimensions`: single
  pipe or duct, known flow.
- `convert_units`: when a user gives you something in units the network tools will not take.

A client that needs both connects to both.

## Errors you will actually meet

**`-32000` with `retryAfterSeconds`**: rate limited. Wait the stated seconds. An API key raises the
budget. Batching edits and reading each vocabulary resource once are the two things that keep you
under it.

**"needs an API key"**: the hydronic tools are key-only. The message says where to get one. Relay the
access terms with it.

**"nothing drives flow"** or **"nothing anchors the pressure"**: see SKILL.md. Add a demand or a
second boundary at a different pressure for the first, and a boundary or a `fillPressure` for the
second.

**A fluid-property complaint mentioning saturation or steam**: this is almost never about steam. It
means the pressure was driven to or below zero somewhere, which means the network cannot deliver the
demand being asked of it. The server now explains this and keeps the original message underneath.

**"This run was NOT started"**: the transient was predicted to take over a minute. The message gives
the step that fits.

**"has ports with no pipe"**: pipe every port of the device named, or for a compressor leave both water
ports open.

**A batch rejected by field name**: read the name. The op vocabulary is the authority and it is one
resource read away.
