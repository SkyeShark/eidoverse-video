# How real terrain is made, and how make_terrain should make it

Research for the new `make_terrain` of the Blender edition (eidoblend). Written 2026-11-08 by the terrain research
agent. Everything about another tool's behaviour or a paper's content carries a link; where I could not check a
number at its source I say so. My own measurements are in section 8 (numpy prototypes in `proto/`, metrics code in
`tools/terrain_metrics.py`). Real elevation data of the landforms is the reference agent's job
(`terrain/reference/landform_refs.py`); I did not duplicate it. The survey to read first is
[Galin et al. 2019](https://diglib.eg.org/handle/10.1111/cgf13657), the state-of-the-art report on terrain
generation (procedural, simulation and example-based).

---

## 0. The short version

**Why Ekigar's landforms never looked like their names.** Every Ekigar landform is a per-pixel function: fBm and
ridged noise, radial stamps (crater, caldera, volcano, cones), slot shapes (canyon, glacial trough), and Phacelle,
an analytic erosion *filter*. None of them knows where water, ice or sand goes, and every real landform is made by
a process that does: a river's depth depends on everything upstream of it. The author of the Phacelle filter says it
himself: its gullies "cannot consistently produce unbroken lines", and a gully "just stops halfway down a
mountainside rather than following through all the way down to the lowest reachable point"
([Johansen 2026](https://blog.runevision.com/2026/03/fast-and-gorgeous-erosion-filter.html)). The Ekigar plan made
that choice deliberately ("Everything else that Gaea does iteratively can go analytic", TERRAIN_GENERATOR_PLAN.md
§4-5), so the breakage is structural, not a bug list. In the hero renders I see the consequences directly: the
mountain range is uniformly jagged everywhere with no valley hierarchy; the volcano is a lump with the same
high-frequency bumps on every flank and no radial drainage; caldera, impact crater and cinder cones are clean
lathe-turned toys (a flat ring, a dome, concentric steps); the glacial trough is a flat slot with vertical walls; the
barchans are pyramids and the star dunes are soft blobs.

**What Gaea / World Machine / Houdini actually do** (section 2): a primitive or painted shape is only the start;
the look comes from *simulation passes run on it* (hydraulic erosion with sediment, thermal talus, deposition, snow,
water), each with a feature-scale knob so the result survives a resolution change, and from the masks those
simulations leave behind (flow, wear, deposits, talus), which drive the texturing.

**What I recommend** (sections 3-6):

1. **Backbone: tectonic uplift + stream-power river incision + hillslope creep/threshold**, run on a coarse grid
   (256-512 cells across) until near steady state, then upsampled x2 and re-eroded with a smaller feature size, twice
   (Cordonnier et al. 2016; Schott et al. 2023, 2024). It is the cheapest model that makes connected, branching,
   concave-up drainage with ridges in the right places. In numpy it is local array shifts; on the GPU every step is
   one fragment pass per field (no compute shader needed), exactly how Schott et al.'s public shaders are written.
   My numpy runs (section 8) pass the generic realism tests that noise and Ekigar fail, and show its traps: start
   from a rough primitive, not a flat plane; cap slopes with creep flux, not a min-plus clip; fight grid-direction
   bias with multiple-flow-direction area, erodibility noise and coarse-to-fine refinement.
2. **Then the family-specific process** on top of (or instead of) the backbone: glacial U-carving along the fluvial
   network for alpine valleys, a Werner slab cellular automaton for dunes, layer-dependent erodibility and cliff angle
   for canyons/mesas/badlands, constructional profiles + flank erosion + lava flows for volcanoes, profile laws for
   impact craters, a Dean profile + cliff retreat for coasts, a cone/tower field + closed depressions for karst.
3. **Then talus and deposition** (thermal at the repose angle; sediment filling valley floors, fans and lakes),
   because flats and aprons are half of what reads as "real" at eye level.
4. **Only then detail**: an analytic erosion filter (the existing Phacelle port is fine here), rock breakup and
   strata, masked by the simulation's wear and slope; and centimetre detail in the materials, not the heightfield.
5. **Surface from the simulation's own masks** (drainage area, wear, deposit, talus, slope, curvature, height,
   aspect, strata), with height-blended, triplanar, world-space-strata materials.

**How to judge** (section 1.2): closed depressions ~0 % of the area for fluvial terrain (fBm noise is full of them);
slope distribution with a threshold peak at 30-40 degrees plus flats, not a bell curve; concave-up river profiles;
valleys with a characteristic spacing; family numbers like crater depth/diameter 0.2 or cinder cone height/width
0.18. `tools/terrain_metrics.py` computes the generic ones for any heightfield in metres.

---

## 1. What makes a landform read as real

### 1.1 The signatures

- **Every drop of water has a way out.** Fluvial landscapes are a tree of valleys that connect downhill to an outlet;
  closed depressions exist only where a process makes them (karst dolines, interdune hollows, glacial overdeepenings
  and lakes, craters, calderas, kettles) and they hold lakes or flat sediment. Noise terrain is pitted with closed
  basins everywhere; that is the single biggest "fake" cue in an aerial.
- **Hierarchy with a characteristic spacing.** Valleys branch into smaller valleys down to a smallest valley whose
  spacing is set by the competition of river incision and hillslope creep; Perron, Kirchner & Dietrich showed the
  spacing is predictable from that balance and measured 30-300 m at five US sites
  ([Perron et al. 2009](https://dspace.mit.edu/handle/1721.1/64681)). Below that scale hillslopes are smooth;
  real topography is *not* fractal across scales and its spectrum shows the characteristic scale
  ([Perron et al. 2008](https://doi.org/10.1029/2007JF000866)). fBm has no characteristic scale, which is why it
  reads as a lumpy blanket at every distance.
- **Concave-up river profiles.** Channel slope falls with drainage area, S ~ A^-theta, theta = m/n; Whipple & Tucker
  give 0.35-0.6 for bedrock rivers (as cited by later work;
  [Whipple & Tucker 1999](https://doi.org/10.1029/1999JB900120)). Main-stream length grows as about A^0.6
  ([Hack 1957](https://pubs.usgs.gov/publication/pp294B)). Valleys flatten and widen downstream; ridges stay sharp
  or rounded but never "fill up".
- **Hillslopes saturate at a threshold angle.** In fast-eroding ranges hillslope angle stops depending on erosion
  rate because landslides cap it ([Burbank et al. 1996](https://doi.org/10.1038/379505a0);
  [Montgomery & Brandon 2002](https://repository.geologyscience.ru/handle/123456789/28097), later cited as
  ~35-40 degree mean slopes). Talus rests at about 30-40 degrees
  ([World Machine Thermal Erosion docs](https://help.world-machine.com/topic/device-thermalerosion/)); dry sand
  avalanches at about 31-34 degrees (the Desertscapes code uses tan = 0.60, section 3.6). So real slope histograms
  have a pile-up just under the threshold, a tail of cliffs only where rock is strong, and a lot of near-flat ground.
- **Flats where material settles.** Valley floors, floodplains, alluvial fans, lake flats, interdune corridors,
  talus aprons, outwash plains. Flats beside steep walls (a bimodal slope distribution) is what canyon, glacial and
  karst landscapes look like; noise never makes it.
- **Structure.** Strata, faults, joints and dip make cliffs, ledges and asymmetric ridges (cuestas, hogbacks); rock
  strength contrasts control mesa/butte/cliff form ([Forte et al. 2016](https://doi.org/10.1002/esp.3947);
  [Glade et al. 2017](https://doi.org/10.1130/G38665.1)).
- **Global shape.** Peaks, saddles and ridges have characteristic prominence/isolation distributions; generators that
  are locally plausible often fail this ([Argudo et al. 2019](https://people.cs.uct.ac.za/~jgain/wp-content/papercite-data/pdf/argudo2019.pdf)).

### 1.2 Measurable tests (use them on every candidate)

| test | real fluvial terrain | what noise / stamps give | where |
|---|---|---|---|
| area in closed depressions deeper than max(1 m, 0.2 % of relief) | ~0 (karst, dunes, craters, glacial lakes are the exceptions) | large | `terrain_metrics.depressions` |
| slope percentiles, fraction > 30 / 40 / 50 degrees, fraction < 5 degrees | threshold pile-up 30-40, flats present | broad bell, few flats | `terrain_metrics.metrics` |
| hypsometric integral | depends on stage and family | arbitrary | same |
| river long profile S vs A | power law, theta 0.35-0.6 | no network | drainage area from the generator |
| valley spacing | one dominant spacing per range | none | spectrum or cross-section count |
| family numbers | e.g. crater d/D 0.2; cinder cone H/W 0.18; U-valley exponent ~2 | arbitrary | sections 3.5-3.12 |

And always look at a hillshade from the north-west at 40 degrees before any lit render: hillshades show drainage,
facets and grid artifacts that a pretty render hides.

---

## 2. What the professional tools actually do (checked against their docs)

**World Machine.** The (legacy) Erosion device simulates erosion for a duration with *rock hardness* and *sediment
carry amount*, a filter type (none; simple, for soil-covered hillslopes; inverse, for ice-carved terrain), a
*geological-time enhancement* with an *uplift* parameter, optional channeled erosion, and outputs **flow, wear and
deposition masks** ("very useful to help drive texturing"); it warns that erosion is slow and differs between tiled
and single builds ([WM Erosion](https://help.world-machine.com/topic/device-erosion/)). Build 4044/4046 re-
parameterized it (Bedrock Strength, Water Power, Soil Scour), added a soil model "such as soil-mantled hills", a
largest-feature-size control, map control of every parameter, and reports >50x speed at high resolution
([4044](https://help.world-machine.com/topic/build-4044-hurricane-ridge/),
[4046](https://help.world-machine.com/topic/build-4046-hurricane-ridge-final/)). Thermal Erosion "simulat[es] the
fracturing of rock due to thermal stresses", piles talus at a repose angle ("real-world talus is typically around
30 to 40 degrees"), and outputs talus mask and talus depth
([WM Thermal](https://help.world-machine.com/topic/device-thermalerosion/)).

**Gaea 2.** Terrain primitives (Mountain, MountainRange, MountainSide, Canyon, Ridge, Rugged, Uplift, DuneSea, Slump,
Crater, CraterField, Island, Plates, Volcano) anchor a graph; Simulate nodes reshape them (Erosion, Erosion2,
EasyErosion, Wizard, Thermal, Thermal2, Debris, Scree, Sediments, Lake, Rivers, Sea, HydroFix, Snow, Snowfield,
Glacier, IceFloe, Trees, Shrubs); Derive nodes make the data maps (Height, Slope, Angle, Curvature, FlowMap,
Occlusion, RockMap, Soil, TextureBase, Texturizer) ([Gaea reference](https://docs.gaea.app/reference/)). Erosion2
exposes Duration, Downcutting, Erosion Scale, three sediment classes (Suspended Load, Bed Load, Coarse Sediments)
each with a Discharge Angle, shape sharpness/detail scale and orographic rain
([Erosion2](https://docs.gaea.app/reference/nodes/simulate/erosion2.html)); Thermal exposes Talus Angle, Settling,
Sediment Removal, Feature Scale and Real Scale ([Thermal](https://docs.gaea.app/reference/nodes/simulate/thermal.html)).
The Volcano node is "a self-contained cone or caldera that you can later erode"
([Volcano](https://docs.gaea.app/reference/nodes/terrain/volcano.html)): the primitive is not the landform.

**Houdini.** HeightField Erode simulates hydraulic and thermal erosion at an **Erosion Feature Size** (metres), with
Flow Force, Bank Angle, Rainfall Coverage, Erosion/Deposition/Removal/Evaporation rates, and thermal Weathering
Force, Cut Angle and Repose Angle; it writes debris, sediment, flow and flow-direction layers; it "will produce very
similar features if the resolution of the input terrain is changed", and finer detail comes from chaining a second
Erode with a smaller feature size ([HeightField Erode](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode.html)).
HeightField Erode Hydro adds strata-dependent erodability
([Erode Hydro](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode_hydro.html)).

**Unreal Engine.** Landscape sculpting has an Erosion tool (thermal: soil moves from higher to lower ground) and a
Hydro Erosion tool (rain amount, sediment cap, iterations)
([quick start](https://dev.epicgames.com/documentation/unreal-engine/landscape-quick-start-guide-in-unreal-engine),
[Hydro Erosion 4.27](https://docs.unrealengine.com/4.27/en-US/BuildingWorlds/Landscape/Editing/SculptMode/HydroErosion)),
plus non-destructive Blueprint brushes (Landmass) on edit layers
([Blueprint brushes](https://dev.epicgames.com/documentation/unreal-engine/landscape-blueprint-brushes-in-unreal-engine)).
These are touch-up tools; the landform itself is normally authored in WM/Gaea/Houdini or taken from real data, and
Unreal's strength is surfacing (material layers, virtual texturing, procedural placement).

**Studios.** Ghost Recon Wildlands built its terrain toolchain around Houdini and assigned terrain materials
procedurally from slope, height, flow and curvature
([GDC 2017](https://gdcvault.com/play/1024029/),
[80.lv](https://80.lv/articles/landscape-and-material-pipeline-of-ghost-recon-wildlands/)). Far Cry 5 generated
biomes, terrain texturing, freshwater networks and cliff rocks procedurally
([GDC 2018](https://gdcvault.com/play/1025557/Procedural-World-Generation-of-Far),
[SideFX talk](https://www.sidefx.com/learn/talks/procedural-world-generation-far-cry-5/)). Frostbite's terrain
shaders splat materials per pixel from height, slope and normal plus painted masks
([Andersson 2007](https://www.advances.realtimerendering.com/s2007/Andersson-TerrainRendering(Siggraph07)-CourseNotes.pdf)).
CD Projekt RED's Witcher 3 talk describes automating terrain and vegetation and moving away from conventional
material layers and linear blends ([Gollent 2014](https://www.gdcvault.com/play/1020394/Landscape-Creation-and-Rendering-in)).
For film, Pixar's *The Good Dinosaur* built its landscapes on USGS elevation data of Wyoming and added rocks and
vegetation on top (press coverage, e.g. [Planetizen](https://planetizen.com/node/82561)): real data is a legitimate
base, and the reference agent's DEMs could be used that way for hero locations.

**The common pattern:** primitive or painted macro shape → hydraulic erosion at a large feature scale → thermal/talus
→ finer erosion at a smaller feature scale → deposition/water/snow → masks drive materials. Feature size in metres,
not iterations per pixel, is what makes the result resolution-independent.

---

## 3. The process toolbox

Each entry: the physics, the discrete method I recommend for numpy (Blender's bundled numpy, no scipy), the GPU
fragment-pass form where it exists, key parameters, failure modes.

### 3.1 Stream-power river incision with tectonic uplift (the backbone)

**Physics.** dh/dt = U(x) - K A^m S^n + (hillslope term). U is rock uplift (or base-level fall), A drainage area,
S channel slope. At steady state S = (U / K)^(1/n) A^(-m/n): the river profile is concave-up with theta = m/n.
Cordonnier et al. made this the core of a terrain generator: the user paints the uplift map, the stream-power law
erodes it into ridges, watersheds and a river network
([Cordonnier et al. 2016](https://hal.archives-ouvertes.fr/hal-01262376)). Schott et al. made it interactive on the
GPU with copy/paste, warping and elevation constraints in the uplift domain, and can invert an existing DEM back to
uplift ([Schott et al. 2023](https://hal.science/hal-04049125), code:
[StreamPowerErosion](https://github.com/H-Schott/StreamPowerErosion), MIT). Tzathas et al. use the law's analytic
solutions so that "time becomes a parameter" (a slider from subtle erosion to full replacement of the input),
with multigrid acceleration and added landslide/hillslope processes
([Tzathas et al. 2024](https://diglib.eg.org/handle/10.1111/cgf15033)).

**Three ways to solve it, same physics:**

- **(a) Local gather, explicit (Schott et al. 2023 shader).** I read `data/shaders/spe_shader.glsl`: per step each
  cell sets its stream area to its own cell area plus what each of the 8 neighbours sends it (multiple-flow-direction
  weights proportional to slope^p_flow), computes the stream-power term with the *steepest* downhill slope,
  subtracts dt x (stream power - k_h x Laplacian [- k_d x slope]), clamps the result to be no lower than its steepest
  receiver, then adds dt x uplift; borders are base level. One Jacobi iteration of the flow accumulation per step:
  area lags the terrain, which is fine because the terrain changes slowly. Defaults in that shader: k = 0.0005,
  p_sa = 0.8 (m), p_sl = 2 (n), p_flow = 1, dt = 50, in its own units. **Every read is a 3x3 neighbourhood, so it
  is a fragment shader with two ping-pong float targets (height, area)**, and in numpy it is 8 array shifts.
  Needs no lake handling: a pit collects area, does not erode, and rises with uplift until it spills.
- **(b) Implicit O(n) on the receiver tree (Braun & Willett 2013, FastScape).**
  h_i <- (h_i + U dt + F_i h_receiver) / (1 + F_i), F_i = K A_i^m dt / L_i for n = 1, solved from the outlets up;
  unconditionally stable for n = 1, so dt can be 10-50 kyr ([Braun & Willett 2013](https://doi.org/10.1016/j.geomorph.2012.10.008)).
  Needs exact single-direction drainage area and a topological order. I vectorised both in numpy by tree depth
  (pointer jumping gives each cell its hop count to the outlet; then each depth level is one numpy op) - see
  `proto/spl_implicit.py`. Single steepest-descent receivers draw straight valleys along the 8 grid directions at
  coarse resolution (section 8). Closed basins need a lake algorithm
  ([Cordonnier, Bovy & Braun 2019](https://esurf.copernicus.org/articles/7/549/2019/), linear-time) or a
  priority-flood fill ([Barnes et al. 2014](https://arxiv.org/abs/1511.04463)); a pure-Python priority queue will
  cost seconds per call at 512^2 (my estimate, not measured), so use it rarely.
- **(c) Steady state directly ("chi" integral).** At steady state h_i = h_receiver + (U_i / (K A_i^m))^(1/n) L_i:
  elevation is a path integral up the drainage tree. Iterating receivers -> area -> integral should converge to a
  mature range in a handful of passes with no time stepping (I did not prototype it). Tzathas et al. build their
  method on the law's analytic solutions, of which this steady state is the simplest. Same tree-ordering cost as
  (b), same D8 straight-valley caveat.

**My recommendation:** (a) for the GPU path and as the default numpy path (one algorithm, two backends, no global
passes); (b) when exact drainage area matters (rivers placed by area threshold) or to jump far in geological time;
use MFD area to avoid straight valleys. A different route builds the river network first and the terrain around it
([Génevaux et al. 2013](https://hal.archives-ouvertes.fr/hal-01339224)); it gives direct control of rivers, but the
terrain between them is procedural, so I prefer the simulation and steer it through the uplift map.

**Key parameters.**
- m/n: 0.4-0.5 (theta). n = 1 is the geomorphology default; Schott's shaders use n = 2, m = 0.8 (theta 0.4).
- K and U set relief: steady-state channel relief scales as (U/K)^(1/n); pick U/K for the target relief, not
  "iterations".
- **Hillslope diffusivity D relative to K sets the smallest valley spacing**: the incision/creep length is
  sqrt(D/K) for m = 0.5 (from Perron et al. 2009's Peclet balance). Measured in section 8 at 78 m cells:
  D/K = 2,000-5,000 m^2 (sqrt(D/K) 45-70 m, about one cell) gave valleys every 4-6 cells and a natural branching
  texture; D/K = 125,000 m^2 (350 m) went soft with few valleys. When you upsample, shrink sqrt(D/K) with the
  cell size, so each finer level adds a finer order of valleys instead of smoothing them away.
- **The starting surface decides the network as much as D/K does** (section 8): from a near-flat start the
  drainage organises as parallel gullies and big planar facets for millions of years; from a rough dome shaped like
  the uplift (eroding a primitive, the WM/Gaea way) a branching range forms within ~2 Myr at the same D/K.
- Threshold slope Sc = tan(30-40 degrees), varied with low-frequency noise (Schott et al. 2024's thermal shader
  defaults to tan = 0.57 and, with noise on, draws the tangent from 0.9-1.4 for rock).
- Uplift map: the art-directable input. Multi-scale texture in it (and in the initial surface) breaks the parallel
  gullies a smooth ramp produces.
- Base level: the map edges (sea) or chosen outlets. For tiles, give the tile edges the neighbour's heights or use a
  periodic domain; otherwise every tile drains radially to its own edge.

**Failure modes** (all seen in section 8 unless marked). Corduroy / zebra stripes: parallel gullies at a few cells'
spacing from a smooth start that has not organised (flat start, far from steady state); mush (D/K too large);
straight valleys on the 8 grid directions (single flow direction, smooth initial surface, too coarse a grid);
parallel gullies on any uniform ramp, e.g. where the uplift fades out toward the sea (put texture in the initial
surface and the uplift); hillslopes faceted along 8 directions if slopes are capped by a min-plus "lowest
neighbour + Sc x distance" clip (that is a chamfer distance; use flux-based creep instead); relief still rising
(not at steady state, valley spacing keeps coarsening); uplift-map creases printed as straight divides; every
slope at threshold and no flats (by reasoning: add deposition); uniform uplift giving one repetitive "range" with no
peaks (not run); closed basins left as unfilled pits in schemes (b)/(c) (not run at scale).

### 3.2 Hillslopes: creep, threshold, talus

- **Nonlinear creep** (Roering et al. 1999): flux q = D S / (1 - (S/Sc)^2), linear at low slope, blowing up near
  Sc; gives convex hilltops and planar slopes near threshold
  ([Roering et al. 1999](https://doi.org/10.1029/1998WR900090)). Explicit on the 4 cell faces is isotropic enough;
  stability needs dt < dx^2 / (4 D_eff) with D_eff = D x cap (cap the blow-up factor, I used 5-50), so sub-step.
- **Threshold landsliding** (Burbank et al. 1996): slopes cannot exceed Sc; debris is carried off by the rivers.
  Cheapest form: the min-plus clip above, but it facets (section 8). Schott's thermal shader instead adds/removes a
  small fixed amount per neighbour pair that exceeds tan(angle), with the angle noise-modulated
  ([MultiScaleErosion thermal.glsl](https://github.com/H-Schott/MultiScaleErosion)); Cordonnier et al. 2023 add a
  debris-flow term dz/dt = -k_df (1 + k_da A^q) max(0, |grad z| - s_c)^q' that erodes cliffs harder where drainage
  concentrates ([Cordonnier et al. 2023](https://www.cs.purdue.edu/homes/bbenes/papers/Cordonnier23ToG.pdf)).
- **Thermal weathering / talus** (Musgrave, Kolb & Mace 1989, the origin of CG thermal erosion,
  [SIGGRAPH 89](https://researchr.org/publication/MusgraveKM89)): material above the repose angle moves to lower
  neighbours in proportion to the excess; mass-conserving, so it builds aprons. Jako's GPU version uses 8 "virtual
  pipes" and a hardness-dependent talus tangent R x Ka + Ki (typical Ka 0.8, Ki 0.1, rate Kt 0.15)
  ([Jako 2011](https://www.old.cescg.org/CESCG-2011/papers/TUBudapest-Jako-Balazs.pdf)). Repose 30-40 degrees for
  rock talus (WM); keep cliffs (strong rock) out of it with a hardness mask, as WM's talus production mask does.
- Failure modes: talus burying every ridge (WM notes talus can "completely bury vulnerable ridgelines"); terraces
  from large thermal steps; perfectly planar talus without boulder texture (add it in materials/scatter).

### 3.3 Hydraulic erosion with sediment (the detail-scale water pass)

- **Grid shallow water with virtual pipes** (Mei, Decaudin & Hu 2007,
  [HAL](https://inria.hal.science/inria-00402079); Stava et al. 2008,
  [PDF](https://www.cs.purdue.edu/homes/bbenes/papers/Stava08SCA.pdf); Jako 2011): water flux through pipes to the
  4 (or 8) neighbours, velocity from flux, capacity C = Kc sin(alpha) |v| (Jako multiplies by a depth ramp so deep
  water deposits), erode Ks (C - s) when under capacity, deposit Kd (s - C) when over, advect sediment
  semi-Lagrangian, evaporate Ke. Jako's typical values: dt 0.02, Kr (rain) 0.012, Ks 0.5, Kd 1, Ke 0.015, Kc 1,
  pipe area 20, g 9.81. All local, so all fragment passes. Good for rain gullies, river beds, sediment fans and
  sea/lake floors; it does not build a mountain range's valley network in any affordable number of steps.
- **Particles / droplets** (Beyer 2015, [thesis](https://ardordeosis.github.io/implementation-of-a-method-for-hydraulic-erosion/thesis-beyer.pdf);
  defaults in [erodr](https://github.com/henrikglass/erodr): 70 000 particles, lifetime 32, erosion radius 2,
  inertia 0.3, capacity 8, evaporation 0.02, erosion 0.7, deposition 0.3, min slope 0.0001). Sequential per
  droplet, so slow in numpy and awkward on a fragment GPU. Produces fine rills and soft deposits; does not create
  large-scale drainage; pits and "worm tracks" appear if the erosion radius is too small; strongly
  resolution-dependent.
- **Use:** after the stream-power backbone, at the finest heightfield level, as the water-detail and deposition pass.

### 3.4 Deposition: floors, fans, lakes

- **Lakes:** fill depressions to their spill level (priority-flood, Barnes et al. 2014) and keep the flat water
  surface as a lake mask; that is also how a "valley fill" is made flat.
- **Sediment routing:** Schott et al. 2024's deposition shader passes sediment down the same MFD weights as water
  and deposits where sediment exceeds a stream-power capacity
  ([MultiScaleErosion deposition.glsl](https://github.com/H-Schott/MultiScaleErosion)); their README recommends the
  sequence "erosion -> thermal -> deposition" alternated with x2 upsampling.
- **Fans:** where a channel leaves a mountain front its slope drops, capacity drops, and sediment spreads into a cone
  with distributary channels; a capacity-based deposition pass gives this for free at the mountain front.
- Failure mode: over-deposition melts everything into putty; keep deposition to valley floors and fronts (mask by
  low slope and high area).

### 3.5 Glacial erosion

- **Physics.** Ice flux: dh/dt + div(u h) = M with mass balance M = min(p_max, beta (s - E)) around the
  equilibrium-line altitude E (snowline). Abrasion dz/dt = -k_e |u_s|^l (sliding speed u_s), quarrying focused on
  slopes facing the flow ([Cordonnier et al. 2023](https://www.cs.purdue.edu/homes/bbenes/papers/Cordonnier23ToG.pdf),
  following Herman et al. 2015 and Egholm et al. 2012). Harbor's cross-section model made U-shapes with erosion
  quadratic in sliding speed ([Harbor 1992](https://doi.org/10.1130/0016-7606(1992)104<1364:NMOTDO>2.3.CO;2), as
  described by later work). Erosion proportional to ice discharge per width gives the long profile: steep
  headwaters, an overdeepening around the ELA, and a step where headwater tributaries join
  ([Anderson, Molnar & Kessler 2006](https://doi.org/10.1029/2005JF000344)). Cross-sections fit y = a x^b with b
  near 2 as glacial erosion matures ([Svensson 1959](https://www.cambridge.org/core/journals/journal-of-glaciology/article/is-the-crosssection-of-a-glacial-valley-a-parabola/EE16DB83DA62DE75D671DE955242CD43);
  Graf 1970). Peak heights track the snowline (the "glacial buzzsaw",
  [Egholm et al. 2009](https://doi.org/10.1038/nature08263)).
- **The trap:** coupling the cheap Shallow Ice Approximation to erosion does *not* make U-valleys. Cordonnier et al.
  2023 show SIA erosion "carves deep narrow defiles that ultimately lead to numerical instability" because SIA lacks
  viscous stresses; their fix is a learned emulator of a higher-order ice model, and it still takes ~2000 steps:
  3.7 min at 512^2, 9.8 min at 1024^2, 37.5 min at 2048^2 on a 24 GB NVIDIA RTX GPU, with CPU drainage and
  transfers about half of that. Not a numpy path.
- **Simplest convincing method (procedural, process-guided):**
  1. Make the pre-glacial fluvial range with the backbone.
  2. Glacier extent: accumulate a mass balance down the fluvial network: Q_ice = sum upstream of
     max(0, beta (h - ELA)) x cell area, minus ablation below the ELA, until it reaches zero (the terminus).
  3. Carve: for each glaciated channel cell, a trough half-width W ~ c Q_ice^0.3-0.5 and depth ~ c' Q_ice^alpha
     (my heuristic exponents, to be tuned against real troughs, not from a paper); every cell's distance to its
     nearest glaciated centreline cell comes from a **jump-flood** pass (log2 N neighbour passes, numpy or fragment
     shader; Rong & Tan 2006, "Jump flooding in GPU with applications to Voronoi diagram and distance transform",
     I3D); new height = min(old, floor + depth x (d/W)^2 for d < W) (b = 2). Trunks carve deeper than
     tributaries, so tributary floors are left **hanging**.
  4. Cirques: bowls at the heads of glaciated valleys above the ELA; where cirques and trough walls meet, the
     leftover ridges are arêtes, and three or more cirques leave a horn.
  5. Talus at the foot of the new walls (thermal), lakes in overdeepenings (fill), flat outwash/valley fill
     downstream, moraine ridges along the terminus and lateral margins (deposit along the glacier outline).
  6. Optionally cap summits a fixed height above the ELA (buzzsaw).
- **Failure modes:** flat-floored slots with vertical walls (Ekigar's trough); every valley the same width;
  tributaries graded to the trunk (no hanging valleys); troughs that ignore the existing drainage; sharp creases
  where two nearest-centreline regions meet (use a smooth minimum); no talus, no lakes, no moraines.

### 3.6 Wind: dunes

- **Model.** Werner's slab cellular automaton: pick a random cell with sand, lift a slab, move it a fixed distance
  downwind, deposit with a probability that is higher on sand than on bare ground, never erode inside a wind shadow,
  avalanche anything steeper than the repose angle. It reproduces barchan, transverse, longitudinal and star dunes
  ([Werner 1995](https://planetarygeoscience.uchicago.edu/doc/Werner_1995.pdf)). Paris et al.'s Desertscapes code
  (I read `desert-simulation.cpp` and `desert.h`) uses: deposition probability 0.6 on sand / 0.4 on bare rock,
  up to 3 bounces with reptation, wind shadow ramping between 5 and 15 degrees over 10 m upwind, sand avalanching
  at tan = 0.60, bedrock at tan = 2.5 (68 degrees), wind speed up to x2 on slopes facing the wind
  ([Paris et al. 2019](https://perso.liris.cnrs.fr/aparis/public_html/projects/paris2019_Deserts.html),
  [code](https://github.com/aparis69/Desertscapes-Simulation)).
- **Which dune you get is the wind regime and the sand supply,** not a shape parameter: bedforms align to maximise
  gross bedform-normal transport ([Rubin & Hunter 1987](https://pubs.usgs.gov/publication/70014126)); with the same
  bidirectional wind, abundant sand grows dunes across the mean flux and scarce sand elongates fingers along it
  ([Courrech du Pont et al. 2014](https://www.ipgp.fr/~narteau/papers/P37.pdf)); star dunes are combined
  longitudinal arms under multidirectional winds ([Zhang et al. 2012](https://www.nature.com/articles/ngeo1503)).
  The classic summary those papers refine: one wind + little sand = barchans; one wind + much sand = transverse
  ridges; two winds more than 90 degrees apart = linear dunes; three or more = star dunes.
- **numpy:** vectorise in batches (move a random 1-5 % of sand cells at once, deposit with `np.add.at`, accept the
  rare collision), periodic boundaries, avalanche pass every few batches. Use sub-cell, rotated hop vectors or the
  crests lock to the grid axes. The GPU fragment form is awkward (scatter); keep it on the CPU at 512^2 and amplify.
- **Failure modes:** symmetric cross-sections without the shadow rule (Werner's original weakness); crests aligned
  to the grid; dune "blobs" from noise; no slip faces; no interdune flats or exposed bedrock; all dunes one size
  (real fields have dunes on dunes).

### 3.7 Volcanoes

- **Shape.** Regular stratovolcanoes: the lower half of the radial profile fits a logarithmic curve; the upper half
  is either near-straight ("C-type") or concave ("P-type")
  ([Karátson et al. 2010](https://ui.adsabs.harvard.edu/abs/2010JVGR..193..171K)). Arc volcanoes grow as cones to a
  size limit, then widen into massifs ([Grosse et al. 2009](https://ri.conicet.gov.ar/handle/11336/55921)). Cinder
  cones: height/basal width about 0.18 and crater/basal width about 0.40 when fresh, lower with age
  ([Wood 1980](https://doi.org/10.1016/0377-0273(80)90040-2), formalising Porter 1972; I could not open the full text
  to re-check the two ratios).
- **Simplest convincing method:** a constructional profile (log lower flank, linear/concave upper flank, crater) as
  the *initial surface* and a small *uplift-like growth term* near the vent, then the backbone's erosion for a
  chosen age, which cuts radial valleys that deepen downslope and leave planèze ribs between them; a debris/lahar
  apron by deposition at the foot; lava flows as thickness deposits along stochastic steepest-descent paths (the
  DOWNFLOW idea: many steepest paths over randomly perturbed topography,
  [Favalli et al. 2005](https://doi.org/10.1029/2004GL021718)), with lobate fronts and levees; a breach (sector
  collapse) as a horseshoe cut; parasitic cones as cinder-cone profiles.
- **Calderas:** a collapse inside a ring fault: steep walls, a flat floor (lake or sediment fill; optionally a
  resurgent dome), talus aprons at the wall foot, outer flanks of the old edifice eroded radially.
- **Failure modes:** perfect radial symmetry; same-depth gullies all around; uniform high-frequency bumps on the
  flanks (Ekigar's volcano); crater as a smooth donut; no apron; no lava flows; mean flank too steep (cinder cones
  sit near the scoria repose angle; strato flanks steepen only near the summit).

### 3.8 Layered rock: canyons, mesas, buttes, cuestas, hogbacks

- **Physics.** Erodibility and cliff angle change with the rock layer. In layered rocks, steady state means equal
  *horizontal* retreat of layer contacts, which produces bigger slope contrasts than simple steady state
  ([Perne et al. 2017](https://esurf.copernicus.org/articles/5/85/2017/)); strength contrasts give long transients
  ([Forte et al. 2016](https://doi.org/10.1002/esp.3947)); blocks shed from resistant layers armour the slopes below
  ([Glade et al. 2017](https://doi.org/10.1130/G38665.1)).
- **Simplest convincing method:** a stratigraphic column in world-space z (layer thickness, strength), optionally
  tilted and warped (dip, folds, faults). Run the backbone with **K(z)** and **Sc(z)** read from the column at each
  cell's current height (strong: low K, cliff angle 60-80 degrees; weak: high K, slope 25-35 degrees), and a talus
  pass whose debris rests on the weak layers below each cliff. Base-level fall (or uplift) drives incision from the
  outlet, so canyons grow headward with tributaries. Mesas and buttes appear where a cap rock is cut through and the
  weak layer below retreats; spires are the last stage. For folded strata showing on eroded cliffs, see Cordonnier
  et al.'s subsurface-geology model ([Cordonnier et al. 2018](https://hal.archives-ouvertes.fr/hal-01517343)).
- Gaea's Terrace/Stratify and WM's Terrace remap height and look like strata from a distance; real strata are
  geological (they exist in the rock whether or not a slope exposes them), so do them in the erodibility, and put
  the colour bands in world space in the material.
- **Failure modes:** terraces on every slope regardless of rock; bands perfectly level across the map (no dip);
  canyons without tributaries or of uniform width; no talus aprons; stair-step aliasing (the cliff band thinner than
  2-3 cells).

### 3.9 Badlands

- Dense, fine dissection of soft mudstone/shale: sharp ridges, V-gullies, rills, very high drainage density, often a
  resistant cap and colour bands. Howard modelled Mancos Shale badlands with a combined diffusive + advective
  drainage-basin model ([Howard 1997](https://core.ac.uk/download/209821525.pdf)).
- **Method:** the backbone at fine spacing (1-5 m cells) with high K, small D (sqrt(D/K) about one cell, as
  measured for mountains in section 8), base-level fall instead of uplift, a few resistant layers in K(z); colour
  bands in world space.
- **Failure modes:** noise bumps (Ekigar's badlands); grid-scale corduroy; rounded "soft" ridges from too much D.

### 3.10 Karst towers

- **Real:** fenglin = isolated towers on a flat alluvial plain; fengcong = clusters of cones on a common base with
  closed depressions between; Waltham argues these Chinese terms are the useful genetic categories and that fenglin
  may evolve from fengcong ([Waltham 2008](https://www.bcra.org.uk/cks105)).
- **Method:** blue-noise (Poisson-disc) tower centres with clustering; per-tower height and footprint; a steep-walled
  profile (near-vertical walls, rounded irregular summits, an undercut notch at plain level) via the jump-flood
  distance to the nearest centre; for fengcong, raise a common base and leave star-shaped closed depressions between
  cones (the one family where closed depressions are correct); a flat plain (flood fill) with a river for fenglin.
- **Failure modes:** smooth noise cones; regular spacing; all towers one height; walls under 60 degrees; no plain.

### 3.11 Impact craters

- **Numbers (Pike 1977 lunar fits, as quoted by [Holsapple 2022](https://arxiv.org/abs/2203.07476); Pike at
  [NTRS](https://ntrs.nasa.gov/citations/19780060140)):** simple craters depth d = 0.2 D and rim height h = 0.036 D;
  complex craters (from D = 10.6 km on the Moon; the transition diameters scale with the inverse of gravity, so a
  few km on Earth) d = 1.044 D^0.301 km, rim h = 0.236 D^0.399 km, flat floor D_f = 0.187 D^1.249 km above 20 km.
  Ejecta thickness falls off about as (r/R)^-3 ([McGetchin et al. 1973](https://doi.org/10.1016/0012-821X(73)90162-3),
  exponent as quoted by later work).
- **Method:** a radial profile (parabolic bowl, rim, r^-3 ejecta) with azimuthal irregularity (polygonal rims from
  joints, uneven rim height, ray/hummock noise in the ejecta); for complex craters a flat floor, slumped terraces
  that are irregular arcs (not concentric rings), and a rough central peak; then age it with diffusion + backbone
  erosion (gullied walls, infilled floor).
- **Failure modes:** a flat ring "donut" with a dome (Ekigar); no ejecta; perfect circles; wrong depth/diameter.

### 3.12 Coasts

- **Beaches:** the equilibrium profile h = A y^(2/3) below the waterline (depth h at distance y from the shoreline;
  A depends on grain size and waves) ([Dean 1991](https://journals.flvc.org/jcr/article/view/78405)); a berm above.
- **Rocky coasts:** sea cliffs retreat, leaving a near-sea-level platform; headlands and bays can be stable even
  without rock contrasts because beaches protect cliffs non-linearly
  ([Limber & Murray 2011](https://doi.org/10.1130/G32315.1)).
- **Method:** sea mask; distance to shore by jump flooding; wave exposure (fraction of open sea within a radius, or a
  few ray casts for fetch); retreat distance = exposure x erodibility noise; inside the retreat distance replace
  terrain with the platform (0 to -2 m) and put a cliff at the retreat line whose height is the land height there;
  talus/boulders at the cliff toe; beaches with the Dean profile in low-exposure bays; stacks where a headland's
  retreat leaves islands.
- **Failure modes:** a uniform beach ring around every island; smooth shore with no cliffs; flat featureless sea floor.

---

## 4. Landform recipes for make_terrain (simplest convincing method per family)

| family | base | process passes (in order) | key parameters | judge against |
|---|---|---|---|---|
| mountain range (fluvial) | painted/noise uplift + rough dome | backbone to near steady state, x2 up + re-erode x2, talus, deposition | U/K (relief), sqrt(D/K) about one cell, Sc 30-40 deg, theta 0.4-0.5 | real ranges' slope histogram, 0 closed depressions |
| alpine glacial valley | fluvial range above | glacier extent from ELA, U-carve (b = 2), cirques, talus, lakes, moraines, outwash | ELA, width/depth vs ice discharge, buzzsaw cap | U cross-sections, hanging valleys |
| stratovolcano | log/linear profile + crater | growth term + backbone for an age, apron deposition, lava flows, breach, parasitic cones | profile type, age, flow count | radial drainage, Karátson profile |
| cinder cone field | cone profiles H/W 0.18, crater 0.4 W | diffusion for age, lava flows from breaches | ages vary per cone | Wood/Porter ratios |
| caldera | strato edifice | ring-fault collapse, wall talus, lake/sediment floor, outer-flank erosion | diameter, wall angle, fill level | flat floor + steep walls |
| canyon / mesa / butte | plateau + strata column (dip, warp) | backbone with K(z), Sc(z), talus on weak layers, headward growth | layer table, base-level fall | stepped cliff-slope profile |
| badlands | soft block + a few caprocks | backbone at 1-5 m cells, high K, small D, base-level fall | sqrt(D/K) about one cell | knife ridges, dense rills |
| dunes (barchan / transverse / linear / star) | bedrock + sand thickness | Werner slab CA with the wind regime, avalanche at ~31-34 deg | wind directions + weights, sand supply | slip faces, interdune flats |
| karst towers | alluvial plain | tower field (jump-flood distance), common base + dolines for fengcong, plain fill | spacing, clustering, wall angle | fenglin vs fengcong |
| impact crater | any surface | radial profile + ejecta + noise, then age | Pike d/D, rim, floor | d/D 0.2 simple |
| coast | any land + sea level | shore distance, exposure, cliff retreat + platform, Dean beaches, talus | exposure, erodibility | cliffs on headlands, beaches in bays |

---

## 5. Multi-scale composition and resolution

- **Coarse to fine, each level with its own feature size** (Houdini's chained Erode with a smaller Erosion Feature
  Size; Schott et al. 2024: erosion -> thermal -> deposition alternated with x2 upsampling,
  [project](https://h-schott.github.io/p/mserosion)):
  - L0, 256-512 cells across (20-100 m/cell): uplift/primitive + backbone. Makes the drainage and the ridges.
  - L1 and L2, x2 each: bicubic upsample, add a little noise (about one coarse cell's relief), re-run the backbone
    for fewer steps with D/K rescaled to the new cell size, so new small valleys branch off the existing ones; then
    thermal and deposition.
  - L3: detail that no process defines at this scale: the existing Phacelle filter is a good *detail octave* on top
    of a simulated base (masked by wear and slope), as is derivative-damped fBm
    ([Quilez](https://iquilezles.org/articles/morenoise)); rock breakup on cliffs; strata ledges.
- **Film shots:** aerials and establishing shots read the drainage pattern, valley spacing and skyline (the
  backbone's job); eye-level shots read talus, ledges, boulders and soil (thermal, strata, scattered rock meshes and
  material displacement). Simulating a 20 km range at 0.5 m is pointless; simulate the range at 20-40 m, then make a
  high-resolution local patch around the camera by the same coarse-to-fine steps, as Ekigar's plan already proposed
  for its "local area" (its geometry-matching rules still apply).
- **Tiling/periodicity:** stream-power needs a base level; for a periodic tile use periodic neighbour reads and pin a
  few low outlets inside the tile (sea or a river exit), or accept a non-periodic patch with sea edges.

---

## 6. Surfacing

- **Masks from the simulation, not only from geometry:** drainage area (rivers, wetness, gravel bars), erosion amount
  ("wear": fresh bedrock), deposit thickness (soil, sediment, fans), talus thickness (scree), lake/sea masks; plus
  geometry masks computed by finite differences of the *final* height (slope, aspect, profile and plan curvature,
  height, occlusion) - the Ekigar plan measured why the analytic gradient is not good enough for this (its §6).
  This is what WM's flow/wear/deposition outputs, Gaea's data maps and Houdini's debris/sediment/flow layers are.
- **Layer rules that read right:** bare rock where slope is above ~35-45 degrees or wear is high and deposit thin;
  scree on the talus mask and concave cliff toes; soil/grass on gentle planar-to-convex slopes; gravel, sand and silt
  on deposits and valley floors, dark and wet along high drainage area; snow by altitude with aspect bias and a slope
  cut-off; vegetation by altitude band, slope, moisture (drainage) and aspect. Ghost Recon Wildlands' procedural
  materials used exactly slope, height, flow and curvature (links in section 2).
- **Strata in world space:** rock colour/roughness bands from a world-space height (plus dip and warp) on steep faces,
  so bands stay level and continuous across ridges; never in UV space.
- **Blend by height, project triplanar:** height-based blending lets sand settle between cobbles instead of
  cross-fading ([Mishkinis 2013](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting));
  triplanar projection on steep faces with per-plane tangents for normal maps
  ([Golus 2017](https://bgolus.medium.com/normal-mapping-for-a-triplanar-shader-10bf39dca05a)); in Blender, the
  Image Texture node's Box projection with Blend is a cheap triplanar.
- **Macro variation** (low-frequency tint/roughness) to kill tiling, and detail that fades with distance.

---

## 7. Implementation notes for eidoblend (numpy + optional GPU fragment passes)

- Everything in sections 3.1 (a), 3.2, 3.3 (grid), 3.4 (capacity deposition), the glacial carve's jump flood, the
  coast's distance/exposure and all masks are 3x3-neighbourhood passes: numpy array shifts now, Blender
  `GPUOffScreen` float ping-pong passes later (Ekigar's plan measured float readback exact in Blender 5.2; no
  compute shaders). Keep one implementation per pass with a numpy reference and a GPU twin, as Ekigar did for TSL.
- Global passes that stay on the CPU: priority-flood lakes (rare), tree ordering for the implicit solver (vectorised
  by depth levels), the dune automaton (scatter).
- Blender's Python has numpy only (no scipy): `np.add.at` for scatters, `np.argsort` for orders, pointer jumping for
  tree depths, FFT spectral synthesis for noise.
- Units: run everything in metres and years so parameters can be compared with the literature, and expose
  art-facing knobs (relief, valley spacing, age) that map onto U/K, D/K and time.

---

## 8. My measurements

Files: `tools/terrain_metrics.py` (metrics + hillshade), `proto/spl_gather.py` (backbone, local gather form),
`proto/spl_implicit.py` (backbone, implicit tree form), `proto/compare_controls.py`, `proto/sheet.py`; outputs in
`proto/out/` (`_sheet_spl.png` is the contact sheet of runs A-I with their numbers printed on each panel;
`_compare_kn.png` shows H, I, J, J2 at 2x; `log_run_<letter>.txt` are the runs' logs). The CPU
was at 100 % from other agents' jobs during these runs, so wall times are inflated; I also give each step's cost in
"plain ops" (one full-grid `a*b+c` timed at the same moment), which does not depend on the load.

### 8.1 The realism metrics on what exists now

| heightfield | cell | relief | slope p50 / p90 (deg) | > 40 deg | < 5 deg | area in closed depressions | depressions / 100 km^2 |
|---|---|---|---|---|---|---|---|
| fBm, spectrum k^-4 (= gain 0.5 octaves), 20 km | 78 m | 1322 m | 10 / 18 | 0 % | 14 % | 11.8 % | 75 |
| fBm, spectrum k^-3 (rougher), 20 km | 78 m | 1119 m | 25 / 40 | 10 % | 2.5 % | 29.2 % | 373 |
| Ekigar mountainRange alpine, 4 km | 3.9 m | 286 m | 50 / 66 | 70.5 % | 0.4 % | 45.7 % | 124 038 |
| Ekigar volcano, 3 km | 2.9 m | 556 m | 27 / 54 | 28.9 % | 15.6 % | 21.6 % | 32 344 |
| Ekigar canyon, 2 km | 2.0 m | 387 m | 10 / 60 | 20.6 % | 18.8 % | 22.9 % | 1 650 |
| Ekigar badlands, 1.5 km | 1.5 m | 213 m | 23 / 76 | 33.8 % | 5.5 % | 27.6 % | 142 178 |
| Ekigar glacialTrough, 3 km | 2.9 m | 430 m | 0.1 / 51 | 16.3 % | 62.6 % | 14.2 % | 100 |
| Ekigar duneField star, 3 km | 2.9 m | 175 m | 26 / 45 | 17.4 % | 6.8 % | 56.4 % | 167 |
| Ekigar impactCrater, 3 km | 2.9 m | 194 m | 6 / 24 | 3.3 % | 45.3 % | 37.9 % (the crater bowl: correct) | 11 |
| Ekigar caldera, 3 km | 2.9 m | 305 m | 11 / 43 | 12.1 % | 21.5 % | 22.9 % (the caldera floor: correct) | 11 |
| stream-power prototypes (all runs below) | 78 m | 710-3340 m | see 8.2 | | | **0 %** | **0** |

What it says: Ekigar's mountain range has 70 % of its area steeper than 40 degrees (a threshold range sits around
35-40 on average) and a closed pit every ~800 m^2; its badlands and volcano are pitted the same way; its star dunes
have 17 % of their area steeper than 40 degrees, which dry sand cannot hold (it avalanches at ~31-34); its glacial
trough is 63 % dead flat with 51-degree walls, a slot. fBm leaves 12-29 % of the area in closed basins. Every
stream-power run has none. (The Ekigar heroes are 1.5-4 km at 1.5-4 m cells, so their slopes are measured at a finer
scale than the 78 m prototypes; real slopes also steepen at finer cells, but not to 70 % above 40 degrees.)

### 8.2 The backbone in numpy: what works and what breaks

20 km square, 256^2 cells (78 m), base level at the map edge, uplift = smooth multi-scale noise fading to zero
near the edges, m = 0.5, n = 1, Sc = tan(36 deg) x (0.85-1.15 noise), creep cap 5 (run B: 50). Runs A and B
came from an earlier revision of `spl_gather.py` (2 m of start noise, no uplift texture); C-J from the current
files. Panels in `proto/out/_sheet_spl.png`:

| run | solver | hillslope | D (m^2/yr) | K | U max | start | Myr | relief | slope p50 / p90 / p99 | what it looks like |
|---|---|---|---|---|---|---|---|---|---|---|
| A | gather | min-plus clip | - | 4e-6 | 1 mm/yr | flat | 3 | 1137 m | 29 / 38 / 40 | facets facing the 8 grid directions (zebra) |
| B | gather | creep | 0.02 | 4e-6 | 1 | flat | 3 | 2365 m | 28 / 38 / 41 | parallel gullies, zebra/corduroy |
| C | gather | creep | 0.5 | 4e-6 | 1 | flat | 3 | 2258 m | 16 / 25 / 28 | soft mush, few valleys |
| D | implicit D8 | creep | 0.5 | 4e-6 | 1 | flat | 3 | 2377 m | 16 / 25 / 28 | mush with straight grid-axis valleys |
| E | gather | creep | 0.1 | 4e-6 | 1 | flat | 5 | 2831 m | 25 / 36 / 41 | big planar facets, parallel edge gullies |
| F | implicit D8 | creep | 0.1 | 4e-6 | 1 | flat | 5 | 3342 m | 27 / 36 / 41 | same, straighter valleys |
| G | gather | creep | 0.1 | 2e-5 | 2 | dome | 2 | 848 m | 14 / 28 / 33 | branching network, even spacing (best) |
| H | gather | creep | 0.04 | 2e-5 | 2 | dome | 2 | 753 m | 15 / 31 / 36 | finer branching, sharper ridges (best) |
| I | gather | creep | 0.04 | 1e-5 | 3 | dome | 2.5 | 3106 m | 34 / 54 / 61 | high relief: valleys comb into straight grid-direction ridges |

Findings, as an environment artist reading the hillshades and as numbers:
1. **No closed depressions in any run**, and slopes pile up just under Sc in the moderate-relief runs: the two
   generic realism tests that noise and Ekigar fail, the backbone passes by construction.
2. **The start decides the network.** B and G have the same incision/creep length sqrt(D/K) = 70 m; B (flat start,
   slow K) is corduroy after 3 Myr, G (rough dome start, K x5 so it nears equilibrium sooner) is a branching range.
3. **Slope capping must be flux-based.** The min-plus clip (A) faceted every hillslope toward one of 8 directions.
4. **D/K sets the texture**: D/K = 125,000 m^2 is mush (C, D); 2,000-5,000 m^2 gives valleys every 4-6 cells (G, H).
5. **Single-direction (D8) area draws straight valleys** along the axes and diagonals (D, F); the MFD gather curves
   them (C, E). Even with MFD, the D8 steepest slope keeps a grid-direction bias that shows when relief is high (I):
   the ridges comb into straight lines. Erodibility noise (Schott et al.'s shader multiplies k by a noise buffer),
   more cells, and the coarse-to-fine refinement are the fixes to try; run J below tests the first.
6. **The uplift map prints itself into the range.** Where uplift fades to zero toward the sea, the uniform ramp grows
   parallel gullies (the edges of every run). My edge fade was min(distance to each edge), whose 45-degree creases
   became straight diagonal divides running through I and J2. Paint uplift without creases, and put the coast where
   the uplift map has texture.
7. **Hillslopes go past Sc when uplift outruns the capped creep** (I: 17 % of the area above 50 degrees): raise the
   cap or add the debris-flow / landslide term (section 3.2) for high-relief ranges.
8. **Cost.** Gather step: 78-240 plain ops (33-130 ms at 256^2 under load; ~10 neighbourhood passes), 2000-2500
   steps to near steady state. Implicit step: 94-203 plain ops with 150-160 tree levels at 256^2, but 10 kyr steps
   instead of 1-2 kyr. Each gather step is a handful of 3x3 passes, so on the GPU as fragment passes 1024^2 is
   cheap; in numpy, 512^2 is ~4x the 256^2 cost per step, needs ~2x the steps (half the dt for the same cell
   Courant number) and ~4x the creep sub-steps - minutes, not seconds, which is why the coarse level should stay
   at 256-512 and the finer levels should run few steps.

**Erodibility noise (runs J, J2; `proto/out/_compare_kn.png`):** K multiplied by 1 +/- 0.6 of smooth noise.

| run | as | relief | slope p50 / p90 / p99 | > 40 deg | closed depressions | what it looks like |
|---|---|---|---|---|---|---|
| J | H + K noise | 712 m | 16 / 31 / 36 | 0 % | 0 % | a little less directional and more irregular than H; the most natural of all runs |
| J2 | I + K noise | 2926 m | 34 / 53 / 60 | 39.5 % | 0 % | still combed at high relief; noise helps only a little there |

Conclusion for the builder: the backbone is right and cheap, and its look at film quality depends on three things my
coarse single-level runs did not have: (1) more cells per valley (the x2 refinement levels of section 5, where new
tributaries branch off at angles the coarse grid cannot draw), (2) an art-directed uplift/primitive with texture at
several scales and no creases, and (3) the talus, deposition and detail passes that put flats, aprons and rock
texture between the valleys. Start the parameter search from run J (D/K = 2,000 m^2, U/K = 100 m, Sc 36 degrees
+/- 15 %, 2000 x 1 kyr steps at 78 m) and raise U/K for relief only together with a stronger hillslope term.

---

## 9. Sources

CG terrain generation
- Galin et al. 2019, A Review of Digital Terrain Modeling, CGF 38(2) - https://diglib.eg.org/handle/10.1111/cgf13657
- Cordonnier et al. 2016, Large Scale Terrain Generation from Tectonic Uplift and Fluvial Erosion, CGF 35(2) - https://hal.archives-ouvertes.fr/hal-01262376
- Schott et al. 2023, Large-scale terrain authoring through interactive erosion simulation, ACM TOG 42(5) - https://hal.science/hal-04049125 ; code https://github.com/H-Schott/StreamPowerErosion
- Schott et al. 2024, Terrain Amplification using Multi-Scale Erosion, ACM TOG 43(4) - https://h-schott.github.io/p/mserosion ; code https://github.com/H-Schott/MultiScaleErosion ; Shadertoy https://www.shadertoy.com/view/XX2XWD
- Tzathas et al. 2024, Physically-based Analytical Erosion for fast Terrain Generation, CGF 43(2) - https://diglib.eg.org/handle/10.1111/cgf15033
- Cordonnier et al. 2023, Forming Terrains by Glacial Erosion, ACM TOG 42(4) - https://www.cs.purdue.edu/homes/bbenes/papers/Cordonnier23ToG.pdf
- Paris et al. 2019, Desertscape Simulation, CGF 38(7) - https://perso.liris.cnrs.fr/aparis/public_html/projects/paris2019_Deserts.html ; code https://github.com/aparis69/Desertscapes-Simulation
- Génevaux et al. 2013, Terrain Generation Using Procedural Models Based on Hydrology, ACM TOG 32(4) - https://hal.archives-ouvertes.fr/hal-01339224
- Cordonnier et al. 2018, Sculpting Mountains: Interactive Terrain Modeling Based on Subsurface Geology, IEEE TVCG 24(5) - https://hal.archives-ouvertes.fr/hal-01517343
- Argudo et al. 2019, Orometry-based Terrain Analysis and Synthesis, ACM TOG 38(6) - https://people.cs.uct.ac.za/~jgain/wp-content/papercite-data/pdf/argudo2019.pdf
- Musgrave, Kolb, Mace 1989, The synthesis and rendering of eroded fractal terrains, SIGGRAPH 89 - https://researchr.org/publication/MusgraveKM89
- Mei, Decaudin, Hu 2007, Fast Hydraulic Erosion Simulation and Visualization on GPU, Pacific Graphics - https://inria.hal.science/inria-00402079
- Stava et al. 2008, Interactive Terrain Modeling Using Hydraulic Erosion, SCA - https://www.cs.purdue.edu/homes/bbenes/papers/Stava08SCA.pdf
- Jako 2011, Fast Hydraulic and Thermal Erosion on GPU, CESCG - https://www.old.cescg.org/CESCG-2011/papers/TUBudapest-Jako-Balazs.pdf
- Beyer 2015, Implementation of a method for hydraulic erosion (thesis) - https://ardordeosis.github.io/implementation-of-a-method-for-hydraulic-erosion/thesis-beyer.pdf ; erodr https://github.com/henrikglass/erodr
- Quilez, noise derivatives ("more noise") - https://iquilezles.org/articles/morenoise
- Johansen 2026, Fast and Gorgeous Erosion Filter (Phacelle) - https://blog.runevision.com/2026/03/fast-and-gorgeous-erosion-filter.html
- Braun & Willett 2013, O(n) implicit stream power solver, Geomorphology 180-181 - https://doi.org/10.1016/j.geomorph.2012.10.008
- Cordonnier, Bovy, Braun 2019, flow routing in topographies with depressions, ESurf 7 - https://esurf.copernicus.org/articles/7/549/2019/
- Barnes, Lehman, Mulla 2014, Priority-Flood, Computers & Geosciences 62 - https://arxiv.org/abs/1511.04463

Geomorphology
- Whipple & Tucker 1999, stream-power incision model, JGR 104(B8) - https://doi.org/10.1029/1999JB900120
- Hack 1957, longitudinal stream profiles, USGS PP 294-B - https://pubs.usgs.gov/publication/pp294B
- Perron, Kirchner, Dietrich 2009, evenly spaced ridges and valleys, Nature 460 - https://dspace.mit.edu/handle/1721.1/64681
- Perron, Kirchner, Dietrich 2008, spectral signatures and nonfractal structure, JGR 113 - https://doi.org/10.1029/2007JF000866
- Roering, Kirchner, Dietrich 1999, nonlinear hillslope transport, WRR 35(3) - https://doi.org/10.1029/1998WR900090
- Burbank et al. 1996, threshold hillslopes, Nature 379 - https://doi.org/10.1038/379505a0
- Montgomery & Brandon 2002, erosion rates and topography, EPSL 201 - https://repository.geologyscience.ru/handle/123456789/28097
- Howard 1997, badland morphology, ESPL 22 - https://core.ac.uk/download/209821525.pdf
- Harbor 1992, U-shaped valleys, GSA Bulletin 104 - https://doi.org/10.1130/0016-7606(1992)104<1364:NMOTDO>2.3.CO;2
- Anderson, Molnar, Kessler 2006, glacial valley profiles, JGR 111 - https://doi.org/10.1029/2005JF000344
- Svensson 1959, glacial valley cross-section, J. Glaciology - https://www.cambridge.org/core/journals/journal-of-glaciology/article/is-the-crosssection-of-a-glacial-valley-a-parabola/EE16DB83DA62DE75D671DE955242CD43
- Egholm et al. 2009, glacial effects limiting mountain height, Nature 460 - https://doi.org/10.1038/nature08263
- Werner 1995, eolian dune simulations, Geology 23 - https://planetarygeoscience.uchicago.edu/doc/Werner_1995.pdf
- Rubin & Hunter 1987, bedform alignment, Science 237 - https://pubs.usgs.gov/publication/70014126
- Courrech du Pont, Narteau, Gao 2014, two modes for dune orientation, Geology 42(9) - https://www.ipgp.fr/~narteau/papers/P37.pdf
- Zhang et al. 2012, star dunes from numerical modelling, Nature Geoscience 5 - https://www.nature.com/articles/ngeo1503
- Karátson et al. 2010, regular shape of stratovolcanoes, JVGR 193 - https://ui.adsabs.harvard.edu/abs/2010JVGR..193..171K
- Grosse et al. 2009, morphometry of arc volcanoes, Geology 37(7) - https://ri.conicet.gov.ar/handle/11336/55921
- Wood 1980, morphometric evolution of cinder cones, JVGR 7 - https://doi.org/10.1016/0377-0273(80)90040-2
- Favalli et al. 2005, DOWNFLOW lava paths, GRL 32 - https://doi.org/10.1029/2004GL021718
- Pike 1977, fresh lunar crater shapes - https://ntrs.nasa.gov/citations/19780060140 ; quoted in Holsapple 2022 https://arxiv.org/abs/2203.07476
- McGetchin, Settle, Head 1973, ejecta thickness, EPSL 20 - https://doi.org/10.1016/0012-821X(73)90162-3
- Dean 1991, equilibrium beach profiles, J. Coastal Research 7(1) - https://journals.flvc.org/jcr/article/view/78405
- Limber & Murray 2011, beach/sea-cliff dynamics, Geology 39(12) - https://doi.org/10.1130/G32315.1
- Waltham 2008, fengcong, fenglin, cone and tower karst, Cave and Karst Science 35(3) - https://www.bcra.org.uk/cks105
- Perne et al. 2017, landscapes in layered rocks, ESurf 5 - https://esurf.copernicus.org/articles/5/85/2017/
- Forte, Yanites, Whipple 2016, incision through layered stratigraphy, ESPL 41 - https://doi.org/10.1002/esp.3947
- Glade, Anderson, Tucker 2017, block-controlled hillslopes, Geology 45(4) - https://doi.org/10.1130/G38665.1

Tools and production
- World Machine: Erosion (legacy) https://help.world-machine.com/topic/device-erosion/ ; Thermal Erosion https://help.world-machine.com/topic/device-thermalerosion/ ; builds 4044/4046 https://help.world-machine.com/topic/build-4044-hurricane-ridge/ , https://help.world-machine.com/topic/build-4046-hurricane-ridge-final/
- Gaea 2: reference https://docs.gaea.app/reference/ ; Erosion2 https://docs.gaea.app/reference/nodes/simulate/erosion2.html ; Thermal https://docs.gaea.app/reference/nodes/simulate/thermal.html ; Volcano https://docs.gaea.app/reference/nodes/terrain/volcano.html ; DuneSea https://docs.gaea.app/reference/nodes/terrain/dunesea.html ; Glacier https://docs.gaea.app/reference/nodes/simulate/glacier.html
- Houdini: HeightField Erode https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode.html ; HeightField Erode Hydro https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode_hydro.html
- Unreal: landscape quick start https://dev.epicgames.com/documentation/unreal-engine/landscape-quick-start-guide-in-unreal-engine ; Hydro Erosion (4.27) https://docs.unrealengine.com/4.27/en-US/BuildingWorlds/Landscape/Editing/SculptMode/HydroErosion ; Blueprint brushes https://dev.epicgames.com/documentation/unreal-engine/landscape-blueprint-brushes-in-unreal-engine
- Ghost Recon Wildlands terrain tools, GDC 2017 https://gdcvault.com/play/1024029/ ; 80.lv https://80.lv/articles/landscape-and-material-pipeline-of-ghost-recon-wildlands/
- Far Cry 5 procedural world generation, GDC 2018 https://gdcvault.com/play/1025557/Procedural-World-Generation-of-Far ; https://www.sidefx.com/learn/talks/procedural-world-generation-far-cry-5/
- Andersson 2007, Terrain Rendering in Frostbite Using Procedural Shader Splatting https://www.advances.realtimerendering.com/s2007/Andersson-TerrainRendering(Siggraph07)-CourseNotes.pdf
- Gollent 2014, Landscape Creation and Rendering in REDengine 3 (Witcher 3) https://www.gdcvault.com/play/1020394/Landscape-Creation-and-Rendering-in
- Mishkinis 2013, Advanced Terrain Texture Splatting https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting
- Golus 2017, Normal Mapping for a Triplanar Shader https://bgolus.medium.com/normal-mapping-for-a-triplanar-shader-10bf39dca05a
- The Good Dinosaur and USGS data (press) https://planetizen.com/node/82561
