"""Fetch PBR textures by search term or exact ID.

Searches Poly Haven, AmbientCG AND TextureCan (all CC0), picks the
best-scoring match across them, and writes `tex_urls.json` containing the
maps the scene script will load.

Usage:
    python3 fetch_texture.py "brick"                # multi-source search
    python3 fetch_texture.py "rusted metal" 2k      # at 2k resolution
    python3 fetch_texture.py brick_wall_006         # exact Poly Haven ID
    python3 fetch_texture.py Bricks074              # exact AmbientCG ID
    python3 fetch_texture.py texturecan:640         # exact TextureCan ID

Resolutions: 1k (default), 2k, 4k, 8k. Map keys written to tex_urls.json:
    diff, rough, normal, ao, metal, displacement, arm, opacity, emissive

For Poly Haven the URLs are CDN links — `loadImageTexture(url)` fetches
them directly. For AmbientCG and TextureCan the zip is downloaded +
extracted into the current directory and `tex_urls.json` contains absolute
local file paths that the engine's local-file asset loader picks up.
"""
import requests, json, sys, os, zipfile, io, re
from concurrent.futures import ThreadPoolExecutor

query = sys.argv[1] if len(sys.argv) > 1 else "concrete"
resolution = (sys.argv[2] if len(sys.argv) > 2 else "1k").lower()


# ───────── source: Poly Haven ─────────

def polyhaven_search(q):
    """Returns [(score, popularity, id, displayName, 'polyhaven', files_dict|None), ...]."""
    out = []
    # exact ID first — score 99 so it wins
    try:
        r = requests.get(f"https://api.polyhaven.com/files/{q}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if any(k in d for k in ("Diffuse", "Color", "Rough")):
                return [(99, 0, q, q, "polyhaven", d)]
    except Exception:
        pass
    try:
        catalog = requests.get("https://api.polyhaven.com/assets?t=textures", timeout=15).json()
        terms = q.lower().split()
        for tid, info in catalog.items():
            cats = [c.lower() for c in info.get("categories", [])]
            tags = [t.lower() for t in info.get("tags", [])]
            name = (info.get("name") or "").lower()
            text = cats + tags + [name, tid.lower()]
            score = sum(1 for t in terms if any(t in s for s in text))
            if score > 0:
                out.append((score, info.get("download_count", 0), tid, info.get("name", tid), "polyhaven", None))
    except Exception as e:
        print(f"[polyhaven] search error: {e}", file=sys.stderr)
    return out


def polyhaven_fetch(tid, files, res):
    if files is None:
        files = requests.get(f"https://api.polyhaven.com/files/{tid}", timeout=10).json()
    urls = {}
    map_keys = {
        "diff":         ["Diffuse", "Color"],
        "rough":        ["Rough"],
        "normal":       ["nor_gl"],
        "ao":           ["AO"],
        "metal":        ["Metal"],
        "displacement": ["Displacement"],
        "arm":          ["arm"],
    }
    for out_name, search_keys in map_keys.items():
        for key in search_keys:
            if key in files and res in files[key]:
                rd = files[key][res]
                if "jpg" in rd: urls[out_name] = rd["jpg"]["url"]; break
                if "png" in rd: urls[out_name] = rd["png"]["url"]; break
    return urls


# ───────── source: AmbientCG ─────────

def ambientcg_search(q):
    """Returns [(score, popularity, id, displayName, 'ambientcg', asset_record|None), ...]."""
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
        params = {"type": "Material", "q": q, "limit": 30}
        r = requests.get("https://ambientcg.com/api/v2/full_json", params=params, timeout=15)
        if r.status_code != 200:
            return out
        assets = r.json().get("foundAssets", [])
        terms = q.lower().split()
        # AmbientCG's q= already filters server-side, so every returned asset is
        # presumed relevant. Base score 1; bonus per literal term hit in tags.
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


def ambientcg_find_zip(asset, res):
    target_attr = f"{res.upper()}-JPG"
    for folder in (asset.get("downloadFolders") or {}).values():
        if not isinstance(folder, dict): continue
        for cat in (folder.get("downloadFiletypeCategories") or {}).values():
            if not isinstance(cat, dict): continue
            for d in (cat.get("downloads") or []):
                if d.get("attribute") == target_attr:
                    link = d.get("downloadLink") or d.get("rawLink") or ""
                    if link and not link.startswith("http"):
                        link = "https://ambientcg.com" + link
                    return link, d.get("fileName")
    return None, None


def ambientcg_fetch(aid, asset, res):
    # downloadFolders is only populated when include=downloadData is requested;
    # re-fetch with it so we get the zip URLs (the search-step payload omits them).
    r = requests.get(
        "https://ambientcg.com/api/v2/full_json",
        params={"id": aid, "include": "downloadData"},
        timeout=15,
    ).json()
    found = r.get("foundAssets", [])
    if not found:
        raise RuntimeError(f"AmbientCG: asset {aid} not found")
    asset = found[0]
    dl_link, dl_name = ambientcg_find_zip(asset, res)
    if not dl_link:
        raise RuntimeError(f"AmbientCG: no {res.upper()}-JPG zip for {aid}")
    print(f"  downloading {dl_name} …")
    r = requests.get(dl_link, timeout=120)
    r.raise_for_status()
    suffix_to_key = {
        "_Color":            "diff",
        "_NormalGL":         "normal",
        "_NormalDX":         "normal_dx",
        "_Roughness":        "rough",
        "_AmbientOcclusion": "ao",
        "_Metalness":        "metal",
        "_Displacement":     "displacement",
        "_Opacity":          "opacity",
        "_Emission":         "emissive",
    }
    out_paths = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for member in z.namelist():
            stem, ext = os.path.splitext(member)
            if ext.lower() not in (".jpg", ".jpeg", ".png"): continue
            for suffix, key in suffix_to_key.items():
                if suffix in stem and key not in out_paths:
                    out_filename = f"{aid}{suffix}{ext.lower()}"
                    with z.open(member) as src, open(out_filename, "wb") as dst:
                        dst.write(src.read())
                    out_paths[key] = os.path.abspath(out_filename)
                    break
    return out_paths


# ───────── source: TextureCan ─────────
# texturecan.com — 650+ CC0 PBR sets. No API: search scrapes /tag/<term>/
# result cards, downloads scrape the coded zip hrefs off /details/<id>/.

TC_BASE = "https://www.texturecan.com"
_TC_CARD = re.compile(r'texture-header"><a href="(/details/(\d+)/)">(.*?)</a>', re.S)
# the site 406s python-requests' default UA — send a browser-ish one
_TC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/zip;q=0.9,*/*;q=0.8",
}


def texturecan_search(q):
    """Returns [(score, popularity, id, displayName, 'texturecan', detail_path), ...]."""
    # exact ID: "texturecan:640" (or a pasted /details/640/ path)
    m = re.match(r"(?:texturecan:|/details/)(\d+)/?$", q.strip(), re.I)
    if m:
        return [(99, 0, f"texturecan:{m.group(1)}", f"TextureCan #{m.group(1)}",
                 "texturecan", f"/details/{m.group(1)}/")]
    seen = {}
    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if t]
    try:
        for term in terms[:3]:   # each word is a tag page
            r = requests.get(f"{TC_BASE}/tag/{term}/", headers=_TC_HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            for path, tid, inner in _TC_CARD.findall(r.text):
                name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
                lname = name.lower()
                score = sum(1 for t in terms if t in lname) or 1
                prev = seen.get(tid)
                if prev is None or score > prev[0]:
                    seen[tid] = (score, 0, f"texturecan:{tid}", name, "texturecan", path)
    except Exception as e:
        print(f"[texturecan] search error: {e}", file=sys.stderr)
    return list(seen.values())


def texturecan_fetch(tid, detail_path, res):
    r = requests.get(TC_BASE + detail_path, headers=_TC_HEADERS, timeout=15)
    r.raise_for_status()
    zips = re.findall(r'href="(/downloads/[^"]+\.zip)"', r.text)
    zips = [u for u in zips if "sbsar" not in u]
    if not zips:
        raise RuntimeError(f"TextureCan: no zip downloads on {detail_path}")
    link = next((u for u in zips if f"_{res}_" in u), zips[0])
    print(f"  downloading {os.path.basename(link)} …")
    r = requests.get(TC_BASE + link, headers=_TC_HEADERS, timeout=180)
    r.raise_for_status()
    # zip members are matched by substring — TextureCan naming varies a bit
    part_to_key = [
        ("normal_opengl", "normal"), ("normal_gl", "normal"),
        ("normal_directx", "normal_dx"), ("normal_dx", "normal_dx"),
        ("normal", "normal"),
        ("basecolor", "diff"), ("albedo", "diff"), ("color", "diff"), ("diff", "diff"),
        ("rough", "rough"),
        ("ao", "ao"), ("ambient", "ao"), ("occlusion", "ao"),
        ("metal", "metal"),
        ("height", "displacement"), ("disp", "displacement"),
        ("opacity", "opacity"), ("alpha", "opacity"),
        ("emissi", "emissive"),
    ]
    prefix = tid.replace(":", "_")
    out_paths = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for member in z.namelist():
            stem, ext = os.path.splitext(os.path.basename(member))
            if ext.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            lstem = stem.lower()
            for part, key in part_to_key:
                if part in lstem and key not in out_paths:
                    out_filename = f"{prefix}_{key}{ext.lower()}"
                    with z.open(member) as src, open(out_filename, "wb") as dst:
                        dst.write(src.read())
                    out_paths[key] = os.path.abspath(out_filename)
                    break
    return out_paths


# ───────── combined search + dispatch ─────────

# Query both sources IN PARALLEL (each is independent network I/O), so the
# wall-time is the slower source, not the sum. Per-source failures are isolated
# — one source erroring still lets the other's matches through. Poly Haven is
# submitted first so it keeps its slight edge on exact score/popularity ties.
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


matches = _parallel_search(polyhaven_search, ambientcg_search, texturecan_search)
if not matches:
    print(f"No textures found matching '{query}' on Poly Haven, AmbientCG, or TextureCan.")
    sys.exit(1)

# Equal-quality matches prefer AmbientCG (the deepest PBR library of the
# three); cross-source popularity numbers aren't comparable, so source
# preference outranks popularity.
matches.sort(key=lambda m: (m[0], m[4] == "ambientcg", m[1]), reverse=True)
score, _pop, tex_id, disp_name, source, payload = matches[0]
print(f"Found {len(matches)} matches across sources. Using: {tex_id} ({disp_name}) from {source}")
if len(matches) > 1:
    others = [f"{m[2]} ({m[4]})" for m in matches[1:8]]
    print(f"Other options: {', '.join(others)}")

if source == "polyhaven":
    tex_urls = polyhaven_fetch(tex_id, payload, resolution)
elif source == "texturecan":
    tex_urls = texturecan_fetch(tex_id, payload, resolution)
else:
    tex_urls = ambientcg_fetch(tex_id, payload, resolution)

with open("tex_urls.json", "w") as f:
    json.dump(tex_urls, f, indent=2)

print(f"\nTexture ID: {tex_id} (source: {source})")
print(f"Maps ({len(tex_urls)}): {', '.join(tex_urls.keys())}")
for k, v in tex_urls.items():
    print(f"  {k}: {v}")
# SPOM availability — createParallaxMaterial NEEDS a height map (it throws
# without one), and the height map IS the displacement. Tell the agent up
# front whether SPOM is possible for this material so it doesn't try + fail.
if "displacement" in tex_urls:
    print("displacement: FOUND -> SPOM available. Load it as heightMap and call "
          "createParallaxMaterial({heightMap, albedoMap, normalMap, depthScale, selfLit}) "
          "+ geom.computeTangents(). See AGENTS.md \"SPOM\".")
else:
    print("displacement: NONE for this material -> SPOM (createParallaxMaterial) needs a "
          "height map and will throw without one. For carved relief, pick a material that "
          "ships Displacement (most stone/brick/tile/wood do).")

print(f"\nSaved to tex_urls.json.")
if source == "polyhaven":
    print("Poly Haven URLs load directly via the engine's loadImageTexture (CORS open).")
else:
    print(f"{'TextureCan' if source == 'texturecan' else 'AmbientCG'} files were extracted to {os.getcwd()}; tex_urls.json holds absolute paths.")
print("Set texture.wrapS = texture.wrapT = THREE.RepeatWrapping and texture.repeat.set(X, Y) for tiling.")
