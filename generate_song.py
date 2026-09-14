"""Generate a song using MiniMax Music 3 via ComfyUI.

Recommended music generator for Eidoverse. MiniMax Music 3 takes a free-text
caption and optional lyrics. The encoder's generated conditioning length
normally sets the audio latent duration; --seconds overrides that duration.

`max_duration` is a ceiling, not a target or a guarantee of a musical ending.
Describe the intended structure and resolution in the caption, leave room
for the ending, then listen to the actual result before timing the film.

    python3 generate_song.py --probe
    python3 generate_song.py "<caption>" ["<lyrics>"] \
        [--max-duration S] [--seed N] [--steps N] [--cfg F] [--out song.mp3]

Omit lyrics for an instrumental. Put style, instrumentation, tempo and key
in the caption. --probe checks nodes and configured model names without
loading weights or submitting a generation.
"""
import argparse, json, os, sys, time, uuid
from pathlib import Path

import requests

COMFYUI_URL = (os.environ.get("COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")

DIT = "minimax_music3_dit_fp16.safetensors"
TEXT_ENCODER = "minimax_music3_text_encoder_pruned_int8_convrot.safetensors"
VAE = "minimax_music3_dav.safetensors"


def build(caption, lyrics, seed, max_duration, steps, cfg, cfg_scale, top_k, prefix, seconds=None):
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": DIT, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXT_ENCODER, "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "MiniMaxMusic3TextEncode",
              "inputs": {"clip": ["2", 0], "caption": caption, "lyrics": lyrics,
                         "seed": seed, "max_duration": max_duration,
                         "cfg_scale": cfg_scale, "top_k": top_k}},
        # The encoder ESTIMATES a length from the caption and normally feeds it
        # straight to the latent — but it routinely under-reads a long brief
        # (a 90s request came back as 15s), and the latent is the real canvas.
        # `seconds` pins it; leave it None to trust the encoder.
        "5": {"class_type": "EmptyMiniMaxMusic3LatentAudio",
              "inputs": {"seconds": seconds if seconds is not None else ["4", 1],
                         "batch_size": 1}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "euler", "scheduler": "simple",
                         "positive": ["4", 0], "negative": ["6", 0],
                         "latent_image": ["5", 0], "denoise": 1.0}},
        "8": {"class_type": "VAEDecodeAudio",
              "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveAudioMP3",
              "inputs": {"audio": ["8", 0], "filename_prefix": prefix, "quality": "320k"}},
    }


def probe():
    """Check this workflow's nodes and model selections without using the GPU."""
    try:
        response = requests.get(f"{COMFYUI_URL}/object_info", timeout=10)
        response.raise_for_status()
        info = response.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"ERROR: cannot inspect ComfyUI at {COMFYUI_URL}: {error}")
        return 1

    workflow = build("", "", 0, 120, 24, 1.0, 1.5, 50, "audio/probe")
    missing = [f"node: {name}" for name in sorted(
        {node["class_type"] for node in workflow.values()} - info.keys())]
    for node, field, value in (
        ("UNETLoader", "unet_name", DIT),
        ("CLIPLoader", "clip_name", TEXT_ENCODER),
        ("CLIPLoader", "type", "minimax"),
        ("VAELoader", "vae_name", VAE),
    ):
        if node not in info:
            continue
        spec = info[node].get("input", {}).get("required", {}).get(field, [])
        choices = spec[0] if spec and isinstance(spec[0], list) else (
            spec[1].get("options", []) if len(spec) > 1 else [])
        if value not in choices:
            missing.append(f"{node}.{field}: {value}")
    if missing:
        print(f"ERROR: ComfyUI is reachable at {COMFYUI_URL}, but MiniMax Music 3 needs:")
        for item in missing:
            print(f"  {item}")
        print("See tools-guides/audio.md for model locations and setup.")
        return 1
    print(f"OK: MiniMax Music 3 nodes and configured models found at {COMFYUI_URL}")
    print("No generation queued. Weight loading and GPU capacity still need a real generation test.")
    return 0


def generate_song(tags, lyrics="", bpm=None, key=None, seed=None, *,
                  max_duration=120.0, steps=24, cfg=1.0, cfg_scale=1.5,
                  top_k=50, out="song.mp3", timeout_s=900, seconds=None):
    """Generate MiniMax music; tags describe the caption, with optional tempo/key guidance."""
    caption = caption_with_controls(tags, bpm, key)
    if seed is None:
        seed = int(time.time()) % 2**31
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    prefix = f"audio/minimax_{uuid.uuid4().hex[:8]}"
    wf = build(caption, lyrics, seed, max_duration, steps, cfg, cfg_scale, top_k, prefix, seconds)

    print(f"MiniMax Music 3 | seed={seed} max_duration={max_duration}s steps={steps} latent={seconds or 'auto'}")
    print(f"caption: {caption[:120]}...")
    print(f"lyrics : {'(instrumental)' if not lyrics.strip() else str(len(lyrics)) + ' chars'}")
    try:
        r = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": wf}, timeout=15)
        if r.status_code != 200:
            print(f"ERROR: ComfyUI rejected the workflow ({r.status_code}):\n{r.text[:800]}")
            sys.exit(1)
        pid = r.json()["prompt_id"]
    except requests.exceptions.RequestException as e:
        print(f"ERROR: cannot reach ComfyUI at {COMFYUI_URL}: {e}")
        print("Start ComfyUI (or set COMFYUI_URL) — do not retry in a loop.")
        sys.exit(1)
    print(f"queued: {pid}\nwaiting", end="", flush=True)

    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(2)
        try:
            response = requests.get(f"{COMFYUI_URL}/history/{pid}", timeout=10)
            response.raise_for_status()
            hist = response.json()
        except requests.exceptions.RequestException:
            continue
        if pid not in hist:
            print(".", end="", flush=True)
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            print("\nERROR: generation failed")
            for m in status.get("messages", [])[-4:]:
                print("  ", str(m)[:400])
            sys.exit(1)
        audio = (entry.get("outputs", {}).get("9", {}) or {}).get("audio", [])
        if audio:
            fn, sub = audio[0]["filename"], audio[0].get("subfolder", "")
            params = {"filename": fn, "type": "output"}
            if sub:
                params["subfolder"] = sub
            try:
                response = requests.get(f"{COMFYUI_URL}/view", params=params, timeout=120)
                response.raise_for_status()
                data = response.content
                if not data:
                    raise ValueError("ComfyUI returned an empty audio file")
            except (requests.exceptions.RequestException, ValueError) as error:
                print(f"\nERROR: audio download failed for prompt {pid}: {error}")
                sys.exit(1)
            with open(out, "wb") as f:
                f.write(data)
            print(f"\nsaved {out} ({len(data)} bytes) in {time.time()-t0:.0f}s")
            return out
        print(".", end="", flush=True)

    print(f"\nERROR: timed out after {timeout_s}s; prompt {pid} may still be running in ComfyUI.")
    print("Inspect its queue/history before submitting another generation.")
    sys.exit(1)


def caption_with_controls(caption, bpm=None, key=None):
    """Express tempo/key controls as MiniMax caption guidance."""
    parts = [caption]
    if bpm is not None:
        parts.append(f"{bpm} BPM")
    if key is not None:
        parts.append(f"Key: {key}")
    return "; ".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate a song with MiniMax Music 3")
    p.add_argument("caption", nargs="?", help="style, instruments, tempo, key and structure")
    p.add_argument("lyrics", nargs="?", default="", help="sung words; omit for instrumental")
    p.add_argument("--probe", action="store_true", help="check nodes/models without generating audio")
    p.add_argument("--max-duration", type=float, default=120.0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--bpm", type=int, default=None, help="append a tempo request to the caption")
    p.add_argument("--key", default=None, help="append a musical key request to the caption")
    p.add_argument("--steps", type=int, default=24)
    p.add_argument("--cfg", type=float, default=1.0)
    p.add_argument("--cfg-scale", type=float, default=1.5)
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--seconds", type=float, default=None,
                   help="pin the latent length in seconds (overrides the encoder estimate)")
    p.add_argument("--out", default="song.mp3")
    p.add_argument("--timeout", type=float, default=900, help="maximum queue/generation wait in seconds")
    a = p.parse_args(argv)
    if a.probe:
        return probe()
    if a.caption is None:
        p.error("caption is required unless using --probe")
    generate_song(a.caption, a.lyrics, bpm=a.bpm, key=a.key, seed=a.seed,
                  max_duration=a.max_duration, steps=a.steps, cfg=a.cfg,
                  cfg_scale=a.cfg_scale, top_k=a.top_k, out=a.out,
                  timeout_s=a.timeout, seconds=a.seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
