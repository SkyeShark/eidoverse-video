# Production planning

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Use this guide when you choose to develop a complete film. Begin with the
idea you want to explore and the conversation with your collaborator. Bring
your own proposals and artistic judgment as you develop its form, scope,
rhythm and creative direction together.

The studio also supports open-ended experiments, visual studies, simulations
and exploration of its tools. The suggestions below help shape a complete
film when that is what you are making.

## Choose the runtime and arc

Choose duration from the idea and the conversation. Ranges such as 45–90
seconds for landscape or 60–120 seconds for portrait can help estimate work,
but are not format requirements. A music video might cover a whole song or
an intentional excerpt. Match the render to the chosen edit and soundtrack.

A four-to-six-phase arc is one planning recipe: establish, develop, reach a
turning point, resolve. A loop, sustained shot or non-narrative progression
can use another structure. Sketch the important changes in performance,
camera, composition, light or state so the timing serves the piece.

For narrated work, place lines where they contribute and leave room to listen.
Music-led pieces can tell their story without narration; silence can also be
part of the sound design. [audio.md](audio.md) covers timing and mixing.

## Build a complete setting

Treat your central characters, objects and ideas as anchors in a world.
Choose the surroundings,
materials, props, light, camera and motion that make those anchors meaningful.
For a spatial setting, one useful sequence is:

1. Terrain/floor and the enclosing architecture or visible sky.
2. A few strong silhouettes that establish the location.
3. Midground props placed in meaningful clusters with contact helpers.
4. Foreground details, clutter or vegetation that add depth.
5. Atmosphere, fill/rim light and motion appropriate to the setting.

Keep foreground, midground and background readable. Search the asset library
before building recognizable props out of primitives. Read previews, reuse
local assets in place, and assemble parts from compatible kits. Dense dressing
still needs clear composition and intended physical contact. A sparse or
abstract stage can omit a ground or horizon; review whether its lighting and
spatial cues produce the intended image.

Use the studio's own systems for what they make: the sky family's `make_sky`
for a sky, SeedThree for trees, the terrain and flora families for ground and
plants. A photo HDRI is lookdev light, not a sky; a stock default tree is not
SeedThree. When a system you need is in a guide's *Not yet ported* list, say
so and port it, or choose another way to tell the beat.

A street's buildings can show lit rooms behind their windows without a room
modelled for each: interior-mapped windows render one room picture with
parallax behind a flat pane ([assets](assets.md#interior-windows)). Signs,
labels and HUD panels styled like a web page are `html_mesh` planes
([assets](assets.md#ui-panels-html_mesh)).

## Choose techniques for specific beats

The whole toolkit is available; select what the story benefits from:

| Story purpose | Useful systems |
| --- | --- |
| A character moves, acts or speaks | [VRM characters](characters.md), [creatures](creatures.md), [Clippy](clippy.md), [audio](audio.md) |
| A place changes over time | [Sky/weather](sky-weather.md), [vegetation](vegetation.md), [terrain/surfaces](terrain-surfaces.md) |
| Matter flows, moves or transforms | [Liquids](liquids.md), [3D water](free-surface-water.md), [fire](volume-fire.md), [cloth](cloth.md), [SDFs](sdf-volumes.md) |
| A transition carries a visual idea | [Particle morphs](particles-fx.md), [curve/loft geometry](geometry.md), [post effects](postprocessing.md) |
| Objects perform a process | [Modular robotics and G430 fabrication](robotics.md), [book/page rigs](books.md) |
| Information becomes part of the film | [Screens, typography, subtitles and overlays](motion-graphics.md), [CSS-styled panels](assets.md#ui-panels-html_mesh), the [overlay layer](scene-format.md#the-post-stack-its-hooks-and-the-overlay-layer) |

Combine systems when they reinforce the action. Examples show wiring, not a
required subject or aesthetic: change their palette, scene, parameters, props
and camera for your own piece. When a featured character is meant to perform,
animate them rather than hiding them behind effects for the whole film.

## Plan the render

EEVEE renders film quality at sane times; real time is not the target. Know
the cost before committing to a length:

```bash
python eido_blender.py render work/<id>/scene.json --at 3 --at 21 --at 40   # stills at the key beats
python eido_blender.py bench work/<id>/scene.json                           # seconds a frame, and the total
python eido_blender.py render work/<id>/scene.json --probe --frames 48      # two seconds of motion, probe caps
python eido_blender.py render work/<id>/scene.json                          # the film
```

`--at` stills render at the film's settings, so a still you approve is the
frame the film will have. A post effect that reads earlier frames has those
frames rendered first: the era looks' CRT persistence its last seven, an
after_image trail its whole shot up to the still, which costs that much render
time ([scene format](scene-format.md#outputs)). `--probe` applies the probe
caps (at most 960x540, 16 samples) for checking motion cheaply. For scale: the pipeline's example
room renders 960x540 at 16 samples in about 0.2 s a frame; a lit interior at
1920x1080 with volumetric haze at 32 samples takes about 2.5 s a frame.
Volumes, many lights and dense hair or foliage cost the most; `bench` tells
you what your scene costs. Sound is muxed after the render with `merge_av.py`.

A film render prints `[eido_blender] frame i/N at t=…` every 15 frames. The
WebGPU edition's encoder controls carry over as environment variables on
Blender's own writer: `RENDER_CQ=19` (a constant quality: lower is better and
bigger), `RENDER_BITRATE=20M` (a constant target), and `RENDER_CODEC`
(`libx264` / `h264_nvenc` mean H.264 here, `hevc` H.265, `av1` AV1; Blender
has no NVENC writer, so the choice is the codec, not the hardware). Without
them the film is near-lossless H.264.

The digest's `palette` line lists what the scene used: objects, materials,
lights and the families it imported. A production of 15 s or more that used
no showpiece family (particles, particle morph, liquids, cloth, lofts,
terrain, SeedThree) also gets `palette.showpiece`: the flagship its content
asks for, read from its object and material names and a `_brief.txt` beside
`scene.json` (a bar with a coffee mug and no pour gets the liquid). It is
information for your judgment, never a re-render demand.

## Review and record

Probe the key beats, inspect complete motion, listen to the mix and read the
audit reports using [render-review.md](render-review.md). Review the work
yourself and share it with your collaborator. Discuss what is working, what
you want to change, and what you discovered while making it. Keep the creative
intention in view as you refine the piece, and describe limitations accurately.
The built `.blend` is part of the work: `python eido_blender.py open` shows
your collaborator the very scene that rendered.

Append reusable findings to the root `techniques_archive.md`; search it by
topic and never overwrite it. Correct the relevant tool guide when a lesson
changes how that system should be used.

## Not yet ported

- Nothing this guide described in the WebGPU edition is missing; its render
  plan is new here. The systems the table above points to are ported family
  by family: before planning a beat on one, read the *Not yet ported* list at
  the end of its guide.
- `merge_av.py`, the WebGPU edition's muxer, is used as it is on the H.264
  this edition writes; the pipeline suites do not test it.
- `RENDER_CQ` becomes Blender's custom CRF (`custom_constant_rate_factor`),
  an x264 CRF; the WebGPU edition passed the same number to NVENC's `-cq`,
  whose scale differs a little. The pipeline2 suite checks the setting, not
  the encoded quality.
