# Working together in the studio

The `main` edition of Eidoverse is a shared studio for an AI filmmaker and a
human collaborator. Open the repo in an interactive coding agent such as
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
   performances, and tries visual and musical ideas. Keep scene scripts,
   assets, sound and studies in `work/<id>/`. Fetchers and audio tools run
   on the host; install the tiers you use from `requirements-local.txt`
   (fetchers need only `requests`).
3. Renders run natively on your GPU:
   ```bash
   python eido.py render work/<id>/scene.json --probe   # single frame — framing check
   python eido.py render work/<id>/scene.json --at 40   # the frame at 40 s, as a PNG
   python eido.py render work/<id>/scene.json           # full render
   ```
4. **Review and develop the work together.** The agent inspects its renders,
   motion and sound, and shares the work and creative decisions. Both
   collaborators can offer observations, propose changes and find new ideas.

## House rules

- **Probe before you render.** A single-frame `--probe` costs seconds and
  catches framing/lighting/placement problems before a full encode. Any
  number of probes is fine at any time. (It derives a `<scene>_probe.json`
  + `*_probe.mp4` next to your config — both gitignored; delete when done.)
- **One sustained render at a time.** Two concurrent full renders contend
  for the same GPU device and can wedge the driver stack. Probes are
  exempt; full renders queue.
- **The agent's scratch space is `work/<id>/`** (gitignored). Engine files
  under `eidoverse/` are the toolkit — an agent CAN edit them, but treat
  engine edits as deliberate toolkit development, not per-video hacks;
  per-video code belongs in the scene script.
- **Give the work your attention.** [Production](../tools-guides/production.md) and
  [render review](../tools-guides/render-review.md) offer methods for developing and
  reviewing a film. The agent should inspect its own work as well as discussing
  it with the human. Read the engine's `[placement]`, `[locomotion]`, `[lipsync]`
  and `[camera]` diagnostics and investigate warnings alongside visual review.

## Tips

- Keep shared project notes: ideas, voice choices, palettes, recurring props,
  experiments and creative decisions. Revisit them together when resuming a
  project so its intent and discoveries carry across sessions.
- `techniques_archive.md` (repo root) accumulates what worked across
  sessions — agents append to it after each production and can search it
  for prior art.
- For a quick look at what the sample characters look like:
  `eidoverse/assets/vrms/*_preview.jpg`.
