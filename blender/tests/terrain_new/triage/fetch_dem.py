"""Real elevation data of the landforms Ekigar's names promise, in the triage cache format, so the same rig renders
them beside the generated ones. Source: the public AWS Terrain Tiles (Terrarium PNG, elevation = R*256 + G + B/256 -
32768 m; USGS 3DEP 10 m in the US, SRTM elsewhere). The tiles go into their own folder in the scratchpad and are
decoded as images only.

    python -I fetch_dem.py [key,key]
"""
import json
import math
import os
import sys
import urllib.request

import numpy as np
from PIL import Image
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenes  # noqa: E402

TILES = os.path.join(os.path.dirname(scenes.CACHE), 'dem_tiles')      # downloads only, nothing runs from here
URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

# key: (lat, lon, crop metres, zoom)
PLACES = {
    'fuji': (35.3606, 138.7274, 30000, 12),
    'goosenecks': (37.1720, -109.9310, 4000, 14),
    'great_sand_dunes': (37.7480, -105.5600, 6000, 14),
    'yosemite': (37.7300, -119.6050, 10000, 13),
    'sp_crater': (35.5830, -111.6320, 8000, 13),
    'meteor_crater': (35.0275, -111.0225, 3000, 14),
    'monument_valley': (36.9830, -110.0950, 6000, 14),
    'badlands': (43.7560, -101.9420, 2000, 15),
    'alps': (46.5550, 7.9500, 10000, 13),
}


def tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y                                     # fractional tile coordinates


def fetch(z, x, y, folder):
    p = os.path.join(folder, f'{z}_{x}_{y}.png')
    if not os.path.exists(p):
        with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=30) as r:
            data = r.read()
        with open(p, 'wb') as f:
            f.write(data)
    a = np.asarray(Image.open(p).convert('RGB'), dtype=np.float64)
    return a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0


def build(key, res=scenes.RES):
    lat, lon, crop, z = PLACES[key]
    folder = os.path.join(TILES, key)
    os.makedirs(folder, exist_ok=True)
    mpp = 156543.03392 * math.cos(math.radians(lat)) / 2 ** z          # ground metres per pixel
    half_px = crop / 2.0 / mpp
    fx, fy = tile_xy(lat, lon, z)
    px, py = fx * 256.0, fy * 256.0                                      # global pixel of the centre
    x0, x1 = int(math.floor((px - half_px) / 256)), int(math.floor((px + half_px) / 256))
    y0, y1 = int(math.floor((py - half_px) / 256)), int(math.floor((py + half_px) / 256))
    rows = []
    for ty in range(y0, y1 + 1):
        rows.append(np.concatenate([fetch(z, tx, ty, folder) for tx in range(x0, x1 + 1)], axis=1))
    mosaic = np.concatenate(rows, axis=0)
    # the crop window in mosaic pixels, resampled to res x res (Mercator is conformal: square pixels locally)
    cx, cy = px - x0 * 256.0, py - y0 * 256.0
    src = np.float32([[cx - half_px, cy - half_px], [cx + half_px, cy - half_px], [cx - half_px, cy + half_px]])
    dst = np.float32([[0, 0], [res, 0], [0, res]])
    M = cv2.getAffineTransform(src, dst)
    elev = cv2.warpAffine(mosaic.astype(np.float32), M, (res, res), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)
    elev = elev[::-1].astype(np.float64)               # image rows run north to south; the field's rows run +y
    W = float(crop)
    h = (elev - elev.min()) / (scenes.VS * W)          # field units: z_m = h * 0.3 * W
    meta = {'name': 'real_' + key, 'W': W, 'vs': scenes.VS, 'z_base': 0.0, 'tile': {'x': 0, 'y': 0}, 'warnings': [],
            'relief_m': float(elev.max() - elev.min()), 'texel_m': W / res, 'source_m_per_px': mpp,
            'lat': lat, 'lon': lon, 'zoom': z, 'nonFinite': int((~np.isfinite(elev)).sum()), 'outs': [],
            'source': 'AWS Terrain Tiles (Terrarium)'}
    np.savez_compressed(scenes.cache_path('real_' + key), meta=json.dumps(meta), height=h.astype(np.float32),
                        aux=np.zeros_like(h, dtype=np.float32))
    return meta


if __name__ == '__main__':
    keys = sys.argv[1].split(',') if len(sys.argv) > 1 else list(PLACES)
    for k in keys:
        m = build(k)
        print(f"{k:18s} relief {m['relief_m']:7.0f} m over {m['W'] / 1000:.1f} km, source {m['source_m_per_px']:.1f} "
              f"m/px", flush=True)
