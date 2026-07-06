"""Generate a song using ACE-Step 1.5 via ComfyUI API.

Usage:
    python3 generate_song.py "genre tags" "timestamped lyrics" [--bpm 120] [--key "C major"] [--seed 42]
    python3 generate_song.py --probe     # fail-fast connectivity check (exit 0/1)

Outputs: song.mp3 in the current directory.
Requires ComfyUI running on the host with ACE-Step 1.5 loaded.

Run `--probe` FIRST (it answers in seconds) before planning a production
around music — _capabilities.json reflects the HOST-side probe, and a
container can still fail to reach host.docker.internal.
"""
import requests
import json
import sys
import time
import argparse
import os
import uuid

COMFYUI_URL = os.environ.get("COMFYUI_URL") or (
    "http://host.docker.internal:8188" if os.path.exists("/.dockerenv") else "http://127.0.0.1:8188")


def probe():
    """Fail-fast reachability check from WHEREVER this runs (host or container)."""
    try:
        r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        r.raise_for_status()
        print(f"OK: ComfyUI reachable at {COMFYUI_URL}")
        return 0
    except Exception as e:  # noqa: BLE001 — any failure means "no audio backend"
        print(f"ERROR: ComfyUI NOT reachable at {COMFYUI_URL}: {e}")
        print("Music/SFX generation is unavailable — plan the production without generated audio.")
        return 1


if "--probe" in sys.argv:
    sys.exit(probe())

# ACE-Step 1.5 split workflow template
WORKFLOW = {
    "3": {
        "inputs": {
            "seed": 42,
            "steps": 8,
            "cfg": 1,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1,
            "model": ["78", 0],
            "positive": ["94", 0],
            "negative": ["47", 0],
            "latent_image": ["98", 0]
        },
        "class_type": "KSampler"
    },
    "18": {
        "inputs": {"samples": ["3", 0], "vae": ["106", 0]},
        "class_type": "VAEDecodeAudio"
    },
    "47": {
        "inputs": {"conditioning": ["94", 0]},
        "class_type": "ConditioningZeroOut"
    },
    "78": {
        "inputs": {"shift": 3, "model": ["104", 0]},
        "class_type": "ModelSamplingAuraFlow"
    },
    "94": {
        "inputs": {
            "tags": "",
            "lyrics": "",
            "seed": 42,
            "bpm": 120,
            "duration": 120,
            "timesignature": "4",
            "language": "en",
            "keyscale": "C major",
            "generate_audio_codes": True,
            "cfg_scale": 2,
            "temperature": 0.85,
            "top_p": 0.9,
            "top_k": 0,
            "min_p": 0,
            "clip": ["105", 0]
        },
        "class_type": "TextEncodeAceStepAudio1.5"
    },
    "98": {
        "inputs": {"seconds": 120, "batch_size": 1},
        "class_type": "EmptyAceStep1.5LatentAudio"
    },
    "104": {
        "inputs": {
            "unet_name": "acestep_v1.5_turbo.safetensors",
            "weight_dtype": "default"
        },
        "class_type": "UNETLoader"
    },
    "105": {
        "inputs": {
            "clip_name1": "qwen_0.6b_ace15.safetensors",
            "clip_name2": "qwen_1.7b_ace15.safetensors",
            "type": "ace",
            "device": "default"
        },
        "class_type": "DualCLIPLoader"
    },
    "106": {
        "inputs": {"vae_name": "ace_1.5_vae.safetensors"},
        "class_type": "VAELoader"
    },
    "107": {
        "inputs": {
            "filename_prefix": "audio/eido_song",
            "quality": "V0",
            "audio": ["18", 0]
        },
        "class_type": "SaveAudioMP3"
    }
}


def generate_song(tags, lyrics, bpm=120, key="C major", seed=None):
    """Submit ACE workflow to ComfyUI and download the result."""
    if seed is None:
        seed = int(time.time()) % 2**31

    # Fill in the workflow
    workflow = json.loads(json.dumps(WORKFLOW))
    workflow["94"]["inputs"]["tags"] = tags
    workflow["94"]["inputs"]["lyrics"] = lyrics
    workflow["94"]["inputs"]["bpm"] = bpm
    workflow["94"]["inputs"]["keyscale"] = key
    workflow["94"]["inputs"]["seed"] = seed
    workflow["3"]["inputs"]["seed"] = seed

    # Unique filename prefix
    prefix = f"audio/eido_{uuid.uuid4().hex[:8]}"
    workflow["107"]["inputs"]["filename_prefix"] = prefix

    print(f"Submitting song generation: bpm={bpm}, key={key}, seed={seed}")
    print(f"Tags: {tags[:100]}...")
    print(f"Lyrics: {len(lyrics)} chars")

    # Queue the prompt
    try:
        resp = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow}, timeout=10)
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        print(f"Queued: {prompt_id}")
    except Exception as e:
        print(f"ERROR: Could not connect to ComfyUI at {COMFYUI_URL}: {e}")
        print("Make sure ComfyUI is running on the host.")
        sys.exit(1)

    # Poll for completion
    print("Waiting for generation...", end="", flush=True)
    for i in range(300):  # 5 min max
        time.sleep(1)
        try:
            hist = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5).json()
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if "107" in outputs:
                    audio_data = outputs["107"].get("audio", [])
                    if audio_data:
                        filename = audio_data[0]["filename"]
                        subfolder = audio_data[0].get("subfolder", "")
                        print(f"\nGenerated: {filename}")

                        # Download the audio
                        params = {"filename": filename, "type": "output"}
                        if subfolder:
                            params["subfolder"] = subfolder
                        audio_resp = requests.get(f"{COMFYUI_URL}/view", params=params, timeout=30)
                        audio_resp.raise_for_status()

                        with open("song.mp3", "wb") as f:
                            f.write(audio_resp.content)
                        print(f"Saved: song.mp3 ({len(audio_resp.content)} bytes)")
                        return "song.mp3"

                # Check for errors
                status = hist[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    print(f"\nERROR: Generation failed: {status}")
                    sys.exit(1)
        except Exception:
            pass
        if i % 10 == 0:
            print(".", end="", flush=True)

    print("\nERROR: Timed out waiting for generation")
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a song with ACE-Step 1.5")
    parser.add_argument("tags", help="Genre/style/instrumentation description")
    parser.add_argument("lyrics", help="Timestamped lyrics")
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--key", default="C major")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    generate_song(args.tags, args.lyrics, args.bpm, args.key, args.seed)
