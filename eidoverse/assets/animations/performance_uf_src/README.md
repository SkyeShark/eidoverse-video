# Performance clips, UNKNOWN FORCE — source

[VRM characters guide](../../../../AGENTS.md) · [DAISY's clips](../performance_src/README.md) · [Blender guide](../../../../docs/blender.md)

Fifteen hand-authored clips (VRM Animation, `.vrma`) for the claudesona in the tuta, made for the UNKNOWN FORCE music
video (2026-10) at **92.90 BPM**: one beat = 0.64584 s, a bar = 2.58336 s. They live next to the other clips in
`eidoverse/assets/animations/` and load as `VRMA_SLOTS`, so a scene plays them by name:

```js
await playVRMADefault(vrm, 'turn_it_down', { loop: false, fade: 0.3 });
// when it has landed (2.583 s), the hold starts exactly on its last frame: a hard cut
await playVRMADefault(vrm, 'turn_it_down_hold', { loop: true, fade: 0 });
```

The register is darker and smaller than DAISY's: grounded, slow, minimal; calm and unbothered, never pleading. They
share DAISY's stance (the same foot marks, planted by leg IK), so they crossfade with DAISY's performance clips
without sliding. The table of clips, their beats and uses is in the
[characters guide](../../../../AGENTS.md).

## Files

| File | Role |
| --- | --- |
| `build_vrma.py` | The authoring script: DAISY's builder (the same IK, hand library, stance and interpolation) with three additions: `arm(..., space='world')` keys a hand where it should be in the world at that key, converted through the key's own torso pose (hands that hang by gravity while the chest arches; a palm offered to the lens); `lockL` / `lockR` weights with `clip(..., lock={...})` re-solve an arm by IK every sample to a fixed world target, like the legs, so breathing cannot slide a hand that holds something (the fence); `clip(..., hang='LR')` keeps those arms out of the breath, nod and roll layers, so they hang by gravity. New layers `breath(period, amp, steady_head)`, `nods(at, every, …)`, `shoulder_roll(period, …)`; new hand shapes `press`, `stop`, `salute`, `hook`, `offer`, `cup` (`--clips zz_hands` builds a test clip of them). Sampled at 40 samples per beat, so beat k is exactly sample 40k and every loop's last sample equals its first. Deterministic. |
| `check_vrma.py` | Measures a clip without the engine, by forward kinematics on its own rest skeleton: the loop seam, toe and ankle travel, elbow, knee and wrist ranges, the fastest bone, DAISY's disc model of the petal ring, and two more: **the mesh** (the tuta's rest vertices with their skin weights, skinned by the clip's FK every other sample: the closest any hand point comes to a petal, flagged under 3.5 cm, and to the body surface, flagged under 1.5 cm or inside) and **the gaze** (elevation, azimuth) with **palm drift** over a loop. One-shot → hold junctions are measured bone by bone. |
| `rig/dump_rig.py` | Writes `rig/rig_points.npz`, the mesh data the checker skins: the petals and the visible body surface of `claude_suit_wardrobe.vrm` in the normalized frame, each vertex with its normal and four strongest weights re-assigned to humanoid bones. |
| `rig/rig_points.npz` | That data (3.2 MB). Rebuild it when the VRM's body changes. |
| `clips.json` | The manifest `build_vrma.py` maintains: file, beats, seconds, loop, section, notes, samples, bpm; `fence_hands` also carries the fence plane. |

## Rebuild, check, add a clip

From the repository root:

```bash
bash run_blender.sh eidoverse/assets/animations/performance_uf_src/build_vrma.py                     # all 15, about 70 s
bash run_blender.sh eidoverse/assets/animations/performance_uf_src/build_vrma.py --clips dark_groove
python eidoverse/assets/animations/performance_uf_src/check_vrma.py eidoverse/assets/animations/dark_groove.vrma
python vrm_turntable.py --anim dark_groove --frames body --views 0,90 --hold 60
```

`run_blender.sh` is the isolated headless runner (see the [Blender guide](../../../../docs/blender.md)); the
build imports `eidoverse/assets/vrms/claude_suit_wardrobe.vrm` and needs the VRM add-on. It writes the `.vrma` files to
`eidoverse/assets/animations/`, `clips.json` here, and its report to `work/vrma_build_report_uf.txt` (elbow, forearm
twist, wrist swing and reach per key; `^^^` when a key leaves the comfortable range, `!!!` when a foot would lift).
Without `--clips` every clip is rebuilt except the `zz_*` tests; none of these names clashes with another slot.

A new clip is one `clip(...)` call: copy a neighbour, key it in beats on the shared `STAND`, read the CONVENTIONS
block at the top of the script, build only that clip, run the checker, then look at frames 10 onward in the engine.
For another tempo, change `BEAT` (the clips are keyed in beats) or play these with the action's
`timeScale = BPM / 92.9`.

## What was verified (2026-10-02)

- Every loop seam 0.000° and 0.00 mm at the hips; every one-shot → hold junction 0.000°; toes travel ≤ 0.39 mm
  (`dark_groove`'s ankles 1.8 mm are its peeling heel).
- No flags from the disc model or the mesh: the closest hand to a petal is 7.7 cm (`salute_abort` at its stop), to the
  body 2.7 cm (`dark_groove`'s hanging thumbs). Elbows 12–110°, wrists ≤ 49°.
- Gaze: `look_up` ends at 50.0°, its hold travels 49–51° high and −36…+44° around; `ask_me` holds 0.0°. The fence
  palms drift 0.0 mm over the hold.
- By eye in the engine, every clip from three views at 92.90 BPM with a click.

## Limits

- The petals are springs at runtime; the mesh test uses their rest shape. From some angles the raised hand of
  `not_that` or `salute_abort` overlaps a petal in projection while 8–15 cm in front of it.
- `not_that` has to rise, show the palm and drop in two beats, so the lift is brisk (the forearm peaks near 480°/s).
- `fence_hands` hooks the fingers through a plane at z = 0.372 film metres (scale 0.87); wires elsewhere make the
  fingers float or clip.
- Palm-up poses (`ask_me`, `sing_low`) need about 90° of supination on one forearm bone (the rig has no twist bones);
  the sleeve hides it.
- No expression tracks: the mouth plates belong to the scene's lipsync. The legs are solved for flat ground.
- The engine's `idle`, `talk` and `dance` have a different stance: crossfading to or from them slides the feet a
  little. `still_breathe` is the matching neutral.

## Credits

Authored by Claude (Opus 5.5) with Skye for UNKNOWN FORCE, on digi's claudesona rig (CC-BY; the claudesona design is
by voooooogel; see [CREDITS](../../../../CREDITS.md)). The clips carry no mesh data from the model;
`rig/rig_points.npz` holds rest vertices of `claude_suit_wardrobe.vrm` (CC-BY, a derivative of digi's model) for the
checker.
