"""The material's check 1 (SURFACING_DESIGN.md 5.4, package 2): the two-slot level reader, before anything is built on
it.

    bash run_blender.sh blender/tests/terrain/surfacing/check_reader.py [--case canyon]
        [--parts parity,edges,look,dolly] [--edges finest,clamped] [--frames 36]
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
dolly   the per-texel material from a camera 2 m up walking across the finest window's edge, --frames frames and
        an H.264 video of them (ffmpeg on the PATH), to watch for a seam ring in motion.
lut     check 9: at grazing angles the material's ramp image reads no other row's colour. Each row of the palette's
        ramp image read exactly as the material reads it (Closest, EXTEND, the row's centre, u = t (W - 1) / W +
        0.5 / W) at t = fract(x / 3.7 + y / 2.3), a pattern that sweeps the whole ramp every few metres, as an
        emission seen from the 2 m and 6 m edge views (grazing), one sample and no film filter, so each pixel shows
        one texel. Every ground pixel must be one of its own row's 256 colours within one 8-bit step (a Closest
        read returns a whole texel: the sRGB decode's rounding is all it may differ by; a bleed returns another
        row's texel, so the record also says how many pixels lie nearer another row). The first row is also read
        Linear (mipmapped, as a plain image read would be), to show the check catches a bleed.
--edges clamped adds (to edges and look) two views from inside the window that sits closest to its parent's edge
(a hero window clamped 16 cells inside its parent, where the reader's dead band is capped by the room left),
looking out across its own edge and its parent's just beyond; alpine_valley's first hero window is one.
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
    return dict(case=opt('--case', 'canyon'), parts=opt('--parts', 'parity,edges,look').split(','),
                edges=tuple(opt('--edges', 'finest').split(',')), frames=int(opt('--frames', '36')))


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
    """eido_terrain_map of the data, with `flow` and `wetness` among its packed maps (the M maps these checks read)."""
    packed = {n for grp in sd.packing() for n in grp}
    need = {'flow', 'wetness'}
    return S.terrain_map_group(sd, names=None if need <= packed else sorted(packed | need))


def parity(sc, t, obj, sd, rec):
    """The parity part (module doc)."""
    tm = map_group(sd)
    flat_scene(sc)
    me = obj.data
    out = {}
    N = 64
    # an 8-bit M map and the half-float F map (strata, where the palette has a rock column; else a second M map), an
    # 8-bit E map and the half-float D map
    cell_names = ('flow', 'strata') if sd.has('strata') else ('flow', 'wetness')
    for i, lv in enumerate(sd.levels):
        m = sd.maps(i)
        h = np.asarray(t.fields(i)['h'], np.float64)
        res = {}
        for grid, names in (('cell', cell_names), ('detail', ('cavity', 'normal_x'))):
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


def clamped_level(sd, cells=20.0):
    """(k, side, margin metres) of the window that sits closest to its parent's edge, when that is within `cells`
    parent cells (a hero window clamped inside its parent: the reader's dead band is capped there); else None.
    side: 'west', 'east', 'south' or 'north'."""
    best = None
    lv = sd.levels
    for k in range(1, len(lv)):
        a, b = lv[k - 1], lv[k]
        m = {'west': b.x0 - a.x0, 'south': b.y0 - a.y0, 'east': a.x0 + a.side - b.x0 - b.side,
             'north': a.y0 + a.side - b.y0 - b.side}
        side = min(m, key=m.get)
        if m[side] <= cells * a.cell and (best is None or m[side] / a.cell < best[2] / lv[best[0] - 1].cell):
            best = (k, side, float(m[side]))
    return best


def edge_views(t, sd, which=('finest',)):
    """[(name, eye, target)]. 'finest': across the finest window's edge at 2 m and 6 m, and across the next one from
    120 m. 'clamped': from inside the window that sits closest to its parent's edge, looking out across its own edge
    and its parent's just beyond, 6 m and 60 m above the ground (none when no window is clamped)."""
    lv = sd.levels
    out = []
    if 'finest' in which:
        f = lv[-1]
        p = lv[-2]
        cx = f.x0 + 0.5 * f.side
        for name, dz, lvl, back in (('grazing_2m', 2.0, f, 0.15), ('low_6m', 6.0, f, 0.3),
                                    ('oblique_120m', 120.0, p, 0.35)):
            ey = lvl.y0 - back * lvl.side * 0.5
            ex = cx
            ez = float(t.height_at(ex, ey)) + dz
            ty = lvl.y0 + 0.25 * lvl.side
            tz = float(t.height_at(ex, ty))
            out.append((name, (ex, ey, ez), (ex, ty, tz)))
    cl = clamped_level(sd) if 'clamped' in which else None
    if cl is not None:
        k, side, margin = cl
        b = lv[k]
        dx, dy = {'west': (-1, 0), 'east': (1, 0), 'south': (0, -1), 'north': (0, 1)}[side]
        cx, cy = b.x0 + 0.5 * b.side, b.y0 + 0.5 * b.side
        ex0, ey0 = cx + dx * 0.5 * b.side, cy + dy * 0.5 * b.side          # the middle of the clamped edge
        for name, dz, back in (('clamped_6m', 6.0, 0.06), ('clamped_60m', 60.0, 0.2)):
            ex, ey = ex0 - dx * back * b.side, ey0 - dy * back * b.side
            ez = float(t.height_at(ex, ey)) + dz
            tx, ty = ex0 + dx * (margin + 0.1 * b.side), ey0 + dy * (margin + 0.1 * b.side)
            out.append((name, (ex, ey, ez), (tx, ty, float(t.height_at(tx, ty)))))
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
    for name, eye, target in edge_views(t, sd, args()['edges']):
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


def lut_material(img, row, interp):
    """An emission of one row of a ramp image read as surfacing's lut() reads it, at t = fract(x / 3.7 + y / 2.3)."""
    W, R = img.size
    mat = bpy.data.materials.new(f'lut_{row}_{interp}')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tc = node(nt, 'ShaderNodeTexCoord')
    sep = node(nt, 'ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    a = node(nt, 'ShaderNodeMath', operation='MULTIPLY')
    nt.links.new(sep.outputs[0], a.inputs[0])
    a.inputs[1].default_value = 1.0 / 3.7
    b = node(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD')
    nt.links.new(sep.outputs[1], b.inputs[0])
    b.inputs[1].default_value = 1.0 / 2.3
    nt.links.new(a.outputs[0], b.inputs[2])
    fr = node(nt, 'ShaderNodeMath', operation='FRACT')
    nt.links.new(b.outputs[0], fr.inputs[0])
    u = node(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD')
    nt.links.new(fr.outputs[0], u.inputs[0])
    u.inputs[1].default_value = (W - 1.0) / W
    u.inputs[2].default_value = 0.5 / W
    cv = node(nt, 'ShaderNodeCombineXYZ')
    nt.links.new(u.outputs[0], cv.inputs[0])
    cv.inputs[1].default_value = (row + 0.5) / R
    tx = node(nt, 'ShaderNodeTexImage', interpolation=interp, extension='EXTEND')
    tx.image = img
    nt.links.new(cv.outputs[0], tx.inputs['Vector'])
    em = node(nt, 'ShaderNodeEmission')
    nt.links.new(tx.outputs['Color'], em.inputs['Color'])
    out = node(nt, 'ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def lut(sc, t, obj, sd, rec):
    """The lut part (module doc)."""
    from eidoblend.terrain.build import palettes as P
    a = args()
    pal_name, strata = MS.palette_args(t)
    pal = S.resolve(pal_name, t.recipe, strata)
    img, index = S._lut_image(pal)
    if img is None:
        rec['lut'] = 'the palette has no ramps'
        MS.log('[reader] lut: the palette has no ramps')
        return
    W, R = img.size
    px = np.empty(W * R * 4, np.float32)
    img.pixels.foreach_get(px)
    enc = np.clip(px.reshape(R, W, 4)[..., :3].astype(np.float64), 0.0, 1.0)
    rows = P.srgb_to_linear(enc)
    # one 8-bit step of each texel, in linear: a Closest read returns a whole texel, so it can differ from the texel
    # only by the sRGB decode's rounding (under a step); a bleed returns another texel
    step = np.maximum(np.abs(P.srgb_to_linear(np.clip(enc + 1.0 / 255.0, 0.0, 1.0)) - rows), 1e-4)
    flat_scene(sc)
    me = obj.data
    views = [v for v in edge_views(t, sd, ('finest',)) if v[0] in ('grazing_2m', 'low_6m')]
    out = dict(rows=R, width=W, ramps={k: v.get('row') for k, v in index.items()}, views={})
    for name, eye, target in views:
        MS.camera(sc, t, a['case'], name, eye=eye, target=target, lens=35.0)
        res = {}
        for row, interp in [(r, 'Closest') for r in range(R)] + [(0, 'Linear')]:
            me.materials.clear()
            me.materials.append(lut_material(img, row, interp))
            im = float_render(sc, os.path.join(OUT, f'lut_{name}_r{row}_{interp}.exr'), (MS.W, MS.H))
            ground = im[..., 3] > 0.5
            got = im[..., :3][ground].astype(np.float64)

            def nearest(rr):
                """Each pixel's distance to the nearest texel of row rr, in that texel's 8-bit steps (the largest
                over the channels)."""
                best = np.full(len(got), np.inf)
                for k0 in range(0, W, 32):
                    d = (np.abs(got[:, None, :] - rows[rr, None, k0:k0 + 32, :])
                         / step[rr, None, k0:k0 + 32, :]).max(-1).min(-1)
                    best = np.minimum(best, d)
                return best
            own = nearest(row)
            other = np.full(len(got), np.inf)
            for rr in range(R):
                if rr != row:
                    other = np.minimum(other, nearest(rr))
            off = own > 1.0
            res[f'{row}_{interp}'] = dict(ground_px=int(ground.sum()), off_row_share=round(float(off.mean()), 5),
                                         worst_steps=round(float(own.max()), 2),
                                         nearer_another_row=round(float((off & (other < own)).mean()), 5))
        out['views'][name] = res
        closest = [v for k, v in res.items() if k.endswith('_Closest')]
        MS.log(f"[reader] lut {name}: Closest, pixels more than one 8-bit step off their row: "
               f"{max(v['off_row_share'] for v in closest):.5f} (worst {max(v['worst_steps'] for v in closest)} "
               f"steps); Linear row 0: {res['0_Linear']}")
    out['pass'] = all(v['off_row_share'] == 0.0 for vw in out['views'].values() for k, v in vw.items()
                      if k.endswith('_Closest'))
    rec['lut'] = out


def look(sc, t, obj, sd, rec):
    """The per-texel material at the edge views, for the eye."""
    a = args()
    case = a['case']
    mat = MS.apply(t, obj, sd)
    out = {}
    for name, eye, target in edge_views(t, sd, a['edges']):
        cam = MS.camera(sc, t, case, name, eye=eye, target=target, lens=35.0)
        sky = os.path.join(OUT, '_sky')
        MS.light(sc, cam, sky)
        MS.frame(sc)
        out[name] = round(MS.frame(sc, os.path.join(OUT, f'look_{case}_{name}.png')), 2)
        MS.clean(sky)
    rec['look_frames_s'] = out
    if 'dolly' in a['parts']:
        dolly(sc, t, sd, case, a['frames'], rec)
    _ = mat


def dolly(sc, t, sd, case, frames, rec):
    """The moving camera: 2 m above the ground, walking north across the finest window's south edge and on across
    the edge of the next finer ring's core, looking ahead and a little down, `frames` frames at 960 x 540 (the
    material already on the object). Frames to out/.../reader/dolly_<case>/, and an H.264 video beside them when
    ffmpeg is on the PATH."""
    import shutil
    import subprocess
    f = sd.levels[-1]
    cx = f.x0 + 0.5 * f.side
    y0, y1 = f.y0 - 0.08 * f.side, f.y0 + 0.10 * f.side
    folder = os.path.join(OUT, f'dolly_{case}')
    os.makedirs(folder, exist_ok=True)
    sky = os.path.join(OUT, '_sky')
    secs = []
    for k in range(frames):
        y = y0 + (y1 - y0) * k / max(frames - 1, 1)
        eye = (cx, y, float(t.height_at(cx, y)) + 2.0)
        ty = y + 60.0
        cam = MS.camera(sc, t, case, 'dolly', eye=eye, target=(cx, ty, float(t.height_at(cx, ty)) + 0.5), lens=28.0)
        if k == 0:
            MS.light(sc, cam, sky)
        secs.append(MS.frame(sc, os.path.join(folder, f'f_{k:03d}.png')))
    MS.clean(sky)
    rec['dolly'] = dict(frames=frames, from_y=round(y0, 1), to_y=round(y1, 1), edge_y=round(f.y0, 1),
                        frame_s=round(sorted(secs)[len(secs) // 2], 2), folder=os.path.relpath(folder, MS.OUT))
    exe = shutil.which('ffmpeg')
    if exe:
        mp4 = os.path.join(OUT, f'dolly_{case}.mp4')
        cmd = [exe, '-y', '-loglevel', 'error', '-framerate', '12', '-i', os.path.join(folder, 'f_%03d.png'),
               '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '16', mp4]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000 if os.name == 'nt' else 0)
        rec['dolly']['video'] = os.path.relpath(mp4, MS.OUT) if r.returncode == 0 else f'ffmpeg failed: {r.stderr[:200]}'
    MS.log(f"[reader] dolly: {json.dumps(rec['dolly'])}")


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    rec = {'case': a['case']}
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(a['case'])
    sd = MS.surface(t)
    rec['levels'] = [str(v) for v in sd.levels]
    if 'look' in a['parts'] or 'dolly' in a['parts']:
        look(sc, t, obj, sd, rec)
        sc = bpy.context.scene
    if 'parity' in a['parts']:
        parity(sc, t, obj, sd, rec)
    if 'edges' in a['parts']:
        edges(sc, t, obj, sd, rec)
    if 'lut' in a['parts']:
        lut(sc, t, obj, sd, rec)
    path = os.path.join(MS.OUT, f"reader_{a['case']}.json")
    if os.path.exists(path):                              # a run of some parts keeps the others' last results
        try:
            old = json.load(open(path, encoding='utf-8'))
            old.update(rec)
            rec = old
        except (OSError, ValueError):
            pass
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
