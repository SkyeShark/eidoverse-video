"""Build, plan and key a storm in Blender, then check what the keyed scene evaluates to. No render (no GPU slot).

    bash run_blender.sh blender/tests/weather/test_blender_build.py

A small street (ground, a building, an awning) under a sky that goes overcast -> darkstorm in 1 s, with a forced
local strike. Checks, each a PASS/FAIL line:
  - the rain streaks the Geometry Nodes tree evaluates at a keyed frame are the JS world-tiled streaks (positions of
    every quad corner against weather_system.js's formulas, in float32 numpy), with the JS opacity under the canopy
  - streaks under the awning and the roof are hidden (the Raycast shelter), streaks in the open are not
  - splashes sit on the surface the rain reaches (ground at 0.015 m, the roof), never under the awning
  - the forced strike lands on a target surface 34-58 m ahead, its bolt is drawn only while its channel glows, and
    the impact sparks / puffs / scorch evaluate where lightning.py puts them
  - the moisture sequence, the shader values and the eido_weather audio properties are keyed; eido_wet wraps the
    street's materials and unwrap restores them exactly
"""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from eidoblend.weather import lightning as L  # noqa: E402

OUT = os.path.join(HERE, 'out', 'build')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 72
sc.render.resolution_x, sc.render.resolution_y = 320, 180
street = bpy.data.collections.new('street')
sc.collection.children.link(street)


def box(name, size, loc, mat):
    me = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz), (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz),
         (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    street.objects.link(ob)
    return ob


asphalt = bpy.data.materials.new('asphalt')
asphalt.use_nodes = True
asphalt.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.05, 0.055, 1)
asphalt.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
brick = bpy.data.materials.new('brick')
brick.use_nodes = True
ground = box('ground', (400, 400, 0.2), (0, 0, -0.1), asphalt)
building = box('building', (10, 10, 8), (15, 20, 4), brick)
awning = box('awning', (10, 3, 0.1), (0, 6.5, 3.0), brick)
cam_d = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_d)
sc.collection.objects.link(cam)
cam.location = (0, -10, 1.7)
cam.rotation_euler = (math.radians(90), 0, 0)
sc.camera = cam

sky = make_sky(sc, camera=cam, hours=15.0, weather='overcast', cache_dir=os.path.join(OUT, 'cache'), quality='draft')
sky.transition_to('darkstorm', 1.0, 1.0, at=0.2)
wx = make_weather_system(sc, sky, occluders=street, strike_targets=[street])
wx.debug_force_local_strike(at=0.5)
n_wrapped = wx.wrap_scene()
check('wrap_scene wraps the street materials', n_wrapped == 2, n_wrapped)
rows = wx.bake(bake_sky=False)
check('planned every frame', len(rows) == 72, len(rows))

# ---- the rain streaks against weather_system.js ----
F = 60
sc.frame_set(F)
row = wx._rows[F]
dg = bpy.context.evaluated_depsgraph_get()
rain = bpy.data.objects['eido_rain'].evaluated_get(dg).data
N = wx.opts['rain_count']
co = np.empty(len(rain.vertices) * 3, np.float32)
rain.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
check('rain: 4 vertices per streak', len(co) == 4 * N, len(co))
f32 = np.float32
idx = np.arange(N, dtype=f32)


def fract(x):
    return x - np.floor(x)


def hashI(n, k):
    q = fract(n * f32(0.1031) + f32(k * 0.61803))
    q2 = q * (q + f32(33.33))
    return fract(q2 * (q2 + q))


h1, h2, h3, h4 = (hashI(idx, k) for k in (1, 2, 3, 4))
cx, cy, cz = (f32(v) for v in row['cam3'])
P = f32(wx.opts['rain_radius'] * 2)
H = f32(wx.opts['rain_height'])
wox, woz = f32(row['wind_offset'][0]), f32(row['wind_offset'][2])
px = cx + (fract(h1 + (wox - cx) / P) - f32(0.5)) * P
pz = cz + (fract(h2 + (woz - cz) / P) - f32(0.5)) * P
py = cy + (fract(h3 - f32(row['fall_phase']) / H - cy / H) - f32(0.35)) * H
base = np.stack([px, py, pz], 1)
wv = row['wind']
sd = np.array([wv[0], -row['fall'], wv[2]], np.float64)
sd /= np.linalg.norm(sd)
dist = np.linalg.norm(base - np.array(row['cam3'], np.float32), axis=1)
ln = row['streak_len'] * (h1 * h1 * 1.1 + 0.45)
wd = ln * 0.125 * (h2 * 0.8 + 0.55) * (dist * 0.012 + 1.0)
right = np.array(row['right3'])
corners = [base + right[None] * (s * wd)[:, None] + sd[None] * (e * ln)[:, None] for s in (-0.5, 0.5) for e in (0, 1)]
ev = np.stack([c[:, [0, 2, 1]] * np.array([1, -1, 1]) for c in corners], 1)   # three -> Blender
got = co.reshape(N, 4, 3)
err = np.min(np.linalg.norm(got[:, :, None, :] - ev[:, None, :, :], axis=3), axis=2)
check('rain: every quad corner where weather_system.js puts it (float32, < 2 cm)', float(err.max()) < 0.02,
      'max %.4f m, mean %.5f m' % (err.max(), err.mean()))
alpha = np.empty(len(rain.vertices), np.float32)
rain.attributes['eido_alpha'].data.foreach_get('value', alpha)
a = alpha.reshape(N, 4)[:, 0]
near = np.clip((dist - 0.9) / (2.6 - 0.9), 0, 1)
near = near * near * (3 - 2 * near)
fd = np.hypot(px - cx, pz - cz)
ff = 1 - np.clip((fd - P / 2 * 0.7) / (P / 2 * 0.3), 0, 1) ** 2 * (3 - 2 * np.clip((fd - P / 2 * 0.7) / (P / 2 * 0.3), 0, 1))
canopy = min(1.0, max(0.0, row['storm_canopy']))
check('rain: darkstorm canopy sealed at this frame', canopy > 0.99, canopy)
rk = row['rain_k']
cg = np.clip((rk - h1) / 0.001, 0, 1)
cg = cg * cg * (3 - 2 * cg)
want = near * ff * (h4 * 0.18 + 0.82) * (h3 * 0.125 + 0.075) * row['dense_a'] * cg * min(1, rk * 2) * (1 + 0.28 * canopy * min(1, rk))
# streaks the shelter hides (alpha 0 where the JS has none) are judged below; compare the open ones
ev_top = base + sd[None] * ln[:, None]
open_ = alpha.reshape(N, 4)[:, 0] > 0
check('rain: opacity of open streaks = the JS opacity (canopy gate, population, density)',
      np.allclose(a[open_], want[open_], atol=2e-3), 'max diff %.5f over %d streaks' % (np.abs(a[open_] - want[open_]).max(), open_.sum()))
# shelter: a streak whose top lies under the awning or inside the building footprint below its roof is hidden
topb = ev_top[:, [0, 2, 1]] * np.array([1, -1, 1])
under_awning = (np.abs(topb[:, 0]) < 4.5) & (np.abs(topb[:, 1] - 6.5) < 1.0) & (topb[:, 2] < 2.9) & (topb[:, 2] > 0.2)
in_building = (np.abs(topb[:, 0] - 15) < 4.5) & (np.abs(topb[:, 1] - 20) < 4.5) & (topb[:, 2] < 7.9)
sheltered = (under_awning | in_building) & (want > 1e-4)
check('rain: streaks under the awning and inside the building are hidden (%d of them)' % sheltered.sum(),
      sheltered.sum() > 0 and np.all(a[sheltered] == 0))
exposed = ((~under_awning) & (~in_building) & (want > 1e-3) & (np.abs(topb[:, 0]) > 7) & (np.abs(topb[:, 0] - 15) > 7)
           & (topb[:, 2] > 0.05))
below = (want > 1e-3) & (topb[:, 2] < -0.25)
check('rain: streaks in the open keep their opacity (%d)' % exposed.sum(), np.all(a[exposed] > 0),
      int((a[exposed] == 0).sum()))
check('rain: streaks below the ground are sheltered by it (%d)' % below.sum(), np.all(a[below] == 0))

# ---- the cell gate through the weather map, mid-transition (canopy half sealed, rain falling) ----
from eidoblend.sky.bake.baker import weather_map  # noqa: E402
FM = 17
wm = weather_map()[..., 0].astype(np.float64)


def coverage3(rm, x3, z3):
    """tslCoverage at three (x, z): the weather map, bilinear at GPU texel centres, repeat-wrapped."""
    nn = wm.shape[0]
    s_ = -0.00005 * rm['w_scale']
    pu = ((z3 - rm['cloud_drift'][2]) * s_) * nn - 0.5
    pv = ((x3 - rm['cloud_drift'][0]) * s_) * nn - 0.5
    iu, iv = np.floor(pu).astype(np.int64), np.floor(pv).astype(np.int64)
    fu, fv = pu - iu, pv - iv
    g_ = lambda a_, b_: wm[b_ % nn, a_ % nn]
    return np.clip(((g_(iu, iv) * (1 - fu) + g_(iu + 1, iv) * fu) * (1 - fv) + (g_(iu, iv + 1) * (1 - fu)
                    + g_(iu + 1, iv + 1) * fu) * fv - rm['large_t']) * rm['large_a'], 0, 2)


def rain_alpha_at(fm):
    """The eido_alpha the rain generator evaluates at frame fm, one value per streak."""
    sc.frame_set(fm)
    me_ = bpy.data.objects['eido_rain'].evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    a_ = np.empty(len(me_.vertices), np.float32)
    me_.attributes['eido_alpha'].data.foreach_get('value', a_)
    return a_.reshape(N, 4)[:, 0]


def want_rain_alpha(rm, upwind):
    """weather_system.js's streak opacity at a frame record: the cell gate at the column the drops fell from (upwind,
    Eanpa's rainCellAt) or at the drop's own column (eidoverse), opened under the canopy. Returns (alpha, coverage)."""
    cx2, cy2, cz2 = (f32(v) for v in rm['cam3'])
    wox2, woz2 = f32(rm['wind_offset'][0]), f32(rm['wind_offset'][2])
    px2 = cx2 + (fract(h1 + (wox2 - cx2) / P) - f32(0.5)) * P
    pz2 = cz2 + (fract(h2 + (woz2 - cz2) / P) - f32(0.5)) * P
    py2 = cy2 + (fract(h3 - f32(rm['fall_phase']) / H - cy2 / H) - f32(0.35)) * H
    kk = np.maximum(rm['cloud_start'] - py2.astype(np.float64), 0) / max(rm['fall'], 1.0) * (1.0 if upwind else 0.0)
    cov = coverage3(rm, px2 - rm['wind'][0] * kk, pz2 - rm['wind'][2] * kk)
    tt = np.clip((cov - rm['cell_lo']) / (rm['cell_hi'] - rm['cell_lo']), 0, 1)
    can = min(1.0, max(0.0, rm['storm_canopy']))
    gate2 = tt * tt * (3 - 2 * tt)
    gate2 = gate2 + (h4 * 0.18 + 0.82 - gate2) * can
    d2 = np.linalg.norm(np.stack([px2, py2, pz2], 1) - np.array(rm['cam3'], np.float32), axis=1)
    nf2 = np.clip((d2 - 0.9) / 1.7, 0, 1)
    nf2 = nf2 * nf2 * (3 - 2 * nf2)
    q2 = np.clip((np.hypot(px2 - cx2, pz2 - cz2) - P / 2 * 0.7) / (P / 2 * 0.3), 0, 1)
    ff2 = 1 - q2 * q2 * (3 - 2 * q2)
    rk2 = rm['rain_k']
    cg2 = np.clip((rk2 - h1) / 0.001, 0, 1)
    cg2 = cg2 * cg2 * (3 - 2 * cg2)
    return (nf2 * ff2 * gate2 * (h3 * 0.125 + 0.075) * rm['dense_a'] * cg2 * min(1, rk2 * 2)
            * (1 + 0.28 * can * min(1, rk2))), cov


rm = wx._rows[FM]
al2 = rain_alpha_at(FM)
want2, cov = want_rain_alpha(rm, upwind=True)
can, rk2 = min(1.0, max(0.0, rm['storm_canopy'])), rm['rain_k']
op2 = al2 > 0
check('rain: mid-transition opacity through the weather-map cell gate (canopy %.2f, rainK %.2f, coverage %.2f-%.2f)'
      % (can, rk2, cov[op2].min() if op2.any() else 0, cov[op2].max() if op2.any() else 0),
      op2.sum() > 100 and np.allclose(al2[op2], want2[op2], atol=3e-3),
      'max diff %.5f over %d streaks' % (np.abs(al2[op2] - want2[op2]).max() if op2.any() else -1, op2.sum()))
sc.frame_set(F)
dg = bpy.context.evaluated_depsgraph_get()

# ---- splashes ----
sp = bpy.data.objects['eido_splashes'].evaluated_get(dg).data
NS = wx.opts['splash_count']
sco = np.empty(len(sp.vertices) * 3, np.float32)
sp.vertices.foreach_get('co', sco)
sco = sco.reshape(NS, 4, 3)
centers = sco.mean(axis=1)
sal = np.empty(len(sp.vertices), np.float32)
sp.attributes['eido_alpha'].data.foreach_get('value', sal)
vis = sal.reshape(NS, 4)[:, 0] > 1e-4
on_roof = (np.abs(centers[:, 0] - 15) < 5) & (np.abs(centers[:, 1] - 20) < 5)
under = (np.abs(centers[:, 0]) < 5) & (np.abs(centers[:, 1] - 6.5) < 1.5)
z = centers[:, 2]
lvl = [np.isclose(z, h, atol=0.01) for h in (0.015, 3.065, 8.015)]
check('splashes: every visible ring lies on an upward surface: ground 0.015 / awning 3.065 / roof 8.015 m',
      np.all((lvl[0] | lvl[1] | lvl[2])[vis]),
      'ground %d awning %d roof %d' % ((vis & lvl[0]).sum(), (vis & lvl[1]).sum(), (vis & lvl[2]).sum()))
check('splashes: no ring on the ground under the awning', not np.any(vis & under & (centers[:, 2] < 1.0)))

# ---- lightning ----
ev0 = wx.sched.events
check('lightning: events happened', len(ev0) >= 1, len(ev0))
imps = wx.sched.impacts
check('lightning: the forced strike is local', len(imps) >= 1, len(imps))
if imps:
    imp = imps[0]
    p3 = imp['point']
    cam3 = rows[[r['t'] for r in rows].index(min((r['t'] for r in rows), key=lambda t: abs(t - imp['birth'])))]['cam3']
    d = math.hypot(p3[0] - cam3[0], p3[2] - cam3[2])
    check('lightning: the forced strike lands 34-58 m ahead on a target surface',
          34 - 1e-6 <= d <= 58 + 1e-6 and (abs(p3[1]) < 0.01 or abs(p3[1] - 8) < 0.01), 'd %.2f y %.3f' % (d, p3[1]))
    fps = 24
    bf = 1 + imp['birth'] * fps
    I = imp['interval']
    bolt = bpy.data.objects.get('eido_bolt_%03d' % I)
    check('lightning: a bolt object for the strike', bolt is not None)
    sc.frame_set(int(round(bf)) + 1)
    on = (not bolt.hide_render) and bolt['eido_channel'] > 0.02
    sc.frame_set(int(round(bf)) + 30)
    off = bolt.hide_render
    check('lightning: the bolt draws while its channel glows and is hidden after', on and off)
    age_f = int(round(bf)) + 5
    sc.frame_set(age_f)
    age = (age_f - 1) / fps - imp['birth']
    dg = bpy.context.evaluated_depsgraph_get()
    spk = bpy.data.objects['eido_impact_sparks_%03d' % I].evaluated_get(dg).data
    sco2 = np.empty(len(spk.vertices) * 3, np.float32)
    spk.vertices.foreach_get('co', sco2)
    per = len(sco2) // 3 // wx.sched.spark_count
    c0 = sco2.reshape(-1, per, 3).mean(axis=1)
    want0 = [L.spark_at(imp['point'], imp['data']['normal'], s, age)[0] for s in imp['data']['sparks']]
    want0 = np.array([(w[0], -w[2], w[1]) for w in want0])
    check('impact: every spark where updateImpactPool puts it (age %.3f s)' % age,
          np.allclose(c0, want0, atol=1e-3), float(np.abs(c0 - want0).max()))
    puf = bpy.data.objects['eido_impact_puffs_%03d' % I].evaluated_get(dg).data
    check('impact: 16 puff bodies of 42 vertices', len(puf.vertices) == 16 * 42, len(puf.vertices))
    scr = bpy.data.objects['eido_impact_scorch_%03d' % I].evaluated_get(dg).data
    sv = np.empty(len(scr.vertices) * 3, np.float32)
    scr.vertices.foreach_get('co', sv)
    sv = sv.reshape(-1, 3)
    c3 = imp['point']
    n3 = imp['data']['normal']
    cen = np.array((c3[0] + n3[0] * 0.018, -(c3[2] + n3[2] * 0.018), c3[1] + n3[1] * 0.018))
    rad = np.linalg.norm(sv - cen, axis=1).max()
    check('impact: scorch disc centred 1.8 cm above the strike, radius = its hashed size',
          np.allclose(sv.mean(axis=0), cen, atol=1e-3) and abs(rad - imp['data']['scorch_size']) < 1e-3,
          'r %.3f want %.3f' % (rad, imp['data']['scorch_size']))
    sc.frame_set(int(round(bf)) + 24 * 6)
    dg = bpy.context.evaluated_depsgraph_get()
    gone = len(bpy.data.objects['eido_impact_sparks_%03d' % I].evaluated_get(dg).data.vertices) == 0
    check('impact: sparks gone after their 0.82 s life', gone)

# ---- a saved .blend replays the weather on its own (no Python weather code in the reloaded process) ----
import hashlib  # noqa: E402
import json as _json  # noqa: E402
import subprocess  # noqa: E402


def measure(frames_):
    out = {}
    for f in frames_:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.objects['eido_rain'].evaluated_get(dg).data
        c = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', c)
        vg = bpy.data.node_groups['eido_weather_values']
        sp_ = [o for o in bpy.data.objects if o.name.startswith('eido_impact_sparks_')]
        out[str(f)] = dict(rain_vertices=len(me.vertices), rain_sum=float(np.round(c.astype(np.float64).sum(), 2)),
                           rain_md5=hashlib.md5(np.round(c, 3).tobytes()).hexdigest(),
                           light_energy=float(bpy.data.objects['eido_lightning_light'].data.energy),
                           rain_light=float(vg.nodes['rain_light'].outputs[0].default_value),
                           wetness=float(vg.nodes['wetness'].outputs[0].default_value),
                           bolts_drawn=sorted(o.name for o in bpy.data.objects
                                              if o.name.startswith('eido_bolt_') and not o.hide_render),
                           spark_vertices=sum(len(o.evaluated_get(dg).data.vertices) for o in sp_),
                           moisture_image=True)
    return out


check_frames = [F] + ([int(round(1 + imps[0]['birth'] * 24)) + d for d in (1, 5)] if imps else [])
live = measure(check_frames)
blend = os.path.join(OUT, 'storm_build.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
r = subprocess.run([bpy.app.binary_path, '--background', '--factory-startup', blend, '--python',
                    os.path.join(HERE, 'check_saved_blend.py'), '--'] + [str(f) for f in check_frames],
                   capture_output=True, text=True)
line = next((ln for ln in r.stdout.splitlines() if ln.startswith('SAVED_BLEND_JSON ')), None)
saved = _json.loads(line[len('SAVED_BLEND_JSON '):]) if line else {}
same = bool(saved) and all(
    saved[k]['rain_vertices'] == live[k]['rain_vertices'] and saved[k]['rain_md5'] == live[k]['rain_md5']
    and abs(saved[k]['light_energy'] - live[k]['light_energy']) < 1e-3
    and abs(saved[k]['rain_light'] - live[k]['rain_light']) < 1e-6
    and abs(saved[k]['wetness'] - live[k]['wetness']) < 1e-6 and saved[k]['bolts_drawn'] == live[k]['bolts_drawn']
    and saved[k]['spark_vertices'] == live[k]['spark_vertices'] and saved[k]['moisture_image'] for k in live)
check('a saved .blend replays rain, light, bolt, sparks and shader values with no Python (frames %s)' % check_frames,
      same, '' if same else (r.stderr[-600:] or str((live, saved))[:600]))
if imps:
    k1 = str(check_frames[1])
    check('  ... at the strike the reloaded file draws the bolt and the sparks and lights the street',
          bool(saved) and saved[k1]['bolts_drawn'] and saved[k1]['spark_vertices'] > 0
          and saved[k1]['light_energy'] > 1000, saved.get(k1))
os.remove(blend)

# ---- the rain shadow: exact under the awning, soft at the building's leeward edge (the gust taps) ----
import OpenImageIO as oiio  # noqa: E402
from eidoblend.weather.shelter import exposure_at  # noqa: E402
meta = wx.shelter


def read_exr(name):
    buf = oiio.ImageBuf(os.path.join(wx.cache_dir, name))
    return np.asarray(buf.get_pixels(oiio.FLOAT)).reshape(meta['h'], meta['w'], 4)[::-1]       # rows bottom-up


emap, smap = read_exr('rain_exposure.exr'), read_exr('rain_exposure_soft.exr')
d_ = meta['d']
edge_x = 20.0 + 8.0 * (-d_[0] / d_[2])        # the leeward foot of the 8 m building's rain shadow
ys = 20.0 + 8.0 * (-d_[1] / d_[2])
prof = [exposure_at(x, ys, 0.0, 1.0, emap, meta, smap) for x in np.arange(edge_x - 3.0, edge_x + 3.001, 0.1)]
steps = np.abs(np.diff(prof))
check('rain shadow: the building\'s leeward edge ramps smoothly over metres (gust-soft mask, no bands)',
      prof[0] < 0.02 and prof[-1] > 0.98 and all(b >= a - 1e-6 for a, b in zip(prof, prof[1:]))
      and steps.max() < 0.1 and sum(0.05 < e < 0.95 for e in prof) >= 12,
      'max step %.3f, %s' % (steps.max(), [round(e, 2) for e in prof[::5]]))
exact_edge = [exposure_at(x, ys, 0.0, 1.0, emap, meta) for x in np.arange(edge_x - 3.0, edge_x + 3.001, 0.1)]
check('  ... where the exact test alone steps from 0 to 1 at one cell', np.abs(np.diff(exact_edge)).max() > 0.9)
aw = exposure_at(0.0 + 3.0 * (-d_[0] / d_[2]), 6.5 + 3.0 * (-d_[1] / d_[2]), 0.0, 1.0, emap, meta, smap)
check('rain shadow: the ground under the middle of the awning stays sheltered (a 3 m occluder swings 0.45 m)',
      aw < 0.02, aw)
check('rain shadow: open ground is fully exposed', exposure_at(-30.0, -30.0, 0.0, 1.0, emap, meta, smap) > 0.999)
roof = exposure_at(15.0, 20.0, 8.0, 1.0, emap, meta, smap)
check('rain shadow: the roof (a raised surface) keeps the exact test: exposed', roof > 0.999, roof)

# ---- keyed data for the shader and the audio contract ----
sc.frame_set(F)
mp = os.path.join(wx.cache_dir, 'moisture_%04d.exr')
check('moisture sequence written for every frame (and the hold copy)', all(os.path.exists(mp % f) for f in range(0, 73)))
vg = bpy.data.node_groups['eido_weather_values']
check('shader values keyed (rain light, rain colour, wetness, time ...)',
      vg.animation_data is not None and vg.animation_data.action is not None)
from eidoblend.media.weather_audio import read_props  # noqa: E402
st = read_props(sc, F)
check('eido_weather audio contract reads the keyed state', abs(st['rainK'] - row['rain_k']) < 1e-4
      and abs(st['wind'] - row['wind_len']) < 1e-3, st)
tl = wx.audio_timeline()
check('audio timeline: rain bed and wind envelopes, one thunder per strike',
      len(tl['rain']) > 0 and len(tl['wind']) > 0 and tl['stats']['strikes'] == len(ev0), tl['stats'])
pr = asphalt.node_tree.nodes['Principled BSDF']
check('eido_wet sits in front of the asphalt Principled BSDF',
      pr.inputs['Base Color'].is_linked and pr.inputs['Base Color'].links[0].from_node.name.startswith('eido_wet'))
from eidoblend.weather.wet import unwrap_material  # noqa: E402
unwrap_material(asphalt)
check('unwrap restores the asphalt exactly', not pr.inputs['Base Color'].is_linked
      and tuple(pr.inputs['Base Color'].default_value) == (0.05000000074505806, 0.05000000074505806, 0.054999999701976776, 1.0)
      and abs(pr.inputs['Roughness'].default_value - 0.8) < 1e-6 and not pr.inputs['Normal'].is_linked)

# ---- receiver flags (userData noWet / noPuddles / wetPorosity, per object and per material) ----
from eidoblend.weather.wet import wrap_material  # noqa: E402
m_nowet = bpy.data.materials.new('glass_no_wet')
m_nowet.use_nodes = True
m_nowet['eido_noWet'] = 1
check('material eido_noWet is never wrapped', wrap_material(m_nowet) is False)
m_np = bpy.data.materials.new('leaves_no_puddles')
m_np.use_nodes = True
m_np['eido_noPuddles'] = 1
m_np['eido_wetPorosity'] = 0.2
wrap_material(m_np)
g = next(n for n in m_np.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup' and n.node_tree.name == 'eido_wet')
check('material eido_noPuddles / eido_wetPorosity reach the group', g.inputs['Puddle Gate'].default_value == 0.0
      and abs(g.inputs['Porosity'].default_value - 0.2) < 1e-6)
m_dry = bpy.data.materials.new('dry_only')
m_dry.use_nodes = True
dry_ob = box('dry_box', (1, 1, 1), (60, 60, 0.5), m_dry)
dry_ob['eido_dry'] = 1
before = len(wx.wrapped)
wx.wrap_scene()
check('object eido_dry: its materials are skipped', not m_dry.get('eido_wet_wrapped'))

# ---- dispose restores the scene and unhooks the sky ----
wx.dispose()
check('dispose: weather objects removed, sky unhooked, materials unwrapped',
      bpy.data.collections.get('eido_weather') is None and not sky.callbacks
      and not brick.get('eido_wet_wrapped'))

# ---- a heightfield strike target (strikeHeightAt) and the local-strike callback ----
seen = []
wx2 = make_weather_system(sc, sky, strike_targets=None, strike_height_at=lambda x, y: 0.05 * x + 1.0,
                          on_local_strike=seen.append, moisture=False)
wx2.debug_force_local_strike(at=0.5)
wx2.bake(bake_sky=False)
imp = wx2.sched.impacts[0] if wx2.sched.impacts else None
check('strike_height_at: the forced strike lands on the heightfield', imp is not None and seen
      and seen[0]['kind'] == 'terrain_heightfield' and abs(seen[0]['point'][2] - 0.04 - (0.05 * seen[0]['point'][0] + 1.0)) < 1e-6,
      seen[:1])
if seen:
    n = seen[0]['normal']
    check('strike_height_at: the impact normal is the heightfield slope (Blender axes)',
          abs(n[0] - (-0.05 / math.sqrt(1.0025))) < 1e-6 and abs(n[2] - 1 / math.sqrt(1.0025)) < 1e-6, n)
wx2.dispose()

# ---- the other options: the eidoverse wet model, colours, a callable target, the gap scale, no splashes ----
wx3 = make_weather_system(sc, sky, wet_model='eidoverse', strike_targets=lambda: [street], splash_count=0,
                          rain_count=2000, moisture=False, shield_color=(1.0, 0.3, 0.2), rain_color=(1.0, 0.55, 0.3),
                          occluders=street, wet_exposure=False)
wx3.wrap_scene()
pr = asphalt.node_tree.nodes['Principled BSDF']
gname = pr.inputs['Base Color'].links[0].from_node.node_tree.name if pr.inputs['Base Color'].is_linked else None
check("wet_model='eidoverse': the asphalt is wrapped by eido_wet_eidoverse", gname == 'eido_wet_eidoverse', gname)
check('colours: the record keeps rain and shield (an Earth sky ignores the shield, as the JS warns)',
      wx3.get_colors()['rain'] == (1.0, 0.55, 0.3) and wx3.get_colors()['shield'] == (1.0, 0.3, 0.2)
      and sky.wx.color['rain'] == (1.0, 0.55, 0.3), wx3.get_colors())
wx3.debug_force_local_strike(at=0.5)
rows3 = wx3.bake(bake_sky=False)
check('strike_targets as a callable: the forced strike lands on the street', len(wx3.sched.impacts) == 1
      and min(abs(wx3.sched.impacts[0]['point'][1] - h) for h in (0.0, 3.05, 8.0)) < 0.01,
      [i['point'] for i in wx3.sched.impacts])
hidden = []
for f in (10, 40, 70):
    sc.frame_set(f)
    hidden.append((bpy.data.objects['eido_splashes'].hide_render, bpy.data.objects['eido_rain'].hide_render))
check('splash_count=0: the splashes are hidden on every frame, the rain is not',
      all(s and not r for s, r in hidden[1:]), hidden)
dg = bpy.context.evaluated_depsgraph_get()
check('rain_count=2000: 2000 streaks', len(bpy.data.objects['eido_rain'].evaluated_get(dg).data.vertices) == 8000)
vg = bpy.data.node_groups['eido_weather_values']
sc.frame_set(60)
check('wet_exposure=False: no rain shadow keyed on wet ground, the drops still ray-cast the occluders',
      vg.nodes['shelter_on'].outputs[0].default_value == 0.0
      and any(n.bl_idname == 'GeometryNodeRaycast' for n in bpy.data.node_groups['eido_rain_streaks'].nodes))
check('the eidoverse wetness reads the keyed wet target (w.wet x k, no history)',
      abs(vg.nodes['wet_target'].outputs[0].default_value - wx3._rows[60]['wet_target']) < 1e-6
      and wx3._rows[60]['wet_target'] > 0.99, wx3._rows[60]['wet_target'])
aj = _json.loads(wx3.audio_json())
check('audio_json(): the toJSON timeline (one thunder per strike)', aj['stats']['strikes'] == len(wx3.sched.events),
      aj['stats'])
check('audio: the recorder getter', wx3.audio is not None and wx3.audio.stats['strikes'] == len(wx3.sched.events))
wx3.dispose()
check("dispose: the eidoverse model's group is gone and the asphalt restored",
      'eido_wet_eidoverse' not in bpy.data.node_groups and not pr.inputs['Base Color'].is_linked)
# the realtime cadence (lightning_gap_scale 1) over the same darkstorm minute has fewer events than the film's 0.42
counts = {}
for gs in (0.42, 1.0):
    sc.frame_end = 24 * 90
    w4 = make_weather_system(sc, sky, lightning_gap_scale=gs, moisture=False, log=lambda *a: None)
    w4.plan()
    counts[gs] = len(w4.sched.events)
    w4.dispose()
sc.frame_end = 72
check('lightning_gap_scale: 0.42 (film) strikes more often than 1.0 (realtime) over 90 s', counts[0.42] > counts[1.0]
      and counts[1.0] >= 1, counts)

# ---- rain_cells: 'column' is eidoverse's own-column gate; the transition diagnostics; the registry rules ----
try:
    make_weather_system(sc, sky, rain_cells='sideways', moisture=False, log=lambda *a: None)
    check('rain_cells: an unknown value raises', False)
except ValueError as e:
    check('rain_cells: an unknown value raises', 'rain_cells' in str(e), str(e)[:72])
w5 = make_weather_system(sc, sky, rain_cells='column', log=lambda *a: None)
w5.plan(frame_end=FM)
T5 = dict(w5.diagnostics['transition'])
check('diagnostics.transition mid-morph: from, target, elapsed, raw and eased progress as the JS records them',
      T5['active'] and T5['from'] == 'overcast' and T5['target'] == 'darkstorm' and abs(T5['durationSeconds'] - 1) < 1e-9
      and 0 < T5['rawProgress'] < 1 and abs(T5['rawProgress'] - T5['elapsedSeconds']) < 1e-9
      and abs(T5['easedProgress'] - T5['rawProgress'] ** 2 * (3 - 2 * T5['rawProgress'])) < 1e-9, T5)
UNIFORMS = ('time', 'camPos', 'camRight', 'camUp', 'rainK', 'fallSpeed', 'fallMul', 'windVec', 'fallPhase', 'windOffset',
            'streakLen', 'streakW', 'dashK', 'rainColor', 'rainLight', 'wetness', 'wetTint', 'puddleK', 'cellLo', 'cellHi',
            'denseA')
check('uniforms: every name of the WebGPU u table (fallSpeed, and streakW, which its shader never reads)',
      all(k in w5.uniforms for k in UNIFORMS), [k for k in UNIFORMS if k not in w5.uniforms])
rows5 = w5.bake(bake_sky=False)
T5b = dict(w5.diagnostics['transition'])
check('diagnostics.transition after the morph: inactive, from and target kept, progress 1',
      not T5b['active'] and T5b['from'] == 'overcast' and T5b['target'] == 'darkstorm' and T5b['rawProgress'] == 1.0
      and T5b['easedProgress'] == 1.0 and T5b['elapsedSeconds'] >= 1.0 - 1e-9, T5b)
check('diagnostics.lightning carries the palette weights and the cadence tables',
      w5.diagnostics['lightning']['paletteWeights'] is L.LIGHTNING_PALETTES
      and w5.diagnostics['lightning']['cadence'] is L.LIGHTNING_CADENCE)
al5 = rain_alpha_at(FM)
want5, cov5 = want_rain_alpha(w5._rows[FM], upwind=False)
op5 = al5 > 0
check("rain_cells='column': each drop is gated by the cell straight above it, eidoverse's sky.tslCoverage(px, pz) "
      '(coverage %.2f-%.2f)' % (cov5[op5].min() if op5.any() else 0, cov5[op5].max() if op5.any() else 0),
      op5.sum() > 100 and np.allclose(al5[op5], want5[op5], atol=3e-3),
      'max diff %.5f over %d streaks' % (np.abs(al5[op5] - want5[op5]).max() if op5.any() else -1, op5.sum()))
gx, gy = np.meshgrid(np.linspace(-300, 300, 13), np.linspace(-300, 300, 13))
rl = rows5[-1]
tt5 = np.clip((coverage3(rl, gx.ravel(), -gy.ravel()) - rl['cell_lo']) / (rl['cell_hi'] - rl['cell_lo']), 0, 1)
g5 = tt5 * tt5 * (3 - 2 * tt5)
want_cell = g5 + (1 - g5) * min(1.0, max(0.0, rl['storm_canopy']))
got_cell = w5._cell_at(gx.ravel(), gy.ravel())
check("rain_cells='column': the moisture history reads the same column as the drops",
      np.allclose(got_cell, want_cell, atol=1e-6), 'max diff %.2e' % float(np.abs(got_cell - want_cell).max()))
w6 = make_weather_system(sc, sky, moisture=False, log=lambda *a: None)
check('a second weather system on the scene disposes the first: its update() returns False (the JS registry)',
      w5.update(1.0) is False and w5._disposed)
w6.dispose()
check('dispose twice: the second call does nothing', w6.dispose() is False and w6.update(1.0) is False)
# in an open storm (no canopy) the upwind gate is the own-column gate moved upwind by the wind x the fall time
sky7 = make_sky(sc, camera=cam, hours=15.0, weather='storm', cache_dir=os.path.join(OUT, 'cache_storm'),
                quality='draft')
w7 = make_weather_system(sc, sky7, moisture=False, log=lambda *a: None)
gx, gy = np.meshgrid(np.linspace(-1500, 1500, 61), np.linspace(-1500, 1500, 61))
g_up = w7._cell_at(gx.ravel(), gy.ravel())
w7._upwind = 0.0                                         # what rain_cells='column' sets
g_col = w7._cell_at(gx.ravel(), gy.ravel())
uu, UU = sky7.wx.u, sky7.sky.U
kf = float(UU['cloudStart']) / max(w7.opts['fall_speed'] * float(uu['fallMul']), 1.0)
wv7 = uu['windVec']
g_shift = w7._cell_at(gx.ravel() - wv7[0] * kf, gy.ravel() + wv7[2] * kf)
check('rain_cells: in an open storm the two gates differ, and the upwind one is the column one moved %.0f m upwind'
      % (math.hypot(wv7[0], wv7[2]) * kf),
      float(np.abs(g_up - g_col).max()) > 0.2 and np.allclose(g_up, g_shift, atol=1e-9),
      'largest difference %.2f, shift error %.1e' % (float(np.abs(g_up - g_col).max()),
                                                     float(np.abs(g_up - g_shift).max())))
w7.dispose()

# ---- a strike target made of instances: a collection instance, rotated and scaled, is cast through its own matrix
# (findLocalStrike casts an InstancedMesh's instances through their instance matrices) ----
kit = bpy.data.collections.new('kit_platform')              # not linked to the scene: only its instance renders
pm = bpy.data.meshes.new('platform')
pv = [(x, y, z) for z in (0.0, 2.0) for x, y in ((-10, -10), (10, -10), (10, 10), (-10, 10))]
pm.from_pydata(pv, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
pm.materials.append(brick)
kit.objects.link(bpy.data.objects.new('platform', pm))
plat = bpy.data.objects.new('platform_instance', None)
plat.instance_type = 'COLLECTION'
plat.instance_collection = kit
plat.location = (0.0, 36.0, 0.0)
plat.rotation_euler = (0.0, 0.0, math.radians(30.0))
plat.scale = (3.0, 3.0, 1.5)
sc.collection.objects.link(plat)
w8 = make_weather_system(sc, sky, strike_targets=[plat], moisture=False, log=lambda *a: None)
w8.debug_force_local_strike(at=0.5)
w8.plan()
imp8 = w8.sched.impacts[0] if w8.sched.impacts else None
rec8 = w8.state.get('lastImpact')
check('strike_targets: a collection instance (rotated 30 degrees, scaled 3 x 3 x 1.5) is struck on its top at 3.0 m, '
      'normal up', imp8 is not None and abs(imp8['point'][1] - 3.0) < 1e-3 and rec8 is not None
      and abs(rec8['normal'][2] - 1.0) < 1e-6, (imp8 or {}).get('point'))
check('  ... the strike record goes on the instancer, as the JS writes it on the InstancedMesh',
      plat.get('eido_lightning_strikes') == 1 and rec8 is not None and rec8['kind'] == 'platform',
      (plat.get('eido_lightning_strikes'), (rec8 or {}).get('kind')))
w8.dispose()
bpy.data.objects.remove(plat, do_unlink=True)

# ---- an instanced occluder keeps the ground dry under it: the rain-exposure capture reads the same surfaces (the
# occluders' instances included) as the drops' ray cast, which realizes them ----
ckit = bpy.data.collections.new('kit_canopy')
cm = bpy.data.meshes.new('canopy')
cv = [(x, y, z) for z in (4.0, 4.2) for x, y in ((-5, -5), (5, -5), (5, 5), (-5, 5))]
cm.from_pydata(cv, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
cm.materials.append(brick)
ckit.objects.link(bpy.data.objects.new('canopy', cm))
occl = bpy.data.collections.new('occluders_with_instances')
sc.collection.children.link(occl)
gm = bpy.data.meshes.new('lot')
gm.from_pydata([(40, 40, 0), (80, 40, 0), (80, 80, 0), (40, 80, 0)], [], [(0, 1, 2, 3)])
gm.materials.append(asphalt)
occl.objects.link(bpy.data.objects.new('lot', gm))
cinst = bpy.data.objects.new('canopy_instance', None)
cinst.instance_type = 'COLLECTION'
cinst.instance_collection = ckit
cinst.location = (60.0, 60.0, 0.0)
occl.objects.link(cinst)
w9 = make_weather_system(sc, sky, occluders=occl, moisture=False, log=lambda *a: None)
w9.wrap_scene()
w9.bake(bake_sky=False)
meta9 = w9.shelter


def read_exr9(name):
    buf = oiio.ImageBuf(os.path.join(w9.cache_dir, name))
    return np.asarray(buf.get_pixels(oiio.FLOAT)).reshape(meta9['h'], meta9['w'], 4)[::-1]


e9, s9 = read_exr9('rain_exposure.exr'), read_exr9('rain_exposure_soft.exr')
d9 = meta9['d']
under = exposure_at(60.0 + 4.1 * (-d9[0] / d9[2]), 60.0 + 4.1 * (-d9[1] / d9[2]), 0.0, 1.0, e9, meta9, s9)
open9 = exposure_at(45.0, 75.0, 0.0, 1.0, e9, meta9, s9)
check('rain shadow: the ground under an instanced canopy stays dry, open ground beside it is exposed',
      under < 0.01 and open9 > 0.999, 'under %.3f, open %.3f' % (under, open9))
w9.dispose()
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
