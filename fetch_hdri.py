"""Fetch an HDRI by search term or exact ID.

Searches Poly Haven AND AmbientCG, picks the best-scoring match across both,
downloads the .hdr file, and writes a base64 sidecar for scene-script injection.

Usage:
    python3 fetch_hdri.py "night urban"           # multi-source search
    python3 fetch_hdri.py "studio" 2k             # at 2k resolution
    python3 fetch_hdri.py cobblestone_street_night  # exact Poly Haven ID
    python3 fetch_hdri.py AerodynamicsWorkshop    # exact AmbientCG ID

Outputs in the current directory:
    hdri.hdr      — the HDRI file
    hdri_b64.txt  — base64 encoded for assets-injection scenes

Resolutions: 1k (default), 2k, 4k, 8k.
"""
import requests, base64, sys, zipfile, io
from concurrent.futures import ThreadPoolExecutor

query = sys.argv[1] if len(sys.argv) > 1 else "night"
resolution = (sys.argv[2] if len(sys.argv) > 2 else "1k").lower()


# ───────── source: Poly Haven ─────────

def polyhaven_search(q):
    out = []
    try:
        r = requests.get(f"https://api.polyhaven.com/files/{q}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if "hdri" in d:
                return [(99, 0, q, q, "polyhaven", d)]
    except Exception:
        pass
    try:
        catalog = requests.get("https://api.polyhaven.com/assets?t=hdris", timeout=15).json()
        terms = q.lower().split()
        for kid, info in catalog.items():
            cats = [c.lower() for c in info.get("categories", [])]
            tags = [t.lower() for t in info.get("tags", [])]
            name = (info.get("name") or "").lower()
            text = cats + tags + [name, kid.lower()]
            score = sum(1 for t in terms if any(t in s for s in text))
            if score > 0:
                out.append((score, info.get("download_count", 0), kid, info.get("name", kid), "polyhaven", None))
    except Exception as e:
        print(f"[polyhaven] search error: {e}", file=sys.stderr)
    return out


def polyhaven_fetch(kid, files, res):
    if files is None:
        files = requests.get(f"https://api.polyhaven.com/files/{kid}", timeout=10).json()
    url = files["hdri"][res]["hdr"]["url"]
    print(f"  downloading {url.split('/')[-1]} …")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


# ───────── source: AmbientCG ─────────

def ambientcg_search(q):
    out = []
    # Exact ID first — score 99 to win.
    try:
        r = requests.get("https://ambientcg.com/api/v2/full_json", params={"id": q}, timeout=10)
        if r.status_code == 200:
            assets = r.json().get("foundAssets", [])
            for a in assets:
                if a.get("assetId", "").lower() == q.lower():
                    return [(99, 0, a.get("assetId"), a.get("displayName", q), "ambientcg", a)]
    except Exception:
        pass
    try:
        params = {"type": "HDRI", "q": q, "limit": 30}
        r = requests.get("https://ambientcg.com/api/v2/full_json", params=params, timeout=15)
        if r.status_code != 200:
            return out
        assets = r.json().get("foundAssets", [])
        terms = q.lower().split()
        for a in assets:
            aid = a.get("assetId", "")
            tags = [t.lower() for t in (a.get("tags") or [])]
            cat = ((a.get("category") or "")).lower()
            name = (a.get("displayName") or "").lower()
            text = tags + [cat, name, aid.lower()]
            score = 1 + sum(1 for t in terms if any(t in s for s in text))
            pop = a.get("popularityScore", 0) or a.get("downloadCount", 0) or 0
            out.append((score, pop, aid, a.get("displayName", aid), "ambientcg", a))
    except Exception as e:
        print(f"[ambientcg] search error: {e}", file=sys.stderr)
    return out


def ambientcg_fetch(aid, asset, res):
    # downloadFolders is only populated when include=downloadData is requested.
    r = requests.get(
        "https://ambientcg.com/api/v2/full_json",
        params={"id": aid, "include": "downloadData"},
        timeout=15,
    ).json()
    found = r.get("foundAssets", [])
    if not found:
        raise RuntimeError(f"AmbientCG: asset {aid} not found")
    asset = found[0]
    target_attr = res.upper()                         # '1K', '2K', etc.
    dl_link, dl_name = None, None
    for folder in (asset.get("downloadFolders") or {}).values():
        if not isinstance(folder, dict): continue
        for cat in (folder.get("downloadFiletypeCategories") or {}).values():
            if not isinstance(cat, dict): continue
            for d in (cat.get("downloads") or []):
                if d.get("attribute") == target_attr:
                    fname = (d.get("fileName") or "")
                    link = d.get("downloadLink") or d.get("rawLink") or ""
                    if link and not link.startswith("http"):
                        link = "https://ambientcg.com" + link
                    dl_link, dl_name = link, fname
                    break
            if dl_link: break
        if dl_link: break
    if not dl_link:
        raise RuntimeError(f"AmbientCG: no {target_attr} download for {aid}")
    print(f"  downloading {dl_name} …")
    r = requests.get(dl_link, timeout=120)
    r.raise_for_status()
    # AmbientCG HDRIs ship as a zip containing one .hdr or .exr.
    if dl_name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            for member in z.namelist():
                if member.lower().endswith((".hdr", ".exr")):
                    return z.read(member)
        raise RuntimeError(f"AmbientCG: zip {dl_name} contained no .hdr/.exr")
    return r.content


# ───────── combined search + dispatch ─────────

# Query both sources IN PARALLEL (independent network I/O) so wall-time is the
# slower source, not the sum; per-source failures are isolated. Poly Haven is
# submitted first so it keeps its edge on exact score/popularity ties.
def _parallel_search(*search_fns):
    out = []
    with ThreadPoolExecutor(max_workers=len(search_fns)) as ex:
        futs = [ex.submit(fn, query) for fn in search_fns]
        for fut in futs:
            try:
                out += fut.result() or []
            except Exception as e:
                print(f"[search] a source failed: {e}", file=sys.stderr)
    return out


matches = _parallel_search(polyhaven_search, ambientcg_search)
if not matches:
    print(f"No HDRIs found matching '{query}'. Falling back to Poly Haven 'studio_small_09'.")
    hdri_id = "studio_small_09"
    files = requests.get(f"https://api.polyhaven.com/files/{hdri_id}", timeout=10).json()
    content = polyhaven_fetch(hdri_id, files, resolution)
    source = "polyhaven"
else:
    matches.sort(key=lambda m: (m[0], m[1]), reverse=True)
    score, _pop, hdri_id, disp_name, source, payload = matches[0]
    print(f"Found {len(matches)} matches across sources. Using: {hdri_id} ({disp_name}) from {source}")
    if len(matches) > 1:
        others = [f"{m[2]} ({m[4]})" for m in matches[1:6]]
        print(f"Other options: {', '.join(others)}")
    if source == "polyhaven":
        content = polyhaven_fetch(hdri_id, payload, resolution)
    else:
        content = ambientcg_fetch(hdri_id, payload, resolution)

with open("hdri.hdr", "wb") as f:
    f.write(content)
b64 = base64.b64encode(content).decode()
with open("hdri_b64.txt", "w") as f:
    f.write(b64)

print(f"Done: hdri.hdr ({len(content)} bytes), hdri_b64.txt ({len(b64)} chars)")
print(f"HDRI ID: {hdri_id} (source: {source})")
