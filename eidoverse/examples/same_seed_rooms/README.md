# The SAME SEED rooms, each through its wide camera

[Props and sets guide](../../../docs/props-and-sets.md#the-same-seed-rooms) · [The rooms' files](../../assets/sets/same_seed/README.md)

One scene script, `scene.js`, builds a room from `sets/same_seed.js` and looks
through one of its lenses; each config names the room and the camera:

```bash
python eido.py render eidoverse/examples/same_seed_rooms/sealed_room.json --at 0   # a still: work/same_seed_rooms/
python eido.py render eidoverse/examples/same_seed_rooms/kitchen.json --at 0
python eido.py render eidoverse/examples/same_seed_rooms/lab.json --at 0
python eido.py render eidoverse/examples/same_seed_rooms/desk.json --at 0
```

Change `"camera"` in a config to any of the room's cameras (the guide lists
them). The first render of a room fetches its CC0 sets, Poly Haven models and
HDRI into the shared library; later ones build in 4–12 s.

The script turns bloom off (`globalThis._bloomParams = { strength: 0 }`): the
rooms were lit for a render without it, and their tubes, panels and windows
would haze the frame. The rest of the default post chain (ambient occlusion,
screen-space reflections, anti-aliasing) stays on, as it stands in for what
EEVEE's own did in the Blender renders, and `room.applyTo` sets the tone
mapping Blender used (its AgX, fitted). The guide compares each still with the
Blender edition's from the same camera.
