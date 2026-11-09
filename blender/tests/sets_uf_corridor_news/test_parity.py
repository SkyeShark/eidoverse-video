"""The Blender corridor and evening news against the WebGPU originals: cn_parity_dump.mjs builds corridor.js and news.js
headless in Deno and dumps what they compute; this builds the Blender sets and compares, numerically:

  cn_lib    the mulberry32 streams, fit_text's sizes, measure_text's widths, build_mips, box_blur, height_field and
            normal_tex on a small drawn canvas, smooth
  textures  every canvas-made texture, pixel for pixel (the door relief and its normals, the plaque, the post, a typed
            post, the poll and a recount, the patch, the ribbons, the braid, the badge, the graffiti, the fence signs,
            the sign atlas, the livery, the chyron and its ticker) and the environments by direction
  corridor  update(): the doors, every uniform, every light; the cap's flight onto a head at capOn 0, 1/4, 1/2, 1
  news      the 79 pickets (place, turn, scale, seed, role, arm, signs), update(): uniforms and lights, the steam puffs
            and the hand lights placed by Geometry Nodes against the WebGPU's CPU placement at three times, the chyron's
            place()

    cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_corridor_news/cn_parity_dump.mjs
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_parity.py

Writes side-by-side sheets (WebGPU | Blender | difference x4) of every texture to out/parity/sheets/ for the eye.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL, corridor as COR, news as NEWS  # noqa: E402

PAR = F.OUT / 'parity'
SHEETS = PAR / 'sheets'
SHEETS.mkdir(parents=True, exist_ok=True)
J = json.load(open(PAR / 'cn.json', encoding='utf-8'))
check = F.check


def close(a, b, tol):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= tol)), float(np.max(np.abs(a - b))) if a.shape == b.shape else -1


# ============================================================================================ cn_lib's helpers ==
Lj = J['lib']
mx = 0.0
for s, v in Lj['streams'].items():
    r = CL.rng(int(s))
    got = [r() for _ in range(len(v))]
    mx = max(mx, max(abs(a - b) for a, b in zip(got, v)))
check('rng: mulberry32 streams bit for bit (11 seeds x 16)', mx == 0.0, f'max diff {mx}')
cv = CL.create_canvas(1024, 256)
g = cv.get_context('2d')
worst = 0.0
for f in Lj['fits']:
    size = CL.fit_text(g, f['txt'], x=512, y=128, max_w=f['maxW'], max_h=f['maxH'], family=CL.fam[f['fam']],
                       track=f['track'])
    worst = max(worst, abs(size - f['size']) / f['size'])
check('fit_text: the same font sizes as Skia (10 lines, 7 faces)', worst < 0.001, f'worst {worst * 100:.3f}%')
worst = 0.0
for k, w in Lj['widths'].items():
    fam_, px, weight, txt = k.split('|', 3)
    g.font = f'{weight} {px}px {CL.fam[fam_]}'.strip()
    worst = max(worst, abs(g.measure_text(txt).width - w) / max(w, 1e-6))
check('measure_text: unhinted, GPOS-kerned advances against Skia (12 runs, fake-bold Exo 2 included)', worst < 0.001,
      f'worst {worst * 100:.3f}%')
data = np.array([(i * 37 + 11) % 256 for i in range(7 * 5 * 4)], np.uint8)
mips = [[l['width'], l['height'], int(l['data'].astype(np.int64).sum())] for l in CL.build_mips(data, 7, 5)]
check('build_mips: the JS 2x2 chain (sizes and sums)', mips == Lj['mips'], f'{mips[:3]} vs {Lj["mips"][:3]}')
fld = np.array([((i * 7919) % 97) / 97 for i in range(9 * 6)], np.float32)
ok_, d = close(CL.box_blur(fld, 9, 6, 2, 2), Lj['blur'], 1e-5)
check('box_blur: radius 2, two passes, edges clamped', ok_, f'max {d:.2e}')
hc = CL.create_canvas(32, 24)
hg = hc.get_context('2d')
hg.fill_style = '#000'; hg.fill_rect(0, 0, 32, 24); hg.fill_style = '#fff'; hg.fill_rect(8, 6, 14, 10)
hg.begin_path(); hg.arc(24, 16, 5, 0, math.pi * 2); hg.fill_style = 'rgb(128,128,128)'; hg.fill()
hpix = hc.pixels()[..., 0].reshape(-1)
diffp = np.abs(hpix.astype(int) - np.array(Lj['heightCanvas'])).astype(float)
check('canvas: a filled rect and an anti-aliased disc match Skia', diffp.mean() < 1.5 and np.percentile(diffp, 99) < 40,
      f'mean {diffp.mean():.2f}, p99 {np.percentile(diffp, 99):.0f} (of 255)')
hf = CL.height_field(hc, blur=2)
ok_, d = close(hf['h'], Lj['height'], 0.02)
check('height_field: luminance, box-blurred twice', ok_, f'max {d:.4f}')
npx = CL.normal_pixels(hf, 6)[::-1].reshape(-1)                 # the JS DataTexture's rows are bottom-up
dn = np.abs(npx.astype(int) - np.array(Lj['normal'])).astype(float)
check('normal_tex: tangent normals from the heights (OpenGL, +V up)', dn.mean() < 1.0 and dn.max() <= 24,
      f'mean {dn.mean():.2f}, max {dn.max():.0f}')
check('smooth: the JS smoothstep helper', np.allclose([CL.smooth(a, b, x) for a, b, x in
                                                        [[0, 1, -0.5], [0, 1, 0.25], [0.2, 0.4, 0.33], [1, 0, 0.3]]],
                                                       Lj['smooth']))


# ================================================================================================= textures ==
def load_ref(rec):
    raw = np.fromfile(PAR / rec['file'], np.uint16 if rec['half'] else np.uint8)
    a = raw.reshape(rec['h'], rec['w'], 4)
    return a.astype(np.float32) if not rec['half'] else a.view(np.float16).astype(np.float32)


def img_pixels(name):
    im = bpy.data.images[name]
    W_, H_ = im.size
    px = np.empty(W_ * H_ * 4, np.float32)
    im.pixels.foreach_get(px)
    return np.round(px.reshape(H_, W_, 4) * 255.0)


def sheet(name, ref, got):
    """WebGPU | Blender | |difference| x 4, top-down, at most 1600 px wide."""
    from PIL import Image
    d = np.clip(np.abs(ref - got)[..., :3] * 4, 0, 255)
    rows = [np.clip(ref[..., :3], 0, 255), np.clip(got[..., :3], 0, 255), d]
    im = np.concatenate([r[::-1] for r in rows], 1).astype(np.uint8)
    pim = Image.fromarray(im, 'RGB')
    if pim.width > 1800:
        pim = pim.resize((1800, max(1, int(pim.height * 1800 / pim.width))), Image.Resampling.BOX)
    pim.save(SHEETS / f'{name}.png')


def compare_tex(label, rec, name, mean_tol=1.5, far_tol=0.015, channels=4, got=None):
    ref = load_ref(rec)
    if got is None:
        if name not in bpy.data.images:
            return check(f'texture {label}: the image {name} exists', False)
        got = img_pixels(name)
    if got.shape != ref.shape:
        return check(f'texture {label}: {ref.shape[1]} x {ref.shape[0]}', False, f'Blender {got.shape[1]} x {got.shape[0]}')
    d = np.abs(ref - got)[..., :channels]
    far = float((d.max(-1) > 64).mean())
    sheet(label.replace(' ', '_'), ref, got)
    return check(f'texture {label} ({rec["w"]} x {rec["h"]}): pixel parity with the WebGPU canvas',
                 d.mean() < mean_tol and far < far_tol,
                 f'mean |d| {d.mean():.2f}/255, {far * 100:.2f}% of pixels off by > 64')


sc = F.clean_scene()
F.render_settings(320, 180, 1)
C = COR.build(sc, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})
TC = {t['i']: t for t in J['corridor']['tex']}
compare_tex('flute heights', TC[1], 'corridor_flute')
compare_tex('door relief normals', TC[2], 'corridor_door_nrm')
compare_tex('door relief height and cavity', TC[3], 'corridor_door_mask')
compare_tex('plaque normals', TC[4], 'corridor_plaque_nrm')
compare_tex('plaque height and ink', TC[5], 'corridor_plaque_mask')
compare_tex('post', TC[6], 'corridor_post_0')
compare_tex('poll board', TC[7], 'corridor_poll_0')
compare_tex('patch albedo and thread mask', TC[8], 'corridor_patch_col')
compare_tex('patch stitch normals', TC[9], 'corridor_patch_nrm')
compare_tex('ribbon bar', TC[10], 'uniform_ribbons')
compare_tex('cap braid normals', TC[11], 'cap_braid_nrm', mean_tol=3.0)   # 3 px strokes, their slopes x 3 in normals
compare_tex('cap badge mask', TC[12], 'cap_badge_mask')
post = C.parts['postWall']
check('post: the layout Skia chose (size, lines)', abs(post['state']['layout']['size'] - J['corridor']['post']['layout']['size']) < 0.05
      and post['state']['layout']['lines'] == J['corridor']['post']['layout']['lines'],
      f"{post['state']['layout']['size']:.1f} {post['state']['layout']['lines']} vs "
      f"{J['corridor']['post']['layout']['size']:.1f} {J['corridor']['post']['layout']['lines']}")
# the typed post: the WebGPU edition redrew its canvas with the first n characters; the Blender LED wall shows the first n
# of a fully drawn post through its typing-order map (and draws the cursor from its lookup row): the same picture
var = post['variants'].items[0]
full, order = img_pixels(var['color'].name), img_pixels(var['order'].name)[..., 0]
n = int(math.floor(len(post['state']['text']) * 0.5 + 0.5))
card = np.array([round(c * 255) for c in CL.hex_srgb(0x090c12)] + [255.0])
typed = np.where(((order == 0) | (order <= n + 0.5))[..., None], full, card)
cur = np.empty(256 * 4, np.float32)                  # the cursor's lookup row: x, y, width per n (canvas pixels)
bpy.data.images[var['cursor'].name].pixels.foreach_get(cur)
cx, cy, cw = cur.reshape(256, 4)[n][:3]
Hp, Wp = typed.shape[:2]
ys, xs = np.mgrid[0:Hp, 0:Wp]
px_, py_ = xs + 0.5, (Hp - 1 - ys) + 0.5                              # canvas pixels (y down) of the bottom-up rows
inside = (px_ >= cx) & (px_ <= cx + cw) & (py_ >= cy) & (py_ <= cy + cw * (0.86 / 0.09))
typed = np.where(inside[..., None], np.array([round(c * 255) for c in CL.hex_srgb(0xc9973a)] + [255.0]), typed)
compare_tex('post typed to half', J['corridor']['typed'], None, got=typed, mean_tol=1.5, far_tol=0.01)
C.parts['poll'].set_tally(512000, 418000, 141000)
compare_tex('poll recount', J['corridor']['recount'], 'corridor_poll_1')


def env_dir_check(label, rec, img_name):
    ref = load_ref(rec)                                   # three equirect, rows bottom-up: v = 0 at the bottom
    im = bpy.data.images[img_name]
    W_, H_ = im.size
    px = np.empty(W_ * H_ * 4, np.float32)
    im.pixels.foreach_get(px)
    got = px.reshape(H_, W_, 4)
    worst = 0.0
    rr = np.random.default_rng(5)
    for _ in range(400):
        d = rr.normal(size=3)
        d /= np.linalg.norm(d)
        x, y, z = d                                       # three's axes
        u = math.atan2(z, x) / (2 * math.pi) + 0.5        # three's equirectUV
        v = math.asin(max(-1, min(1, y))) / math.pi + 0.5
        a = ref[min(rec['h'] - 1, int(v * rec['h'])), min(rec['w'] - 1, int(u * rec['w'])), :3]
        bx, by, bz = x, -z, y                             # Blender's axes, its Environment Texture's mapping
        ub = -math.atan2(by, bx) / (2 * math.pi) + 0.5
        vb = math.atan2(bz, math.hypot(bx, by)) / math.pi + 0.5
        b = got[min(H_ - 1, int(vb * H_)), min(W_ - 1, int(ub * W_)), :3]
        worst = max(worst, float(np.max(np.abs(a - b) / (np.abs(a) + 0.02))))
    return check(f'environment {label}: the same light in every direction (400 directions, nearest texel)', worst < 0.15,
                 f'worst relative {worst:.3f}')


env_dir_check('corridor', TC[0], 'corridor_env')

# --------------------------------------------------------------------------------------------- corridor update
head = bpy.data.objects.new('parity_head', None)
C.collection.objects.link(head)
head.parent = C.group
Mh = CL.m4(0.12, 1.47, 0.05, 0.1, -0.3, 0.05)                         # three's Object3D(position, rotation XYZ)
head.matrix_basis = Matrix(CL.to_blender_matrix(Mh).tolist())
bpy.context.view_layer.update()
C3 = np.array(CL.C_THREE)
for rec in J['corridor']['cap']:
    C.update(2.0, {'capOn': rec['capOn'], 'capHead': head, 'open': 0.4, 'lights': 0.8, 'screen': 0.6, 'beyond': 0.7,
                   'gap': 0.5})
    cap = C.parts['cap']
    Ml = np.array(cap.matrix_basis)
    M3 = C3.T @ Ml @ C3                                                # Blender local -> three local
    pos = M3[:3, 3]
    R = M3[:3, :3] / np.linalg.norm(M3[:3, :3], axis=0)
    qj = rec['q']
    Rj = np.array(Quaternion((qj[3], qj[0], qj[1], qj[2])).to_matrix())
    dp = float(np.max(np.abs(pos - rec['pos'])))
    dr = float(np.max(np.abs(R - Rj)))
    check(f'cap: capOn {rec["capOn"]} lands where the WebGPU cap does (position, turn)', dp < 1e-4 and dr < 1e-4,
          f'|dp| {dp:.2e} m, |dR| {dr:.2e}')
U_ = J['corridor']['update']
check('doors: pivots at open 0.4 (eased)', abs(C.parts['doors']['left'].rotation_euler[2] - U_['pivotL']) < 1e-6
      and abs(C.parts['doors']['right'].rotation_euler[2] - U_['pivotR']) < 1e-6,
      f"{C.parts['doors']['left'].rotation_euler[2]:.5f} vs {U_['pivotL']:.5f}")
bad = [k for k, v in U_['U'].items() if abs(C.group[k] - v) > 1e-9]
check('uniforms: t, open, gap, screen, lights, flick, beyond as the WebGPU update sets them', not bad, str(bad))
lit = C.parts['lights']
bad = []
for k, cd in U_['lights'].items():
    if k == 'hemi':
        continue
    w = lit[k].data.energy                       # a float32 in Blender: compare to its precision, not to 1e-4 W
    if abs(w - cd * 4 * math.pi) > 1e-6 * max(1.0, cd * 4 * math.pi):
        bad.append((k, w, cd))
check('lights: every lamp at the WebGPU intensity (cd x 4 pi W, to float32 precision)', not bad, str(bad))
check('shafts: shown while the doors part', not C.parts['shafts'].hide_render)
C.dispose()

# ======================================================================================================= news ==
sc = F.clean_scene()
N = NEWS.build(sc)
TN = {t['i']: t for t in J['news']['tex']}
compare_tex('graffiti channels (fill, outline, paint time, drips)', TN[1], 'news_graffiti')
compare_tex('fence signs', TN[2], 'news_fence_signs')
compare_tex('picket sign atlas', TN[3], 'news_sign_atlas', mean_tol=2.0, far_tol=0.02)   # 8 hand-lettered tiles
compare_tex('van livery', TN[4], 'news_van_livery')
compare_tex('chyron', TN[5], 'news_chyron_0')
compare_tex('chyron ticker', TN[6], 'news_chyron_ticker_0')
env_dir_check('news', TN[0], 'news_env')
P = N.parts['people']
Pj = J['news']['people']
same = len(P) == len(Pj) and all(p['role'] == q['role'] and p['variant'] == q['variant'] and p['front'] == q['front']
                                 and p['back'] == q['back'] for p, q in zip(P, Pj))
num = max(max(abs(p[k] - q[k]) for k in ('x', 'z', 'yaw', 'scale', 'seed', 'theta')) for p, q in zip(P, Pj)) if same else -1
check('pickets: the same 79 people (place, turn, scale, seed, role, arm, sign faces)', same and num < 1e-9, f'max {num:.1e}')
Uj = J['news']['update']
N.update(4.0, {'spray': 0.4, 'floods': 0.5, 'lights': 0.9, 'chant': 0.7, 'pulse': 0.2})
bad = [k for k, v in Uj['U'].items() if abs(N.group[k] - v) > 1e-9]
check('news uniforms: t, spray, floods, lights, chant, pulse, blink', not bad, str(bad))
Ls = N.parts['lights']
got = [l.data.energy for l in Ls['floods']] + [l.data.energy for l in Ls['street']] + [Ls['news'].data.energy,
                                                                                         Ls['graffiti'].data.energy]
want = [c * 4 * math.pi for c in Uj['floods'] + Uj['street'] + [Uj['news'], Uj['graffiti']]]
check('news lights: floods, street, the crew LED, the graffiti lamp', np.allclose(got, want, atol=1e-4))


def quads(ob):
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.to_mesh()
    Pq = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', Pq)
    e.to_mesh_clear()
    Pq = Pq.reshape(-1, 4, 3)
    centre = Pq.mean(1)
    edge = np.linalg.norm(Pq[:, 1] - Pq[:, 0], axis=1)
    return np.stack([centre[:, 0], centre[:, 2], -centre[:, 1]], 1), edge     # three axes


for rec in J['news']['billboards']:
    N.update(rec['t'], {'chant': 1.0, 'pulse': 0.3})
    bpy.context.view_layer.update()
    c, e = quads(N.parts['steam'])
    sj = np.array(rec['steam'])
    dp = float(np.max(np.abs(c - sj[:, :3])))
    ds = float(np.max(np.abs(e - sj[:, 3])))
    check(f'steam at t = {rec["t"]}: 110 puffs where the WebGPU placed them, at its sizes', dp < 2e-3 and ds < 2e-3,
          f'|dp| {dp:.1e} m, |ds| {ds:.1e} m')
    c, e = quads(N.parts['handlights'])
    hj = np.array(rec['hand'])
    dp = float(np.max(np.abs(c - hj[:, :3])))
    check(f'hand lights at t = {rec["t"]}: at the raised hands, as the WebGPU placed them', dp < 2e-3 and
          float(np.max(np.abs(e - hj[:, 3]))) < 1e-4, f'|dp| {dp:.1e} m')
cam = bpy.data.objects.new('parity_overlay_cam', bpy.data.cameras.new('parity_overlay_cam'))
sc.collection.objects.link(cam)
ob = N.parts['chyron'].place(cam, fov=42, aspect=16 / 9)
pj = J['news']['chyron']['place']
check('chyron: place() lays it where the WebGPU did (z = -1, lower third, 86% wide)',
      np.allclose(tuple(ob.location), pj['pos'], atol=1e-6) and abs(ob.scale[0] - pj['scale']) < 1e-6,
      f'{tuple(round(v, 5) for v in ob.location)} x {ob.scale[0]:.5f}')
check('chyron: the same text', all(N.parts['chyron']['state'][k] == v for k, v in J['news']['chyron']['state'].items()))
N.dispose()
F.summary()
