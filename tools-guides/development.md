# Maintaining the toolkit and its documentation

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Start with [AGENTS.md](../AGENTS.md) and the guide for the system being changed.
The [tool inventory](../docs/TOOLS.md) maps first-party source files to those
guides. Source determines the actual API; comments and old scenes can be stale.

## Preserve the workspace

Inspect `git status` and the relevant diffs before editing. Keep unrelated
collaborators' changes intact. Put experiments and archives in ignored `work/<id>/`;
apply shared-library changes within the agreed scope. Replacing a tool
means updating its callers, examples and docs together. Preserve the old
implementation in Git history and a local archive when requested; do not
rewrite history to remove it.

## How tools become available

- The native runner is `eido.py`; dependency versions/import mappings are in
  `deno.json` and `deno.lock`. Setup is in [SETUP.md](../docs/SETUP.md).
- `render_scene.mjs` loads the scene's declared assets as raw bytes, injects
  the ordered `HELPER_MODULES`, initializes special imported helpers, then
  evaluates the scene script and calls `setup()` and `renderFrame(t, frameIndex)`.
- Eval helpers install a global API. Dependencies must appear earlier in the
  helper list. Check injection errors: a skipped helper may only fail when
  the scene first uses its global.
- ESM systems such as cloth and fluids are dynamically imported inside scene
  `setup()` using `EIDOVERSE_DIR`. Scene scripts are eval'd, so top-level
  `import` declarations do not work there.
- `sky_worlds.js` is an explicit facade loaded by a scene. It loads its own
  package components. Do not label every file in `eidoverse/` an injected global.
- Use pinned Three.js NodeMaterials/TSL, the native texture helpers and the
  engine's adapter/device. Preserve existing rendering and time ownership.

Paths in this native edition resolve from the repository root. Some code
retains `/workspace` fallbacks for the container edition; a container mount
is not a prerequisite of this checkout.

## Documentation changes

`AGENTS.md` is the shared main instruction and the complete guide index.
`tools-guides/*.md` are ordinary tool and craft guides; there is no custom skill dispatcher.
Keep `CLAUDE.md` importing `AGENTS.md` so both entry paths reach the same rules.

When adding a system:

1. Explain when to use it, how it loads, and any dependencies it actually needs.
2. Include a source-checked setup example, return object, controls, coordinate
   conventions, update/cleanup ownership and material limitations that affect use.
3. Add or update its `tools-guides/<system>.md`, the index in `AGENTS.md`, and its
   source mapping in `docs/TOOLS.md`. Use working relative Markdown links.
4. Update affected examples and remove obsolete active API instructions. Keep
   optional or historical utilities clearly identified; do not advertise absent
   files as supported imports.
5. Check every guide link, every inventory path and all newly documented names.
   Include HTML entry points, CLI scripts, injected globals, dynamic modules
   and optional utilities. A source filename in a table does not replace
   usable API instructions; distinguish internal support exports from scene APIs.
6. Preserve the branch's relationship between collaborators. On `main`, the
   agent is a filmmaker working with a human collaborator; ideas may come from
   either. The `auto` branch's parent-agent brief and collector workflow belong
   there. Technical requirements should explain actual behavior, while artistic
   recipes should leave room for artistic judgment and experimentation.

Public guides describe making scenes with this Three.js toolkit. Authoring
notes for creating the robotics assets belong in their separate working
project, not in the public kit's assembly instructions.

## Validation

For a docs-only change, verify navigation, file/API references and source
coverage; no video render is needed. For behavior changes, run the affected
checks and inspect appropriate probe frames/motion. Use the available suites:

```bash
deno test --no-check --allow-read --node-modules-dir=manual --no-lock eidoverse/robotics/tests/runtime_test.mjs
deno test --no-check --allow-read --node-modules-dir=manual --no-lock eidoverse/audit_core_test.mjs
deno test --no-check --allow-read --node-modules-dir=manual --no-lock eidoverse/dismember_core_test.mjs
```

Read a test's imports/permissions when extending it. `--no-check` bypasses
missing external TypeScript declarations; it does not disable assertions.
The renderable examples cover basic VRM, the obstacle course, modular assembly,
robot motion, MANTIS and G430 manufacturing. Render probes before long encodes
and keep one sustained GPU render active at a time.

Report what was actually checked. A catalog/motion test does not establish
visual quality or physical contact validity; an asset inventory is not a
license review; an imported function is not necessarily a runnable feature
without its optional backend.

## Internal support code

`render_common.mjs` owns native renderer/canvas setup, config and asset loading,
camera interpolation, UI rasterization, readback and encoding. Its exported
`setupRenderer`, `setupScene`, `loadConfig`, `loadAssets`, `getCameraAtTime`,
`readbackFrame`, `drainReadback`, `startFfmpegPipe`, `logProgress` and `shutdown`
support the runner. Scene authors normally use `setup`, `renderFrame` and the
injected helpers, rather than starting a second renderer/readback pipeline.
`HTMLCanvasShim`, the installed `HTMLCanvasElement` and `Worker` compatibility
objects are environment plumbing, not new scene tool systems.

The same distinction applies to physics/topology helpers in `dismember_core`,
vegetation geometry generators, curl-noise primitives, and modular robotics
I/O/material/motion modules. Their system guides explain the public entry
points; inspect the corresponding source when changing those internals.
Tests and standalone demonstrations remain indexed with their execution or
availability notes, even when they are not scene-importable libraries.
