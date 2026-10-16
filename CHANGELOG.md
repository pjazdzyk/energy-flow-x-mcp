# Changelog

Notable changes, newest first. Breaking changes are marked as such.

## Unreleased

Nothing here is released. No version number was changed, and the items marked breaking are recorded for the later major version.

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
