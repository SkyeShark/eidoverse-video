# Autonomous mode: how an unattended run works

You are running inside the `auto-blender` render image, started by a parent agent with
`python eido_blender.py agent --brief brief.txt`. Nobody will answer questions during the run:
interpret the brief, make the film, and finish with a playable result or a concrete blocker report.
The toolkit itself is the Blender 5.2 EEVEE edition: [AGENTS.md](../AGENTS.md) indexes its guides,
and [docs/TOOLS.md](TOOLS.md) maps every module and tool to its guide. Open the guides your film needs.

## What you are given

| file | what it holds |
|---|---|
| `/workspace/_brief.txt` | the brief: what to make |
| `/workspace/_context.txt` | optional background from the parent (may be absent) |
| `/workspace/_capabilities.json` | what this run can use: `renderer` (`blender-eevee`), `comfyui` and `comfy_url` (music and sound generation through ComfyUI), `jina_ai`, `gpu_adapter` |

Plan audio from `_capabilities.json`: with `comfyui: false`, `generate_song.py` and `generate_sfx.py`
cannot run, so build the mix from narration (`voicebox/`, edge-tts), synthesis (`synthkit/`) and
CC0 foley instead. Never fake a tool call; degrade honestly and say so in your report.

## Where you work

- Everything you make goes in `/workspace/work/<short_id>/`: `scene.json`, `scene.py` (with
  `setup(ctx)` building the world and `render_frame(ctx, t, i)` keying what changes), a `plan.md`
  (the plan, then what you did and anything you could not do), stills and the final `.mp4`.
- The toolkit is mounted read-only (`blender/`, `eidoverse/`, `tools-guides/`, `docs/`, `docker/`,
  `synthkit/`, `voicebox/`, the runners and `AGENTS.md`). Use it; never try to change it.
- The texture and model library (`eidoverse/assets/cache/`) is writable: `fetch_texture.py`,
  `fetch_model.py` and the loaders fetch what a scene asks for on first use.
- `work/bestiary/` is not yours: it holds Creature Creator v2's shipped assets (WIP: realistic
  creatures, humans and accessories as glb files that import into Blender as assets; what each is:
  `eidoverse/bestiary/README.md`). Import them into your scene; never change or move them.

## Props made before the scene

The helicopter is made once into a file, then appended; `setup()` does not build it
(`tools-guides/props-and-sets.md`, "The helicopter"). Make it in your folder, since its default
`work/props/` is not yours (about 3 minutes, before the first still):

```bash
python3 blender/eidoblend/props/helicopter/make.py --out work/<id>/helicopter
```

```python
import os
from eidoblend.props import helicopter
heli = helicopter.build(ctx=ctx, blend=os.path.join(ctx.scene_dir, 'helicopter', 'helicopter.blend'))
heli.group.location = (0.0, 0.0, 70.0)                     # its root: key it to fly
heli.spin(ctx.frame_start, ctx.frame_end, fps=ctx.fps)     # the rotors turning, LINEAR keys
```

- The carbine's chain bakes the high onto the low with `blender/tools/gpu_bake.py` (NVIDIA Warp,
  `warp-lang`, which `docker/Dockerfile` installs; without CUDA in the container Warp bakes on
  its CPU device, slower). If `blender/eidoblend/props/carbine/make.py` stops before the bake
  with exit code 3, your image was built before `warp-lang` was added: say so in `plan.md` and
  keep the rifle out of the shot.

## How you render

Inside the image these run right where you are (no `--local` needed):

```bash
python3 eido_blender.py doctor                              # the GPU renderer, EEVEE, the VRM add-on, ffmpeg
python3 eido_blender.py render work/<id>/scene.json --at 2.5 # one still, to look at before the film
python3 eido_blender.py bench  work/<id>/scene.json          # how long the film will take
python3 eido_blender.py render work/<id>/scene.json          # the film: H.264 + AAC, plus probe frames
```

- Check with stills first (the probe preset: 960x540, 16 samples), and LOOK at them. A passing
  build is not a review.
- Read the build's audit (`<out>.audit.txt`; every check name is explained in
  `tools-guides/render-review.md`) and fix what it flags before rendering the film.
- The first frame of a new scene is slow while EEVEE compiles its shaders; later frames are fast.
- The parent's `--timeout-min` stops the run when time is up: render the film once the stills are
  right, and leave time for it (`bench` tells you how much).

## DLSS 5 is a host step, not yours

If the brief asks for DLSS 5 over the film: it cannot run in this image. `dlss5nr/dlss5nr.py` needs
Windows, an NVIDIA Ada (or newer) GPU with NVIDIA's Vulkan extensions and weights the operator
supplies (tools-guides/postprocessing.md, "DLSS 5 over a finished film"). Render the film as usual and
put the host's commands in `plan.md`, with your film's paths filled in; the collected `.blend` is
all its motion needs:

```bash
bash run_blender.sh blender/tools/render_motion.py --blend work/<id>/scene.blend --out work/<id>/motion
python dlss5nr/dlss5nr.py work/<id>/scene.mp4 work/<id>/scene_dlss5.mp4 --model <weights> --style 1 \
    --motion work/<id>/motion --convention "+X -Y" --offset -1 --cuts work/<id>/motion/cuts.txt
```

(`--offset` is minus the scene's `frame_start`; `render_motion.py` prints the exact `dlss5nr.py`
line when it ends.) Say in `plan.md` that the delivered film is NOT through DLSS 5 yet. Never look
for, download or describe a source of the weights.

## After the film renders

The finishing tools run in the image too (numpy, Pillow, librosa, stable-ts, ffmpeg), on the mp4,
after `merge_av.py`:

```bash
python3 song_clock.py work/<id>/song.wav --out work/<id>/song_clock.json        # beats, bars, lines, in frames
python3 song_clock.py work/<id>/song.wav --offset work/<id>/film.mp4           # 0 ms when the mux is right
python3 film_print.py work/<id>/film.mp4 --out work/<id>/film_print.mp4 --parts 4   # if the brief asks for film
python3 contact_sheet.py work/<id>/film.mp4 --lines --timeline work/<id>/song_clock.json \
    --beats work/<id>/song_clock.json --png
```

- `film_print.py` (a 1970s or 1960s release print) is a look, not a step every film takes: use it when
  the brief wants an old film's print. It runs last, after any neural pass; see
  `tools-guides/postprocessing.md` ("After the render: the release print").
- If the brief asks for DLSS 5 as well, do NOT print the film here: the print goes after DLSS (a
  network would smooth its grain and dirt away), so put the `film_print.py` line in `plan.md` after
  the host's DLSS 5 lines and deliver the unprinted film.
- The line-by-line sheet is the parent's quickest read of a song film: leave it beside the final mp4
  (`--png`, since the parent collects PNGs).
- A singing mouth from a vocal stem: `characters.lipsync.visemes_from_vocal` in the scene
  (`tools-guides/claudesona.md`). `blender/tests/finishing/` is a whole example: copy its
  `scene.json` into `work/<id>/` and point `outputVideo` there, since `blender/` is read-only here.

## How the run ends

- Finish with a playable final `.mp4` in `work/<short_id>/` and a `plan.md` saying what the film is,
  what you used, and anything that fell short.
- If you cannot finish, write the concrete blocker in `plan.md` (the command, the error, what you
  tried) and stop. Exit honestly; the parent reads your exit code.
- The parent collects what this run wrote: `work/**/*.mp4`, `*.png`, `scene.py`, `scene.json`,
  `plan.md` and the built `*.blend`, so it can open the very scene that rendered.

## House rules that matter most here

- EEVEE is the renderer; global illumination stays on, interiors included. When a render looks wrong,
  fix the scene setup (geometry, probes, lights, materials), never the engine.
- Motion is keyed or baked at build time, so any frame renders the same whether jumped to or played.
- Name things in the film for what they are; keep work in `work/<short_id>/`.
