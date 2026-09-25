---
name: fluid-properties
description: >-
  Look up validated thermophysical properties for 29 fluids and solids from reference equations of
  state, using the free EnergyFlowX MCP tools. Use this whenever a calculation needs a real property
  rather than a remembered one: density, viscosity, specific heat, conductivity, enthalpy or entropy
  at a state, saturation and boiling points, humid air from six input pairs, steam from any two of p,
  T, h, s, x, natural gas by composition with its calorific value and Wobbe index, refrigerant,
  glycol and brine properties, and unit conversion between them. Reach for it whenever a number like "water is about 1000 kg/m3" or "cp is
  roughly 4.2" is about to be used in real work, because a remembered property is the most common
  quiet error in an engineering calculation.
---

# Fluid properties

These tools answer "what is this fluid actually like at this state" from reference equations of
state, not from a table someone typed in. They are free, need no API key, and live on the `/mcp`
endpoint, which the plugin connects as the `energy-flow-x` server. The network tools are a separate
server, `energy-flow-x-hydronic`, and nothing here needs it.

## Why not just recall the number

Because the recalled number is right to two figures and wrong in the way that matters. Water's
viscosity at 70 °C is about a third of its value at 20 °C, so a heating circuit costed from the
room-temperature figure reports friction losses that are too high. A 35% ethylene glycol is denser
than water *and* has a lower specific heat, so the same duty needs more mass flow and more pumping
head, twice over. Those are not rounding differences, and neither of them is visible in the answer.

Use the tools whenever the property feeds something a person will act on.

## The tools

| Tool | For |
| --- | --- |
| `list_fluids` | the catalogue: every fluid, the state inputs it takes, its validity range, method and access tier |
| `get_fluid_properties` | properties at a state, for 28 of the 29 |
| `get_saturation_properties` | saturation of the pure fluids with a dome, not water: boiling point at a pressure or the reverse, phase densities, latent heat, critical and triple points |
| `get_natural_gas_properties` | GERG-2008 plus ISO 6976 calorific value and Wobbe index, from a preset or an explicit composition |
| `get_solid_properties` | ice |
| `convert_units` | conversion, and `listUnitsFor` to discover which symbols a quantity accepts |

**Call `list_fluids` first when you are unsure** which code a fluid has or which state inputs it
accepts. It is one call and it saves a round of guessing at enum values.

## Reading an answer properly

Every property result states **the method used and its validity range**. Both are part of the
answer, not decoration.

- **Check the state is inside the range.** Outside it the tool refuses, or for a glycol above 60 %
  answers with a warning that the values are interpolated. It never extrapolates silently, and that refusal is usually a finding about the calculation rather than an obstacle: if
  you are asking for liquid water at 0.001 bar, something upstream has gone wrong.
- **Quote the method when the number goes into a report.** "IAPWS-IF97" or "GERG-2008" is what makes
  a figure checkable by someone else, and it costs a clause.
- **A zeotropic blend has no single boiling point.** It glides. `get_saturation_properties` covers
  the pure refrigerants, with a key, and refuses R454B, R410A and R407C: a blend does not have a dome
  line to report, and a single "boiling point" for one is a fiction.
- **Water is not on `get_saturation_properties`.** Ask `get_fluid_properties` for `STEAM` at the
  pressure with `vapourQuality` 0 and then 1. Both return the saturation temperature, and the latent
  heat is the difference between the two enthalpies.

## Humid air and steam take several input pairs

Steam takes any two of pressure, temperature, enthalpy, entropy and quality. Humid air takes pressure
plus one of these pairs: temperature with relative humidity, temperature with humidity ratio, wet bulb
with relative humidity, dew point with relative humidity, enthalpy with humidity ratio, or humidity
ratio with relative humidity. Use the pair the user actually has rather than converting by hand first:
the conversion is the tool's job and doing it yourself adds an error the result cannot show.

Two common pairs are not on that list:

- **Dry bulb with dew point.** The humidity ratio depends only on the dew point and the pressure, so
  run the psychrometric route below at the dew point and 100 % relative humidity. The humidity ratio
  it reports is the air's own. Then ask again with the dry bulb and that humidity ratio.
- **Dry bulb with wet bulb.** No tool takes this pair. Say so and ask for the relative humidity or the
  dew point, rather than applying a psychrometric formula from memory.

### Psychrometric quantities

`get_fluid_properties` gives humid air's thermophysical properties (density, viscosity, cp,
conductivity, enthalpy and the rest of the 20), **not** its psychrometric state: it does not return
humidity ratio, dew point or wet bulb. For those, call `calculate_air_process` with one `HEATING`
step whose `targetTemperature` is the inlet temperature. The step changes nothing, and every state
it reports carries relative humidity, humidity ratio, enthalpy, dew point, wet bulb and density. Any
`flow` will do for a state, so say that the flow is nominal if you show it.

## Units

Every quantity carries its unit. `convert_units` exists so you never have to apply a factor from
memory, and `listUnitsFor` tells you which symbols a quantity accepts when a user's notation is
unusual. A conversion done in your head is the one step of a calculation nobody can audit.

## Access

The tools are free and anonymous. A few fluids, the refrigerants and brines, are members-only, and
`list_fluids` states the tier per fluid. An anonymous call for one of those is refused with an
explanation rather than a blank, so relay what it says. If the client also has a keyed connection to
the same `/mcp` address (the README suggests naming it `energy-flow-x-keyed`), call those fluids
through that one instead.

## When the question is bigger than a property

- Sizing a pipe or duct for a known flow: the `conduit-sizing` skill.
- Heating, cooling, mixing or humidifying an air stream: the `hvac-processes` skill.
- A network of pipes where the flows are not known until it is solved: the `hydronic` skill.
