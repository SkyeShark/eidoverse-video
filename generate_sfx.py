"""Headless Stable Audio 3 driver for the ComfyUI workflow in Downloads.

Usage: python generate_sfx.py "<prompt>" <seconds> <category> <out.mp3> [seed]
       python generate_sfx.py --probe    # fail-fast connectivity check (exit 0/1)
Categories: Music | Instrument | SFX | One-shot
"""
import json, sys, time, random, urllib.request, urllib.parse
from pathlib import Path

COMFY = __import__("os").environ.get("COMFYUI_URL") or (
    "http://host.docker.internal:8188" if __import__("os").path.exists("/.dockerenv") else "http://127.0.0.1:8188")

if "--probe" in sys.argv:
    # answer in seconds so agents can rule audio in/out BEFORE planning —
    # _capabilities.json reflects the HOST probe; a container can still
    # fail to reach host.docker.internal
    try:
        urllib.request.urlopen(f"{COMFY}/system_stats", timeout=5)
        print(f"OK: ComfyUI reachable at {COMFY}")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: ComfyUI NOT reachable at {COMFY}: {e}")
        sys.exit(1)
WF_PATH = Path("/workspace/sa3_workflow.json") if Path("/workspace/sa3_workflow.json").exists() else Path.home() / "Downloads" / "audio_stable_audio_3_medium_base.json"

def main():
    # Flags (anywhere in argv):
    #   --raw         bypass the workflow's LLM PROMPT ENHANCER (node 52:35): the
    #                 prompt reaches Stable Audio verbatim. The enhancer rewrites
    #                 the input through a per-category system prompt at temp 0.7 —
    #                 "One-shot" is a MUSIC-SAMPLE brief ("pluck, slam, stab"), so a
    #                 page riffle came back as a sci-fi riser and a book closing as
    #                 a rattling slam. For foley, go raw and structure the prompt
    #                 the way Stability's SFX guide does: "TrackType: SFX." + source
    #                 + action/duration + mic/room/processing.
    #   --neg "<text>" negative prompt (node 52:7; the workflow ships it empty)
    args = [a for a in sys.argv[1:]]
    raw = "--raw" in args
    neg = None
    if "--neg" in args:
        i = args.index("--neg"); neg = args[i + 1]; del args[i:i + 2]
    args = [a for a in args if a != "--raw"]
    prompt, seconds, category, out = args[0], float(args[1]), args[2], args[3]
    seed = int(args[4]) if len(args) > 4 else random.randrange(2**48)
    wf = json.load(open(WF_PATH, encoding="utf-8"))
    wf["52:31"]["inputs"]["value"] = prompt
    wf["52:36"]["inputs"]["value"] = seconds
    cats = ["Music", "Instrument", "SFX", "One-shot"]
    wf["52:43"]["inputs"]["choice"] = category
    wf["52:43"]["inputs"]["index"] = cats.index(category)
    wf["52:3"]["inputs"]["seed"] = seed
    if raw:
        wf["52:35"]["inputs"]["value"] = False      # switch -> on_false = the raw prompt
    if neg is not None:
        wf["52:7"]["inputs"]["text"] = neg
    wf["19"]["inputs"]["filename_prefix"] = "audio/eidoverse_sfx"

    r = urllib.request.urlopen(urllib.request.Request(
        f"{COMFY}/prompt", data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"}), timeout=30)
    pid = json.loads(r.read())["prompt_id"]
    print("queued", pid, flush=True)

    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(3)
        hist = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=15).read())
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            print("ERROR:", json.dumps(status)[:2000]); sys.exit(1)
        outputs = entry.get("outputs", {})
        if outputs:
            for node, o in outputs.items():
                for a in o.get("audio", []):
                    q = urllib.parse.urlencode({"filename": a["filename"],
                                                "subfolder": a.get("subfolder", ""),
                                                "type": a.get("type", "output")})
                    data = urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=60).read()
                    Path(out).write_bytes(data)
                    print(f"saved {out} ({len(data)} bytes) in {time.time()-t0:.0f}s")
                    return
    print("TIMEOUT"); sys.exit(2)

if __name__ == "__main__":
    main()
