"""The judge's boards (SURFACING_DESIGN.md section 6): per view, the photograph | the render before | the render after
| the layer map, and under them two places of the frame where a defect would show, enlarged 2x, before beside after
(system Python: numpy, Pillow):

    python blender/tests/terrain/surfacing_judge/board.py <recipe> [<recipe> ...] [--before review_11-13]
           [--after latest] [--views a,b] [--plan <views.json>] [--terrains <json>] [--no-splat]

before and after are states (states.py: a frozen state, a review_views.py tag, '<folder>:<tag>' for another
package's renders of the same cameras, or 'latest'). The layer map is the after state's layer-map render
(review_views.py --layers), else the before state's, else, for an aerial view, the palette's layers splatted into the
camera from the saved terrain (--terrains, default out/surfacing_judge/terrains.json; no render: labelled so, and
coarse; a few minutes a view, which --no-splat skips). A render whose camera is not the view's (a view the judge
moved: the state still holds the review's camera) says so in its label.

The two enlarged places are the view's own `crops` (views.json: two boxes [x0, y0, x1, y1] in render pixels) when it
names them; else the judge picks them from the layer map: the middle of the largest area one layer covers alone (a
flat single material shows there, and its tiling) and the place where the most layer edges meet (how transitions
read); without a layer map, the near ground and the aim. Writes out/surfacing_judge/boards/<recipe>_<before>_<after>.jpg.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from surfacing_judge import OUT, rel  # noqa: E402
from surfacing_judge import layers as LY  # noqa: E402
from surfacing_judge import measures as M  # noqa: E402
from surfacing_judge import states as S  # noqa: E402
from surfacing_judge import views as V  # noqa: E402

TW, TH = 480, 270                     # a tile: the 960 x 540 render at half size; a crop: 240 x 135 render pixels at 2x
CW, CH = 240, 135
BG = (20, 20, 20)


def _font(size):
    from PIL import ImageFont
    for name in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _blank(label, size=(TW, TH)):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', size, (38, 38, 38))
    ImageDraw.Draw(im).text((12, size[1] // 2 - 8), label, fill=(175, 175, 175), font=_font(15))
    return im


def photo_tile(v):
    from PIL import Image
    p = V.photo_path(v)
    if not p:
        return _blank('no photograph at this spot')
    im = Image.open(p).convert('RGB')
    return im.crop(V.fit_box(im.width, im.height)).resize((TW, TH), Image.LANCZOS)


def layer_picture(w, ground):
    """A layer map as a picture: each layer's debug colour mixed by weight, off the ground dark (H, W, 3) uint8."""
    img = LY.encode_layer_map(w, alpha=ground.astype(float))
    rgb = img[..., :3] * img[..., 3:4] + (1.0 - img[..., 3:4]) * (np.array(BG) / 255.0)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def _centre_of_largest(mask):
    """The pixel deepest inside the largest 8-connected region of a mask (an erosion run until it would vanish)."""
    m = np.asarray(mask, bool)
    if not m.any():
        return None
    from PIL import Image, ImageFilter
    cur = np.pad(m, 1)                                 # the picture's edge counts as outside the region
    k = 0
    while True:
        im = Image.fromarray((cur * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))
        nxt = np.asarray(im) > 127
        if not nxt.any() or k > 60:
            break
        cur = nxt
        k += 1
    ys, xs = np.nonzero(cur)
    return int(np.median(xs)) - 1, int(np.median(ys)) - 1


def pick_crops(v, w, ground, cam_aim=None):
    """The two boxes the board enlarges (module doc), in render pixels."""
    if v.get('crops'):
        return [tuple(int(c) for c in b) for b in v['crops'][:2]]
    H, Wd = 540, 960

    def box(cx, cy):
        x0 = int(min(max(cx - CW // 2, 0), Wd - CW))
        y0 = int(min(max(cy - CH // 2, 0), H - CH))
        return x0, y0, x0 + CW, y0 + CH
    out = []
    if w is not None and ground is not None and ground.any():
        top, topw = w.argmax(0), w.max(0)
        best, area = None, 0
        for i in range(w.shape[0]):
            m = (top == i) & (topw > 0.9) & ground
            a = int(m.sum())
            if a > area:
                best, area = m, a
        c = _centre_of_largest(best) if best is not None else None
        if c:
            out.append(box(*c))
        gy, gx = np.gradient(w, axis=(1, 2))
        edges = (np.abs(gx) + np.abs(gy)).sum(0) * ground
        k = np.ones(CW // 4)
        e2 = np.apply_along_axis(lambda r: np.convolve(r, k, 'same'), 1, edges)
        e2 = np.apply_along_axis(lambda r: np.convolve(r, np.ones(CH // 4), 'same'), 0, e2)
        if out:                                       # away from the first box
            x0, y0, x1, y1 = out[0]
            e2[max(y0 - CH // 2, 0):y1 + CH // 2, max(x0 - CW // 2, 0):x1 + CW // 2] = -1
        j, i = np.unravel_index(int(np.argmax(e2)), e2.shape)
        if e2[j, i] > 0:
            out.append(box(i, j))
    if len(out) < 2:
        out.append(box(480, 540 - CH // 2) if V.kind_of(v) == 'eye' else box(480, 400))
    if len(out) < 2:
        out.append(box(*(cam_aim or (480, 270))))
    return out[:2]


def _render(path, label):
    from PIL import Image
    if not path:
        return None, _blank(label)
    im = Image.open(path).convert('RGB')
    if im.size != (960, 540):
        im = im.resize((960, 540), Image.LANCZOS)
    return im, im.resize((TW, TH), Image.LANCZOS)


def view_row(recipe, v, before, after, stack=None, numbers=None):
    from PIL import Image, ImageDraw
    rec_b, rec_a = S.record(recipe, v['name'], before), S.record(recipe, v['name'], after)
    full_b, tile_b = _render(S.render(recipe, v['name'], before), f'not rendered in {before}')
    full_a, tile_a = _render(S.render(recipe, v['name'], after), f'not rendered in {after}')
    lay = S.layers(recipe, v['name'], after) or S.layers(recipe, v['name'], before)
    w = ground = None
    lay_label = 'layer map'
    pal = LY.palette(stack if stack is not None else recipe)
    if lay:
        w, ground, _ws, info = LY.decode_layer_map(M.load_rgba(lay), len(pal['layers']))
        lay_label = f"layer map ({'after' if S.layers(recipe, v['name'], after) else 'before'})"
    elif stack is not None and V.kind_of(v) != 'eye':
        rec = rec_a or rec_b
        cam = V.Camera.from_record(rec) if rec else V.camera_of(stack, v)[0]
        ws, seen = LY.frame_splat(stack, pal, cam, size=(240, 135))
        iy = np.minimum(np.arange(540) * 135 // 540, 134)
        ix = np.minimum(np.arange(960) * 240 // 960, 239)
        w, ground = ws[:, iy[:, None], ix[None, :]], seen[iy[:, None], ix[None, :]]
        lay_label = 'layers splatted from the saved terrain (no render)'
    if w is not None:
        tile_l = Image.fromarray(layer_picture(w, ground)).resize((TW, TH), Image.NEAREST)
        dl = ImageDraw.Draw(tile_l)                    # the legend: each layer's colour and name
        dl.rectangle([0, TH - 21, TW, TH], fill=BG)
        cols = LY.layer_colours(len(pal['layers']))
        x = 4
        for L, c in zip(pal['layers'], cols):
            rgb = tuple(int(255 * float(ch)) for ch in M.linear_to_srgb(np.array(c)))
            dl.rectangle([x, TH - 16, x + 10, TH - 6], fill=rgb, outline=(0, 0, 0))
            dl.text((x + 13, TH - 18), L['name'], fill=(255, 255, 255), font=_font(12))
            x += 18 + 7 * len(L['name'])
    else:
        tile_l = _blank('no layer map (review_views.py --layers)')
    crops = pick_crops(v, w, ground)
    font, small = _font(16), _font(13)
    head = 46
    gap = 40                                           # the numbers' line, then the crops' labels
    row = Image.new('RGB', (4 * TW, head + TH + gap + 2 * CH), BG)
    for k, im in enumerate((photo_tile(v), tile_b, tile_a, tile_l)):
        row.paste(im, (k * TW, head))
    d = ImageDraw.Draw(row)
    d.text((6, 3), f"{recipe} / {v['name']}: {v.get('caption', '')}"[:200], fill=(255, 220, 120), font=font)
    sb, sa = S.same_camera(v, rec_b), S.same_camera(v, rec_a)
    labels = ['photograph', f'before: {before}' + (' (another camera: the review\'s)' if sb is False else ''),
              f'after: {after}' + (' (another camera)' if sa is False else ''), lay_label]
    for k, s in enumerate(labels):
        d.text((k * TW + 6, 25), s, fill=(205, 205, 205), font=small)
    for k, (x0, y0, x1, y1) in enumerate(crops):
        for j, full in enumerate((full_b, full_a)):
            X = (2 * k + j) * TW
            Y = head + TH + gap
            if full is not None:
                row.paste(full.crop((x0, y0, x1, y1)).resize((2 * CW, 2 * CH), Image.NEAREST), (X, Y))
            else:
                row.paste(_blank('-', (2 * CW, 2 * CH)), (X, Y))
            d.text((X + 6, Y - 18), f"{'before' if j == 0 else 'after'}, 2x: render pixels {x0}-{x1}, {y0}-{y1}",
                   fill=(190, 190, 190), font=small)
        # mark the crop on the before and after tiles
        for t in (1, 2):
            d.rectangle([t * TW + x0 // 2, head + y0 // 2, t * TW + x1 // 2, head + y1 // 2],
                        outline=(255, 210, 60) if k == 0 else (90, 200, 255), width=2)
    if numbers:
        d.text((6, head + TH + 2), numbers[:230], fill=(170, 220, 170), font=small)
    return row


def _numbers(state, recipe, view):
    from surfacing_judge.baseline import file_name
    p = os.path.join(OUT, f'baseline_{file_name(state)}.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        fr = (json.load(f).get('frames') or {}).get(f'{recipe}/{view}')
    if not fr or 'error' in fr:
        return None
    om = fr.get('one_material') or {}
    col = fr.get('colour') or {}
    parts = []
    if om.get('largest') is not None:
        ref = om.get('photo_largest')
        parts.append(f"largest one-material region {100 * om['largest']:.0f} % ({om.get('largest_layer')})"
                     + ('' if ref is None else f", the photograph's {100 * ref:.0f} %")
                     + (' !' if om.get('flag') else ''))
    if fr.get('repetition_worst') is not None:
        parts.append(f"repetition {fr['repetition_worst']:.2f}")
    if col.get('delta_e') is not None:
        parts.append(f"colour dE {col['delta_e']:.1f} exposure matched, spread {col.get('spread_ratio_L') or 0:.2f}")
    if fr.get('seam_worst_delta_e') is not None:
        parts.append(f"seam dE {fr['seam_worst_delta_e']:.2f} over its control")
    return f"{state}: " + '; '.join(parts) if parts else None


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    before, after = opt('--before', 'review_11-13'), opt('--after', 'latest')
    plan = V.load(opt('--plan'))
    only = set((opt('--views') or '').split(',')) - {''}
    recipes = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in
                                                                          ('--before', '--after', '--views', '--plan',
                                                                           '--terrains'))]
    from surfacing_judge.check_views import load_terrain, terrain_sources
    src = {} if '--no-splat' in argv else terrain_sources(opt('--terrains'))
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    from PIL import Image
    for r in recipes or list(plan):
        st = load_terrain(r, src[r]) if r in src else None
        rows = []
        for v in plan[r]['views']:
            if only and v['name'] not in only:
                continue
            if not (S.render(r, v['name'], before) or S.render(r, v['name'], after)):
                continue
            nums = ' | '.join(x for x in (_numbers(before, r, v['name']), _numbers(after, r, v['name'])) if x)
            rows.append(view_row(r, v, before, after, st, nums or None))
        if not rows:
            print(f'{r}: no view rendered in {before} or {after}')
            continue
        sheet = Image.new('RGB', (rows[0].width, sum(im.height for im in rows)), BG)
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        from surfacing_judge.baseline import file_name
        p = os.path.join(OUT, 'boards', f'{r}_{file_name(before)}_{file_name(after)}.jpg')
        sheet.save(p, quality=88)
        print(rel(p), len(rows), 'views')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
