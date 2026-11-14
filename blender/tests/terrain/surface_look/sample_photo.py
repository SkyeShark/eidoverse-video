"""The photograph colour sampler: what colours a kind of ground has in a photograph of the place, as spreads
rather than one swatch, and the albedos that render to them under the review's light. A layer's ramp stops are
written from this (SURFACING_DESIGN.md 3.1): plain Python (numpy, Pillow).

    python blender/tests/terrain/surface_look/sample_photo.py --photo <photograph>
        --regions "talus:0.28,0.38,0.45,0.50;cliff:0.0,0.38,0.17,0.62" [--chart <chart.json>] [--light flat]
        [--tag canyon_tw07]
    python blender/tests/terrain/surface_look/sample_photo.py --photo <photograph> --layers <layer map .png>
        --names soil,wash,scrub,talus,slickrock,cliff [--chart <chart.json>]
    python blender/tests/terrain/surface_look/sample_photo.py --retint "#9c6e52" --render-lab 45,6,7
        --photo-lab 59,10,20 [--light flat]       # a layer's albedo moved to the photograph's hue (retint())
    (--photo can be a review render too: the same regions measured on the render and on the photograph are the
    two colours --retint takes)

Where a kind of ground is in the photograph is said one of two ways:
  --regions   named rectangles, x0,y0,x1,y1 as fractions of the photograph from its left and its top: the reader
              marks the cliff, the talus, the plateau. The way for a recipe, whose render matches the photograph's
              camera but not its ground pixel for pixel. A name may repeat (several rectangles, one region)
  --layers    the matched view's layer map (render_look.py --layers), laid over the photograph: a layer's region is
              where its flat colour holds the pixel (the nearest layer colour, within 0.12). Right where the terrain
              is the place's own elevation data (real_place); a first guess otherwise

Per region it reports CIELAB percentiles (10th, 50th, 90th of L*, a*, b*), then the region split into three
brightness bins by L* (shade, mid, lit) with each bin's median colour, and three ramp stops: the median colours of
the darkest, middle and brightest fifths of the region's sunlit two thirds, also as `tints` (each stop's linear
colour over the middle one's) with the median's hue angle and chroma. The tints and hues are what a palette takes:
a photograph's exposure and tone curve are its own, so its pixel values are not albedos (the review renders are
darker than these photographs: a sunlit sandstone pixel of tw_07 asks for an albedo near 0.9 under the review's
light). With --chart (the table surfacing/calibrate_light.py renders: albedo patches under the review's sky and view
transform) every colour also comes as the albedo that would render to it at the review's exposure, which says how
far the photograph's exposure is from the render's. --light picks the chart's row: flat (level ground, the
default), wall_to_sun, wall_to_camera.

Writes out/surface_look/photo_samples/<tag>.json and <tag>.jpg (the photograph with the regions outlined and their
swatches: displayed colour above, albedo below).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'surface_look', 'photo_samples')
CHART = os.path.join(TN, 'out', 'surfacing', 'calibration', 'chart.json')
DEBUG_COLOURS = [(0.55, 0.38, 0.25), (0.35, 0.55, 0.2), (0.85, 0.75, 0.45), (0.6, 0.35, 0.6), (0.2, 0.55, 0.85),
                 (0.95, 0.95, 0.95)]


# ------------------------------------------------------------------------------------------------- colour ---

def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def srgb_to_lab(rgb):
    """sRGB 0..1 (..., 3) -> CIELAB (D65)."""
    lin = srgb_to_linear(rgb)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    lab = np.asarray(lab, np.float64)
    fy = (lab[..., 0] + 16) / 116
    fx, fz = fy + lab[..., 1] / 500, fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * np.array([0.95047, 1.0, 1.08883])
    m = np.linalg.inv(np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                                [0.0193339, 0.1191920, 0.9503041]]))
    return np.clip(linear_to_srgb(xyz @ m.T), 0.0, 1.0)


def hexs(rgb):
    return '#%02x%02x%02x' % tuple(int(round(255 * float(v))) for v in np.clip(rgb, 0, 1))


# ------------------------------------------------------------------------------------- the light's chart ---

class Chart:
    """calibrate_light.py's table for one orientation: albedo (linear) against the displayed sRGB. albedo(d): the
    albedo that renders to the displayed colour d (sRGB 0..1): each channel through the grey patches' curve, then
    corrected by what the chart's nearest colours say that estimate misses (the view transform bends saturated
    colours; an inverse-distance mean of the log errors in CIELAB, the greys pulling it back to no correction)."""

    def __init__(self, path, light='flat'):
        rows = json.load(open(path, encoding='utf-8'))['rows'][light]
        rows = [(lb, np.array(a, np.float64), np.array(d, np.float64) / 255.0) for lb, a, d in rows if d is not None]
        grey = [(a, d) for _lb, a, d in rows if abs(a[0] - a[1]) < 1e-9 and abs(a[1] - a[2]) < 1e-9]
        self.g_alb = np.array([a[0] for a, _d in grey])
        self.g_disp = np.array([d for _a, d in grey])                     # (N, 3)
        order = np.argsort(self.g_alb)
        self.g_alb, self.g_disp = self.g_alb[order], self.g_disp[order]
        self.anchors = []
        for _lb, a, d in rows:
            self.anchors.append((srgb_to_lab(d), np.log(np.maximum(a, 1e-4) / np.maximum(self._grey_inverse(d), 1e-4))))

    def _grey_inverse(self, d):
        d = np.asarray(d, np.float64)
        out = np.empty(3)
        for c in range(3):
            x = np.maximum.accumulate(self.g_disp[:, c])                  # displayed value rises with the albedo
            out[c] = np.interp(d[c], x, self.g_alb)
        return out

    def albedo(self, d):
        d = np.asarray(d, np.float64)
        a0 = self._grey_inverse(d)
        lab = srgb_to_lab(d)
        w = np.array([1.0 / (np.sum((lab - L) ** 2) + 9.0) ** 2 for L, _e in self.anchors])
        e = np.sum(w[:, None] * np.array([e for _L, e in self.anchors]), 0) / w.sum()
        return np.clip(a0 * np.exp(e), 0.0, 0.95)

    def display(self, a):
        """The displayed sRGB of a grey-curve albedo (each channel through the greys' curve): a check, not a model."""
        a = np.asarray(a, np.float64)
        return np.array([np.interp(a[c], self.g_alb, self.g_disp[:, c]) for c in range(3)])


def retint(old_albedo, render_lab, photo_lab, chart):
    """A layer's new albedo (linear rgb) from its old one, the colour its region renders to (CIELAB, measured on a
    review frame with this sampler) and the colour of the same kind of ground in the photograph: the render keeps its
    own lightness, and takes the photograph's hue and chroma scaled to that lightness (a* and b* over L* + 16 do not
    change when an exposure does: every channel scales alike under a cube root). The chart turns both displayed
    colours into albedos, and their ratio moves the old albedo: what the material adds on top (AO, tone, the sky's
    fill) stays as it is."""
    render_lab = np.asarray(render_lab, np.float64)
    photo_lab = np.asarray(photo_lab, np.float64)
    s = (render_lab[0] + 16.0) / (photo_lab[0] + 16.0)
    target = np.array([render_lab[0], photo_lab[1] * s, photo_lab[2] * s])
    a_now = chart.albedo(lab_to_srgb(render_lab))
    a_tgt = chart.albedo(lab_to_srgb(target))
    return np.clip(np.asarray(old_albedo, np.float64) * a_tgt / np.maximum(a_now, 1e-4), 0.0, 0.95)


# ------------------------------------------------------------------------------------------------ regions ---

def parse_regions(text):
    out = {}
    for part in (text or '').split(';'):
        if not part.strip():
            continue
        name, box = part.split(':')
        out.setdefault(name.strip(), []).append(tuple(float(v) for v in box.split(',')))
    return out


def layer_masks(layer_png, names, size, tol=0.12):
    """{name: boolean mask at the photograph's size} from a layer map: the nearest layer colour per pixel."""
    im = Image.open(layer_png).convert('RGBA').resize(size, Image.BILINEAR)
    a = np.asarray(im, np.float64) / 255.0
    lin = srgb_to_linear(a[..., :3])
    cols = np.array(DEBUG_COLOURS[:len(names)])
    d = np.sqrt(((lin[..., None, :] - cols[None, None]) ** 2).sum(-1))
    near = d.argmin(-1)
    ok = (d.min(-1) < tol) & (a[..., 3] > 0.9)
    return {nm: ok & (near == i) for i, nm in enumerate(names)}


def describe(px, chart=None):
    """One region's pixels (N, 3) sRGB 0..1 -> its record."""
    lab = srgb_to_lab(px)
    L = lab[:, 0]
    rec = dict(pixels=int(len(px)))
    pct = np.percentile(lab, [10, 50, 90], axis=0)
    rec['lab_p10'], rec['lab_p50'], rec['lab_p90'] = ([round(float(v), 1) for v in row] for row in pct)
    rec['mean_srgb'] = hexs(lab_to_srgb(lab.mean(0)))
    rec['spread_ab'] = round(float(np.hypot(lab[:, 1].std(), lab[:, 2].std())), 2)

    def colour(sel):
        med = np.median(lab[sel], 0)
        d = lab_to_srgb(med)
        out = dict(lab=[round(float(v), 1) for v in med], srgb=hexs(d))
        if chart is not None:
            alb = chart.albedo(d)
            out['albedo'] = hexs(linear_to_srgb(alb))
            out['albedo_linear'] = [round(float(v), 4) for v in alb]
        return out
    t1, t2 = np.percentile(L, [33.3, 66.7])
    rec['bins'] = dict(shade=colour(L <= t1), mid=colour((L > t1) & (L <= t2)), lit=colour(L > t2))
    sun = L > t1                                         # the sunlit two thirds: the ramp's spread
    q = np.percentile(L[sun], [20, 40, 60, 80])
    rec['stops'] = [colour(sun & (L <= q[0])), colour(sun & (L > q[1]) & (L <= q[2])), colour(sun & (L > q[3]))]
    # what carries across exposures: the stops as linear multipliers of the middle one (a ramp of tints around the
    # layer's own colour), and the hue and chroma of the median. A photograph's exposure and tone curve are its own
    # (the review's renders are darker: a sunlit sandstone pixel there asks for an albedo near 0.9), so its pixel
    # values are not albedos; its spreads and hues are what a palette takes from it
    lin = [srgb_to_linear(np.array([int(c['srgb'][k:k + 2], 16) for k in (1, 3, 5)]) / 255.0) for c in rec['stops']]
    mid = np.maximum(lin[1], 1e-4)
    rec['tints'] = [[round(float(v), 3) for v in (s / mid)] for s in lin]
    med = np.median(lab, 0)
    rec['hue_deg'] = round(float(np.degrees(np.arctan2(med[2], med[1]))) % 360.0, 1)
    rec['chroma'] = round(float(np.hypot(med[1], med[2])), 1)
    return rec


def run(photo, regions=None, layers=None, names=None, chart_path=None, light='flat', tag=None, log=print):
    im = Image.open(photo).convert('RGB')
    W, H = im.size
    a = np.asarray(im, np.float64) / 255.0
    chart = Chart(chart_path, light) if chart_path and os.path.exists(chart_path) else None
    masks = {}
    for nm, boxes in (regions or {}).items():
        m = np.zeros((H, W), bool)
        for x0, y0, x1, y1 in boxes:
            m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = True
        masks[nm] = m
    if layers:
        masks.update(layer_masks(layers, names, (W, H)))
    res = dict(photo=os.path.basename(photo), light=light, chart=bool(chart), regions={})
    for nm, m in masks.items():
        if m.sum() < 50:
            continue
        res['regions'][nm] = describe(a[m], chart)
    # the sheet: the photograph with the regions outlined, and each region's swatches
    S = 900
    thumb = im.resize((S, int(S * H / W)), Image.LANCZOS)
    rows = len(res['regions'])
    sheet = Image.new('RGB', (S, thumb.size[1] + 8 + 64 * rows), (18, 18, 18))
    sheet.paste(thumb, (0, 0))
    dr = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype('arial.ttf', 13)
    except OSError:
        f = ImageFont.load_default()
    for nm, boxes in (regions or {}).items():
        for x0, y0, x1, y1 in boxes:
            dr.rectangle([x0 * S, y0 * thumb.size[1], x1 * S, y1 * thumb.size[1]], outline=(255, 255, 0))
            dr.text((x0 * S + 3, y0 * thumb.size[1] + 2), nm, fill=(255, 255, 0), font=f)
    for k, (nm, r) in enumerate(res['regions'].items()):
        y = thumb.size[1] + 8 + 64 * k
        dr.text((6, y), f"{nm} ({r['pixels']} px): L* {r['lab_p10'][0]:.0f} / {r['lab_p50'][0]:.0f} / "
                        f"{r['lab_p90'][0]:.0f}, a* {r['lab_p50'][1]:.0f}, b* {r['lab_p50'][2]:.0f}, mean "
                        f"{r['mean_srgb']}", fill=(230, 230, 230), font=f)
        cells = [('shade', r['bins']['shade']), ('mid', r['bins']['mid']), ('lit', r['bins']['lit']),
                 ('stop 0', r['stops'][0]), ('stop 1', r['stops'][1]), ('stop 2', r['stops'][2])]
        for j, (lb, c) in enumerate(cells):
            x = 6 + 148 * j
            dr.rectangle([x, y + 18, x + 140, y + 38], fill=c['srgb'])
            if 'albedo' in c:
                dr.rectangle([x, y + 38, x + 140, y + 58], fill=c['albedo'])
            dr.text((x + 3, y + 21), f"{lb} {c['srgb']}", fill=(0, 0, 0), font=f)
            if 'albedo' in c:
                dr.text((x + 3, y + 41), f"albedo {c['albedo']}", fill=(255, 255, 255), font=f)
    os.makedirs(OUT, exist_ok=True)
    tag = tag or os.path.splitext(os.path.basename(photo))[0]
    sheet.save(os.path.join(OUT, tag + '.jpg'), quality=90)
    with open(os.path.join(OUT, tag + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1)
    if log:
        for nm, r in res['regions'].items():
            log(f"[sample] {tag} {nm}: L* {r['lab_p10'][0]:.0f}/{r['lab_p50'][0]:.0f}/{r['lab_p90'][0]:.0f} a* "
                f"{r['lab_p50'][1]:.0f} b* {r['lab_p50'][2]:.0f} (hue {r['hue_deg']:.0f}, chroma {r['chroma']:.0f}); "
                f"lit {r['bins']['lit']['srgb']}" + (f" -> albedo {r['bins']['lit']['albedo']}" if chart else '')
                + '; stops ' + ', '.join(c['srgb'] for c in r['stops'])
                + '; tints ' + ', '.join('(%.2f, %.2f, %.2f)' % tuple(t) for t in r['tints']))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--photo')
    ap.add_argument('--regions')
    ap.add_argument('--layers')
    ap.add_argument('--names')
    ap.add_argument('--chart', default=CHART)
    ap.add_argument('--light', default='flat')
    ap.add_argument('--tag')
    ap.add_argument('--retint', help='an old albedo "#rrggbb": print the new one (retint) from --render-lab and '
                                     '--photo-lab ("L,a,b": the medians this sampler reports)')
    ap.add_argument('--render-lab')
    ap.add_argument('--photo-lab')
    a = ap.parse_args()
    if a.retint:
        chart = Chart(a.chart, a.light)
        old = srgb_to_linear(np.array([int(a.retint.strip('#')[k:k + 2], 16) for k in (0, 2, 4)]) / 255.0)
        new = retint(old, [float(v) for v in a.render_lab.split(',')], [float(v) for v in a.photo_lab.split(',')],
                     chart)
        print(f'[retint] {a.retint} -> {hexs(linear_to_srgb(new))} (linear {np.round(new, 4).tolist()})')
        return
    run(a.photo, parse_regions(a.regions), a.layers, (a.names or '').split(',') if a.names else None, a.chart,
        a.light, a.tag)


if __name__ == '__main__':
    main()
