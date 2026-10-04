# Changelog

Notable changes, newest first. Breaking changes are marked as such.

## 2.0.0 (2026-10-04)

### What a report looks like

- The README shows a report: the worked compressed-air plant from energyflowx.com/hydronic, its drawing
  (`assets/example-plant.png`), the question it answers, what came back, and that it is illustrative only, not a
  real design or a complete P&ID.

### Access terms with a year, and no "Hydronic MCP"

- The Hydronic network tools are free for testing and move to a paid plan in **2027**, in the README, CAPABILITIES
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
