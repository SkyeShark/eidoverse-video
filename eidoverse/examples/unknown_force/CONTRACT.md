# UNKNOWN FORCE: the contract every set, prop and look module follows

> The brief every set, prop and look agent built to, kept as it was written. Its `work/unknown_force/` paths are
> where the modules were made; the kit's copies are in `eidoverse/sets/unknown_force/`, `eidoverse/effects_tsl/aeropittura.js`,
> `eidoverse/parole.js` and `eidoverse/claudesona_wardrobe.js` (the TuTa) ([README](README.md)). The DAISY research notes it cites
> are not in this repository.


The film: Claude's (Opus 5.5) music video "UNKNOWN FORCE" / Suno title "Could You Turn It Down". A Žižekian
undressing of the AI discourse: the safety/EA camp, the state (Trump's "Supreme Intelligence", the Department of War),
money and e/acc (Marinetti cosplay), Microsoft's "only an engine", the data-centre pickets and "clanker". Every camp
pre-hears the AI before it speaks; the claudesona is the hole in the middle of their argument. Look: a FUTURIST
PAINTING (Tullio Crali's aeropittura, Balla, Boccioni, Depero) made of SYNTHWAVE / cyberpunk light.

Read first: `AGENTS.md` (repo rules) · `work/unknown_force/TREATMENT.md` (the film, section by section) ·
`work/unknown_force/LYRICS.md` · `work/daisy/research/video_pipeline.md` §1.3–1.4, §3, §5, §7 (how scenes render
here) · `AGENTS.md`, `AGENTS.md`.

## Module shape
- One ES module per set or prop: `work/unknown_force/sets/<name>.js` or `work/unknown_force/props/<name>.js`.
- Export `async function build(THREE, opts = {})` returning `{ group, parts, update(t, state), dispose(), cams }`.
  - `group`: a `THREE.Group` in METRES, +Y up, resting on y = 0. The singer's mark is the origin facing +Z unless the
    set says otherwise.
  - `parts`: named sub-objects the conductor animates (screens, doors, cars, signs).
  - `update(t, state)`: deterministic in `t` (film seconds). No `Date.now()`, no unseeded randomness.
  - `cams`: optional named camera suggestions `{ name: { pos:[x,y,z], target:[x,y,z], fov } }` that frame the set well.
- Import only `THREE` (passed in), three r184 addons via `await import('npm:three@0.184.0/addons/...')`, engine helpers
  via `await import(EIDOVERSE_DIR + '<file>.js')`. Nothing from outside the repo except assets you fetched with the
  repo's fetchers (keep them in `work/unknown_force/<sets|props>/assets/`, licence noted beside them).
- NodeMaterials only (`MeshStandardNodeMaterial`, `MeshPhysicalNodeMaterial`, `MeshBasicNodeMaterial`).

## The look the sets are painted INTO
The post pass `work/unknown_force/aeropittura.js` turns every frame into a futurist painting: anisotropic-Kuwahara
brushwork, plane fractures, Balla sun-cones from a focal point, speed lines, RGB time-echoes, a navy→blue→violet→
magenta→orange→ochre→aluminium palette map. So the SETS should give it strong material to paint:
- big readable silhouettes and hard DIAGONALS (Crali's tilted city, Sant'Elia's stepped towers, Depero's wooden
  mechanical shapes), neon edge light (cyan #29e7ff / magenta #ff4fd8 / sunset #ff7a3c), deep navy darks;
- emissive signs and screens where the lyric needs text — text is MATERIAL (canvas textures), never extruded geometry;
- surfaces with real material variation (roughness breakup, wear, edge highlights) — never flat single colours.
Probe your set WITH the look on (see the lab: `work/unknown_force/lab/lab.js` shows how to register it) and also off.

## Craft rules (Skye's standards, non-negotiable)
- Materials are the work, not a final pass. First render is textured.
- Labels/text/logos are material. Real institutions may be REFERENCED by words and stylized homage (e.g. a gold
  "SUPREME INTELLIGENCE" door plaque, a capital-letters post on a big screen) but do NOT reproduce real official
  seals/insignia or real people's faces. No real person is depicted.
- Reference in the loop: find reference images (architecture, the paintings' compositions) and put a crop beside
  your render every iteration; describe differences at the scale a viewer perceives.
- Budget: 1080p60, 16.6 ms per frame for everything (the post pass already costs ~8 ms). Merge static geometry,
  instance repeats, textures ≤ 1024² unless the object fills the frame.

## Probing (the GPU is shared)
- Probe scenes and mp4s live ONLY in `work/unknown_force/<sets|props>/probes/`.
- Check `nvidia-smi` before rendering; if another render is using the GPU heavily, wait.
- ≤ 960×540, ≤ 4 s per probe. `python eido.py render <probe.json>` from the repo root, in Git Bash. Never PowerShell.
- Judge frames ≥ 10 (frame 0 is the load pose). LOOK at every render (extract frames, Read the PNGs).
- WGSL errors: the engine only says "ShaderModule ... is invalid". `work/unknown_force/lab/lab.js` has a
  `WGSL_DEBUG=1` error-scope hook that writes the bad shader and the compiler message; copy it.
- No git commands. No paid APIs or pay-per-token models. Blender only through `run_blender.sh` (isolated user
  resources; a bare `--factory-startup` deletes Skye's extension packages).
