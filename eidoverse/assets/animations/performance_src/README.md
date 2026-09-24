# Performance clips — source

[VRM characters guide](../../../../AGENTS.md) · [Blender guide](../../../../docs/blender.md)

Nineteen hand-authored singing and stage clips (VRM Animation, `.vrma`), made
for the claudesona in the DAISY (DAY'S EYE) music video. They live next to the
other clips in `eidoverse/assets/animations/` and load as `VRMA_SLOTS`, so a
scene plays them by name:

```js
await playVRMADefault(vrm, 'hand_to_heart', { loop: false, fade: 0.4 });
// ...when it has landed, hold the pose:
await playVRMADefault(vrm, 'hand_to_heart_hold', { fade: 0.1 });
```

They are for a stationary VRM (no controller waypoints), like the other
expressive clips. They retarget to other VRM 1.0 humanoids through three-vrm.
They have been checked on `claude_suit_wardrobe.vrm` and `aletheia.vrm`
(`python vrm_turntable.py --vrm <vrm> --outfits - --anim <clip>,<clip>`
renders a clip sheet).

## The clips

All clips are timed in beats at 128 BPM (one beat = 0.46875 s). Loops end
exactly on a beat, so they can be retimed to another tempo with the action's
`timeScale` (`BPM / 128`).

| Clip | Beats | Plays | Use |
| --- | --- | --- | --- |
| `stand_breathe` | 8 | loop | Standing and singing. Use it as the idle between these clips; it shares their foot marks, so crossfades never slide. |
| `sing_gesture_a` (+`_mirror`) | 4 | loop | Presenting something beside her: "this is the machine singing". |
| `sing_gesture_b` | 4 | loop | Singing to the audience. |
| `chorus_sway` | 8 | loop | Singalong sway; also works for a vigil. |
| `sing_open_arms` | 8 | loop | Long notes, choirs, a big finish. |
| `hand_to_heart` → `hand_to_heart_hold` | 5 → 8 | once → loop | A sincere line; the hold starts on the one-shot's last frame. |
| `look_up_sky` → `look_up_sky_hold` | 6 → 8 | once → loop | Dawn, lanterns, a light coming on. |
| `phone_raise` (+`_mirror`) → `_hold` | 4 → 8 | once → loop | Raising a phone light at a vigil, then a slow sway. |
| `head_bow` → `head_bow_hold` | 6 → 8 | once → loop | Mourning, a moment of respect. |
| `wave_goodbye` (+`_mirror`) | 4 | loop | Goodbye to the viewer. |
| `bow_thanks` | 7 | once | A thank-you bow to the audience. |

`_mirror` clips use the other hand toward her other side, from the same stance.
`clips.json` holds each clip's beats, seconds, loop flag and intended use.

## Files

| File | Role |
| --- | --- |
| `build_vrma.py` | The authoring script. Poses are keyed in beats in three-vrm's normalized humanoid frame. Arms and legs are solved by IK every frame (palm target, palm normal, finger direction, elbow pole). Hermite interpolation, `lag` for follow-through and procedural `layers` (breath, sway) are baked at 64 fps and exported with the VRM add-on. Deterministic: same script, same bytes. |
| `check_vrma.py` | Measures a clip without the engine: the loop seam, foot travel (planted toes stay under ~1 mm), elbow, knee and wrist ranges, the fastest bone (pops show as spikes), and hand points entering the claudesona's petals. A flag means "look at this frame"; frames decide. |
| `clips.json` | The manifest `build_vrma.py` maintains. |

## Rebuild or add a clip

From the repository root:

```bash
bash run_blender.sh eidoverse/assets/animations/performance_src/build_vrma.py --clips hand_to_heart,head_bow
python eidoverse/assets/animations/performance_src/check_vrma.py eidoverse/assets/animations/hand_to_heart.vrma
python vrm_turntable.py --anim hand_to_heart --frames body --views 0,90 --hold 60
```

`run_blender.sh` is the isolated headless runner; see the
[Blender guide](../../../../docs/blender.md). A new clip is one `clip(...)` call in `build_vrma.py`:
copy a neighbour, keep the shared `STAND` stance so it crossfades with the
rest, and read the CONVENTIONS block at the top of the script first. Without
`--clips`, every clip is rebuilt except test clips named `zz_*`. The build
report goes to `work/vrma_build_report.txt`.

At 64 fps one beat at 128 BPM is exactly 30 frames. Every key lands on a whole
frame and every loop's last sample equals its first.

## Credits

Authored by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09),
on digi's `claude_suit.vrm` rig (CC-BY; the claudesona design is by voooooogel;
see [CREDITS](../../../../CREDITS.md)). The clips carry no mesh data from the model.
