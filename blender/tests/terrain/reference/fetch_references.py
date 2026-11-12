"""Fetch the real landform references (sites.py) from open elevation data and write data/ (landform_refs.py says
the format) plus quicklook/<name>.png (a numpy hillshade with the eye-level viewpoint marked).

    python -I fetch_references.py --downloads <empty folder> [--only name,name] [--context-only]

Run it with -I: the downloads are untrusted data. Each fetch downloads into its own subfolder of --downloads (kept as
a cache: a second run reads the files already there). The system Python's numpy / Pillow / cv2 live in the user site,
which -I drops, so it is added back explicitly below.

Sources (no keys):
  gsi          GSI tiles DEM10B (Japan), 10 m:            cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png
  usgs3dep     USGS 3DEP best available (1 m lidar where flown, else 1/3 arc-second), its ImageServer exportImage
  copernicus   Copernicus DEM GLO-30 (30 m) 1-degree COGs on AWS Open Data
  swissalti3d  swisstopo swissALTI3D 2 m tiles, listed through the federal STAC API
  terrarium    AWS Terrain Tiles (Tilezen joerd) in Terrarium PNG encoding
"""
import argparse
import json
import math
import os
import site
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.append(site.getusersitepackages())
os.environ.setdefault('OPENCV_LOG_LEVEL', 'ERROR')
import numpy as np  # noqa: E402
import cv2  # noqa: E402
from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import landform_refs as R  # noqa: E402
from sites import SITES  # noqa: E402

UA = {'User-Agent': 'eidoverse-terrain-reference/1.0 (open-source film toolkit; one-off reference fetch)'}
Image.MAX_IMAGE_PIXELS = None
WGS84_A = 6378137.0


# ---------------------------------------------------------------- downloads
def get(url, path, tries=4, allow_404=False):
    """Download url to path once (a cache); returns path, or None on a 404 when allowed."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    if os.path.exists(path + '.404'):
        return None
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                data = r.read()
            with open(path + '.part', 'wb') as f:
                f.write(data)
            os.replace(path + '.part', path)
            return path
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) and allow_404:            # (S3 answers 403 for a key that is not there)
                open(path + '.404', 'w').close()
                return None
            last = e
        except Exception as e:  # noqa: BLE001 (network: retry whatever it was)
            last = e
        time.sleep(2 + 3 * k)
    raise RuntimeError(f'download failed: {url}: {last}')


def get_json(url, tries=4):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * k)
    raise RuntimeError(f'request failed: {url}: {last}')


def geotiff(path):
    """(float32 array with NaN for nodata, dict: scale, tiepoint, pixel_is_point)."""
    a = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if a is None:
        raise RuntimeError(f'cv2 could not read {path}')
    a = a.astype(np.float32)
    t = Image.open(path).tag_v2
    scale, tie = t[33550], t[33922]
    keys = t.get(34735, ())
    raster = 1
    for i in range(4, len(keys), 4):
        if keys[i] == 1025:
            raster = keys[i + 3]
    nod = t.get(42113)
    if nod not in (None, ''):
        a[a == np.float32(float(nod))] = np.nan
    a[(a < -1e4) | (a > 1e4)] = np.nan
    return a, dict(scale=scale, tie=tie, pixel_is_point=(raster == 2))


# ---------------------------------------------------------------- sources: a mosaic + where a lat/lon falls in it
class Mosaic:
    """src: float32 heights (NaN = no data); colrow(lat, lon) -> float (col, row), integer = pixel centre;
    pixel_m: the mosaic's ground pixel; info: what it is, for the JSON."""

    def __init__(self, src, colrow, pixel_m, info):
        self.src, self.colrow, self.pixel_m, self.info = src, colrow, pixel_m, info


def merc_xy(lat, lon, z):
    n = 2.0 ** z
    x = (np.asarray(lon, np.float64) + 180.0) / 360.0 * n
    y = (1.0 - np.arcsinh(np.tan(np.radians(np.asarray(lat, np.float64)))) / math.pi) / 2.0 * n
    return x, y


def tile_mosaic(kind, bbox, z, dl):
    lat_s, lat_n, lon_w, lon_e = bbox
    x0, y0 = (int(math.floor(v)) for v in merc_xy(lat_n, lon_w, z))
    x1, y1 = (int(math.floor(v)) for v in merc_xy(lat_s, lon_e, z))
    jobs = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    if kind == 'gsi':
        url = 'https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png'
    else:
        url = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

    def fetch(xy):
        x, y = xy
        return xy, get(url.format(z=z, x=x, y=y), os.path.join(dl, f'{z}_{x}_{y}.png'), allow_404=(kind == 'gsi'))
    with ThreadPoolExecutor(8) as ex:
        paths = dict(ex.map(fetch, jobs))
    src = np.full(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), np.nan, np.float32)
    for (x, y), p in paths.items():
        if p is None:
            continue                                          # GSI: no tile = sea / outside Japan
        c = np.asarray(Image.open(p).convert('RGB')).astype(np.float64)
        if kind == 'gsi':
            v = c[..., 0] * 65536 + c[..., 1] * 256 + c[..., 2]
            h = np.where(v < 2 ** 23, v, v - 2 ** 24) * 0.01
            h[v == 2 ** 23] = np.nan
        else:
            h = c[..., 0] * 256 + c[..., 1] + c[..., 2] / 256 - 32768
        src[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = h

    def colrow(lat, lon):
        mx, my = merc_xy(lat, lon, z)
        return mx * 256 - x0 * 256 - 0.5, my * 256 - y0 * 256 - 0.5
    lat_c = 0.5 * (lat_s + lat_n)
    pix = 2 * math.pi * WGS84_A * math.cos(math.radians(lat_c)) / (256 * 2 ** z)
    return Mosaic(src, colrow, pix, dict(zoom=z, tiles=len(jobs), tile_range=[x0, y0, x1, y1]))


USGS = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'


def usgs_mosaic(bbox, sample_m, dl):
    lat_s, lat_n, lon_w, lon_e = bbox
    lat_c = 0.5 * (lat_s + lat_n)
    w_m = (lon_e - lon_w) * math.pi / 180 * WGS84_A * math.cos(math.radians(lat_c))
    h_m = (lat_n - lat_s) * math.pi / 180 * 6367449.0
    s = max(sample_m, w_m / 4000, h_m / 4000)
    w, h = int(math.ceil(w_m / s)), int(math.ceil(h_m / s))
    q = dict(bbox=f'{lon_w},{lat_s},{lon_e},{lat_n}', bboxSR=4326, imageSR=4326, size=f'{w},{h}', format='tiff',
             pixelType='F32', noData=-9999, noDataInterpretation='esriNoDataMatchAny',
             interpolation='RSP_BilinearInterpolation', f='json')
    meta_path = os.path.join(dl, 'export.json')
    tif = os.path.join(dl, 'export.tif')
    req_path = os.path.join(dl, 'export_request.json')       # the cache is this request's: a moved site refetches
    same = False
    if os.path.exists(meta_path) and os.path.exists(req_path):
        with open(req_path) as f:
            same = json.load(f) == q
    if os.path.exists(meta_path) and not same:
        for p in (meta_path, tif):
            if os.path.exists(p):
                os.remove(p)
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            m = json.load(f)
    else:
        m = get_json(USGS + '?' + urllib.parse.urlencode(q))
    if not os.path.exists(tif):
        get(m['href'], tif)
        with open(meta_path, 'w') as f:
            json.dump(m, f)
        with open(req_path, 'w') as f:
            json.dump(q, f)
    a, _g = geotiff(tif)
    a[a <= -9998] = np.nan
    e = m['extent']
    W, H = m['width'], m['height']

    def colrow(lat, lon):
        return ((np.asarray(lon) - e['xmin']) / (e['xmax'] - e['xmin']) * W - 0.5,
                (e['ymax'] - np.asarray(lat)) / (e['ymax'] - e['ymin']) * H - 0.5)
    lidar = []
    try:                                                      # which 1 m lidar projects the best-available mosaic has here
        r = get_json('https://tnmaccess.nationalmap.gov/api/v1/products?' + urllib.parse.urlencode(
            dict(datasets='Digital Elevation Model (DEM) 1 meter', bbox=f'{lon_w},{lat_s},{lon_e},{lat_n}', max=20)),
            tries=2)
        lidar = sorted({it.get('title', '') for it in r.get('items', [])})
    except Exception:  # noqa: BLE001 (best effort: metadata only)
        lidar = ['(TNM Access query failed)']
    return Mosaic(a, colrow, s, dict(request=dict(q, f='json'), export_size=[W, H], export_pixel_m=round(s, 3),
                                     lidar_1m_products_here=lidar))


def copernicus_mosaic(bbox, dl):
    lat_s, lat_n, lon_w, lon_e = bbox
    lats = list(range(int(math.floor(lat_n)), int(math.floor(lat_s)) - 1, -1))    # north to south
    lons = list(range(int(math.floor(lon_w)), int(math.floor(lon_e)) + 1))
    grid, info = [], None
    for la in lats:
        row = []
        for lo in lons:
            name = 'Copernicus_DSM_COG_10_%s%02d_00_%s%03d_00_DEM' % ('N' if la >= 0 else 'S', abs(la),
                                                                     'E' if lo >= 0 else 'W', abs(lo))
            p = get(f'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif', os.path.join(dl, name + '.tif'),
                    allow_404=True)
            if p is None:                                     # GLO-30 has no tile over open ocean
                row.append(None)
                continue
            a, g = geotiff(p)
            row.append(a)
            if info is None:                                  # the north-west tile places the mosaic
                if la != lats[0] or lo != lons[0]:
                    raise RuntimeError('copernicus: the north-west tile of the mosaic is missing (open ocean)')
                info = dict(g, name=name)
        grid.append(row)
    shape = next(a.shape for row in grid for a in row if a is not None)
    src = np.concatenate([np.concatenate([a if a is not None else np.zeros(shape, np.float32) for a in row], axis=1)
                          for row in grid], axis=0)
    sx, sy = info['scale'][0], info['scale'][1]
    tl, tt = info['tie'][3], info['tie'][4]
    c_lon0 = tl if info['pixel_is_point'] else tl + 0.5 * sx                         # first pixel's centre
    c_lat0 = tt if info['pixel_is_point'] else tt - 0.5 * sy

    def colrow(lat, lon):
        return (np.asarray(lon) - c_lon0) / sx, (c_lat0 - np.asarray(lat)) / sy
    lat_c = 0.5 * (lat_s + lat_n)
    pix = math.sqrt(sx * math.pi / 180 * WGS84_A * math.cos(math.radians(lat_c)) * sy * math.pi / 180 * 6367449.0)
    return Mosaic(src, colrow, pix, dict(tiles=[f'{la},{lo}' for la in lats for lo in lons],
                                         arcsec=[round(sx * 3600, 3), round(sy * 3600, 3)],
                                         pixel_is_point=info['pixel_is_point']))


def wgs84_to_lv95(lat, lon):
    """swisstopo's approximate formulas (about 1 m): WGS84 degrees -> LV95 E, N metres."""
    p = (np.asarray(lat, np.float64) * 3600 - 169028.66) / 10000
    l = (np.asarray(lon, np.float64) * 3600 - 26782.5) / 10000  # noqa: E741
    E = 2600072.37 + 211455.93 * l - 10938.51 * l * p - 0.36 * l * p ** 2 - 44.54 * l ** 3
    N = 1200147.07 + 308807.95 * p + 3745.25 * l ** 2 + 76.63 * p ** 2 - 194.56 * l ** 2 * p + 119.79 * p ** 3
    return E, N


def swiss_mosaic(bbox, dl):
    lat_s, lat_n, lon_w, lon_e = bbox
    url = ('https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d/items?'
           + urllib.parse.urlencode(dict(bbox=f'{lon_w},{lat_s},{lon_e},{lat_n}', limit=100)))
    best = {}
    listing = os.path.join(dl, 'stac_items.json')
    listing_bbox = os.path.join(dl, 'stac_bbox.json')         # the listing is this box's: a moved site lists again
    if os.path.exists(listing):
        same = False
        if os.path.exists(listing_bbox):
            with open(listing_bbox) as f:
                same = json.load(f) == [lat_s, lat_n, lon_w, lon_e]
        if not same:
            os.remove(listing)
    if os.path.exists(listing):
        with open(listing) as f:
            best = {tuple(int(v) for v in k.split('-')): tuple(x) for k, x in json.load(f).items()}
    else:
        while url:
            d = get_json(url)
            for ft in d.get('features', []):
                _, year, en = ft['id'].split('_')
                e_km, n_km = (int(v) for v in en.split('-'))
                href = next((a['href'] for k, a in ft['assets'].items() if k.endswith('_2_2056_5728.tif')), None)
                if href and ((e_km, n_km) not in best or int(year) > best[(e_km, n_km)][0]):
                    best[(e_km, n_km)] = (int(year), href)
            url = next((ln['href'] for ln in d.get('links', []) if ln.get('rel') == 'next'), None)
        with open(listing, 'w') as f:
            json.dump({f'{e}-{n}': v for (e, n), v in best.items()}, f)
        with open(listing_bbox, 'w') as f:
            json.dump([lat_s, lat_n, lon_w, lon_e], f)
    es = [k[0] for k in best]
    ns = [k[1] for k in best]
    e0, e1, n0, n1 = min(es), max(es), min(ns), max(ns)
    src = np.full(((n1 - n0 + 1) * 500, (e1 - e0 + 1) * 500), np.nan, np.float32)

    def fetch(item):
        (e, n), (_year, href) = item
        return (e, n), get(href, os.path.join(dl, os.path.basename(href)))
    with ThreadPoolExecutor(8) as ex:
        paths = dict(ex.map(fetch, best.items()))
    for (e, n), p in paths.items():
        a, g = geotiff(p)
        assert abs(g['scale'][0] - 2.0) < 1e-6 and abs(g['tie'][3] - e * 1000) < 1e-3 and abs(g['tie'][4] - (n + 1) * 1000) < 1e-3, p
        r0, c0 = (n1 - n) * 500, (e - e0) * 500
        src[r0:r0 + a.shape[0], c0:c0 + a.shape[1]] = a

    def colrow(lat, lon):
        E, N = wgs84_to_lv95(lat, lon)
        return (E - e0 * 1000) / 2.0 - 0.5, ((n1 + 1) * 1000 - N) / 2.0 - 0.5
    years = sorted({v[0] for v in best.values()})
    return Mosaic(src, colrow, 2.0, dict(tiles_1km=len(best), years=years, grid='LV95 (EPSG:2056)'))


SOURCE_INFO = {
    'gsi': dict(
        dataset='GSI Tiles DEM10B (10 m mesh digital elevation model, elevation PNG tiles)',
        publisher='Geospatial Information Authority of Japan (GSI)',
        url='https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png', native_resolution_m=10,
        vertical_datum='Tokyo Peil (Japanese orthometric heights)',
        licence='GSI Content Terms of Use (compatible with CC BY 4.0): free use with source credit; '
                'https://www.gsi.go.jp/ENGLISH/page_e30286.html',
        attribution='Source: Geospatial Information Authority of Japan (GSI Tiles, DEM10B)'),
    'usgs3dep': dict(
        dataset='USGS 3D Elevation Program (3DEP), best-available DEM (3DEPElevation ImageServer)',
        publisher='U.S. Geological Survey',
        url=USGS, native_resolution_m='1 m lidar where flown (see lidar_1m_products_here), else 1/3 arc-second (~10 m)',
        vertical_datum='NAVD88',
        licence='Public domain (U.S. Government work); https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits',
        attribution='Courtesy of the U.S. Geological Survey, 3D Elevation Program (3DEP)'),
    'copernicus': dict(
        dataset='Copernicus DEM GLO-30 (public), 1 arc-second, AWS Open Data copernicus-dem-30m',
        publisher='European Space Agency / Copernicus programme',
        url='https://copernicus-dem-30m.s3.amazonaws.com/', native_resolution_m=30,
        vertical_datum='EGM2008 geoid',
        licence='Copernicus DEM licence for GLO-30 Public: free, worldwide, any lawful use, attribution required; '
                'https://spacedata.copernicus.eu/documents/20123/122407/GEO1988-CopernicusDEM-SPE-002_ProductHandbook_I5.0+%281%29.pdf',
        attribution='Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space '
                    'GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved',
        caveat='A digital SURFACE model: it includes forest canopy and buildings.'),
    'swissalti3d': dict(
        dataset='swissALTI3D, 2 m tiles (1 km x 1 km), latest edition per tile',
        publisher='Federal Office of Topography swisstopo',
        url='https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d', native_resolution_m=2,
        vertical_datum='LN02 (Swiss national heights)',
        licence='swisstopo free geodata (Open Government Data): free use, the source must be cited; '
                'https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices',
        attribution='(c) swisstopo, swissALTI3D'),
    'terrarium': dict(
        dataset='Terrain Tiles (Mapzen / Tilezen joerd), Terrarium PNG encoding, AWS Open Data elevation-tiles-prod',
        publisher='Mapzen / Linux Foundation Tilezen, hosted by AWS',
        url='https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
        native_resolution_m='varies by region: 3DEP 3-10 m (USA), EU-DEM 25 m (Europe), SRTM 30-90 m, GMTED, ETOPO1',
        vertical_datum='per source (mostly EGM96 geoid / NAVD88)',
        licence='Open data, each underlying source credited: https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
        attribution='Terrain Tiles (Tilezen joerd) from: EU-DEM, produced using Copernicus data and information funded '
                    'by the European Union; SRTM and GMTED2010 courtesy of the U.S. Geological Survey; ETOPO1, '
                    'U.S. National Oceanic and Atmospheric Administration; (where in the UK) (c) Environment Agency '
                    'copyright and/or database right 2015; (where in the USA) 3DEP courtesy of the U.S. Geological Survey'),
}


def mosaic_for(source, bbox, out_pixel_m, dl):
    k = source['kind']
    if k in ('gsi', 'terrarium'):
        return tile_mosaic(k, bbox, source['zoom'], dl)
    if k == 'usgs3dep':
        return usgs_mosaic(bbox, source.get('sample_m', out_pixel_m / 2), dl)
    if k == 'copernicus':
        return copernicus_mosaic(bbox, dl)
    if k == 'swissalti3d':
        return swiss_mosaic(bbox, dl)
    raise ValueError(k)


# ---------------------------------------------------------------- resampling onto the local grid
def fill_nearest(a):
    bad = ~np.isfinite(a)
    if not bad.any():
        return a, bad
    if bad.all():
        return np.zeros_like(a), bad
    _d, lab = cv2.distanceTransformWithLabels(bad.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    vals = a[~bad]                                            # labels number the valid pixels in raster order
    out = a.copy()
    out[bad] = vals[lab[bad] - 1]
    return out, bad


def resample(mos, lat, lon, out_pixel_m, denoise_px=0.0):
    col, row = mos.colrow(lat, lon)
    src, bad = fill_nearest(mos.src)
    ratio = out_pixel_m / mos.pixel_m
    if ratio > 1.25:                                          # downsampling: low-pass first (no aliasing)
        src = cv2.GaussianBlur(src, (0, 0), sigmaX=0.45 * ratio)
    elif denoise_px > 0 and ratio >= 0.8:                     # a radar DSM's speckle
        src = cv2.GaussianBlur(src, (0, 0), sigmaX=denoise_px)
    interp = cv2.INTER_CUBIC if ratio < 0.8 else cv2.INTER_LINEAR
    c32, r32 = col.astype(np.float32), row.astype(np.float32)
    out = cv2.remap(src, c32, r32, interp, borderMode=cv2.BORDER_REPLICATE)
    if denoise_px > 0 and ratio < 0.8:                        # upsampled: the speckle and the source lattice
        out = cv2.GaussianBlur(out, (0, 0), sigmaX=denoise_px / ratio)
    valid = cv2.remap((~bad).astype(np.float32), c32, r32, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                      borderValue=0.0)
    inside = (col >= -0.5) & (row >= -0.5) & (col <= mos.src.shape[1] - 0.5) & (row <= mos.src.shape[0] - 0.5)
    return out.astype(np.float32), (valid > 0.5) & inside, ratio


def bbox_of(lat0, lon0, extent_m, margin):
    half = extent_m / 2.0 * (1 + margin)
    xs = np.array([-half, 0, half, -half, half, -half, 0, half])
    ys = np.array([half, half, half, 0, 0, -half, -half, -half])
    la, lo = R.xy_to_latlon(lat0, lon0, xs, ys)
    return float(la.min()), float(la.max()), float(lo.min()), float(lo.max())


def build(name, s, role, dl_root):
    spec = s if role == 'main' else s['context']
    extent, pix, source = spec['extent_m'], spec['pixel_m'], spec['source']
    n = int(round(extent / pix))
    lat0, lon0 = s['lat'], s['lon']
    meta = dict(name=name if role == 'main' else name + '_context', role=role, title=s['title'],
                landform=s['landform'], note=s.get('note', ''), centre_lat=lat0, centre_lon=lon0,
                pixel_size_m=float(pix), extent_m=[n * pix, n * pix],
                grid='local azimuthal equidistant (sphere R=6371008.8 m) centred on centre_lat/centre_lon; x east, '
                     'y north; row 0 = north edge; pixel centre x = (col + 0.5 - cols/2) * pixel_size_m, '
                     'y = (rows/2 - row - 0.5) * pixel_size_m')
    if s.get('data_note'):
        meta['data_note'] = s['data_note']
    if role == 'context':
        meta['context_of'] = name
    dl = os.path.join(dl_root, f'{name}_{role}_{source["kind"]}')
    os.makedirs(dl, exist_ok=True)
    t0 = time.time()
    mos = mosaic_for(source, bbox_of(lat0, lon0, extent, 0.04), pix, dl)
    meta_g = dict(rows=n, cols=n, pixel_size_m=pix)
    X, Y = R.grid_xy(meta_g)
    lat, lon = R.xy_to_latlon(lat0, lon0, X, Y)
    denoise = source.get('denoise_px', 0.6 if source['kind'] == 'copernicus' else 0.0)
    h, valid, ratio = resample(mos, lat, lon, pix, denoise)
    missing = float(1 - valid.mean())
    sea = any(w['kind'] == 'sea' for w in s.get('water', []))
    if missing > 0:
        if sea or source['kind'] == 'gsi':
            h[~valid] = 0.0                                   # no data off the coast: sea level
        else:
            h, _ = fill_nearest(np.where(valid, h, np.nan).astype(np.float32))
    if sea:                                                   # the sea floor is not part of the reference
        lvl = next(w['level_m'] for w in s['water'] if w['kind'] == 'sea')
        h = np.where(h <= lvl + 0.3, lvl - 2.0, h).astype(np.float32)
        n_lab, lab, st, _c = cv2.connectedComponentsWithStats((h > lvl + 0.3).astype(np.uint8), connectivity=8)
        big = st[1:, cv2.CC_STAT_AREA].max() if n_lab > 1 else 0
        specks = [i for i in range(1, n_lab) if st[i, cv2.CC_STAT_AREA] < 0.05 * big]
        if specks:                                            # offshore steps and spikes of the source's sea data
            h[np.isin(lab, specks)] = lvl - 2.0
        meta['sea_floor'] = (f'every height at or below {lvl + 0.3:g} m is set to {lvl - 2.0:g} m: the sea surface is '
                             f'{lvl:g} m and the source\'s bathymetry is left out; {len(specks)} offshore patches of the '
                             f'source\'s sea data (each under 5% of the mainland) are sea as well')
    info = dict(SOURCE_INFO[source['kind']])
    lid = [t for t in mos.info.get('lidar_1m_products_here', []) if t and not t.startswith('(')]
    if source['kind'] == 'usgs3dep':
        info['native_resolution_m'] = ('1 m lidar where the projects in lidar_1m_products_here cover the tile, '
                                       'elsewhere 1/3 arc-second (~10 m)' if lid else
                                       '1/3 arc-second (~10 m): no 1 m lidar DEM listed here')
    if source.get('native_resolution_m'):                     # what this place really carries, when known
        info['native_resolution_m'] = source['native_resolution_m']
    info.update(kind=source['kind'], fetched=time.strftime('%Y-%m-%d'), mosaic_pixel_m=round(mos.pixel_m, 3),
                resampling=('Gaussian low-pass (sigma %.2f source px) then bilinear' % (0.45 * ratio)) if ratio > 1.25
                else (('bicubic (upsampled %.1fx from the source grid: no detail finer than the native resolution)'
                       % (1 / ratio) if ratio < 0.8 else 'bilinear')
                      + (', then Gaussian sigma %.2f source px (%.1f m) against the radar speckle and the source '
                         'lattice' % (denoise, denoise * mos.pixel_m) if denoise else '')),
                no_data_fraction=round(missing, 5), **mos.info)
    meta['source'] = info
    meta['licence'], meta['attribution'] = info['licence'], info['attribution']
    meta['water'] = s.get('water', [])
    meta['shape_stats'] = R.shape_stats(h, pix)
    out = R.save(meta['name'], h, meta)
    print(f'[fetch] {meta["name"]}: {n}x{n} @ {pix} m from {source["kind"]} (mosaic {mos.src.shape[1]}x'
          f'{mos.src.shape[0]} @ {mos.pixel_m:.2f} m), {h.min():.1f}..{h.max():.1f} m, no data {missing:.4f}, '
          f'{time.time() - t0:.1f}s', flush=True)
    return h, out


def water_mask(name, h, meta, s, tol_m=0.5):
    """The open water of a main tile: sea = ground at or under its level; a lake = the flat surface connected to
    its seed (a DEM carries a lake as its water level). Writes <name>_water.png and the bodies into the JSON."""
    bodies = s.get('water', [])
    if not bodies:
        return meta
    mask = np.zeros(h.shape, np.uint8)
    out, lake_i = [], 0
    for w in bodies:
        w = dict(w)
        if w['kind'] == 'sea':
            m = h <= w['level_m'] + 0.3
            mask[m] = 255
            w.update(mask_value=255)
        else:
            x, y = R.latlon_to_xy(meta, *w['seed'])
            c = int(round(float(x) / meta['pixel_size_m'] + meta['cols'] / 2 - 0.5))
            r = int(round(meta['rows'] / 2 - 0.5 - float(y) / meta['pixel_size_m']))
            level = float(h[r, c])
            ff = np.zeros((h.shape[0] + 2, h.shape[1] + 2), np.uint8)
            cv2.floodFill(h.astype(np.float32).copy(), ff, (c, r), 0, tol_m, tol_m,
                          4 | cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
            m = ff[1:-1, 1:-1] > 0
            m &= mask == 0
            mask[m] = 128 + lake_i
            w.update(mask_value=128 + lake_i, level_m=round(level, 2), seed=list(w['seed']))
            lake_i += 1
        w['area_km2'] = round(float(m.sum()) * meta['pixel_size_m'] ** 2 / 1e6, 3)
        print(f'[fetch] {name}: water {w["name"]} {w["area_km2"]} km2 at {w.get("level_m")} m', flush=True)
        out.append(w)
    R.write_png(os.path.join(R.DATA, f'{name}_water.png'), mask, 8)
    meta['water'] = out
    meta['water_mask_png'] = f'{name}_water.png'
    meta['water_mask_encoding'] = '8-bit: 0 land, 255 sea, 128 + i the i-th lake of `water`'
    with open(os.path.join(R.DATA, name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    return meta


def quicklook(name, h, meta, s, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    hs = R.hillshade(h, meta['pixel_size_m'], 315, 45)
    img = np.repeat((hs * 255).astype(np.uint8)[..., None], 3, axis=2)
    ev = s['views']['eye']
    rows = meta['rows']

    def px(lat, lon):
        x, y = R.latlon_to_xy(meta, lat, lon)
        return (int(round(float(x) / meta['pixel_size_m'] + meta['cols'] / 2 - 0.5)),
                int(round(rows / 2 - 0.5 - float(y) / meta['pixel_size_m'])))
    a, b = px(*ev['at']), px(*ev['look'])
    r = max(3, rows // 150)
    cv2.line(img, a, b, (255, 200, 0), max(1, rows // 500))
    cv2.circle(img, a, r, (255, 0, 0), -1)
    cv2.circle(img, b, r, (0, 160, 255), -1)
    for w in s.get('water', []):
        if w['kind'] == 'lake':
            cv2.drawMarker(img, px(*w['seed']), (0, 255, 255), cv2.MARKER_CROSS, 4 * r, max(1, rows // 400))
    Image.fromarray(img).save(os.path.join(out_dir, f'{name}.png'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--downloads', required=True, help='a folder for the downloaded files (one subfolder per fetch)')
    ap.add_argument('--only', default='')
    ap.add_argument('--context-only', action='store_true')
    ap.add_argument('--main-only', action='store_true')
    ap.add_argument('--quicklook-only', action='store_true', help='redraw quicklook/ from data/ (no downloads)')
    a = ap.parse_args()
    only = [v for v in a.only.split(',') if v]
    for name, s in SITES.items():
        if only and name not in only:
            continue
        if a.quicklook_only:
            h, meta = R.load(name)
            quicklook(name, h, meta, s, os.path.join(HERE, 'quicklook'))
            continue
        if not a.context_only:
            h, meta = build(name, s, 'main', a.downloads)
            h, meta = R.load(name)                            # as stored (16-bit), so the water levels match the file
            meta = water_mask(name, h, meta, s)
            quicklook(name, h, meta, s, os.path.join(HERE, 'quicklook'))
        if not a.main_only:
            build(name, s, 'context', a.downloads)


if __name__ == '__main__':
    main()
