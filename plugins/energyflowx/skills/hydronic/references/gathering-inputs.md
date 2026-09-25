# Working out what to solve, and getting the data to solve it

Most of the difficulty in a hydraulic job is over before a single number is computed. Someone arrives
with a load in kilowatts, a rough sketch, no elevations and no stated question, and the work is to turn
that into something a solver can answer and a person can act on.

This file is about that half. It is the part no tool schema can express, and the part where an agent
most easily goes wrong, not by calculating badly but by calculating the wrong thing beautifully.

## Contents

- [First: what is the unknown?](#first-what-is-the-unknown)
- [The minimum data, per job](#the-minimum-data-per-job)
- [The conversion nobody gets right](#the-conversion-nobody-gets-right)
- [Absolute or gauge](#absolute-or-gauge)
- [What you may assume, and what you must ask](#what-you-may-assume-and-what-you-must-ask)
- [How to ask without interrogating](#how-to-ask-without-interrogating)
- [Sanity-check the inputs, not just the answer](#sanity-check-the-inputs-not-just-the-answer)
- [A worked intake](#a-worked-intake)

---

## First: what is the unknown?

"Size my system" can mean five different jobs that need different data and produce different answers.
The cleanest way to tell them apart is to ask what is actually unknown. Do this before anything else,
because getting it wrong is far more expensive than any arithmetic error, because you will produce a correct
answer to a question nobody asked, and it will look exactly like a useful one.

| The unknown | The job | What decides it |
| --- | --- | --- |
| Diameters | **Sizing** | a velocity or pressure-gradient criterion |
| Pressure at some point | **Checking** | what is left at the worst outlet |
| Plant pressure | **Selection** | the pressure the design needs at design flow |
| *Where* the pressure goes | **Diagnosis** | the worst edges, element by element |
| Which of two options | **Comparison** | one criterion, both solved the same way |

Two of these need saying out loud because they are routinely conflated:

**Sizing and checking are opposite directions.** Sizing picks diameters to satisfy a criterion.
Checking takes the diameters as given and asks whether the result is acceptable. A user who says "size
this" but has already fixed the pipe sizes wants a check, and telling them their DN50 "should be DN50"
is not an answer.

**Selection is not sizing.** A pump is chosen against the *system* curve, which only exists once the
network is solved. Give a candidate pump its datasheet curve as a device and the solve returns its duty
point; with no pump yet, a `FIXED_PRESSURE` plant gives the pressure the design needs, and the pump is
chosen from that. If someone asks for a pump before the pipework is settled, say so: the duty moves
when the sizes do.

## Equipment and runs over time: what each needs

Each of these is on a datasheet or a drawing. None of them is a typical value to fill in.

- **A pump**: at least three points of its curve, flow against the pressure it develops. A curve in
  metres of head becomes a pressure through the liquid's density (`ρ·g·H`), so get the density from
  `get_fluid_properties` at the loop temperature. A pump belongs on a liquid only.
- **A compressor**: free air delivery at ISO 1217, its discharge pressure (absolute), its full-load
  electrical input or its isentropic efficiency, the share of that input its oil cooler can give to
  water (the heat-recovery figure), and the air temperature leaving its aftercooler.
- **A receiver**: its volume and the pressure it starts at, absolute. A user's "7 bar" is almost always
  gauge, so add an atmosphere and say so.
- **A pressure switch**: its cut-in and cut-out pressures, absolute, and which device it drives.
- **A storage tank**: its volume and starting temperature, and for a run of hours its standby loss (a
  conductance in W/K) with the room temperature it loses to.
- **A heat exchanger**: its UA or its effectiveness at the design flows, from the selection.

**The run itself.** The duration covers the question: a trip until the far tool falls below what it
needs, a tank until it reaches its setpoint. The step is short enough to see what matters: for a
pressure switch, a tenth of the shortest time spent loaded or unloaded. An unload lasts about
`V·(p_off − p_on) / (p_atm·Q)`, with the receiver volume, the band in absolute pressure, and the free-air
draw: a 2 m³ receiver with a 1.5 bar band drawn at 5.6 m³/min unloads in about 32 s, so a 3 s step.

## The minimum data, per job

Every network solve needs all of this, whatever the job:

1. **A fluid**, its temperature, and what that fluid needs besides: a concentration for a glycol or a
   brine, a humidity for humid air, a preset or composition for natural gas. A plant with several
   fluids is several systems in one design, each with its own.
2. **Something holding the pressure**: a boundary node, or a fill pressure for a sealed loop.
3. **Something making the fluid move**: fixed demands, two pressure boundaries at different
   pressures, a pump on a liquid, or a compressor on air.
4. **Topology**: what connects to what.
5. **Lengths**, and **sizes** unless the job is to find them.
6. **Elevations.**

Then, per job:

- **Sizing** also needs the criterion. "Around 1 m/s" and "no more than 200 Pa/m" give different
  answers on the same network, and the user usually has a house standard.
- **Checking** also needs the acceptance condition: how much pressure must be left, and where.
- **Selection** also needs the design flow and any minimum-flow constraint on the machine.
- **Diagnosis** needs what is *observed* as well as what is designed. The gap between them is the
  finding.
- **Comparison** needs both options expressed to the same level of detail. Comparing a carefully
  fitted-out option against a bare one measures the modelling, not the design.

**Elevation is the one that gets left out**, because it looks optional and every other field is about
the pipe. It is not optional in any building. Water is about 9.8 kPa per metre, so eleven metres is
about 108 kPa. On a 5 bar system that is a fifth of everything available, spent before any friction. A model
with the elevations missing is not a rough model, it is a model of a flat building.

## The conversion nobody gets right

Users give heating and cooling duties in kilowatts. The network tools want a mass flow. The bridge is

```
ṁ = Q / (cp · ΔT)
```

and **ΔT is a design decision, not a measurement.** It is the single most consequential number in the
intake: doubling ΔT halves the flow, which changes every pipe size and the pump duty with it. Ask for
it, or state the value you used in the same sentence as the answer. Never let it sit unmentioned.

Get `cp` from the free `/mcp` endpoint with `get_fluid_properties` at the design temperature rather
than from memory. Two reasons it matters more than it looks:

- **A glycol needs more flow for the same duty.** Its specific heat is meaningfully lower than water's,
  so the same kilowatts demand a larger ṁ, and it is also denser and more viscous, so that larger flow
  costs more head again. Sizing a glycol circuit off the water figure under-sizes it twice over.
- **The temperature you evaluate at is not free either.** Water's viscosity at 70 °C is about a third
  of its value at 20 °C, so a heating circuit solved cold reports friction losses that are too high.

Volume flows of a liquid are easier: `add_node`'s `demand` accepts `"4.3m3/h"` directly and the
server converts using the fluid's density at the design temperature, then states the conversion in the
response. Read it once to confirm it used the density you meant.

A gas volume is a different animal, because it means nothing without the state it was measured at.
Find out which of three it is before you type it:

- **Free air delivery**, how compressors and air tools are rated: `flowBasis: FAD`, dry air only.
- **Normal or standard cubic metres**, how gas meters, boilers and burners are quoted: write the unit,
  `"40Nm3/h"` or `"40Sm3/h"`. Normal is 0 °C, standard is 15 °C, both at 101.325 kPa, and they differ by
  about 5%.
- **The volume at the line**, how ventilation airflows are given: `flowBasis: ACTUAL`, converted at the
  node's own solved pressure.

A burner's rating in kW becomes a gas flow through the calorific value, which
`get_natural_gas_properties` gives for the same preset or composition.

## Absolute or gauge

The design API takes **absolute** pressure. A user saying "4 bar" in a building almost always means
4 bar gauge, which is about 5.01 bar absolute, and a bar is a large fraction of most systems.

This is not a hypothetical: the difference was documented wrong in this codebase's own javadoc and went
unnoticed, because both numbers look entirely plausible on a schedule.

So: when someone gives a pressure, ask which it is, or state the assumption in the answer. "I have
taken your 4 bar as gauge, so 5.01 bar absolute" costs one clause and removes the whole class of error.

## What you may assume, and what you must ask

The test is not "how confident am I". It is **what happens if I am wrong, and would the reader spot
it.** An assumption that is both consequential and invisible is the one to refuse.

**Assume, and say so in the output:**

- *Wall roughness*, from a named material. Name the material, not the number.
- *Fluid temperature*, when the user did not say. State it: it moves the friction noticeably.
- *A fittings allowance*, if you must, expressed as a percentage of straight-run loss and labelled as
  an allowance. Counting the fittings is better and the vocabulary supports it.
- *Ambient temperature*, where it only affects a thermal term nobody is asking about. A pipe exchanges
  no heat with its surroundings here, so it takes none; a storage tank states its own standby loss.

**Never assume. Ask, or refuse to answer:**

- *A glycol or brine concentration.* The server refuses it too, and rightly: a 30% ethylene glycol is
  about 6% denser and roughly twice as viscous as water at 20 °C, so a defaulted concentration is a
  wrong friction loss presented as a real one.
- *What a gas volume was measured at*, *the humidity of humid air*, and *the composition of a natural
  gas*. The server refuses all three when they are missing. Grid gases differ by more than 10% in
  density, and a compressed-air figure read as the wrong basis is out by the pressure ratio.
- *Elevations*, in anything with more than one floor. See above.
- *Demands.* An invented flow produces a complete, confident, fictional study.
- *ΔT*, for a kW conversion.
- *Gauge or absolute*, for a stated pressure.
- *The acceptance criterion.* "Is it OK" has no answer until somebody says what OK is.

There is a rule underneath all of these: **an assumption is only acceptable if it appears in the
output.** The study's assumptions section exists for exactly this, and an assumption that is not
written down is indistinguishable from a measurement to whoever reads the report next.

## How to ask without interrogating

A twenty-question intake is how a user gives up. A better order, which also uses a feature the server
already has:

1. **Build what you can from what they gave you.** A half-built design is a normal state and the server
   is happy to hold one.
2. **Ask the server what is missing**: `hydronic_inspect(handle, what="readiness")`. It answers in two
   groups: what would make the answer meaningless, and what merely gets assumed.
3. **Ask the user only for the blocking group**, in one message, in their vocabulary rather than the
   API's. "I need the height of the top floor above the plant room, and whether your 4 bar is gauge"
   beats a list of field names.
4. **Solve, and report the assumed group as assumptions** alongside the answer.

That order means the user is asked once, for the fewest things, at the point where it is obvious why
each one is needed. It also means you are never guessing at what is missing, because the server knows.

## Sanity-check the inputs, not just the answer

The solver will faithfully solve nonsense. These four catch most of it, and all four are worth running
before the solve rather than after:

- **Does the total demand make sense against the source?** A 15 kg/s demand on a 22 mm supply is a
  typo, not a design.
- **Is the ΔT plausible?** 5 K and 40 K are both real in different systems; 400 K is a unit error.
- **Do the elevations span what the building spans?** All zeros in a six-storey block is the omission
  described above.
- **Is the fluid right for the temperature?** Water at −10 °C is a hint that the circuit is glycol and
  nobody said.

## A worked intake

> "Can you size the pipework for our plant room? It's 24 kW of heating going up to the third floor."

Nothing here is sufficient yet, and the useful move is to notice *which* gaps are blocking.

**Derivable:** 24 kW is a duty, not a flow. With water and a stated ΔT it becomes a mass flow. Third
floor is roughly 11 m, but "roughly" is doing real work in a pressure calculation.

**Blocking, so ask:** the ΔT (or accept their house value), the actual height, the supply pressure and
whether it is gauge, and the sizing criterion.

**Assumable, so state:** commercial steel roughness, 70 °C flow temperature, and a fittings allowance
if they have no fitting counts.

A good reply builds the skeleton first, then asks once:

> I have set up a riser with a 24 kW load at the top. Four things decide the answer and I would rather
> not guess at them:
>
> - **Design ΔT**: at 20 K that is 0.29 kg/s, at 10 K it is 0.57 kg/s, which is a pipe size or two.
> - **Height** to the third-floor connection. At about 11 m that is roughly 108 kPa of static head
>   before any friction.
> - **Supply pressure**, and whether that figure is gauge or absolute.
> - **Sizing criterion**: a velocity limit, or a pressure gradient, if you have a house standard.
>
> I will assume commercial steel and 70 °C flow unless you say otherwise, and both will be listed in
> the study.

That is four questions, each with its consequence attached, and the user can answer all of them in one
line.
