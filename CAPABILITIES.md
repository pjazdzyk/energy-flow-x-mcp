# What the EnergyFlowX MCP servers can do

This is the detailed list, tool by tool, of what the two EnergyFlowX MCP servers accept and return.
The [README](README.md) is the short version and the place to start.

The servers themselves are the final authority, and they describe themselves. `list_fluids` returns
the live fluid catalogue with every validity range. Hydronic MCP publishes its full vocabulary
as MCP resources. If this page and a server ever disagree, the server is right, and we would like to
hear about it.

Everything on this page was checked against the live servers on 24 September 2026.

## Contents

- [The two servers](#the-two-servers)
- [How every tool on the main server behaves](#how-every-tool-on-the-main-server-behaves)
- [Fluid properties](#fluid-properties)
- [Saturation](#saturation)
- [Natural gas](#natural-gas)
- [Ice](#ice)
- [Unit conversion](#unit-conversion)
- [The conduit catalogue](#the-conduit-catalogue)
- [Sizing one pipe or duct](#sizing-one-pipe-or-duct)
- [Choosing a size](#choosing-a-size)
- [Air handling](#air-handling)
- [Hydronic MCP (complex hydraulics)](#hydronic-mcp-complex-hydraulics)
- [Limits and access](#limits-and-access)

## The two servers

| | Main server | Hydronic MCP |
| --- | --- | --- |
| Address | `https://energyflowx.com/energy-flow-x/mcp` | `https://energyflowx.com/energy-flow-x/mcp/hydronic` |
| Name in the plugin | `energy-flow-x` | `energy-flow-x-hydronic` |
| Tools | 11 | 4, plus 6 resources |
| API key | optional: refrigerants, brines, larger sweeps | required on every call |
| What it does | properties, sizing, air processes | builds and solves whole pipe networks |

The network tools live on their own address because a client carries every tool's schema on every
turn. Keeping them apart means someone who only wants the density of water does not pay for a
network vocabulary.

## How every tool on the main server behaves

- **Inputs carry their units.** Every quantity is a string such as `"20oC"`, `"293.15K"`, `"70degF"`,
  `"1.5bar"`, `"101.325kPa"`, `"14.7psi"`, `"8g/kg"` or `"40%"`. There is no input unit setting to get
  wrong. Pressures are absolute. `atm` is not an accepted symbol.
- **Outputs come in three unit systems.** `SI` is the default (°C, kPa, kJ/kg). `SI_STRICT` gives K,
  Pa and J/kg. `IMPERIAL` gives °F, psi and BTU/lb. A per-property `units` map overrides the system for
  the properties you name.
- **Every result key names its unit**, for example `density_kgpm3` or `specificEnthalpy_BTUplb`, so
  the unit you received is in the payload rather than assumed.
- **Every computed result names its method**, for example "IAPWS-IF97" or "GERG-2008
  (ISO 20765-2)", and every property and sizing result also states the validity range it used.
- **Nothing fails silently.** A property the model cannot give appears under `unavailable` with the
  reason. A default the tool applied appears as a warning. A truncated list says it is truncated.
- **Errors say how to fix the call.** A refusal states what was received, what is accepted and what
  to send instead. A rejected unit names the symbol it could not read and shows the accepted form, and
  `convert_units` with `listUnitsFor` lists every symbol a quantity takes.
- **Every tool is read-only, idempotent and closed-world**, and declares itself so. Clients do not
  need to ask permission for a lookup.
- **Sweeps.** `get_fluid_properties` takes a list of `states` and returns one table in one call. The
  cap is 5 states per call anonymously and 20 with an API key. Top-level fields act as defaults for every
  state, so "one temperature, many pressures" is a short request.

## Fluid properties

Tools: `get_fluid_properties`, `list_fluids`.

### The 29 fluids

- **Water and steam**: liquid water and steam, by IAPWS-IF97.
  - Liquid water is valid from 273.15 to 623.15 K, up to 100 MPa (region 1).
  - Steam is valid from 273.15 to 1073.15 K up to 100 MPa, and to 2273.15 K up to 50 MPa (region 5).
  - Steam takes any two of pressure, temperature, specific enthalpy, specific entropy and vapour
    quality. On the saturation line, use vapour quality, because pressure and temperature are not
    independent there.
- **Air**:
  - Dry air, by the Lemmon reference equation of state, from 60 to 2000 K up to 70 MPa.
  - Humid air, as moist-air psychrometrics over the dry-air and water reference models, from about
    −80 to 200 °C, humidity ratio up to 3 kg/kg.
  - Humid air takes pressure plus one pair: temperature with relative humidity, temperature with
    humidity ratio, wet bulb with relative humidity, dew point with relative humidity, enthalpy with
    humidity ratio, or humidity ratio with relative humidity. Dry bulb with wet bulb and dry bulb with
    dew point are not accepted pairs.
  - It returns humid air's thermophysical properties, the 20 below. It does not return humidity
    ratio, dew point or wet bulb. Every air state from [`calculate_air_process`](#air-handling) does.
- **Industrial gases**: hydrogen, carbon dioxide, ammonia, propane, nitrogen, oxygen, argon, helium,
  methane and nitrous oxide. Each uses its multiparameter Helmholtz reference equation of state, valid
  from the triple point to the upper limit of that equation.
- **Natural gas**: see [Natural gas](#natural-gas), which has its own tool.
- **Glycols**: ethylene glycol and propylene glycol, by the Melinder correlations for aqueous
  secondary coolants.
  - Concentration 0 to 60 % by mass. Above 60 % the values are interpolated, and the response says so.
  - Concentration can be given by mass, volume or mole fraction.
  - The lowest valid temperature is the freezing point at the concentration given, and the upper
    limit is 100 °C.
- **Refrigerants** (API key): R134a, R1234ze, R1234yf, R32, R125, R454B, R410A and R407C, each by its
  multiparameter Helmholtz reference equation of state.
- **Brines** (API key): calcium chloride, ethanol, methanol and potassium formate solutions, by the
  Melinder correlations. Each needs a concentration.

### The 20 properties

- **Returned by default**: density, dynamic viscosity, kinematic viscosity, specific heat cp, thermal
  conductivity, specific enthalpy and Prandtl number.
- **On request**: specific volume, specific heat cv, heat capacity ratio, specific internal energy,
  specific entropy, thermal diffusivity, speed of sound, compressibility factor, isothermal
  compressibility, isentropic compressibility, cubic expansion coefficient, surface tension and
  freezing point.
- Not every model provides every property. A missing one is listed under `unavailable` with the
  reason, for example cp for steam under IAPWS-IF97.
- A state close to a saturation line is answered with a warning naming the branch that was returned.

### The catalogue

- `list_fluids` returns every fluid with its code, its accepted state inputs, its method, its access
  tier and its validity range, both in words and as numbers.
- It also lists every property name the tools accept and the default set.

## Saturation

Tool: `get_saturation_properties`.

- **Fluids**: nitrogen, oxygen, argon, methane, nitrous oxide, carbon dioxide, ammonia, propane and
  hydrogen. With an API key, also the pure refrigerants R134a, R1234ze, R1234yf, R32 and R125.
- **Inputs**: a temperature, giving the saturation pressure, or a pressure, giving the boiling or
  condensing temperature.
- **Outputs**: saturation temperature and pressure, saturated liquid and vapour densities, latent heat
  of vaporisation, critical point and triple point.
- **Curves**: `curvePoints` adds a sample of the whole dome, 5 to 40 points, to the point you asked
  for.
- **Refused**: a state outside the dome, and the zeotropic blends (R454B, R410A, R407C), which glide
  and have no single saturation line.
- Water and steam are not served by this tool. Ask `get_fluid_properties` for `STEAM` at a pressure
  with vapour quality 0 or 1 instead, which returns the saturation temperature with the state.

## Natural gas

Tool: `get_natural_gas_properties`.

- **Method**: the GERG-2008 wide-range equation of state (ISO 20765-2), valid from 90 to 450 K up to
  70 MPa, with calorific values and Wobbe index per ISO 6976.
- **Presets**: `PL_GZ50`, `PL_GZ415`, `PL_GZ35`, `US_PIPELINE`, `NG_H2_20` (20 % hydrogen),
  `RAW_BIOGAS`, `PURE_PROPANE`, `PURE_BUTANE` and `LPG_PROPANE_BUTANE`.
- **Your own composition**: mole fractions over 21 components. They should sum to 1; a composition that
  does not is normalised, and the answer says what it summed to. The components are
  methane, nitrogen, carbon dioxide, ethane, propane, isobutane, n-butane, isopentane, n-pentane,
  n-hexane, n-heptane, n-octane, n-nonane, n-decane, hydrogen, oxygen, carbon monoxide, water,
  hydrogen sulfide, helium and argon.
- **Always returned**: gross and net calorific value per m³ and per kg, superior and inferior Wobbe
  index, relative density and molar mass.
- **Thermodynamic properties** at the stated temperature and pressure: the same property names as
  `get_fluid_properties`.
- The same presets and compositions are accepted by `size_conduit` and `select_conduit_size`, so a gas
  run is sized with the real gas.

## Ice

Tool: `get_solid_properties`.

- Density, specific heat, specific enthalpy, specific volume and specific entropy of ice at or below
  0 °C, at any stated pressure.
- Liquid water below 0 °C is outside the IAPWS liquid model, and the error points here.

## Unit conversion

Tool: `convert_units`.

- Converts any supported quantity between units, for example `"20oC"` to `degF`.
- `listUnitsFor` lists the symbols a quantity accepts, which is the fix for a rejected unit.
- Every factor is built from an exact, sourced definition (Unitility 4.2.0, checked against
  NIST SP 811).
- `quantityType` disambiguates a symbol that several quantities share, such as `%`.

## The conduit catalogue

Tools: `search_conduit_catalog`, `get_conduit_dimensions`.

- **Search** by catalogue code or manufacturer, for pipes or ducts. Each product returns its shape,
  its wall roughness variants, its size classes (PN, SDR or schedule for pipe) and every size it comes
  in.
- **17 pipe products**:
  - Steel: EN 10216 and EN 10217 pressure pipe (EN-L, EN-M, EN-H), ASME B36.10M carbon steel (SCH10
    to SCH160), ASME B36.10M A335 alloy steel for high-pressure steam, ASME B36.19M stainless (SCH10S
    to SCH80S), and EN 10255 threaded galvanised tube (light, medium, heavy).
  - Copper: EN 1057 for water and heating, EN 12735-1 metric and ASTM B280 inch refrigeration tube.
  - Plastics: PE100 and PE80 water pressure pipe (Pipelife), PE100 SDR11 for gas (EN 1555), PE-X,
    PE-RT, PP-R, PVC-U and CPVC.
  - Aluminium tube for compressed-air mains.
- **11 duct products**: galvanised steel rectangular and Spiro, aluminium flex, concrete and brick
  ducts, PVC chemically resistant ducts in rectangular, circular and thickened circular (Chemowent),
  textile supply and exhaust ducts (A-WENT), and PROMADUCT-500 fire-rated ducts (Etex).
- **Dimensions**: for every size in every class, the inner and outer size, wall thickness, SDR, the
  size basis and, for metal pipe, an informational working pressure. This `innerSize` is the bore that
  `size_conduit` needs. A nominal DN is not a bore.

## Sizing one pipe or duct

Tool: `size_conduit`.

- **Shapes**: circular, by inner diameter, and rectangular, by inner width and height.
- **Fluids**: all 29, including humid air with its humidity, steam by pressure and vapour quality, and
  natural gas by preset or composition.
- **Flow**: volumetric flow, mass flow, dry-air mass flow for humid air, or a heat load with supply and
  return temperatures for water, glycols, brines and air.
- **Outputs**: velocity, pressure drop over the run (or per metre without a length), Reynolds number,
  friction factor and flow regime.
- **Method**: Darcy-Weisbach, 64/Re in laminar flow, a linear bridge from Re 2300 to 4000, and
  Colebrook-White in turbulent flow. It is the same solver as the web sizing calculator.
- **Gases and steam need a length**, because their density changes along the run. The friction then
  uses the mean density and the velocity is judged at the outlet.
- **Roughness**: stated directly, or the commercial-steel default, and the response says which.
- **Refused**: a state on the saturation line, two-phase steam, and a sub-cooled liquid whose pressure
  drop would take it to boiling.

## Choosing a size

Tool: `select_conduit_size`.

### What it returns

- The smallest catalogue size of one product that meets every limit.
- The size just below it, and which limit it breaks and by how much.
- The next size up.
- The continuous ideal bore at which every limit is met.
- The utilisation of every limit at the chosen size.
- A window of neighbouring sizes, or the whole series with `window: ALL`.
- `NO_SIZE_FITS_BAND` when no size satisfies every limit, together with the closest size. It never
  returns a pick that quietly breaks a rule.
- Without a product code, the ideal round bore and the products that suit the criteria.

### Criteria

Criteria come from a named rule set, from explicit limits, or from both. Explicit limits override the
rule set's. With none, the error lists the rule sets that fit the product.

- **Library rule sets**, by `systemType` and `role` or by `ruleSet` id. Each is representative
  practice chosen by EnergyFlowX, not a table from a standard, and the response says so.
  - Cold water: header, branch.
  - Hot water: supply, recirculation.
  - Heating: main, distribution, connection.
  - District heating: transmission, distribution, service.
  - Chilled water: main, distribution, connection.
  - Coolant and brine: main, connection.
  - Compressed air: ring, distribution, equipment drops.
  - Natural gas: low pressure, medium pressure.
  - Refrigeration: suction, suction riser, discharge, liquid line.
  - Process gas: header, branch.
  - Ventilation: main, distribution, quiet distribution, connection.
  - Textile ducts: the 1:2 and 3:4 ratios.
  - Smoke extraction: main.
  - Dust extraction: local exhaust.
  - Generic, for any system: distribution, riser.
- **Explicit limits** in `maxLimits`, each recognised by its unit: a velocity (`"1.5m/s"`), a gradient
  (`"200Pa/m"`), a total drop (`"5kPa"`), a refrigerant saturation-temperature drop (`"0.5K"`) or a
  duct aspect ratio (`"4"`). `minVelocity` sets a floor.

### Schedules and paths

- Up to 20 segments in one call, each with its own flow or heat load, length and fittings as a sum of
  loss coefficients.
- `series: true` makes the segments one run in order, such as meter to appliance. Each segment then
  starts at the previous outlet pressure, and a total-drop limit is judged on the whole path.
- The path result ranks the segments by their share of the drop, gives the drop one size up for each,
  and gives the equal-friction gradient that would meet the budget.

### Ducts and pressure classes

- A rectangular duct takes `fixedHeight` to keep one catalogue height, or `maxHeight` for a ceiling
  void, where the outer height must fit.
- The answer includes the narrowest passing width at each allowed height.
- `designPressure`, as a gauge pressure, checks the product's pressure class.

### Warnings it gives

- A pick in transitional flow, where the gradient depends on the regime model more than on the wall.
- Fitting losses below Re 10,000, where published loss coefficients understate the loss, so the local
  drop is a lower bound.
- A product catalogued for a different application than the rule set.
- A liquid that would flash to vapour at a size's pressure drop, reported as `TWO_PHASE_FLASHING`.

## Air handling

Tool: `calculate_air_process`.

### The chain

- One block, or a straight chain of up to 8. Each step's outlet feeds the next.
- The inlet air is given by temperature, humidity (relative humidity or humidity ratio), flow and
  pressure. The pressure is shared by every stream, so a site away from sea level is one field.
- Extra streams, such as return air for a mixing box or extract air for heat recovery, are listed once
  and named by the steps that use them.
- The flow can be stated at the inlet or as the flow the chain delivers at its outlet.
- Every air state a step reports is complete: temperature, relative humidity, humidity ratio,
  enthalpy, dew point, wet bulb, density, volumetric flow, mass flow and dry-air mass flow. A coil
  reports its inlet and outlet, a heat-recovery unit its four ports, and a mixing box every stream.
- `outletAsInput` is the outlet written as inputs, ready to start the next call.

### The blocks

- **Heating coil**: to a target temperature or at a stated power. Returns the duty and, with supply and
  return temperatures, the heating-water flow. The medium can be water, ethylene glycol or propylene
  glycol at a stated concentration, and the flow is computed with that fluid's own properties.
- **Cooling coil**: to a target temperature, a target relative humidity or a stated power. Returns the
  duty, whether the coil runs wet, the condensate flow and temperature, the chilled-water flow, the
  coil wall temperature and the bypass factor.
- **Mixing**: up to 6 inlets, mixed by mass. Name the fresh-air inlet and it also returns the
  fresh-air share by mass and by volume.
- **Heat recovery**: a plate (sensible) or sorption rotor (enthalpy) exchanger, to EN 16798-3 ports
  (outdoor, supply, extract, exhaust).
  - Runs at a stated effectiveness, to a supply temperature or at a recovered power.
  - Leakage from 0 to 20 % in either direction.
  - Frost protection: none, bypass, preheater or stopping both fans, with the trigger surface
    temperature. It reports the coldest surface, whether frost protection engaged and any residual
    risk.
  - Returns EN 308 temperature and humidity effectiveness, recovered power, preheater power and
    condensate on either side, and the achievable range when a target is out of reach.
- **Fan**: a total pressure rise and a total efficiency. Returns air, shaft and electrical power, the
  specific fan power, and the heat the fan adds to the stream.
- **Steam humidifier**: to a target relative humidity, from steam at a stated supply pressure.
- **Air-water contact**: a recirculating washer, wetted media, spray chamber, high-pressure atomiser,
  ultrasonic humidifier or compressed-air atomiser, adiabatic or with a stated spray water temperature.
- **Dehumidification**: to a moisture target with the dry bulb put back. The reheat comes from nothing,
  a separate heater, hot gas, condenser recovery or a run-around loop, and the result splits the
  reheat into bought and recovered.
- **Desiccant wheel**: to a process dew point, with a moisture effectiveness. With a regeneration
  stream named, it returns the regeneration heater duty.

### Feasibility

- A target a step cannot reach comes back as `feasible: false` with the reason and what to change. It
  is never returned as a clean answer.
- `firstInfeasibleStep` names where a chain first failed.
- Every step after a failed one is marked `upstreamClamped`, because it was computed on air the design
  never produced.

### Out of scope

- No loops, splitters or zones. A process where air goes two ways is not a straight chain, and the
  tool says so rather than approximating it.

## Hydronic MCP (complex hydraulics)

Server: `/mcp/hydronic`. Tools: `hydronic_session`, `hydronic_edit`, `hydronic_solve`,
`hydronic_inspect`. An API key is required on every call.

### What this release solves

- Networks of liquids, gases and steam, in steady state or over time: water and glycol circuits, water mains,
  compressed-air rings, natural-gas distribution, ventilation duct trees, steam mains, industrial-gas
  lines and refrigerant liquid or vapour lines.
- Branched networks, rings and meshes of any topology, with elevations, fittings and lumped
  resistances.
- Several fluid systems in one design, such as the gas supply and the heating circuit of one plant
  room, each solved on its own at its own temperature and fill pressure.
- Flow is driven by fixed demands, two pressure boundaries at different pressures, a pump on a
  liquid, or a compressor on air.
- **Equipment** (`add_device`): a pump with its datasheet curve (liquids only), an air compressor
  rated in free air delivery with its oil-cooler heat recovered into a water circuit, a heater or
  boiler (a power, or an outlet temperature it holds), a heat exchanger between two systems (UA or
  effectiveness), and a storage tank, well mixed or stratified in layers. A `PRESSURE_TANK` node is a
  receiver on a gas, storing its real-gas mass, or an expansion vessel on a liquid. Each device's ports
  and settings are in `hydronic://vocabulary/devices`.
- **Transient runs** (`mode="transient"`): schedules on a pump, a compressor, a demand or a boundary
  pressure, ON_OFF pressure or flow switches and PI loops, over the duration `set_transient` states.
  Returned: each vessel's swing with when, the lowest pressures and when, each machine's starts,
  average power, energy and recovered heat, how far each store charged, every command change and a
  sampled table of 24 rows. At most 2,000 steps, and a run predicted to take over 60 s is refused with
  the step that would fit.
- **Not yet**: fans (a pump curve is a liquid's), control valves, balancing and regulation. Also not
  modelled: two-phase flow (wet steam, condensate with flash steam), heat exchange between a pipe and
  its surroundings, water hammer and surge, and devices that change the fluid, such as dryers and
  coils.

### Sessions

- A network is never passed as a tool argument. It lives on the server behind a handle, so its size
  costs nothing per call and the design cannot drift from what the assistant remembers.
- Actions: `create` a new design, `open` one from a previous export, `export` it, `list` your
  sessions and `close` one.
- Export in two formats: `session`, which opens again here, and `request`, the payload the EnergyFlowX
  REST API takes.
- A session belongs to the account whose key created it. Another account cannot read it, and any key
  of the same account can.
- Sessions expire after 24 hours, so export is the save.
- Up to 20 open sessions per account, and up to 2,000 nodes and edges per design.

### Editing

- **Batches**: up to 500 ops in one call, applied all or nothing. A refusal names the op index and the
  field. `dryRun` validates a batch without applying it.
- **Strict fields**: a field that does not belong to its op is refused by name, never ignored.
- **Ops**: `set_fluid`, `set_conditions`, `add_node`, `add_pipe`, `add_fitting`, `add_resistance`,
  `set` and `remove`.
- **Systems**: `set_fluid` with a `system` name creates a further fluid system, and `add_pipe` or
  `add_resistance` with that name puts an edge in it. A node belongs to the system of its edges, and a
  node joining two systems is refused, because two fluids meet only inside a device. An edge naming a
  system that does not exist is refused on its op. `remove` takes a system with no edges left.
- **Node kinds**:
  - `JUNCTION`, a plain connection.
  - `FIXED_PRESSURE`, a boundary at a stated pressure, such as a main or a pump discharge.
  - `FIXED_DEMAND`, a terminal drawing a stated flow.
  - `OUTLET`, a discharge to a stated pressure.
  - Any node can carry an elevation, which produces the static head between levels.
- **Demands**, each converted to the mass flow a network conserves, with the conversion stated:
  - A mass flow, for any fluid.
  - A volume flow of a liquid, at the design temperature.
  - A normal or standard gas volume, `"450Nm3/h"`, `"120Sm3/h"` or `"80scfm"`, with the real-gas density
    at that unit's own reference state.
  - A plain gas volume with `flowBasis`: `FAD`, free air delivery at ISO 1217 (20 °C, 1 bar absolute,
    dry), for dry air only, or `ACTUAL`, at the node's own solved pressure, which the solve iterates
    until the mass flows settle.
  - A plain gas volume with no basis is refused: 10 m³/min of free air is about eight times the mass of
    10 m³/min at 7 bar.
- **Pipes**: circular, rectangular or elliptic in section, with a length and a size. State a material or
  an absolute roughness. With neither, a commercial-steel roughness is used and reported as an
  assumption.
- **Materials**: PVC, copper, drawn tubing, stainless steel, commercial steel, galvanised steel, cast
  iron, riveted steel and concrete.
- **Fittings**, each with a tabulated loss coefficient that a measured `zeta` can override, and a
  `count`: elbows at 90°, 45°, 30° and 15°, a long-radius 90° bend, tee straight through, tee branch,
  reducer, expansion, entry from a vessel, exit into a vessel, open damper, generic valve and strainer.
- **Resistances**: a lumped component given as a Kv or as a quadratic coefficient K. A Kv is solved as
  `dp = 1 bar × (Q/Kv)² × ρ/1000` with the density of the fluid inside the component, so it holds for a
  glycol or a gas as well as for water. A K is a fixed coefficient that does not follow density. There
  is deliberately no fixed pressure-drop component, because it would impose the same drop at any flow
  and in either direction.
- **Conditions**: a fill pressure for a sealed loop, per system.

### Fluids

Each system carries one of 29 fluids. What a fluid needs beyond its code is required, and what it does
not take is refused by name:

- **Liquids**: water by IAPWS-IF97, ethylene and propylene glycol, and calcium chloride, ethanol,
  methanol and potassium formate brines. A glycol or brine needs a concentration.
- **Air**: dry air by the Lemmon reference equation of state, for compressed air after a dryer and dry
  ventilation air, and humid air of one humidity ratio, which needs a relative humidity or a humidity
  ratio.
- **Fuel and process gases**: natural gas by GERG-2008 with a preset or a composition in mole
  fractions, and nitrogen, oxygen, argon, helium, hydrogen, methane, carbon dioxide, nitrous oxide,
  propane and ammonia by their reference equations of state.
- **Steam**: superheated or dry saturated, by IAPWS-IF97.
- **Refrigerants**: R-32, R-125, R-134a, R-1234yf, R-1234ze(E), R-410A, R-407C and R-454B, as a liquid
  line or a vapour line.

A defaulted concentration, humidity or gas composition would be a wrong friction loss reported as a
real one, so none is assumed.

### Solving

- **Refused before solving** when the answer could not mean anything: nothing anchors the pressure (no
  `FIXED_PRESSURE` or `OUTLET` node and no fill pressure), or nothing drives the flow (no demand and not
  two boundaries at different pressures). Without this check such a network converges to zero flow and
  returns a report that looks real.
- **Refused** when the design fails validation. Numbers are never reported beside the reasons they
  should not be trusted.
- **The verdict**: whether it converged, the iteration count, the status and the termination reason. A
  run that did not converge says so in a warning with its largest residual, and its values are marked
  as the last iterate rather than a solution.
- **The network**: node and edge count, total demand and dissipated power.
- **The worst edges**, ranked by the pressure they lose: mass flow, the pressure drop split into
  friction and local losses, and the static head reported separately, because it is not a loss. The flow sign gives the direction against the edge as it was
  drawn, so on a ring the sign change is the flow divide. A pipe row also carries its velocity.
- **The fastest pipes**, ranked by velocity. For a gas the velocity is the one at the faster end, and
  the Mach number comes with it wherever the fluid model has a speed of sound.
- **The lowest and highest pressure nodes**, as absolute pressures.
- **Gas pipes** are solved with the isothermal compressible pipe law: the density follows the pressure
  along the run, and the pressure spent accelerating the expanding gas is included and reported with
  the local losses.
- **Phase**: every node is checked against the fluid's saturation line. Steam that condenses, a liquid
  that flashes or boils (water, refrigerants, carbon dioxide, ammonia, propane), a blend inside its
  glide, and humid air past its dew point are each reported as a `PHASE` warning and a `phaseProblems`
  row, because those numbers are not a state the system can reach. Glycols and brines have no
  saturation check.
- **Several systems** are reported one entry each under `systems`, with every warning named by its
  system.
- `detail` sets the rows in each ranking: 5 by default, up to 50. A network of up to 50 edges and 50
  nodes can therefore be read in full from one solve.
- **Warnings**, each a complete sentence:
  - Run notices from the engine, such as a substituted fluid property, a value held at a physical
    limit, or a node at or below zero absolute pressure, which withdraws the answer.
  - Validation warnings.
  - A gas pipe above Mach 0.3, where a real gas cools noticeably as it accelerates, and above 0.7,
    near choking.
  - A Kv component on a gas that takes more than 10% of its inlet pressure, where the incompressible
    valve law understates the drop.
  - Every assumption, for example a volume-flow demand converted to mass flow with the density used.
- **Refused as undeliverable**: a gas network whose demands would drive its pressure below what the
  fluid can be evaluated at, with what to change.
- **Not returned**: a critical path.

### Inspecting

- `hydronic_inspect` reads the design back as authored: `design` (the whole document), `nodes`,
  `edges`, one `node` or one `edge` by id, and `readiness`. It never returns solved values.
- `fluids` lists the fluids this server carries, and needs no session.
- `readiness` lists what is still missing and runs the full design validator without solving, with
  its error and warning counts. A half-built design is a normal state.
- Every `hydronic_session` and `hydronic_edit` reply also carries a summary of the design, which
  splits what blocks a solve from what will be assumed.
- Lists return up to 50 rows by default, and up to 500 with `limit`.

### Resources

Nine MCP resources carry the vocabulary, so it costs nothing on a turn that does not need it:

- `hydronic://vocabulary/ops`: every op with its required and optional fields.
- `hydronic://vocabulary/fittings`: every fitting type.
- `hydronic://vocabulary/materials`: every wall material.
- `hydronic://vocabulary/fluids`: the fluid codes, what each needs, how a gas is solved and the phase
  checks.
- `hydronic://vocabulary/devices`: each device type's ports and settings, schedules, controllers, and
  what a transient run returns.
- `hydronic://recipes/riser`: a complete, solvable plant riser.
- `hydronic://recipes/ring-main`: a complete campus ring main, and how to read its result.
- `hydronic://recipes/compressed-air-ring`: a workshop compressed-air ring in free air delivery, with a
  filter as a Kv component.
- `hydronic://recipes/compressor-heat-recovery`: a compressor on a pressure switch charging a receiver,
  its heat pumped into a hot-water store, run for twenty minutes.

### What the plugin adds

- The `hydronic` skill carries the method: working out which question is being asked, what may be
  assumed and what must be asked for, the order to read a solve in, and what each failure means.
- A bundled renderer turns a solve into a self-contained HTML study with a schematic diagram laid out
  by elevation and distance from the supply, node and edge schedules, and a qualifications section
  that is never dropped.

## Limits and access

| | Anonymous | With a free API key |
| --- | --- | --- |
| Water, steam, air, gases, natural gas, glycols, ice | yes | yes |
| Refrigerants and brines | refused, with the reason | yes |
| States per property call | 5 | 20 |
| Pipe and duct sizing, size selection, air processes | yes | yes |
| Hydronic MCP | refused, with the reason | yes |

- Rate limits apply per client IP address: currently 20 requests per second and 1,000 per hour. A
  throttled call comes back as a JSON-RPC error with a retry time, not as an empty result.
- The current limits are published at `https://energyflowx.com/energy-flow-x/api/mcp/limits`.
- **Network solving is free while it is being tested, and that is temporary.** It costs real compute
  and will become a paid feature. The free access can be limited, metered or withdrawn at any time and
  without notice. The tools on the main server are free today and need no key.
- Keys are created in [account settings](https://energyflowx.com/settings). A key is shown once and
  stored only as a hash, so a lost key is revoked and replaced, not recovered.
