"""The material's check 1 (SURFACING_DESIGN.md 5.4, package 2): the two-slot level reader, before anything is built on
it.

    bash run_blender.sh blender/tests/terrain/surfacing/check_reader.py [--case canyon] [--parts parity,edges,look]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

parity  On every level, a 64 x 64 texel patch deep inside its own ring (no window edge within 40 of its cells)
        rendered top-down, orthographic, one texel a pixel, as an emission of maps read through eido_terrain_map
        (the material's reader): an 8-bit mask (flow, M), an 8-bit detail map (cavity, E), the field normal's x
        (D, half float) and the stratigraphic height (strata, F, half float, decoded on the mesh's own z). Against
        the bake's arrays at the texel centres: within 1/255 for the 8-bit maps, 1e-3 relative (of the map's range
        on the patch) for the half-float ones.
edges   Views across window edges (2 m and 6 m above the ground looking across the finest window's edge, and an
        oblique view 120 m up across the next one): the same maps through the reader against a read with no mips
        (each pixel's own level, Cubic, no blending). On pixels within 2 px of a window edge (the level map's
        changes) the error's share over 0.05, mean and max, against the error elsewhere: probe D's measure, within
        twice. The emission renders and the level map are written for the eye.
look    the same three views in the per-texel material under make_sky, for the eye (no seam ring at 1x).
Writes out/surfacing/material/reader_<case>.json and the renders (out/surfacing/material/reader/).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402
from eidoblend.terrain.surface import maps as MP  # noqa: E402

OUT = os.path.join(MS.OUT, 'reader')


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(case=opt('--case', 'canyon'), parts=opt('--parts', 'parity,edges,look').split(','))


def node(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def remap(nt, sock, lo, hi):
    m = node(nt, 'ShaderNodeMapRange', clamp=False)
    nt.links.new(sock, m.inputs['Value'])
    m.inputs['From Min'].default_value = float(lo)
    m.inputs['From Max'].default_value = float(hi)
    return m.outputs['Result']


def emission(name, socks):
    """A material emitting up to three float sockets (builders: nt -> socket) as R, G, B."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    comb = node(nt, 'ShaderNodeCombineColor')
    for k, fn in enumerate(socks):
        if fn is not None:
            nt.links.new(fn(nt), comb.inputs[k])
    em = node(nt, 'ShaderNodeEmission')
    nt.links.new(comb.outputs[0], em.inputs['Color'])
    out = node(nt, 'ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def map_socket(tm, name, lo, hi):
    def fn(nt):
        g = node(nt, 'ShaderNodeGroup')
        g.node_tree = tm
        return remap(nt, g.outputs[name], lo, hi)
    return fn


def reference_socket(sd, fam, ch, lo, hi):
    """A map read at each pixel's own level with no mips (Cubic) and no blending: the reference."""
    def fn(nt):
        rd = node(nt, 'ShaderNodeGroup')
        rd.node_tree = S.reader_group(sd)
        tc = node(nt, 'ShaderNodeTexCoord')
        nt.links.new(tc.outputs['Object'], rd.inputs['Position'])
        sep = node(nt, 'ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Object'], sep.inputs[0])
        lay = sd.reader_constants()['detail' if fam in ('D', 'E') else 'cell']
        img = sd.images()[fam]
        acc = None
        for k, tl in enumerate(lay):
            u = node(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD')
            nt.links.new(sep.outputs[0], u.inputs[0])
            u.inputs[1].default_value = tl['du'] / tl['side']
            u.inputs[2].default_value = tl['u0'] - tl['du'] * tl['x0'] / tl['side']
            v = node(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD')
            nt.links.new(sep.outputs[1], v.inputs[0])
            v.inputs[1].default_value = tl['dv'] / tl['side']
            v.inputs[2].default_value = tl['v0'] - tl['dv'] * tl['y0'] / tl['side']
            cv = node(nt, 'ShaderNodeCombineXYZ')
            nt.links.new(u.outputs[0], cv.inputs[0])
            nt.links.new(v.outputs[0], cv.inputs[1])
            tx = node(nt, 'ShaderNodeTexImage', interpolation='Cubic', extension='EXTEND')
            tx.image = img
            nt.links.new(cv.outputs[0], tx.inputs['Vector'])
            if ch == 3:
                val = tx.outputs['Alpha']
            else:
                sc = node(nt, 'ShaderNodeSeparateColor')
                nt.links.new(tx.outputs['Color'], sc.inputs[0])
                val = sc.outputs[ch]
            eq = node(nt, 'ShaderNodeMath', operation='COMPARE')
            nt.links.new(rd.outputs['Level'], eq.inputs[0])
            eq.inputs[1].default_value = float(k)
            eq.inputs[2].default_value = 0.5
            term = node(nt, 'ShaderNodeMath', operation='MULTIPLY')
            nt.links.new(eq.outputs[0], term.inputs[0])
            nt.links.new(val, term.inputs[1])
            if acc is None:
                acc = term.outputs[0]
            else:
                ad = node(nt, 'ShaderNodeMath', operation='ADD')
                nt.links.new(acc, ad.inputs[0])
                nt.links.new(term.outputs[0], ad.inputs[1])
                acc = ad.outputs[0]
        return remap(nt, acc, lo, hi)
    return fn


def float_render(sc, path, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    im = sc.render.image_settings
    im.file_format = 'OPEN_EXR'
    im.color_depth = '32'
    im.color_mode = 'RGBA'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def flat_scene(sc):
    """Emission renders: no world light, a transparent film (alpha marks the ground), the Standard view, no film
    filter, one sample."""
    sc.world = bpy.data.worlds.new('black')
    sc.world.color = (0.0, 0.0, 0.0)
    sc.render.film_transparent = True
    vs = sc.view_settings
    vs.view_transform = 'Standard'
    vs.look = 'None'
    vs.exposure = 0.0
    vs.gamma = 1.0
    sc.eevee.taa_render_samples = 1
    try:
        sc.render.filter_size = 0.0
    except (AttributeError, TypeError):
        pass
    sc.render.use_compositing = False


def ortho_camera(sc, cx, cy, side, z):
    cam = bpy.data.objects.get('ortho_cam') or bpy.data.objects.new('ortho_cam', bpy.data.cameras.new('ortho_cam'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = side
    cam.data.clip_start, cam.data.clip_end = 1.0, 20000.0
    cam.location = (cx, cy, z)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    sc.camera = cam
    return cam


def patch_origin(t, sd, i, n_px, grid):
    """(i0, j0) texel index of a patch of n_px texels inside level i's own ring, at least 40 cells from every window
    edge (its own and its child's), on its `grid` ('cell' or 'detail')."""
    lv = sd.levels[i]
    lay = sd.reader_constants()[grid][i]
    tex = lay['texel']
    m = 40.0 * lv.cell
    child = sd.levels[i + 1] if i + 1 < len(sd.levels) else None
    cand = []
    for fx in np.linspace(0.12, 0.88, 13):
        for fy in np.linspace(0.12, 0.88, 13):
            x = lv.x0 + fx * lv.side
            y = lv.y0 + fy * lv.side
            half = 0.5 * n_px * tex
            if i > 0 and not (lv.x0 + m + half < x < lv.x0 + lv.side - m - half
                              and lv.y0 + m + half < y < lv.y0 + lv.side - m - half):
                continue
            if child is not None:
                if (child.x0 - m - half < x < child.x0 + child.side + m + half
                        and child.y0 - m - half < y < child.y0 + child.side + m + half):
                    continue
            cand.append((abs(fx - 0.5) + abs(fy - 0.5), x, y))
    if not cand:
        return None
    cand.sort()
    _d, x, y = cand[0]
    i0 = int(round((x - lv.x0) / tex - 0.5 * n_px))
    j0 = int(round((y - lv.y0) / tex - 0.5 * n_px))
    return i0, j0, tex


def map_group(sd):
    """eido_terrain_map of the data, with `flow` among its packed maps (the M map these checks read)."""
    packed = {n for grp in sd.packing() for n in grp}
    return S.terrain_map_group(sd, names=None if 'flow' in packed else sorted(packed | {'flow'}))


def parity(sc, t, obj, sd, rec):
    """The parity part (module doc)."""
    tm = map_group(sd)
    flat_scene(sc)
    me = obj.data
    out = {}
    N = 64
    for i, lv in enumerate(sd.levels):
        m = sd.maps(i)
        h = np.asarray(t.fields(i)['h'], np.float64)
        res = {}
        for grid, names in (('cell', ('flow', 'strata')), ('detail', ('cavity', 'normal_x'))):
            po = patch_origin(t, sd, i, N, grid)
            if po is None:
                res[grid] = 'no patch'
                continue
            i0, j0, tex = po
            arrs, lims = [], []
            ys = lv.y0 + (j0 + np.arange(N) + 0.5) * tex
            xs = lv.x0 + (i0 + np.arange(N) + 0.5) * tex
            X, Y = np.meshgrid(xs, ys)
            for nm in names:
                a = np.asarray(m[nm], np.float64)
                sub = a[j0:j0 + N, i0:i0 + N]
                if nm == 'strata':                        # the shader decodes on the mesh's own z
                    sub = sub - h[j0:j0 + N, i0:i0 + N] + np.asarray(t.height_at(X, Y), np.float64)
                lo, hi = float(sub.min()), float(sub.max())
                if hi - lo < 1e-6:
                    hi = lo + 1.0
                arrs.append(sub)
                lims.append((lo, hi))
            socks = [map_socket(tm, nm, lo, hi) for nm, (lo, hi) in zip(names, lims)]
            mat = emission(f'parity_{i}_{grid}', socks)
            me.materials.clear()
            me.materials.append(mat)
            z = float(np.max(np.asarray(t.height_at(X, Y)))) + 500.0
            ortho_camera(sc, lv.x0 + (i0 + 0.5 * N) * tex, lv.y0 + (j0 + 0.5 * N) * tex, N * tex, z)
            img = float_render(sc, os.path.join(OUT, f'parity_L{i}_{grid}.exr'), (N, N))
            r = {}
            for c, (nm, sub, (lo, hi)) in enumerate(zip(names, arrs, lims)):
                got = lo + img[..., c].astype(np.float64) * (hi - lo)
                err = np.abs(got - sub)
                spec = MP.spec(nm)
                if spec.encoding in ('unit', 'signed', 'bend', 'thick'):
                    tol = 1.0 / 255.0 * (2.0 if spec.encoding == 'signed' else 1.0)
                    if spec.encoding == 'thick':
                        tol = 2.0 * math.sqrt(max(hi, 1e-6) / spec.t_max) / 255.0 * spec.t_max
                    ok = float(np.percentile(err, 99)) <= tol
                    r[nm] = dict(p99=float(np.percentile(err, 99)), max=float(err.max()), tol=tol, ok=ok)
                else:
                    rng = max(hi - lo, 1e-6)
                    rel = err / rng
                    r[nm] = dict(p99_rel=float(np.percentile(rel, 99)), max_rel=float(rel.max()), range=rng,
                                 ok=float(np.percentile(rel, 99)) <= 1e-3)
            res[grid] = dict(texel=tex, origin=[i0, j0], maps=r)
        out[f'L{i}'] = res
        MS.log(f'[reader] parity L{i}: {json.dumps(res)}')
    rec['parity'] = out


def edge_views(t, sd):
    """[(name, eye, target)]: across the finest window's edge at 2 m and 6 m, and across the next one from 120 m."""
    lv = sd.levels
    f = lv[-1]
    p = lv[-2]
    cx = f.x0 + 0.5 * f.side
    out = []
    for name, dz, lvl, back in (('grazing_2m', 2.0, f, 0.15), ('low_6m', 6.0, f, 0.3), ('oblique_120m', 120.0, p, 0.35)):
        ey = lvl.y0 - back * lvl.side * 0.5
        ex = cx
        ez = float(t.height_at(ex, ey)) + dz
        ty = lvl.y0 + 0.25 * lvl.side
        tz = float(t.height_at(ex, ty))
        out.append((name, (ex, ey, ez), (ex, ty, tz)))
    return out


def edges(sc, t, obj, sd, rec):
    tm = map_group(sd)
    flat_scene(sc)
    me = obj.data
    maps = [('flow', 'M', 0.0, 1.0), ('cavity', 'E', 0.0, 1.0), ('normal_x', 'D', -1.0, 1.0)]
    chans = {}
    for nm, fam, _lo, _hi in maps:
        f, ch, _rule = sd.channel(nm)
        chans[nm] = (f, ch)
    read = emission('edges_reader', [map_socket(tm, nm, lo, hi) for nm, _f, lo, hi in maps])
    ref = emission('edges_ref', [reference_socket(sd, chans[nm][0], chans[nm][1], lo, hi)
                                 for nm, _f, lo, hi in maps])

    def level_fn(nt):
        g = node(nt, 'ShaderNodeGroup')
        g.node_tree = tm
        return remap(nt, g.outputs['Level'], 0.0, 16.0)
    lvl = emission('edges_level', [level_fn, None, None])
    out = {}
    for name, eye, target in edge_views(t, sd):
        cam = MS.camera(sc, t, args()['case'], name, eye=eye, target=target, lens=35.0)
        imgs = {}
        for key, mat in (('reader', read), ('ref', ref), ('level', lvl)):
            me.materials.clear()
            me.materials.append(mat)
            imgs[key] = float_render(sc, os.path.join(OUT, f'edges_{name}_{key}.exr'), (MS.W, MS.H))
        L = np.rint(imgs['level'][..., 0] * 16.0)
        valid = imgs['level'][..., 3] > 0.5
        ch = np.zeros(L.shape, bool)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                ch |= np.roll(np.roll(L, dy, 0), dx, 1) != L
        edge = ch & valid
        far = valid.copy()
        for dy in range(-6, 7, 2):
            for dx in range(-6, 7, 2):
                far &= np.roll(np.roll(L, dy, 0), dx, 1) == L
        r = {'edge_px': int(edge.sum()), 'other_px': int(far.sum()), 'camera': [round(v, 1) for v in eye]}
        for c, (nm, _f, lo, hi) in enumerate(maps):
            e = np.abs(imgs['reader'][..., c] - imgs['ref'][..., c])
            r[nm] = dict(edge_over_005=float((e[edge] > 0.05).mean()) if edge.any() else None,
                         edge_mean=float(e[edge].mean()) if edge.any() else None,
                         edge_max=float(e[edge].max()) if edge.any() else None,
                         other_over_005=float((e[far] > 0.05).mean()), other_mean=float(e[far].mean()),
                         other_p99=float(np.percentile(e[far], 99)))
        out[name] = r
        MS.log(f'[reader] edges {name}: {json.dumps(r)}')
        _ = cam
    rec['edges'] = out


def look(sc, t, obj, sd, rec):
    """The per-texel material at the edge views, for the eye."""
    case = args()['case']
    mat = MS.apply(t, obj, sd)
    out = {}
    for name, eye, target in edge_views(t, sd):
        cam = MS.camera(sc, t, case, name, eye=eye, target=target, lens=35.0)
        sky = os.path.join(OUT, '_sky')
        MS.light(sc, cam, sky)
        MS.frame(sc)
        out[name] = round(MS.frame(sc, os.path.join(OUT, f'look_{case}_{name}.png')), 2)
        MS.clean(sky)
    rec['look_frames_s'] = out
    _ = mat


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    rec = {'case': a['case']}
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(a['case'])
    sd = MS.surface(t)
    rec['levels'] = [str(v) for v in sd.levels]
    if 'look' in a['parts']:
        look(sc, t, obj, sd, rec)
        sc = bpy.context.scene
    if 'parity' in a['parts']:
        parity(sc, t, obj, sd, rec)
    if 'edges' in a['parts']:
        edges(sc, t, obj, sd, rec)
    path = os.path.join(MS.OUT, f"reader_{a['case']}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    MS.log(f'[reader] done -> {path}')


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
