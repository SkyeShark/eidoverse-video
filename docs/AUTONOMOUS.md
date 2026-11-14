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
