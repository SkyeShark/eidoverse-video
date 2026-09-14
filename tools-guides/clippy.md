# Clippy: paperclip character and morph performances

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

`makeClippy` is injected by the renderer. It constructs the wire, face and
paper with compatible morph targets and exposes a named clip vocabulary.

```js
const clippy = makeClippy({height: 1.2});
const placement = new THREE.Group();
placement.position.set(2, 0, -1);
placement.add(clippy.group);
_s.add(placement);
console.log(clippy.clips, clippy.morphs);
clippy.play('IdleAtom', 2); // start at media time 2 seconds
// In renderFrame(t): clippy.update(t);
```

`play(name, startTime)` schedules a clip; an omitted start uses the current
animation time. Validate names against `.clips` because an unknown name is
ignored by the current implementation. `playAll(startTime, gap)` schedules the
full catalog and returns `[name, start, duration]` rows. Use it for inspection;
choose clips to suit the scene in a finished performance.

`currentClip(t)` reports the active name. `.morphs` lists available pose,
expression and shape channels. The sequencer resets weights during each
`update`, so `setWeight` is not a persistent override of a running clip.

Call `update(t)` once per frame. It owns the inner group's scale, position and
rotation for slide, hop and spin actions; put world placement on an outer
group as above. It is not auto-updated by the renderer. Inspect the whole clip
for ground contact, paper clearance and camera framing.
