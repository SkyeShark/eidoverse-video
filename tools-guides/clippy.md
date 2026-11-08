# Clippy: paperclip character and morph performances (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md)

`make_clippy` (`blender/eidoblend/characters/clippy.py`, the port of
`eidoverse/clippy.js`) builds the wire, face and paper as one mesh whose shape
keys are his transformations, and exposes his named clip vocabulary: all 43
original Microsoft Agent clips.

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.characters.clippy import make_clippy, CLIPS, MORPHS

clippy = make_clippy(height=1.2, location=(2.0, 1.0, 0.0), rotation=0.0)   # heading deg about +Z; he faces -Y
print(clippy.clips, clippy.morphs)
clippy.play('IdleAtom', 2.0)            # start at scene second 2 (frame = frame_start + 2 * fps)
clippy.bake(1, 240)                     # key every frame: the shape keys and the inner object
```

`play(name, t0)` schedules a clip at scene second `t0`; an unknown name raises
(the WebGPU edition ignored it silently). `play_all(t0, gap)` schedules the
full catalog and returns `(name, start, duration)` rows. Use it for inspection;
choose clips to suit the scene in a finished performance. `current_clip(t)`
reports the active name; `state(t)` returns the weights and the inner transform
the sequencer computes at `t`, without keying.

`bake(f0, f1)` is the WebGPU edition's `update(t)` run once per frame, in order,
and keyed LINEAR: every shape key, and the inner object's scale, position and
rotation for the slide, hop and spin actions (`@scale`, `@hopY`, `@spinY`,
`@slideX`) plus the idle bob, sway and the fidgets between clips. No handler
runs at render time. The objects are a root (`clippy_root`: put world placement
here), its child the inner object the clips move (`clippy_inner`), and the mesh
(`clippy`, scale = height). Schedule every clip first, then bake once: a second
bake replaces the first's actions.

**What is the same as the WebGPU edition.** The geometry is clippy.js's, line for
line: the gem clip's segments (narrow end up, both free ends curled out as
little arms), the ten transformation shapes (atom, pile, floppy, envelope,
printer, wizard, check, vortex, bike, mobile), the pose field (lean, tilt,
squash, curl, and the arms' wave, tap, scratch, point), the parallel-transport
tube with the ghost pinches, the face anchors per shape, the pencil and
headphones tucked away until their keys, and the lined legal-pad page with its
64 × 88 texture. Each of the 31 keys is the whole character re-evaluated with
that one channel at 1, so one key is one transformation; their sliders run
−1 … 1.25, as three's influences are clamped. Materials: chrome (metallic 1,
roughness 0.17), white, black, the page (roughness 0.92, both sides) and the
pencil's yellow.

**What differs.** The spheres and the tube share their seam and pole vertices
(three's SphereGeometry splits its seam), so EEVEE shades them without a
crease; base and keys share the one topology (15,485 vertices).

Inspect the whole clip for ground contact, paper clearance and camera framing:
`blender/tests/characters/test_clippy.py` renders eight clips at their peaks
(RestPose, Greeting, IdleAtom, Writing, CheckingSomething, GetWizardy, Print,
Congratulate) on the studio floor.

## Not yet ported

- `setWeight(n, w)` (a one-frame override in the WebGPU edition, reset by the
  sequencer each update): key the shape key yourself after `bake`.
