"""The carved stock (stock.py): its field against an independent evaluation, its history, its VDB files and the
surface Blender meshes from them. Nothing renders.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_stock_field.py

Checks
  field          at 400 random voxels mid-program, the incremental field equals clamp(max(blank, max over every
                 cutting stroke so far of minus path.sweep_distance (the JS-exact scalar), the current stroke to its
                 fraction)), within float32
  history        many forward seeks == one jump; seeking back rebuilds the same field as a fresh stock
  carving        at the end the target sculpture is inside the stock (no gouge beyond a cell) and the stock is gone
                 1.5 mm outside it (the finish reached it)
  vdb            a written frame reads back as minus the field (half floats)
  surface        the Volume to Mesh surface of a frame: every face normal agrees with the field's gradient
                 (outward), the surface lies on the field's zero level, and the stock frame turns it with the chuck
  snapshot       to_mesh() makes the same surface as a static mesh; rotary_surface() a closed target mesh
Prints PASS / FAIL.
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fabrication.rotary import (StockField, create_rotary_stock, rotary_program,      # noqa: E402
                                          rotary_surface, sample_rotary, sweep_distance)
from eidoblend.fabrication.rotary.removal import blank_distance_np                       # noqa: E402

OUT = os.path.join(HERE, 'out', 'stock_field')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def trilinear(field, fs, p):
    """the field at stock points p (N, 3), trilinear as the WebGPU read()"""
    g = (np.asarray(p) - np.asarray(fs.bounds['min'])) / np.asarray(fs.cell)
    base = np.floor(g).astype(int)
    f = g - base
    n = np.asarray(fs.resolution)
    out = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                idx = np.clip(base + (dx, dy, dz), 0, n - 1)
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * field[idx[:, 0], idx[:, 1], idx[:, 2]]
    return out


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
rng = np.random.default_rng(5)
for tool in ('ball', 'flat'):
    p = rotary_program(sample_rotary, angles=16, sample_step=.004, tool=tool,
                       flute_length=.018 if tool == 'flat' else .017)
    path, s = p.path, p.settings
    fs = StockField(path, s, (96, 40, 40))
    t_mid = path.duration * .43
    st = path.sample(t_mid)
    fs.update(st)
    # random voxels near the material (where cuts happen), and a few anywhere
    nx, ny, nz = fs.resolution
    picks = []
    while len(picks) < 400:
        ijk = (rng.integers(0, nx), rng.integers(0, ny), rng.integers(0, nz))
        if abs(fs.blank[ijk]) < fs.band or rng.random() < .1:
            picks.append(ijk)
    picks = np.asarray(picks)
    P = np.stack([fs.axes[k][picks[:, k]] for k in range(3)], 1)
    want = np.clip(blank_distance_np(P, s), -fs.band, fs.band)
    cuts = [seg for seg in path.segments if seg['type'] == 'cut' and seg['index'] <= st['index']]
    for seg in cuts:
        f = st['fraction'] if seg['index'] == st['index'] else 1.0
        d = np.array([sweep_distance(q, seg, s['radius'], s['flute_length'], f, tool) for q in P])
        want = np.maximum(want, np.clip(-d, -fs.band, fs.band))
    got = fs.field[picks[:, 0], picks[:, 1], picks[:, 2]]
    err = np.abs(got - want).max()
    changed = int((np.abs(want - np.clip(blank_distance_np(P, s), -fs.band, fs.band)) > 1e-9).sum())
    if tool == 'ball':
        check(f'field (ball): 400 voxels mid-program equal the independent max over {len(cuts)} strokes '
              f'({changed} of them cut)', err < 2e-7 and changed > 20, f'worst {err:.2e} m')
    else:
        # the flat end's distance below a sloped stroke is the JS's normalised bound, evaluated (there by bins, here
        # by the stroke's box) only near the stroke: inside / outside is exact, values agree except deep under it
        same_sign = np.array_equal(got < 0, want < 0)
        close = np.abs(got - want) < 1e-6
        check(f'field (flat): 400 voxels mid-program: inside / outside equal the independent max over {len(cuts)} '
              f'strokes ({changed} cut), values equal at {close.mean() * 100:.1f} %', same_sign and close.mean() > .97,
              f'worst {err:.2e} m')
    # history: many small forward steps == one jump; rewinding == fresh
    a = StockField(path, s, (96, 40, 40))
    for t in np.linspace(0, t_mid, 37):
        a.update(path.sample(t))
    if tool == 'ball':
        check('history (ball): 37 forward seeks give the same field as one jump', np.array_equal(a.field, fs.field))
    else:
        # below a sloped flat stroke the bound is not monotone in the stroke's fraction, so values under the floor
        # depend on the frames sampled (in the WebGPU edition too); the surface does not
        check('history (flat): 37 forward seeks give the same surface (inside / outside) as one jump',
              np.array_equal(a.field < 0, fs.field < 0), f'{(a.field != fs.field).mean() * 100:.2f} % of values differ')
    a.update(path.sample(path.duration * .2))
    b = StockField(path, s, (96, 40, 40))
    b.update(path.sample(path.duration * .2))
    check(f'history ({tool}): seeking back rebuilds the field a fresh stock has', np.array_equal(a.field, b.field))
    # the finished part from a finer program (64 stations, 2 mm samples): fewer scallops between stations
    fine = rotary_program(sample_rotary, angles=64, sample_step=.002, tool=tool,
                          flute_length=.018 if tool == 'flat' else .017)
    end = StockField(fine.path, fine.settings, (160, 64, 64))
    end.update(fine.path.sample(fine.path.duration))
    # the finished part: the target inside the stock, the stock gone just outside it
    xs = np.linspace(s['start'] + .002, s['end'] - .002, 60)
    th = np.linspace(0, 2 * math.pi, 90, endpoint=False)
    X, TH = np.meshgrid(xs, th)
    R = sample_rotary(X, TH, {'start': s['start'], 'end': s['end'], 'stock_width': s['stock_width'],
                              'stock_height': s['stock_height']})
    on = np.stack([X, -R * np.sin(TH), R * np.cos(TH)], -1).reshape(-1, 3)
    off = np.stack([X, -(R + .0015) * np.sin(TH), (R + .0015) * np.cos(TH)], -1).reshape(-1, 3)
    d_on, d_off = trilinear(end.field, end, on), trilinear(end.field, end, off)
    cell = max(end.cell)
    check(f'carving ({tool}): the finished stock holds the whole target (no gouge beyond a cell)',
          d_on.max() < cell, f'max field on the target {d_on.max() * 1000:.3f} mm (cell {cell * 1000:.2f} mm)')
    check(f'carving ({tool}): and is cut away 1.5 mm outside it',
          (d_off > 0).mean() > .97, f'{(d_off > 0).mean() * 100:.1f} % of points outside the stock')

# ------------------------------------------------------------------------------- the Blender stock and its files ---
from eidoblend.characters.robotics import make_robot                                    # noqa: E402
from eidoblend.fabrication.rotary import rotary_carve                                     # noqa: E402

m = make_robot('cnc_rotary', textures=False)
job = rotary_carve(m, sample_rotary, angles=16, sample_step=.004, duration=10, resolution=(128, 48, 48),
                   cache_dir=os.path.join(OUT, 'cache'))
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 3
t0 = time.time()
job.play(frames=[1, 2, 3], frame_start=1, frame_end=3)
check(f'play: three frames keyed and written ({time.time() - t0:.1f} s)', job.stock.frames_written == [1, 2, 3])
import openvdb as vdb                                                                    # noqa: E402
g = vdb.read(job.stock.frame_path(3), 'density')
arr = np.zeros(job.stock.resolution, dtype=np.float32)
g.copyToArray(arr)
fs3 = StockField(job.path, job.settings, job.stock.resolution)
fs3.update(job.path.sample(min(2 / 24, job.duration) / job.duration * job.path.duration))   # frame 3: t = 2 / 24 s
err = np.abs(arr + fs3.field).max()
check('vdb: frame 3\'s file reads back as minus the field at its time (half floats)', err < 2e-6, f'worst {err:.1e} m')
sc.frame_set(3)
dg = bpy.context.evaluated_depsgraph_get()
ev = job.stock.mesh.evaluated_get(dg)
me = ev.data
nf = len(me.polygons)
cen = np.empty(nf * 3)
me.polygons.foreach_get('center', cen)
nrm = np.empty(nf * 3)
me.polygons.foreach_get('normal', nrm)
cen, nrm = cen.reshape(-1, 3), nrm.reshape(-1, 3)
# object space -> stock space (the surface object's frame in the stock frame)
F = np.asarray(job.stock.mesh.matrix_basis.to_3x3())
cs, ns = cen @ F.T, nrm @ F.T
eps = np.asarray(fs3.cell) * .5
grad = np.stack([trilinear(fs3.field, fs3, cs + e) - trilinear(fs3.field, fs3, cs - e)
                 for e in np.diag(eps)], 1)
gn = grad / np.maximum(np.linalg.norm(grad, axis=1, keepdims=True), 1e-12)
agree = (np.einsum('ij,ij->i', gn, ns) > 0).mean()
check(f'surface: {nf} faces from Volume to Mesh face outward along the field gradient', agree > .99,
      f'{agree * 100:.2f} % agree')
level = np.abs(trilinear(fs3.field, fs3, cs))
check('surface: and lie on the field\'s zero level', np.median(level) < .1 * min(fs3.cell),
      f'median |field| {np.median(level) * 1e6:.1f} um, cell {min(fs3.cell) * 1e3:.2f} mm')
bpy.context.view_layer.update()
chuck = m.roots['rotary_chuck']
rel = chuck.matrix_world.inverted() @ job.mesh.matrix_world
check('surface: the stock frame rides the chuck (no turn relative to it, on its axis)',
      abs(rel.to_quaternion().angle) < 1e-6 and abs(rel.translation.y) < 1e-9 and abs(rel.translation.z) < 1e-9)
snap = job.stock.to_mesh('carved snapshot')
check(f'snapshot: to_mesh() makes a static mesh of the current field ({len(snap.data.vertices)} vertices)',
      len(snap.data.vertices) > 1000)
tm = rotary_surface(sample_rotary, nx=40, na=64)
edges_ok = all(e.use_edge_sharp is False for e in tm.edges)
import bmesh                                                                             # noqa: E402
bm = bmesh.new()
bm.from_mesh(tm)
manifold = all(e.is_manifold for e in bm.edges)
bm.free()
check(f'rotary_surface: a closed, welded target mesh ({len(tm.vertices)} vertices, {len(tm.polygons)} faces)',
      manifold and len(tm.vertices) == 41 * 64 + 2 and edges_ok)
job.dispose(files=True)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
