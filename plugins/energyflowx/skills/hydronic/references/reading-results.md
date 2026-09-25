# Reading a solve like an engineer

A hydraulic solve returns a lot of numbers and almost none of them are the answer. This is what to look
at, in what order, and what each thing means when it goes wrong.

## Contents

- [The order to read in](#the-order-to-read-in)
- [Run notices, one by one](#run-notices-one-by-one)
- [The lowest node is usually the answer](#the-lowest-node-is-usually-the-answer)
- [Signs, and the flow divide](#signs-and-the-flow-divide)
- [Sanity checks that catch real mistakes](#sanity-checks-that-catch-real-mistakes)
- [What the solver will not tell you](#what-the-solver-will-not-tell-you)

---

## The order to read in

1. `warnings`
2. `converged`
3. `lowestPressureNodes` and `worstEdges`
4. the signs on edge flows
5. `fastestEdges`: velocities, and for a gas Mach numbers

The order matters because each step can invalidate the ones after it. Reading velocities first and
notices last is how a number that should never have left the machine ends up in a report.

## Run notices, one by one

A notice is the engine saying what computing the answer *involved*. Every one of them produces a
perfectly ordinary-looking number, which is the entire reason the channel exists. Notices arrive in
the solve's `warnings` as complete sentences, not as codes, so recognise each one by what it says.
The code names below are the engine's, for reference.

### `NON_PHYSICAL_PRESSURE`: stop

A node settled at or below **zero absolute pressure**. The sentence reads "Node '...' settled at
... kPa absolute". No fluid is ever at that state, so the answer is
a mathematical solution to a physical impossibility, and every number downstream of that node is
arithmetic on it.

Why it happens: a fixed demand is a promise the solver keeps whatever it costs. When the head available
cannot drive that flow through the pipe sizes drawn, the pressure field is pushed through zero to
satisfy it. The solve converges cleanly, because nothing about the linear algebra objects.

What to do: **do not quote any number from that run.** Tell the user the network cannot deliver what is
being asked. Then reduce the demand, open up the run, or raise the supply pressure, and solve again.

The one honest thing you can take from such a run is *where* it ran out. The node named in the notice
is where the head was exhausted, and that is a real piece of information about the design.

### `PUMP_OUTSIDE_RATED_RANGE`: qualify

The duty point settled past the flow range the pump curve describes. The off-design policy keeps the
solve well-posed out there, so the answer is the best the model can give, but the head and the power are
an **extrapolation past the datasheet** rather than a reading off it.

What to do: report the duty with that qualification attached, in those words. Suggest a pump whose curve
spans the flow, or a change in resistance that brings the duty back inside it. Do not quietly present the
extrapolated power as a selection.

### `FLUID_PROPERTY_SUBSTITUTED`: qualify, and check the state

A property could not be evaluated for the committed state, so a substitute was used. The number is real
arithmetic on a fluid state that is not the one in the pipe.

What to do: look at the temperature and pressure at that element. A state outside the fluid model
usually means the run is being pushed somewhere the design does not actually go, which is a design
finding in its own right. If the state is intended, then the fluid is the wrong one for it.

### `VALUE_CLAMPED`: qualify

A quantity was held at a physical limit instead of computed. The reported value is a **bound**, not an
answer, and a bound nobody is told about looks exactly like a result.

### A code you have not seen

Relay its message. The engine's contract is that every notice message is a complete sentence that
stands on its own, precisely so a consumer that does not recognise the code can still pass it on. Do not
drop it, and do not invent advice for it.

## The lowest node is usually the answer

More often than not, the question behind a network solve is "does enough pressure reach the far end",
and `lowestPressureNodes` answers it directly: which node has the least, and how much.

A design with a comfortable margin at the lowest node works, whatever any individual pipe's velocity
looks like. A design with nothing left there fails, however tidy the rest of the schedule is.

`worstEdges` tells you *where* to spend money. It ranks the edges by the head they consume, with
friction, local and static parts split apart, so the one contributing most is the one to change.
Static head is not a loss and no bore will reduce it. Upsizing anything else is wasted.

The solve returns no critical path as such. Trace it from the edges along the route to the lowest
node when a report needs one.

## Signs, and the flow divide

In a solved network the sign of an edge flow is its **direction** relative to the from/to the edge was
declared with. In a branched network that is bookkeeping. In a **loop** it is the whole point.

Somewhere around a ring, the flow changes sign. That place is the **flow divide**: the point fed from
both directions, where the two routes from the source meet. It is set by the whole loop at once, by every
length, every diameter, every demand and every elevation, and it moves when any of them change.

This is the thing that cannot be reached by sizing pipes one at a time. A single-conduit calculation
starts by assuming the flow through that conduit is known, and around a ring it is not known until the
network is solved. If you ever find yourself estimating how a flow splits, that is the signal to build
the network instead.

Worth saying to a user in as many words when you report a ring: which blocks are fed which way, and
where the divide sits. It is usually the most useful sentence in the whole report, and it is invisible
in a table of magnitudes.

## Sanity checks that catch real mistakes

**Mass balance.** The supply's net flow should equal the sum of the demands, to within rounding. If it
does not, something is not connected where you think it is.

**Velocity.** `fastestEdges` gives every pipe's velocity, for a gas at its faster end with the Mach
number beside it. Roughly 0.5 to 1.5 m/s in liquid distribution pipework is unremarkable,
compressed-air mains are commonly designed for 6 to 10 m/s, saturated steam mains for 25 to 40 m/s,
and low-velocity ventilation ducts for a few metres per second. An order of magnitude out almost always
means a unit went in wrong or a demand landed on the wrong node, not that the design is exotic. Above
Mach 0.3 the solve warns that the drop is an estimate, and above 0.7 that the run is close to choking.

**Phase.** A `PHASE` warning, with rows in `phaseProblems`, means the fluid crossed its saturation line
at the nodes it names: steam condensing, a liquid line flashing, water boiling at a high point, humid air
at its dew point. The numbers around those nodes were computed with properties of the wrong phase, so
they are not a state the system can reach. Change the design and solve again.

**Static head.** Water is about 9.8 kPa per metre. If a node 11 m up does not read about 108 kPa below
one at the datum, elevations are missing or on the wrong nodes. This one catches the single most common
authoring mistake, which is leaving `elevation` off because it looked optional.

**Reynolds number.** Below about 2300 the flow is laminar, and in a distribution network that usually
means the pipe is far too big for the flow rather than that anything interesting is happening.

## What the solver will not tell you

**Whether the design is a good one.** It reports what the network does, not whether the pipe sizes are
economic, whether the pump is a sensible selection, or whether the system will be quiet. Those are
engineering judgements and they belong to the person reading.

**Whether the inputs are right.** A demand typed as 20 kg/s instead of 2 solves perfectly. The sanity
checks above exist because nothing else will catch it.

**Absolute pressures, when there is no datum.** A sealed loop with no fill pressure has fully determined
flows and pressure differences, and arbitrary absolute readings, because the field is fixed only up to a
constant. This server refuses to solve it until something anchors the pressure, so set `fillPressure`
and say that the absolute readings rest on it.

**A run over time, read for its questions.** A vessel's lowest pressure and when it happened is the
worst the far end saw. A machine's starts over a short run is its cycling rate: scale it to an hour
before judging it against the maker's limit. The energy a compressor or a heater put in should reappear
in the store it charged, within a few per cent, and when it does not, say why before quoting either
figure. A switch acts at step boundaries, so a dip below cut-in of about one step's draw is the step.

**Anything about pressure waves.** A transient run here is quasi-steady: each step is a steady network
solve, so it answers how a receiver swings, how long the air lasts after a compressor trip, how often a
machine cycles and how far a store charges. A surge or water hammer after a valve slam or a pump trip
travels at the speed of sound in the pipe and is not in it.
