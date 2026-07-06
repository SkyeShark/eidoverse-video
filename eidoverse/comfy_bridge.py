"""ComfyUI bridge — a stable, Docker-reachable endpoint for a roaming ComfyUI.

WHY THIS EXISTS
    The eidoverse music pipeline (generate_song.py / ACE-Step) runs INSIDE the
    Docker sandbox and reaches ComfyUI on the host via
    `http://host.docker.internal:8188`. That needs ComfyUI to be (a) on a KNOWN
    port and (b) listening on a Docker-reachable interface (0.0.0.0).

    The new ComfyUI Desktop breaks both: it binds 127.0.0.1 ONLY (localhost —
    Docker can't reach it) and auto-picks its port starting at 8000, so it lands
    on whatever's free (8000/8001 are often taken by local web apps → it grabs 8002,
    or wanders if those are down). It ignores the port/listen values in
    comfy.settings.json, and the Desktop UI has no server-config panel anymore.

WHAT THIS DOES
    Runs a tiny TCP proxy that LISTENS on 0.0.0.0:8188 (Docker-reachable) and
    forwards every connection to wherever ComfyUI actually is on localhost. It
    DISCOVERS ComfyUI's port by probing 127.0.0.1:<p>/system_stats across a range
    and caches the hit; if the upstream dies (ComfyUI restarted on a new port) it
    re-discovers on the next connection. So `host.docker.internal:8188` is a
    STABLE endpoint no matter what port ComfyUI roams to — no harness edits, no
    fighting the Desktop app.

RUN
    python comfy_bridge.py
    # leave it running alongside ComfyUI (or autostart it). Verify from another
    # shell: curl http://127.0.0.1:8188/system_stats  (should return ComfyUI stats)

    Optional env:
      BRIDGE_PORT   port to expose (default 8188 — what the harness expects)
      SCAN_PORTS    comma range/list to probe for ComfyUI (default 8000-8020)
      COMFY_HOST    upstream host (default 127.0.0.1)
"""
from __future__ import annotations

import asyncio
import os
import urllib.request

BRIDGE_HOST = "0.0.0.0"
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8188"))
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1")


def _scan_ports() -> list[int]:
    spec = os.environ.get("SCAN_PORTS", "8000-8020")
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


SCAN = _scan_ports()
_cached_port: int | None = None


def _probe(port: int, path: str, needle: str) -> bool:
    """True if COMFY_HOST:port answers `path` with HTTP 200 containing `needle`."""
    try:
        with urllib.request.urlopen(f"http://{COMFY_HOST}:{port}{path}", timeout=0.6) as r:
            if r.status != 200:
                return False
            body = r.read(4000).decode("utf-8", "ignore").lower()
            return needle in body
    except Exception:
        return False


def _is_comfy(port: int) -> bool:
    """True if a ComfyUI server answers on COMFY_HOST:port.

    Do NOT key liveness on /system_stats alone — some ComfyUI Desktop builds
    return HTTP 500 there while the rest of the API is perfectly healthy (the
    /prompt + /history endpoints generate_song.py actually uses still work).
    Keying discovery on the one broken endpoint made the bridge declare a live
    ComfyUI "not found" and refuse to proxy. Probe /queue first — tiny, always
    200 on a live server, and {"queue_running",...} is a strong ComfyUI
    fingerprint — then fall back to /system_stats and /object_info."""
    return (
        _probe(port, "/queue", "queue_running")
        or _probe(port, "/system_stats", "system")
        or _probe(port, "/object_info", "ksampler")
    )


def discover_comfy(prefer: int | None = None) -> int | None:
    """Find ComfyUI's port. Tries the cached/preferred port first (fast path),
    then scans the configured range. Skips the bridge's own port."""
    order: list[int] = []
    if prefer:
        order.append(prefer)
    order += [p for p in SCAN if p != BRIDGE_PORT and p != prefer]
    for p in order:
        if _is_comfy(p):
            return p
    return None


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
    global _cached_port
    # discover (cached fast-path, re-scan if the cached port is gone)
    port = _cached_port if (_cached_port and _is_comfy(_cached_port)) else discover_comfy(_cached_port)
    if not port:
        peer = client_w.get_extra_info("peername")
        print(f"[bridge] no ComfyUI found on {COMFY_HOST}:{SCAN[0]}-{SCAN[-1]} (probe from {peer}) — is ComfyUI running?")
        try:
            client_w.close()
        except Exception:
            pass
        return
    if port != _cached_port:
        print(f"[bridge] ComfyUI -> {COMFY_HOST}:{port}  (exposing 0.0.0.0:{BRIDGE_PORT})")
        _cached_port = port
    try:
        up_r, up_w = await asyncio.open_connection(COMFY_HOST, port)
    except Exception as e:
        print(f"[bridge] could not connect to ComfyUI {COMFY_HOST}:{port}: {e}")
        try:
            client_w.close()
        except Exception:
            pass
        _cached_port = None  # force re-discovery next time
        return
    await asyncio.gather(_pipe(client_r, up_w), _pipe(up_r, client_w))


async def main() -> None:
    global _cached_port
    _cached_port = discover_comfy()
    if _cached_port:
        print(f"[bridge] ComfyUI found at {COMFY_HOST}:{_cached_port}")
    else:
        print(f"[bridge] ComfyUI not found yet on {COMFY_HOST}:{SCAN[0]}-{SCAN[-1]} — will keep probing per-connection.")
    try:
        server = await asyncio.start_server(handle, BRIDGE_HOST, BRIDGE_PORT)
    except OSError as e:
        # Port already bound = a bridge is already running. Idempotent: this lets
        # `ensure_running()` / a redundant launch be a harmless no-op.
        print(f"[bridge] {BRIDGE_HOST}:{BRIDGE_PORT} already in use — a bridge is already running. Exiting. ({e})")
        return
    print(f"[bridge] listening on {BRIDGE_HOST}:{BRIDGE_PORT} -> ComfyUI (auto-discovered) | host.docker.internal:{BRIDGE_PORT} now stable")
    async with server:
        await server.serve_forever()


def is_running(host: str = "127.0.0.1", port: int = BRIDGE_PORT, timeout: float = 0.5) -> bool:
    """True if a bridge is already listening on `port` (cheap TCP connect)."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_running() -> bool:
    """Start the bridge detached if it's not already up. Host-side, idempotent —
    safe to call before every production. Returns True if the bridge is (now) up.
    Used by the video producer so eidoverse's ComfyUI bridge is always running
    without a separate daemon. (The bridge keeps running across productions.)"""
    import os as _os
    import subprocess
    import sys as _sys
    import time as _time
    if is_running():
        return True
    script = _os.path.abspath(__file__)
    creationflags = 0x00000008 if _sys.platform == "win32" else 0  # DETACHED_PROCESS
    try:
        subprocess.Popen(
            [_sys.executable, script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creationflags, close_fds=True,
        )
    except Exception as e:
        print(f"[bridge] ensure_running: could not launch: {e}")
        return False
    for _ in range(20):                 # wait up to ~2s for it to bind
        if is_running():
            return True
        _time.sleep(0.1)
    return is_running()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bridge] stopped.")
