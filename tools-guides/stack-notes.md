# Blender and EEVEE notes

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Blender](blender.md) · [Cameras and lighting](camera-lighting.md)

Facts about Blender 5.2 and EEVEE, run headless through `run_blender.sh`,
that are worth knowing before you script them. The toolkit is built on them;
a scene of your own meets them too. EEVEE is a mature engine: when a frame
looks wrong, check the scene's setup against these notes and Blender's
manual (its geometry, probes, lights, materials and render settings) before
anything else.

## Running Blender headless

- **Headless Blender runs GPU compute shaders.** In background mode, call
  `gpu.init()` once, describe the kernel with `gpu.types.GPUShaderCreateInfo`
  and run it with `gpu.compute.dispatch`. Kernels read `sampler2D` /
  `sampler3D` textures (hardware filtered when the texture's filter is on) and
  write `image2D` / `image3D`; Blender inserts a texture-fetch and
  image-access barrier after every dispatch, so kernels chain in the order
  they are submitted. Python has no storage buffers, so per-point data
  travels in a float texture read with `texelFetch`. The sky's baker, the
  volume fire, the free-surface water, the SDF mesher and the terrain
  solvers all run this way, thousands of times faster than numpy on the same
  grid; `eido_blender.py doctor` checks a dispatch's readback.
- **Blender exits 0 even when the script raises.** Check that every output
  exists, and give command-line tools their own exit code.
  `look/probe_cli.py` catches the failure, prints the traceback and calls
  `os._exit(code)`; the runner checks its outputs and the digest's status.
- **Run headless through `run_blender.sh`.** It starts with
  `--factory-startup` in an isolated user folder, so a run can't strip your
  installed extensions' packages. Scripts enable the add-ons they need:
  `bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')`.
- **The first frame of a Blender process takes longer**: EEVEE compiles its
  shaders. Time a render from its second frame (`eido_blender.py bench` does).
- **`bpy.ops.object.transform_apply` applies location and rotation too unless
  told not to.** All three default to True. A script that only means to apply
  scale must pass `location=False, rotation=False, scale=True`, or the origin
  moves to the world origin.
- **A `.blend` saved by a newer build** warns "expect loss of data!" in an
  older binary. It reads fine; don't save it back from the older binary.

## Keys, actions and modifiers

- **Actions are layered in 5.2** (slots, layers, strips, channel bags).
  `keyframe_insert` works as before; to write a whole channel at once, get the
  slot's channel bag (`bpy_extras.anim_utils.action_ensure_channelbag_for_slot`)
  and fill an F-curve's `keyframe_points` in one call (`weather/keys.py`,
  `fabrication/_keys.py`).
- **A Geometry Nodes modifier's inputs are RNA in 5.2**:
  `modifiers["GN"].properties.inputs.<Socket_N>.value`, keyable at that data
  path. The modifier holds no ID properties: `m.keys()` and `m["Socket_N"]`
  raise `TypeError` (`harness.keying.node_inputs` reads both forms). The VRM
  add-on's MToon outlines are such modifiers.
- **An NLA strip's fades:** set `strip.use_auto_blend = False` before
  `blend_in` / `blend_out`; while auto-blend is on, Blender ignores them.

## Output and the compositor

- **A render's own multilayer EXR holds only Combined.** Passes leave through a
  compositor File Output node: `scene.compositing_node_group` is a
  `CompositorNodeTree`, then `fo.file_output_items.new(type, name)` and a
  link to `fo.inputs[name]`, with `save_as_render=False` for data.
- **A File Output node writes only its first item into a multilayer EXR.**
  Use one node per pass (`lighting.debug_passes` does).
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
  round trip through it and its inverse comes back within 6 levels at the
  worst pixel.
- **Map UV reads the UV's Z as coverage** (the UV pass's alpha). A Combine XYZ
  feeding it needs Z = 1, or every pixel is masked out to black.
- **Image Coordinates: `Pixel` is the integer pixel, `Normalized` its centre**,
  (pixel + 0.5) / size. One pixel in normalised units is therefore
  `Normalized / (Pixel + 0.5)`, exact at every pixel.
- **Translate moves the image's domain; it does not resample it.** A channel
  translated and combined with untranslated ones gives the combine the shifted
  domain. With 'Clip' the uncovered edge is black, and with 'Extend' it is
  clamped, but the untranslated channels are clamped there too. Sample offsets
  through Map UV with 'Extend' instead (`post/custom_effects.py` does).
- **`Image.save_render(path, scene=scene)` applies the scene's colour
  management at save time.** One render's Render Result can be saved at many
  exposures (`look.exposure`'s sweep): exactly on flat areas, approximately
  along high-contrast edges, because EEVEE's film accumulation sees the view
  exposure. Confirm an exposure picked from saves with a real render
  (`auto_expose` does).

## World, sky and volumes

- **EEVEE draws no sun disc from the Sky Texture** and casts no shadow from
  it. Pair the sky with a sun light from the same direction (the sky
  family's `make_sky` does).
- **The Sky Texture's sun sits at azimuth = `sun_rotation`, from +Y toward
  +X**: rotation 0 puts the glow due +Y, 60° puts it 60° toward +X.
- **A world volume fills everything to infinity**: even a thin one (0.012/m)
  extinguishes the sun and the sky. Fog is a finite volume (a box with a top).
- **EEVEE spreads its volume froxels over the camera's clip range** unless
  `use_volume_custom_range` is on; `volumetric_start` / `volumetric_end` take
  effect only then. Cover the scene's volumes with them, and use a smaller
  `volumetric_tile_size` for a small volume far away
  (`sdf.volume_render_settings()` and `fit_volume_range` set both).
- **The Principled Volume's Density Attribute defaults to `density`.** On a
  volume whose shader already reads its density grid, clear it: the grid
  would multiply absorption and scattering a second time (not emission).
- **`world.use_nodes` is deprecated;** a new world may already have its node
  tree. Check `world.node_tree` before setting it.

## Light, probes and interiors

- **Global illumination is on everywhere**: ray tracing, Fast GI and light
  probes together. An interior holds its light when it is built to: walls,
  floor and ceiling with real thickness, and a volume probe that covers the
  room.
- **A volume probe lays an axis's N samples at (i + 1) / (N + 1) of its
  box**, one spacing in from the faces, and a surface within about 0.75 of a
  spacing of the box's faces, or outside the box, is lit by the world. Reach
  a room's probe past its inside faces, so its outermost samples sit inside
  the walls (`look.lighting.add_room_probe` does, and refuses walls too thin
  for its spacing). A probe is baked once and static: leave animated
  emitters out of the bake and let their real lights move.
- **Thin glass** reads as a pane with `surface_render_method = 'DITHERED'`,
  `use_raytrace_refraction = True`, `thickness_mode = 'SLAB'` and the pane's
  thickness (0.015 for 1.5 cm) into the Material Output's Thickness. A thin
  translucent sheet (a leaf, paper) wants its Thickness linked to 0.
- **EEVEE draws blended objects back to front by their origins' depth along
  the view**; there is no render order. Move an origin to change where an
  object sorts (the city's cloud deck rides far down the camera's view so it
  is drawn first).
- **Light linking ignores an include collection that holds no objects**:
  such a light lights everything. Keep a placeholder in the receivers, or
  exclude the set's own collections as well.
- **EEVEE has no Pointiness.** Bake curvature into an attribute for a
  material that wants edge wear (`voice_machines.write_curvature`).

## Colour

- **AgX (Blender 5.2's OCIO config, Base Contrast, exposure 0):** scene-linear
  0.18 → 117.6 of 255, 1.0 → 196.6, 4 → 233, 8 → 245, 16 → 254.6. A grey
  channel reaches 250 about 6 stops above 18% grey. Punchy puts 0.18 at 88.3.
  Medium High Contrast clips at 8. `look.exposure.mid_grey_luma(scene)` reads
  it for the scene's own view and look.
- **Looks are named by OCIO:** 'AgX - Base Contrast', 'AgX - Punchy', ... The
  enum is dynamic (listing it without a scene returns only 'NONE'); set the
  string.

## VRMs and the VRM add-on

- **The add-on switches the view to Standard on import** unless
  `set_view_transform_to_standard_on_import=False`.
- **A VRM imports facing −Y** (glTF's +Z forward). The humanoid bone mapping
  is snake_case on the add-on's property group (`human_bones.left_foot`); the
  bone names themselves are VRM's camelCase.
- **MToon and shadows:** the add-on's 'MToon 1.0 Output' group mixes in a
  Transparent BSDF by its opacity × Is Camera Ray, so every ray that is not a
  camera ray sees the surface transparent. With the material's
  `use_transparent_shadow` on (Blender 5.2's default), EEVEE's shadow pass
  evaluates that and the character casts no sun shadow. EEVEE's Light Path
  sets Is Shadow Ray in the shadow pass, so the group's opacity read as
  max(Is Camera Ray, Is Shadow Ray) gives the shadow pass the alpha clip the
  camera sees; an opaque material needs no transparency in its shadow
  (`use_transparent_shadow = False`). `load_vrm` does both
  ([characters](characters.md#loading-a-vrm)).

## Rendering

- **EEVEE keeps no history between final renders.** A frame rendered alone
  matches the same frame rendered after its previous frame. Stills can jump
  to any time: no warm-up, no history reset on cuts.
- **Instanced geometry and ray casts:** `scene.ray_cast` hits instances (a
  Geometry Nodes scatter blocks sightlines), and reports a hit as the
  INSTANCED object (the scatter's source, e.g. `grass_medium_02_d`), with the
  instance's matrix as the returned matrix, never as the scatter. To ignore a
  scatter, ignore what it instances: the depsgraph's `object_instances` list
  each instance's `object` and its `parent`, the instancer. BVH clearance tests
  see only real objects. `scene.objects` includes objects in collections
  excluded from the view layer (a scatter's sources), so filter by what
  renders. `look.camera_safety` does both.
- **Probe costs on an RTX 5090 Laptop (960 × 540, 16 samples):**
  - a meadow (a 108k-triangle VRM, about 16,000 scanned grass instances):
    0.4 to 0.8 s a frame;
  - a lit room with its volume probe: about 0.3 s;
  - a hazy stage: 0.2 to 0.3 s;
  - a 29-exposure sweep: one render plus about 3 s of saves.

## Encoding and delivery copies

If a render already contains macroblocking, encoding that MP4 at a higher
bitrate cannot recover the lost detail. Re-render, or encode again from a
higher-quality master if one exists.

Blender renders straight to H.264 (the runner does): `media_type = 'VIDEO'`,
FFMPEG, MPEG4, H264, `constant_rate_factor = 'PERC_LOSSLESS'`, preset GOOD,
GOP 24, chunks starting on a keyframe. Deliver a copy re-encoded by the system
ffmpeg as H.264 High, yuv420p, with AAC sound, so it plays everywhere:

```bash
ffmpeg -i master.mp4 -c:v libx264 -profile:v high -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k delivery.mp4
```

Lower CRF generally means higher quality and a larger file. These values are
starting points, not a guarantee for every resolution or motion pattern.
Review busy areas and gradients in the encoded copy, and retain the master.
Measure where a slow frame's time goes before optimising it.

## Not yet ported

Nothing here waits for a port. The WebGPU engine's own stack notes have no
Blender counterpart and are not carried over: the adapter and doctor checks
of Deno's WebGPU (Blender's GPU check is `eidoblend.harness.gpu_check`),
NodeMaterial against non-node materials, `VolumeNodeMaterial` under Naga,
texture orientation per loader path, VRMs only through `GLTFLoader`,
transparency through alpha opacity, the auto-enhance MRT G-buffer and
transparent quads, depth-keyed screen effects over particle quads, NVENC
bitrates, 16-bit float render targets and readback strides, binding limits,
`_rawRenderAsync`, motion-vector MRT naming, compute-written index buffers,
timestamp queries and the draw count.
