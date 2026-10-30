# Changelog

Notable changes, newest first. Breaking changes are marked as such.

## Unreleased

Nothing here is released. No version number was changed, and the items marked breaking are recorded for the later major version.

### Humid air, R-32 and R-454B, helium and steam (2026-10-30)

- **Result-affecting: humid air.** Its properties now come from one description of the mixture. At 1 atm the heat capacity at constant volume moves by 0.3 to 1 %, the heat capacity ratio and the speed of sound by 0.1 to 1 % (25 °C at 55 % RH: speed of sound up 0.30 %), the density by a few parts per million. Enthalpy, heat capacity at constant pressure, wet bulb and dew point did not change. In fog the heat capacity at constant pressure includes the evaporation of the suspended water (20 °C, 20 g/kg: 3.35 kJ/(kg·K), was 1.06).
- **Breaking: values left out with a reason.** `get_fluid_properties`, `get_property_table` and `calculate_air_process` list under `unavailable`, with "not defined for <fluid> at this state: <reason>", the properties of fog that a single gas phase defines only (heat capacity at constant volume and its ratio, speed of sound, compressibility factor, compressibilities, expansion coefficient), the dew point of dry air, a dew point or wet bulb below -80 °C, and helium's thermal conductivity, thermal diffusivity and Prandtl number above 100 MPa. A table leaves the value out of that row and says why in `warnings`. Dry air now has a wet bulb (5.81 °C at 1 atm and 20 °C).
- **Changed: R-32 and the blends.** R-32 answers from its triple point (-136.8 °C), where it was refused below -23.15 °C. R-454B vapour conductivity is up to 5.6 % lower at 200 K. R-454B below 220 K and R-410A and R-407C below 250 K carry a warning that their viscosity and conductivity are less certain.
- **Changed: steam** below the triple-point pressure (611.2 Pa), and given by enthalpy and entropy near freezing, now answers.

### Pure-fluid density near saturation (2026-10-30)

- **Result-affecting: a pure fluid just above its saturation pressure, or within about 2 % of it.** `get_fluid_properties`, `get_property_table` and Hydronic networks carrying a pure fluid could return the vapour density for a compressed liquid, or a density inside the two-phase region, with no warning. Nitrogen at 89.99 K and 3.96 bar read 16.8 kg/m³ (liquid 745.2), hydrogen at 15 K and 0.3 bar 0.514 kg/m³ (liquid 76.15), argon at 138.251 K and 29.38 bar 514.5 kg/m³ (vapour 161.6). Propane, methane and R-1234ze(E) showed the same at a few states. The stable phase is now returned at every state. Every other state is unchanged to the last digit, and refrigerant blends and natural gas did not change.

### Hydronic: regulators held in a run over time (2026-10-30)

- **New: a run over time holds the design's regulators** (PICV, DPCV, CAV, pressure regulators) at every step, where `hydronic_solve(mode="transient")` refused them by name. `set_transient` takes `regulationBand` (default 0.05, 0 regulates every step), stated in the reply: at 0.05 a held flow may lie up to 5 % off its setpoint and a starve is seen a few steps late. `data.regulators` gives each regulator's regimes over time, its held quantity against the setpoint, the instants not held and its first starve. The report's run part draws them as a table and a chart, with `run-regulators.csv`.
- **Refused:** a pump that states a speed control, in a run over time.

### Hydronic: pump speed control, system curve and surge over MCP (2026-10-30)

- **New: pump speed control.** A PUMP takes `control` (`CONSTANT_DP`, `PROPORTIONAL_DP`, `REMOTE_DP`, `DUCT_STATIC`) with its setpoint, a speed range at most rated speed, a design flow and `zeroFlowFraction` for the proportional mode, and the sensed nodes for the remote mode. A steady solve, every envelope case and every scenario report the held speed and regime. A scenario's `control.<pump>` replaces the pump's whole control. A control that did not settle says so (`PUMP_CONTROL_NOT_HELD`, `PUMP_CONTROL_NOT_SOLVED`).
- **Breaking (value): `CONTROL_MODE` recommends `PROPORTIONAL_DP` or `CONSTANT_DP`** in place of `PROPORTIONAL_PRESSURE` and `CONSTANT_PRESSURE`, and its warning offers the recommended mode as fix ops only when the swept cases show it clears the warning.
- **New: speed trim.** A balance with a pump surplus reports the speed that puts the index element at its minimum drop, verified by a solve, as a recommendation never written into the design.
- **New: `hydronic_solve` modes `system_curve` and `surge`.** The same points and the same screen as the REST endpoints, through the same code. Surge screens a pump trip. A valve closure is refused until a valve device exists. Its events are in `hydronic://vocabulary/surge`.

### Steam from enthalpy and entropy (2026-10-30)

- **`get_fluid_properties` for `STEAM` with `specificEnthalpy` and `specificEntropy`**, and `get_property_table` mode `STEAM_H_S`, always answer or refuse within a second. A pair outside the region the steam formulation covers could keep the call busy for minutes. It is now refused with the highest (or lowest) enthalpy the isentrope reaches. A cold liquid pair whose isentrope dips below 0 °C at some pressures, such as 49.18 kJ/kg and 0 kJ/(kg·K), now answers where it raised an error. Every state that answered before gives the same values.
- **`get_property_table` keeps only the `outputs` asked for.** The parameter was accepted but every column came back. An unknown output name is refused with the names that mode produces.

### Transport properties corrected (2026-10-30)

- **Result-affecting: nitrous oxide gas below about -55 °C.** `get_fluid_properties`, `get_saturation_properties` and `get_property_table` gave a viscosity two to four times too high, and at some states far more (0.173 Pa·s at -59 °C and 4 bar, where the gas has about 1.1e-5). Now about 1e-5 Pa·s and smooth. Liquid and supercritical nitrous oxide unchanged.
- **Result-affecting: R-1234yf and R-32 at their coldest states.** A saturation table gave R-1234yf vapour a negative viscosity and conductivity near its triple point, and R-32 a liquid conductivity that fell as the liquid cooled. Below the correlations' limits (R-1234yf 220 K, R-32 conductivity 250 K) a saturation row now leaves out those values and keeps the rest.

### Property tables over MCP (2026-10-30)

- **New members tool `get_property_table`.** The web calculators' property tables in one call: a fluid over a range of one input, a grid over two inputs (at most 10 values and 500 states), up to 1000 states in one call. Small tables answer inline (60 rows), larger ones with their shape and a CSV link kept for 24 hours.
- **Saturation-line tables.** For the 14 fluids with a vapour-liquid dome, by temperature or by pressure, with both phases' properties and the latent heat on every row.
- **`get_saturation_properties` with a pressure** now finds the saturation temperature by the same search the tables use. Answers move by about a millionth of a kelvin, below the printed precision.

### Hydronic: one status, longer runs (2026-10-27)

- **Result-affecting: `status` says whether the answer can be used.** A Hydronic solve, balance, design or run over time reads `CONVERGED` only when the solve converged, every target was met and the state is physical. Otherwise it reads `NOT_CONVERGED`, `TARGETS_MISSED` or `NOT_PHYSICAL`, and `converged` is true exactly when `status` is `CONVERGED`. The solver's own result moved to `solverStatus`. Before, a node at -831 kPa absolute, or a balance that missed its targets, could read `CONVERGED`. A run over time reads its final instant, and `everyInstantConverged` says whether every instant converged. The skill reads `status` first.
- **Riser valves and closed loops.** A balancing valve in series with the radiators takes its design flow from them, and a flow stated on it is checked against them. An ordinary two-pipe circuit sizes, balances and reports in one `mode="design"` call with every run on `auto`. The inventory calls a system by the design's own name, a run that misses only a velocity floor is not reported infeasible, and a valve at a pump or boiler port solves.
- **Longer computing time.** A run over time may compute for 75 s (was 30 s), a balance and a design run's sizing passes for 40 s, a size run and a forward solve for 45 s.

### Heat recovery frost protection

- **Result-affecting (2026-10-25, `calculate_air_process` with `HEAT_RECOVERY`): frost risk follows the physics.** Frost risk is reported when the coldest exchanger wall is at or below 0 °C and the exhaust can deposit vapour on it, whatever trigger is set. Before, the verdict followed the trigger, so a wall between the trigger and 0 °C was reported free of frost. A wall held at 0 °C by freezing condensate now counts as frost. The trigger only sets where a protection strategy engages.
- **Result-affecting (2026-10-25): the wall near 0 °C and in reversed flow.** The cold-corner wall no longer jumps across 0 °C. It holds at 0 °C while condensate freezes. With one air stream reversed, the wall is the colder end of the core and the bypass follows the parallel-flow relation. Before, the reversed-flow wall read several kelvin too cold.
- **New field `frost.frostProtectionOutcome`.** Each heat recovery result states the outcome of frost protection as one value: `NO_FROST`, `NOT_PROTECTED`, `NOT_ENGAGED`, `PROTECTED`, `HELD_BELOW_FREEZING`, `FROST_FREE_AT_LIMIT`, `OUT_OF_RANGE`, `NOT_CONVERGED` or `FROST_BETWEEN_STOPS`, with one warning for each value that needs one. The `frostRisk` and `residualFrostRisk` flags stay.
- **Faster Preheater solves.** A Preheater strategy that ran out of the 30 s limit now answers in a few seconds.
- **A target out of reach beside a preheater answers (2026-10-26).** A heat recovery target mode with a Preheater, whose target lies out of reach just past the point where the preheater engages, now answers infeasible at the closest value it can reach, where it ran out of the 30 s limit. On the calculator's default network at -15 °C, a target of 12 °C answers in about 24 s. The answers of other questions stay the same. A target inside the jump where the preheater engages can still run out of the limit.
- **Faster target modes with frost protection (2026-10-26).** A heat recovery target mode with a Preheater or a Bypass does about 60 % less work, with the same answers. On the calculator's default network at -15 °C, Preheater targets of 14 to 20 °C answer in 10 to 15 s, where they took 23 to 30 s or ran out of the 30 s limit. A target that lies inside the jump where a preheater engages can still run out of the limit.
- **Result-affecting (2026-10-25): frost protection stops where frost can no longer form.** A bypass or preheater lifts the coldest wall to its trigger or target, or only as far as the wall at which the exhaust vapour stops reaching it, when that is lower. With dry exhaust air it opens less, or preheats less, than before, and `frost.frostProtectionOutcome` reads `PROTECTED` with the wall it reached, which can lie below the trigger.
- **Result-affecting (2026-10-25): heat recovery target modes.** A target the exchanger cannot reach is `feasible: false`, answered at the closest value the exchanger delivers and at the lowest rating that delivers it. Before, a target mode with frost protection could report a missed target as met, or miss a reachable one.
- **Result-affecting (2026-10-25): energy books near a 0 °C exhaust.** Where the exhaust leaves at 0 °C with its condensate freezing only in part, the energy balance now closes. Before, it could be open by up to 1.3 kW.
- The reported wall is a mean estimate that runs warm, so a trigger above 0 °C adds margin. The tool description says so.

### Result evidence

- **`meta.stamp` on every tool response.** Every reply of every tool, free and members, carries `meta.stamp` last in `meta`, with `software` (the service name and version), `engines` (the version of eos-engine, hvac-engine-pro, flow-symphony, solar-engine, numenor-math and unitility), `computedAt` (UTC), `notice` (the review sentence) and `terms` (the Terms of Use address). Nothing under `data` changed. An assistant should relay the version and any warnings when it reports a number a user may rely on. The four skills now say so.
- **A tool can be switched off with a message.** The service can take one tool out of service without a deploy. The tool then computes nothing and answers with a tool error of the form `<tool> is out of service: <message> (switched off since <date>, ask again in <n> s)`. An assistant relays that message and does not invent a result.
- **Result-affecting defects are tagged from now on.** A defect that changes a number a user may have relied on is listed in this changelog with the prefix `Result-affecting:`, the date and the tools affected. The current list of known issues is on https://energyflowx.com/known-issues.
- **Report files carry a result record.** Files of a Hydronic report state the software version, the engine versions, the UTC time and the digests of the inputs and of the outputs, with the review sentence.

### Wording and legal corrections

- **Paid plans.** The text "free for testing and move to a paid plan in 2027" is replaced everywhere (README, CAPABILITIES, the hydronic skill, the access-terms check) by "free during testing. Paid plans are planned, and no date or price is set." The 2.0.0 entry below keeps its original wording as history.
- **Claim words removed.** "Same answer every time", "same figures as the largest model", "real product catalogues" and the "validation evidence" link text are gone. The README states plainly that results produced through an AI assistant are for the user to verify, that the service does not guarantee what an assistant says, and that results are for review by a professional engineer who remains responsible and are not a design certification. Each skill tells the assistant to say so when it presents numbers.
- **Standards by number only.** Heat recovery is no longer described "to EN 16798-3 and EN 308" (ports are named in plain words, effectiveness "as EN 308 defines it"), calorific values "follow the method of ISO 6976", and free air delivery refers to the conditions of ISO 1217.
- **Trademark and non-affiliation line** now covers every product, vendor and maker name the README and skills mention, and the standards bodies.
- The Codex review example uses "two heat demands of 3 kW each" instead of radiators.

### Accuracy against the service documentation

- Seventeen tools (eleven free and six Hydronic), eleven resources and two resource templates: `hydronic://vocabulary/components` is listed.
- Valves, dampers, regulators and emitters are placed as elements (`define_component`, `add_valve`, `add_damper`, `add_emitter`). `hydronic_solve` and `hydronic_report` take `mode="balance"` and `mode="design"`, and `hydronic_inspect` reads `results`, `components` and `elements`. The skill no longer says balancing and regulation are not available. Fans and fire-protection (sprinkler) hydraulics are listed as not available.
- Pipe catalogue after the evidence rule: 11 generic pipe products (a size needs two independent makers), PE-X, PVC-U and CPVC are manufacturer series only, 46 manufacturer series from 29 makers.
- Duct series name their makers' documents (Promat, A-WENT circular, Chemowent).

### Breaking or notable on the service side, for the later major version

- **BREAKING: two duct series are withdrawn with no alias.** The Chemowent PVC thick-wall circular series and the A-WENT rectangular series answer as not found.
- **BREAKING: the compressed-air water ranks are our own grades.** They are no longer the classes of a standard, and the integers changed.
- The surge result carries a new optional list of assumptions.
- The Hydronic MCP greeting and the tool texts changed (wording and the access terms).

## 2.2.0 (2026-10-06)

### For OpenAI too: ChatGPT and Codex

- `.codex-plugin/plugin.json` makes this repository an OpenAI plugin as well, for ChatGPT and Codex: the same
  four skills from `skills/`, and the members server from its own `.codex-mcp.json` (Codex names a remote
  server by `url` alone, where Claude's `.mcp.json` needs `type: http`). Its listing (`interface`) links the
  same pages as the Claude one. Each release carries `energyflowx-openai-<version>.zip`, the archive ChatGPT's
  "Upload plugin" takes. Claude reads only `.claude-plugin/`, so nothing changes for Claude.
- `tests/check_skills.py` holds the OpenAI manifest to the plugin's name, version, description, keywords,
  links and server.

### The access terms link the page instead of quoting the year

- The hydronic skill relays the access terms as the server now states them in the chat: the network tools are
  free while in testing, that can change, they will become part of a paid EnergyFlowX plan, and the plans and
  terms are at energyflowx.com/mcp-server. App directories keep selling out of the conversation, so the year
  stays in the README and on the page, for people, and the skill names no price or plan of its own.

## 2.1.0 (2026-10-06)

### A Gemini CLI extension

- `gemini-extension.json` at the root makes this repository a Gemini CLI extension as well: the members server
  over Streamable HTTP, signed in with OAuth, and the same four skills from `skills/`. Install it with
  `gemini extensions install https://github.com/pjazdzyk/energy-flow-x-mcp`. Claude reads only `.claude-plugin/`,
  so nothing changes for Claude.
- The marketplace entry carries the plugin's author, homepage, repository, licence and keywords, and the keywords
  add `hydronic`, `pipe-network`, `dxf` and `mcp`.
- `tests/check_skills.py` holds every client manifest to the same name, version, description and server.

## 2.0.0 (2026-10-04)

### The design is checked against the user's sketch before it is solved

- A new members tool, `hydronic_preview`, draws the design the way the engine reads it, without solving it. It
  uses the report's own drawing and symbols, and also describes the network in words: the separate groups, the
  closed loops, the branches that end nowhere, the nodes drawn at 0 m for want of an elevation, and which
  systems each device joins.
- The hydronic skill's loop gains the step "Check the drawing before you solve", and when the user gave a
  picture it asks them whether the preview is their network. `references/workflow.md` has the call and every
  field. The README and the capabilities page list the tool.

### A run over time reports its mass and energy balance

- The hydronic skill and `references/report.md` describe the balance a run now reports (`data.balance`, and a
  section of the report): per fluid circuit the mass in, out and kept, a gas receiver's counted from its flows and
  from its own state, and the energy per device and circuit with what is left over. The README example quotes it.

### A run over time is reported with its design point, apart

- The hydronic skill and `references/report.md` describe the two-part report `hydronic_report(mode="transient")`
  now gives: the design point, solved steady, which the drawing and schedules show, and the run over time apart from
  it, with each machine over the run and the lowest pressure each point saw. New verdicts and reply fields
  (`parts`, `runConverged`) are listed. The README example quotes both parts and says all five systems are solved
  together in one design.

### What a report looks like

- The README shows a report: the worked compressed-air plant from energyflowx.com/hydronic, its drawing
  (`assets/example-plant.png`), the question it answers, what came back, and that it is illustrative only, not a
  real design or a complete P&ID.

### Access terms with a year, and no "Hydronic MCP"

- Superseded by the Unreleased wording (no date, no price). At the time the Hydronic network tools were free for testing with a stated paid-plan year, in the README, CAPABILITIES
  and the hydronic skill alike. `check_skills.py` fails when any of them names another year, or drops the year.
- "Hydronic MCP" is gone as a name: since 2.0.0 the Hydronic tools are on the members server, not a server of their
  own. `check_skills.py` refuses the phrase in a skill.

### BREAKING: one server, one sign-in, no API key

The plugin now connects **one** server, `energy-flow-x`, at `https://energyflowx.com/energy-flow-x/mcp/members`. It
carries every EnergyFlowX tool: the fluid, sizing and air tools with nothing held back (refrigerants, brines and the
steam humidifier included) and the five Hydronic network tools. You sign in once from `/mcp` with your free account,
and the plugin never asks for an API key.

- **Before:** two servers, `energy-flow-x` (`/energy-flow-x/mcp`, anonymous) and `energy-flow-x-hydronic`
  (`/energy-flow-x/mcp/hydronic`, sign-in). Refrigerants, brines and the steam humidifier needed an API key on a
  third, keyed connection even after signing in.
- **The old addresses are gone** on the server side, so 1.x stops working when the server changes. Update to 2.0.0.
  A connection named `energy-flow-x-hydronic` or `energy-flow-x-keyed` from 1.x can be removed.
- **What it costs:** the plugin now asks for the sign-in even for a free lookup such as the density of water. The
  account is free. Without one, connect the free server, `https://energyflowx.com/energy-flow-x/mcp/free`, yourself
  ([Other clients](README.md#other-clients)).
- **Skills are client-neutral.** They name tools and the two servers by role and address, never by a plugin
  connection name, so a skill downloaded on its own reads correctly in any assistant. `tests/check_skills.py` fails
  on wording that only makes sense with the plugin installed.
- **Skills download on their own.** Every release carries `fluid-properties.zip`, `conduit-sizing.zip`,
  `hvac-processes.zip`, `hydronic.zip` and `energyflowx-skills.zip`, built by
  `energy-flow-x-iac/scripts/package-plugin-skills.py`. The plugin itself still ships no code.
- Folds in 1.5.0, which was never published: `hydronic_report` makes the study on the server.
