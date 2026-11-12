# Working together in the studio

The `blender` edition of Eidoverse is a shared studio for an AI filmmaker and
a human collaborator. Open the repo in an interactive coding agent such as
Claude Code, codex CLI or opencode. [AGENTS.md](../AGENTS.md) introduces the
studio and links to its tool guides.

The conversation is the writers' room. Either collaborator can bring an idea,
propose a direction or suggest an experiment. The agent makes artistic choices,
explores the toolkit and develops the work alongside the human.

## Flow

1. **Explore an idea together.** Talk about what you want to make or learn,
   exchange ideas, and develop a direction. A film, a world, a simulation or
   an experiment can begin with either collaborator's curiosity.
2. **Build and experiment.** The agent chooses tools, develops scenes and
   performances, and tries visual and musical ideas. Keep scene configs,
   scripts, assets, sound and studies in `work/<id>/`. Fetchers and audio
   tools run on the host's Python; install the tiers you use from
   `requirements-local.txt` (fetchers need only `requests`).
3. Renders run in Blender on your GPU:
   ```bash
   python eido_blender.py render work/<id>/scene.json --at 4 --at 40   # PNG stills at those seconds, film settings
   python eido_blender.py render work/<id>/scene.json --probe          # the first frame at the probe caps
   python eido_blender.py bench work/<id>/scene.json                   # seconds a frame, and the film's total
   python eido_blender.py render work/<id>/scene.json                  # the film, H.264
   python eido_blender.py open work/<id>/scene.json                    # the built .blend in Blender's window
   ```
4. **Review and develop the work together.** The agent inspects its renders,
   motion and sound, and shares the work and creative decisions. Both
   collaborators can offer observations, propose changes and find new ideas.
   The built `.blend` is the scene itself: either of you can open it, look
   around, and adjust a light or a camera by hand. The runner renders a
   hand-edited `.blend` as it is and never rebuilds over it unasked.

## House rules

- **Stills before you render.** A few `--at` stills cost seconds once the
  scene is built and catch framing, lighting and placement problems before a
  full render. Any number of them is fine at any time. A build is reused
  while its inputs are unchanged, so stills after the first are quick.
- **One render at a time.** Two concurrent renders contend for the same GPU
  and its memory. Builds without a render are lighter, but a heavy scene's
  build bakes on the GPU too.
- **The agent's scratch space is `work/<id>/`** (gitignored). The toolkit is
  `blender/eidoblend/` (and the WebGPU engine's source under `eidoverse/`): an
  agent CAN edit it, but treat those edits as deliberate toolkit development,
  not per-video hacks; per-video code belongs in the scene script.
- **EEVEE as Blender's manual describes it.** When a render looks wrong, fix
  the scene: its geometry, probes, lights, materials and render settings.
  Global illumination stays on, interiors included.
- **Give the work your attention.** [Production](../tools-guides/production.md) and
  [render review](../tools-guides/render-review.md) offer methods for developing and
  reviewing a film. The agent should inspect its own work as well as discussing
  it with the human. Read the audit digest beside each output
  (`<out>.audit.txt`: preflight, placement, motion, framing) and investigate
  its warnings alongside visual review.

## Tips

- Keep shared project notes: ideas, voice choices, palettes, recurring props,
  experiments and creative decisions. Revisit them together when resuming a
  project so its intent and discoveries carry across sessions.
- `techniques_archive.md` (repo root) accumulates what worked across
  sessions — agents append to it after each production and can search it
  for prior art.
- For a quick look at what the sample characters look like:
  `eidoverse/assets/vrms/*_preview.jpg`.
