# Cloth — create_cloth_panel

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

`eidoblend.fx.cloth` ports the engine's mass-spring cloth panels
(`cloth_sim.js`) for flags, banners, curtains, capes and hanging fabric. Pin
any edge or corners; wind, gravity, and box, sphere, floor or mesh
collision are supported. The solver is the engine's kernel in numpy:

- each vertex averages its corrections over 12 springs (structural, shear,
  bend), with the anti-streak ramp capped at 0.85;
- Verlet integration with damping and a velocity clamp of 0.45 spacings per
  step;
- wind and gravity are per-step impulses;
- colliders keep a skin of `thickness` between cloth and surface.

`bake()` writes a `.pc2` point cache. A Mesh Cache modifier plays it, with
Subdivision Surface and smooth shading on top, so lit folds shade smoothly
and the `.blend` needs no Python at render time.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.cloth import create_cloth_panel

cloth = create_cloth_panel(
    name='banner', material=fabric, location=(0, 0, 2.2),   # the panel hangs in XZ, its face looks along -Y
    width=3, height=2.2, cols=36, rows=28,
    pin='top',              # 'top' | 'top-corners' | 'left' | 'none' | [vertex ids] | f(col, row) -> bool
    wind=0.0004,            # GUST strength: 0.001 is already a strong gale
    wind_bias=0.15,         # constant-push fraction of wind (see recipes)
    wind_dir=(0, -1, 0),    # push direction, Blender axes (the engine's panel +Z face is Blender -Y)
    floor=0.0)              # ground plane: fabric won't sink through
cloth.collide_with([booth, table])                       # fabric respects scene geometry
cloth.collide_with([character], as_sphere=True, track=True)
cloth.settle(60)                                         # pre-roll so frame 1 shows DRAPED fabric
cloth.bake(1, 240, controls=lambda frame, t, c: c.set_pin_position(0, (x, y, z)))
```

The probe `blender/tests/fx/test_cloth.py` is the two recipes below: a
banner draping over a ball and a flag streaming from a pole. The bake takes
0.3 s for 90 frames of both.

**Collision is opt-in: a cloth collides with nothing until
`collide_with([...])` registers geometry.** If the fabric hangs near
anything (a wall, ribs or battens, a sign, a pole, a booth, a screen frame,
a character), register it. Otherwise the cloth sways and billows straight
through whatever is behind it, the single most common cloth defect. A
top-pinned cloth flutters several centimetres, so give it clearance *and*
register the collider; the skin then holds it proud.

`collide_with` derives box colliders from the objects' bounds by default.
`as_sphere=True` makes spheres for round things, up to 8 boxes and 8
spheres. `mode='mesh'` collides against the evaluated mesh itself: the
nearest-surface push-out through a BVH tree, for shapes a box flatters.
The cloth rests `thickness` (default 3 cm, the collision skin) proud of
every collider. Raise it for thick or heavy fabric, or for coarse cloth
that still pokes through. For a cape or flag on a moving character or
prop, pass `track=True`: colliders re-derive every step. Collision resolves
at vertex resolution, so for a thin protrusion (a pole) keep `cols` and
`rows` high or raise `thickness`. Register colliders before `settle()`, so
the pre-roll drapes over them.

**The fabric.** `material=` is the panel's material. Without one the panel
gets the engine's default fabric, `fabric_material()`: base colour
`0xcccccc` (linear 0.604), roughness 0.6, metalness 0, both faces drawn.
`cloth.material` is the material in use.

**Text or a logo goes on the fabric itself**: hand the graphic to the panel
as `map=` (or `texture=`, the engine's other name for it). It rides the
folds and sway because the panel's `UVMap` is intact, top row of the
graphic along the panel's top edge, read from the front (−Y). A separate
rigid plane floated in front of the cloth detaches, z-fights, and doesn't
move with the fabric.

```python
from eidoblend.media.raster import Canvas

art = Canvas(1024, 512, ss=2, background='#16141d')
art.text_fit('EIDOVERSE', x=art.w / 2, y=art.h * 0.3, max_width=art.w * 0.86, font='Anton', px=260,
             fill='#f4efe6')
banner = create_cloth_panel(name='banner', map=art, width=3, height=1.5, location=(0, 0, 2.3))
flag = create_cloth_panel(name='flag', texture='//flags/harbour.png', material=flag_cloth, pin='left')
```

`map` takes a `bpy` Image, an image file path (loaded as sRGB), a
`media.raster.Canvas`, a PIL image, or an (h, w, 3 or 4) uint8 array with
its top row first. As in the engine, the graphic multiplies the
material's base colour (three's `color × map`): on the default fabric it
shows at 0.6 of its brightness, so for the graphic's own colours give a
white material. The alpha is not used: the cloth stays opaque. The map
goes on only where nothing feeds the Principled BSDF's Base Color yet
(three set `mat.map` only when the material had none), and a material with
no Principled BSDF refuses it. `apply_decal(material, graphic)` does the
same to any material.
`blender/tests/fx/test_cloth_map.py` checks all of it, and renders a
painted banner draped over a ball beside a plain panel and a banner on its
own material with a file texture.

**Pick wind by what the fabric is doing**: a hanging banner is not a flag.
- Hanging banner, tapestry or curtain: `wind` 0.0003–0.0006, `wind_bias`
  0–0.2, settle 60. It drapes and sways. Cranking the wind "to add life"
  blows it horizontal toward `wind_dir`, and the banner streams at the
  viewer as stretched streaks.
- Streaming flag: `wind` 0.0006–0.001, `wind_bias` 0.8–1.0, `wind_dir`
  pointed where it should stream. Give `wind_dir` a component across the
  flag's plane, as `(1, -0.4, 0)` does for a flag in XZ. Wind exactly in
  the flag's own plane exerts no force out of it, and the deterministic
  solver never breaks that symmetry, so the flag stays flat.

**Time.** The engine's `step()` advanced 1/60 s per call, and scenes called
it once per frame, so the cloth's speed followed the frame rate. The
recipes above were tuned that way. `steps_per_frame=1`, the default, keeps
their meaning. `steps_per_second=60` makes the motion frame-rate
independent; at 30 fps it runs twice as fast as the engine did.

**Place flags with the stream in mind.** `pin='left'` hangs the panel off
its pole. The wind carries the free end a full panel-length along
`wind_dir`, and the cloth also drapes to near ground level below the pin.
Budget that whole swept volume when placing: a pole 2 m upwind of a
showpiece drapes the flag over it. Frame it like any prop. A flag near the
dwell camera fills the shot with fabric, and one parked behind the camera
disappears from the scene. If a shot needs the flag out of the way, move
the pole (a scene decision) rather than adjusting the sim.

The engine's kernel read its neighbours from the same buffer it was
writing, so a GPU race added noise to every pass. This port is truly
Jacobi: every pass reads the previous pass's positions, and a bake repeats
exactly.

## Not yet ported

- `setPinPosition` from a bone or object without a `controls` callback
  (for example `pin_to=armature_bone`). Today you move pins yourself each
  frame in `controls`, in the panel's local space.
- Self-collision. The engine had none either. For garments that fold onto
  themselves, Blender's own Cloth modifier is the explicit opt-in. Its
  units differ from these recipes.
