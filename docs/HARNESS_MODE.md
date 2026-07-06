# Harness mode — a model + a human, interactively

The primary way to use Eidoverse day-to-day: open the repo in an
interactive coding agent (Claude Code, codex CLI, opencode — all of them
auto-read `AGENTS.md`, which is the complete contract) and direct it in
conversation.

## Flow

1. **You** describe the video you want — subject, mood, length, music
   direction, anything you care about. That conversation IS the brief.
2. **The agent** plans phases, fetches assets, writes
   `work/<id>/scene.js` + `scene.json`, generates/mixes audio, renders.
   `fetch_hdri.py` / `fetch_texture.py` run fine on the host (they just
   need `requests`); **run `fetch_model.py` inside the container**
   (`python eido.py shell`) — preview rendering and ranking need the
   container toolchain, and a host run degrades (no previews, and
   candidate downloads can pile up unranked).
3. Renders go through the container — or fully locally with `--local`
   (host deno + GPU, several times faster; see docs/SETUP.md §6):
   ```bash
   python eido.py render work/<id>/scene.json --probe   # single frame — framing check
   python eido.py render work/<id>/scene.json           # full render (container)
   python eido.py render work/<id>/scene.json --local   # full render (no docker)
   python eido.py shell                                 # interactive container shell
   ```
4. **You** review the mp4 (and any probe frames) and give notes; the agent
   iterates.

## House rules

- **Probe before you render.** A single-frame `--probe` costs seconds and
  catches framing/lighting/placement problems before a full encode. Any
  number of probes is fine at any time. (It derives a `<scene>_probe.json`
  + `*_probe.mp4` next to your config — both gitignored; delete when done.)
- **One sustained render at a time.** Two concurrent full renders contend
  for the same GPU device and can wedge the driver stack. Probes are
  exempt; full renders queue.
- **The agent's scratch space is `work/<id>/`** (gitignored). Engine files
  under `eidoverse/` are the toolkit — a harness agent CAN edit them (they
  are only ro-mounted in the agentic loop), but treat engine edits as
  deliberate toolkit development, not per-video hacks; per-video code
  belongs in the scene script.
- **Review like a producer.** The bar in `AGENTS.md` ("looks like a real
  produced short") applies; the human eye is the final audit. The engine's
  render-log audits (`[placement]`, `[locomotion]`, `[lipsync]`,
  `[camera]`) are worth reading in the agent's output — a `⚠` line is a
  real defect.

## Tips

- Keep a running character/style sheet in your repo (voice choices, palette,
  recurring props) and paste it into briefs — the toolkit is stateless
  between sessions; continuity comes from you.
- `techniques_archive.md` (repo root) accumulates what worked across
  sessions — agents append to it after each production and can search it
  for prior art.
- For a quick look at what the sample characters look like:
  `eidoverse/assets/vrms/*_preview.jpg`.
