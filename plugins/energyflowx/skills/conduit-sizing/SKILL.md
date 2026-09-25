---
name: conduit-sizing
description: >-
  Size a single pipe or duct against real criteria using the free EnergyFlowX MCP tools: velocity,
  pressure drop, Reynolds number and flow regime for a known flow, or the catalogue size that passes
  a stated rule set with the size below and above it and the limit each one breaks. Use this for
  "what size pipe for 2 kg/s", "is DN50 enough for this duct run", "which duct for 3000 m3/h at
  4 m/s", choosing between standard products, looking up a real pipe's inner bore, wall thickness or
  SDR, or sizing a short schedule of segments with fittings against a total pressure-drop budget.
  Works for water, glycols, brines, air, gases, steam and natural gas, and accepts a heat load instead
  of a flow. Reach for it whenever a pipe or duct size is being chosen, even if the request does not
  say "size": "what diameter do I need" is the same question.
---

# Sizing one pipe or duct

Four free tools on the `/mcp` endpoint, no key, connected by the plugin as the `energy-flow-x`
server. They answer the single-conduit question properly, against a real product catalogue and real
fluid properties. The network server, `energy-flow-x-hydronic`, is for the moment a flow is unknown.

| Tool | For |
| --- | --- |
| `size_conduit` | one pipe or duct at a known flow: velocity, pressure drop, Reynolds, friction factor, regime |
| `select_conduit_size` | the catalogue size that passes your criteria, plus the ones either side |
| `search_conduit_catalog` | standard products by code or manufacturer: shape, roughness, size classes, every size |
| `get_conduit_dimensions` | one product's full size table: inner and outer size, wall thickness, SDR, size basis |

## The boundary that matters most

**Sizing one conduit assumes its flow is already known.** That assumption is fine for a branch with a
single terminal on it, and it is false the moment the flow depends on the rest of the system: a ring
main, a branch competing with another, anything where two routes serve the same point.

If you find yourself estimating how a flow splits, stop. That is a network question and it needs the
`hydronic` skill, which solves the whole thing at once. A single-conduit answer built on a guessed
split is confident and wrong, and nothing in its output shows the guess.

## Choosing a size, not just checking one

`select_conduit_size` is the one to reach for when the size is the unknown. It does not return a
single number: it gives **the smallest passing size, the one below it and the limit that one breaks,
and the one above**. That is deliberate and it is what makes the answer useful. The size below and
its failing criterion is the argument for the size you chose, and the size above is what someone will
ask about.

Criteria come either from a library rule set (`systemType` + `role`, or `ruleSet`) or from explicit
limits. Ask which the user works to before assuming: a house standard is common and "around 1 m/s" and
"no more than 200 Pa/m" give different answers on the same duty.

For ducts it also gives **the narrowest width at each allowed height**, which is the form the answer
is actually needed in when a duct has to fit a ceiling void.

## Things that bite

- **Gases and steam need a `length`.** Their density changes along the run, so a pressure drop without
  a length is not defined. Water and glycols do not.
- **A heat load can replace a flow** for water, glycols, brines and air, but the ΔT behind it is a
  design decision, not a measurement. State it in the answer: doubling ΔT halves the flow and changes
  the size.
- **`get_conduit_dimensions` gives the `innerSize` that `size_conduit` needs.** A nominal DN is not a
  bore. Sizing DN50 as 50 mm is a real error on steel and a large one on plastic, where SDR decides
  the wall.
- **Roughness comes from the product**, so search the catalogue rather than passing a number you
  remember. A drawn copper tube and an old cast-iron main differ by two orders of magnitude.

## Schedules and series paths

`select_conduit_size` takes a schedule of up to 20 segments with fittings (Σζ) and can judge a series
path against a **total** drop budget rather than per segment. Use that when the question is "does this
run reach the far end", because sizing each segment independently to the same gradient and adding them
up is not the same calculation and usually gives a different answer.

Beyond 20 segments, or as soon as the path is not a simple series, it is a network: use `hydronic`,
which solves the whole network for liquids, gases and steam alike, rings and meshes included. A branched
system can still be sized run by run here, each branch carrying the flow of what it feeds, but the
moment a flow depends on how two routes share it, stop guessing the split and solve the network.
The same goes for a pump's duty point, which is where its curve meets the whole system, and for
anything over time, such as how long a receiver holds the far tool after a compressor trips: both are
`hydronic` questions.

## Report it so someone can check it

Give the chosen size, the criterion it was judged against, the governing number (velocity or
gradient), and the size below with the limit it breaks. That last part is what turns a number into a
decision somebody else can agree or disagree with.
