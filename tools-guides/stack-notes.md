# Stack notes — Blender 5.2 / EEVEE behavior and observed issues

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

These notes collect the Blender edition's integration facts and issues observed
in its renders. They are for Blender 5.2.0 LTS, run headless through
`run_blender.sh`, rendering with EEVEE. Treat a workaround as a diagnosis to
verify in the current scene, rather than assuming every dark frame has the
same cause. Each note says how it was established.

## Running Blender

- **Blender exits 0 even when the script raises.** Check that every output
  exists, and give command-line tools their own exit code.
  `look/probe_cli.py` catches the failure, prints the traceback and calls
  `os._exit(code)`.
- **Run headless through `run_blender.sh`.** It starts with `--factory-startup`
  in an isolated user folder, so a run can't strip your installed extensions'
  packages. Scripts enable the add-ons they need:
  `bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')`.
- **Every render goes through the shared GPU slot** (`heavy.sh`). It refuses
  to start when another heavy job holds it or when VRAM or RAM is short: wait
  and retry.
- **`bpy.ops.object.transform_apply` applies location and rotation too unless
  told not to.** All three default to True. A script that only means to apply
  scale must pass `location=False, rotation=False, scale=True`. Otherwise the
  origin moves to the world origin, which breaks any later code that reads
  `matrix_world.translation` as the object's centre (seen 11-07 in a test).
- **A blend saved by a newer build** warns "expect loss of data!" in the 5.2.0
  binary (episode three's house: file subversion 45). It reads fine; don't save
  it back from the older binary.

## Output and the compositor

- **A render's own multilayer EXR holds only Combined.** Passes leave through a
  compositor File Output node: `scene.compositing_node_group` is a
  `CompositorNodeTree`, then `fo.file_output_items.new(type, name)` and a
  link to `fo.inputs[name]`, with `save_as_render=False` for data.
- **A File Output node writes only its FIRST item into the multilayer EXR.**
  Measured 11-07: Shadow + Diffuse Direct + Normal items on one node wrote a
  file holding Shadow.V alone; three nodes with one item each wrote all three.
  `lighting.debug_passes` uses one node per pass.
- **A Render Layers node keeps the pass sockets it had when it was made.**
  Switch the passes on first, then create the node. An older node's sockets for
  new passes are unavailable: linked, they write nothing.
- **EEVEE's pass sockets in 5.2:** 'Image', 'Alpha', 'Depth', 'Normal',
  'Diffuse Direct', 'Glossy Direct', 'Shadow', 'Ambient Occlusion', and
  'Vector' with motion blur off. There are no indirect sockets: the "direct"
  ones carry EEVEE's light.
- **`image_settings.media_type` comes before `file_format`:** `IMAGE`,
  `MULTI_LAYER_IMAGE` or `VIDEO`.
- **Compositor settings are menu and input sockets now.** Examples: Glare
  'Type' ('Bloom', 'Ghosts', 'Streaks', 'Fog Glow', 'Simple Star',
  'Sun Beams', 'Kernel'), Filter 'Type' ('Sobel', 'Kirsch', ...), Blur
  'Type'. Set them with `node.inputs['Type'].default_value = 'Bloom'`. A group
  node's inputs are keyable (`socket.keyframe_insert('default_value', frame=f)`).
- **The compositor's output** is a `NodeGroupOutput` with an 'Image' interface
  socket; there is no Composite node. Shader math nodes (Math, Mix, Map Range,
  Combine/Separate XYZ, the procedural textures) work in the compositor. Hue
  Saturation, Invert and Combine/Separate Color must use their `CompositorNode`
  forms.
- **Convert To Display carries its own view settings** (default Standard, not
  the scene's), and its exposure and gamma are read-only. Copy the scene's
  transform and look into it, and carry the exposure with Exposure nodes. The
  round trip through it and its inverse came back within 6 levels at the worst
  pixel.
- **Map UV reads the UV's Z as coverage** (the UV pass's alpha). A Combine XYZ
  feeding it needs Z = 1, or every pixel is masked out to black.
- **Image Coordinates: `Pixel` is the integer pixel, `Normalized` its centre**,
  (pixel + 0.5) / size (measured on a 64 × 36 render). One pixel in normalised
  units is therefore `Normalized / (Pixel + 0.5)`, exact at every pixel.
- **Translate moves the image's domain; it does not resample it.** A channel
  translated and combined with untranslated ones gives the combine the shifted
  domain. With 'Clip' the uncovered edge is black, and with 'Extend' it is
  clamped, but the untranslated channels are clamped there too (measured:
  +3 px on a ramp). Sample offsets through Map UV with 'Extend' instead
  (`post/custom_effects.py` does).
- **`Image.save_render(path, scene=scene)` applies the scene's colour
  management at save time.** One render's Render Result can be saved at many
  exposures (`look.exposure`'s sweep), exactly on flat areas but only
  approximately along high-contrast edges: EEVEE's film accumulation sees the
  view exposure. On the meadow, the exposure-0 render saved at +2.25 differed
  from a render made at +2.25 by up to 56 levels at single pixels (6.3% of
  pixels over 2), on silhouettes, shadow edges and the horizon. On the corner
  room, real renders passed the highlight check at +2.00 and +2.25 where the
  sweep's saves had failed. `auto_expose` confirms its pick and its ceiling with
  real renders.

## World, sky and volumes

- **EEVEE draws no sun disc from the Sky Texture.** With `sun_disc` on, the
  render had no sun and no shadows. Pair the sky with a sun light from the same
  direction.
- **The Sky Texture's sun sits at azimuth = `sun_rotation`, from +Y toward
  +X.** Measured with four sky-only views: rotation 0 puts the glow due +Y,
  60° puts it 60° toward +X.
- **An infinite world volume extinguishes the sun and the sky.** At
  0.012/m, a meadow frame went black apart from emission. Fog is a finite
  volume (a box with a top), with `use_volume_custom_range` and
  `volumetric_end` covering it so its froxels aren't spread over the camera's
  whole clip range.
- **`world.use_nodes` is deprecated;** a new world may already have its node
  tree. Check `world.node_tree` before setting it.
- **Indoors, a volume probe is the difference between a room and a lit
  void.** Without one, the world lights the interior through the walls.
- **A volume probe's samples are cell-centred, and beyond the outermost ones
  EEVEE fades to the world's light.** A probe sized to the corner room's
  interior left its walls, floor and the spheres' undersides lit by the world:
  pale blue walls, and a dark cap on a white sphere where its top reached the
  samples. A box ending at the mid-wall rows did the same. A probe whose
  outermost rows sit in the middle of the walls (`lighting.add_room_probe`)
  gave the walls the room's light. 14 × 13 × 9 samples at 1024 baked in about
  1.2 s.
- **Fast GI leaks the world indoors.** Its screen-space scan fills the
  directions it can't resolve from the world, through the walls: a blue
  crescent under a white sphere at its floor contact, bright strips along the
  wall bases, and grain that took 64 samples to clear. AO-only mode did the
  same. With fast GI off and a baked room probe, the corner room matched Cycles
  and a white sphere was clean at 16 samples.
- **Cycles is the reference.** `probe.render_reference` path traces the same
  still on the GPU (OptiX on this machine; about 6 s at 960 × 540, 512 samples,
  denoised). Both indoor faults above showed in one comparison.
- **Thin glass: dithered, ray-traced refraction, slab thickness.** A 1.5 cm
  pane as BLENDED with ray-traced refraction rendered as a dark panel with
  bright sparkles. `surface_render_method = 'DITHERED'`,
  `use_raytrace_refraction = True`, `thickness_mode = 'SLAB'` and 0.015 into
  the Material Output's Thickness made it read as Cycles does, the floor seen
  through it. Cycles also draws the pane's top edge as a thin dark line, which
  EEVEE doesn't.

## Colour

- **AgX (Blender 5.2's OCIO config, Base Contrast, exposure 0):** scene-linear
  0.18 → 117.6 of 255, 1.0 → 196.6, 4 → 233, 8 → 245, 16 → 254.6. A grey
  channel reaches 250 about 6 stops above 18% grey. Punchy puts 0.18 at 88.3.
  Medium High Contrast clips at 8. `look.exposure.mid_grey_luma(scene)` reads
  it for the scene's own view and look.
- **Looks are named by OCIO:** 'AgX - Base Contrast', 'AgX - Punchy', ... The
  enum is dynamic (listing it without a scene returns only 'NONE'); set the
  string.
- **The VRM add-on switches the view to Standard on import** unless
  `set_view_transform_to_standard_on_import=False`.

## Rendering

- **EEVEE keeps no history between final renders.** A frame rendered alone
  matched the same frame rendered after its previous frame to within 1 level
  (0 in one run, 1 in another: noise; `test_probe_modes.py`). Probes jump; no
  warm-up, no history reset on cuts.
- **Grain in a dim interior: suspect fast GI before the sample count.** A
  white sphere was grainy at 16 and 32 samples and clean only at 64 with fast
  GI on. With it off (and a baked room probe), it was clean at 16.
- **Probe costs measured on this machine (RTX 5090 Laptop, 960 × 540, 16
  samples):**
  - The meadow (a 108k-triangle VRM, about 16,000 scanned grass instances):
    0.4 to 0.8 s a frame.
  - The corner room: 0.2 s with fast GI off (0.3 s with it on).
  - Its Cycles reference: about 6 s at 512 samples, denoised.
  - The hazy stage: 0.2 to 0.3 s.
  - A 29-exposure sweep: one render plus about 3 s of saves.
- **Instanced geometry and ray casts:** `scene.ray_cast` hits instances (a
  Geometry Nodes scatter blocks sightlines), and reports a hit as the
  INSTANCED object (the scatter's source, e.g. `grass_medium_02_d`), with the
  instance's matrix as the returned matrix, never as the scatter. To ignore a
  scatter, ignore what it instances: the depsgraph's `object_instances` list
  each instance's `object` and its `parent`, the instancer. BVH clearance tests
  see only real objects. `scene.objects` includes objects in collections
  excluded from the view layer (a scatter's sources), so filter by what
  renders. `look.camera_safety` does both.
- **The VRM add-on imports `claude_robot.vrm` facing -Y** (glTF's +Z forward),
  with Principled BSDF materials. Its humanoid bone mapping is snake_case on
  the add-on's property group (`human_bones.left_foot`); the bone names
  themselves are VRM's camelCase.

## Encoding and delivery copies

If a render already contains macroblocking, encoding that MP4 at a higher
bitrate cannot recover the lost detail. Re-render, or encode again from a
higher-quality master if one exists.

Blender can render straight to H.264 (episode two's `render_h264.py`):
`media_type = 'VIDEO'`, FFMPEG, MPEG4, H264, `constant_rate_factor =
'PERC_LOSSLESS'`, preset GOOD, GOP 24, chunks starting on a keyframe. Deliver a
copy re-encoded by the system ffmpeg as H.264 High, yuv420p, with AAC sound,
so it plays everywhere:

```bash
ffmpeg -i master.mp4 -c:v libx264 -profile:v high -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k delivery.mp4
```

Lower CRF generally means higher quality and a larger file. These values are
starting points, not a guarantee for every resolution or motion pattern.
Review busy areas and gradients in the encoded copy, and retain the master.
Measure before optimising: a guess about where a slow frame's time goes has
been wrong here more than once.

## Not carried over

These WebGPU notes have no counterpart in Blender and were dropped on purpose:

- The adapter and doctor checks.
- NodeMaterial vs non-Node materials.
- `VolumeNodeMaterial` under Naga.
- Texture orientation per loader path.
- VRMs only through `GLTFLoader`.
- Transparency through alpha opacity.
- The auto-enhance MRT G-buffer and transparent quads.
- Depth-keyed screen effects over particle quads (fog is a real volume now).
- nvenc bitrates.
- 16-bit float render targets and readback strides.
- Binding limits.
- `_rawRenderAsync`.
- Motion-vector MRT naming.
- Compute-written index buffers.
- Timestamp queries.
- The draw-count note.
- The close-up scene's placement-audit hang and the console-capture note.

For Blender's own transparency, see the material settings:
`surface_render_method` DITHERED or BLENDED, `use_raytrace_refraction` with
`thickness_mode`, `use_transparent_shadow`. The corner test's glass pane uses
BLENDED with ray-traced refraction. It has not been judged closely yet.
