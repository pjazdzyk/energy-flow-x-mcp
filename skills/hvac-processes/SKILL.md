---
name: hvac-processes
description: >-
  Calculate what happens to an air stream through an air-handling unit, using the free EnergyFlowX
  MCP tool: heating, cooling with condensate, mixing up to six streams, heat recovery to EN 16798-3
  and EN 308, fans and the heat they add, steam humidification, air-water contact, dehumidification
  and desiccant wheels, as one block or a chain of up to eight. Use it for coil duties, condensate
  rates, water flows, supply conditions, off-coil temperatures, recovery effectiveness and frost
  protection, and for any psychrometric question about an AHU. Reach for it whenever an air stream is
  being heated, cooled, mixed, humidified, dried or recovered from, even if the request just says
  "what comes off this coil" or "how much heat do I need for this air", and for sanity-checking a
  supply condition someone has quoted.
---

# Air handling and psychrometrics

One free tool on the `/mcp` endpoint, `calculate_air_process`, no key, on the plugin's
`energy-flow-x` server. It computes one block or a straight chain of up to eight, and every block is
one the network engine carries as a real step rather than a simplified stand-in.

## The blocks

`HEATING`, `COOLING`, `MIXING` (up to six inlets), `HEAT_RECOVERY`, `FAN`, `STEAM_HUMIDIFIER`,
`AIR_WATER_CONTACT`, `DEHUMIDIFICATION`, `DESICCANT_WHEEL`.

What each gives you beyond the outlet state:

- **Coils** give duty, condensate and water flow. A cooling coil below dew point is a wet coil, and
  the condensate is part of the answer, not a footnote.
- **Heat recovery** gives EN 16798-3 ports, EN 308 effectiveness, leakage and frost protection.
- **The fan** gives air, shaft and electrical power, and **the heat it adds to the stream**. That heat
  is real and it is routinely left out of hand calculations, which is why a supply temperature comes
  out a degree or two low.
- **Dehumidification** splits its reheat into bought and recovered, which is the distinction that
  decides what the process actually costs to run.
- **The desiccant wheel** gives its regeneration heater duty when a regeneration stream is named.

## The one behaviour to rely on

**A target a step cannot reach comes back as `feasible: false`, never as a clean answer**, and that
includes a block that quietly missed its own target part-way down a chain. So `feasible` is the first
field to read, before any temperature or duty.

This matters most in a chain. A cooling coil asked for a supply condition it cannot reach does not
silently return the closest it managed and let the next block carry on from a state that never
existed. Check `feasible` on every step, not just the last one.

## Chains are linear only

Up to eight blocks in a straight line. **No loops, no splitters, no zones.** If the question involves
air going two ways, or a zone feeding back, this tool is the wrong shape and saying so is better than
approximating it into a chain.

## Getting the inputs right

- **Humidity is relative humidity or humidity ratio.** Those are the two the tool takes. If the user
  has a dew point, run a one-step chain first at the dew point and 100 % relative humidity, with a
  heating step that targets that same temperature. The humidity ratio it reports is the air's own. If they have a wet bulb with the dry bulb, no tool takes that
  pair, so ask for one of the others rather than converting from memory.
- **Barometric pressure matters** more than people expect for psychrometrics. The tool takes an
  absolute `pressure`, not an altitude. If the site is not near sea level, ask for its pressure, or
  state the pressure you used and how you got it.
- **Mixing needs the flows, not just the states.** Two streams mix in proportion to their mass flows,
  and a mixed condition computed from states alone is wrong unless they happen to be equal.
- **A fan's position in the chain changes the answer**, because its heat lands wherever it sits. Draw
  the order from the actual unit rather than a typical one.

## Psychrometric state alone

The same one-step trick answers "what is the dew point, wet bulb or humidity ratio of this air": a
`HEATING` step targeting the inlet temperature changes nothing and reports the full state.
`get_fluid_properties` does not return those quantities for humid air.

## Reporting it

Give the outlet condition, the duty, and for a wet coil the condensate rate. Then state the two things
a reviewer will check first: the **barometric pressure used**, and **which humidity input was
used**. Both are cheap to say and both change the numbers.

For property lookups behind all this (densities, enthalpies, saturation states), the
`fluid-properties` skill covers the same free endpoint.
