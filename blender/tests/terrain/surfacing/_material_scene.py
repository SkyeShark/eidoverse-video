"""The material's test scenes (SURFACING_DESIGN.md 5.4, package 2): a case's terrain from the surface-data tests'
snapshots (surface_data/_cases.py), its object built as make_terrain builds it, its surface data baked into the
surface cache's own root, the material applied with or without that data, and the judge's cameras lit the way the
review lights them (make_sky daylight from the view's left).

    import _material_scene as MS
    sc = MS.scene(samples=16)                       # a fresh file: EEVEE 960 x 540, AgX, 16x anisotropic filtering
    t, obj = MS.terrain('canyon')                   # the snapshot's terrain and its object (grey clay)
    sd = MS.surface(t)                              # its SurfaceData (palette 'auto': far colour and provenance)
    mat = MS.apply(t, obj, sd, cameras=[cam])       # the per-texel material; MS.apply(t, obj, None): the old one
    cam = MS.camera(sc, t, 'canyon', 'brink_down')  # a judge view (surfacing_judge/views.json); 'recipe' looks up
                                                    # the view in that recipe's plan
    MS.light(sc, cam, cache_dir)                    # make_sky for that view
    secs = MS.frame(sc, path)                       # one render (written when path is given): seconds

Cases are the snapshot names (_cases.CASES): canyon, alpine_valley, toroweap, lauterbrunnen, meteor_crater, ...;
any other recipe name loads the judge's saved terrain of that recipe (out/surfacing_judge/terrains/<recipe>.npz, made
by surfacing_judge/make_terrains.py: the terrain the review's views were framed on, context and main levels only),
e.g. sea_cliffs, impact_crater, badlands. A view's plan is the case's recipe in views.json (real places: their own
entry when the judge has one).
"""
import json
import math
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
OUT = os.path.join(TN, 'out', 'surfacing', 'material')
for p in (BLENDER_DIR, os.path.join(TN, 'surface_data'), os.path.join(TN, 'reference')):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy  # noqa: E402

import _cases as C  # noqa: E402
import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import surface as SU  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

W, H = 960, 540
EXPOSURE = -0.5                         # the review's textured exposure
VIEWS = os.path.join(TN, 'surfacing_judge', 'views.json')
JUDGE_TERRAINS = os.path.join(TN, 'out', 'surfacing_judge', 'terrains')
# the judge's plan a case's views come from
PLAN_OF = {'canyon': 'canyon', 'alpine_valley': 'alpine_valley', 'lauterbrunnen': 'real_place',
           'meteor_crater': 'impact_crater', 'toroweap': 'canyon', 'fluvial_range': 'fluvial_range'}


def log(*a, **k):
    print(*a, **k, flush=True)


def scene(samples=16, res=(W, H), aniso=16, exposure=EXPOSURE):
    """A fresh file set up as the review renders: EEVEE, AgX, the anisotropic filter set before any image is drawn
    (a GPU texture keeps the filter it was made with)."""
    sc = RR.new_scene(res, samples, exposure)
    bpy.context.preferences.system.anisotropic_filter = f'FILTER_{aniso}'
    return sc


def load(case):
    """The case's Terrain (no Blender object, no GPU): its surface-data snapshot, else the judge's saved terrain of
    that recipe."""
    if case in C.CASES:
        return C.terrain(case)
    p = os.path.join(JUDGE_TERRAINS, case + '.npz')
    if not os.path.exists(p):
        raise FileNotFoundError(f'{case!r} is neither a surface-data case ({", ".join(C.CASES)}) nor a judge terrain '
                                f'({p}: surfacing_judge/make_terrains.py makes them)')
    return A.Terrain.load(p, build=False)


def terrain(case, name=None, mesh_res=None, mask_attributes=True):
    """(Terrain, object): the case's snapshot or judge terrain (load(): no GPU) and its ring mesh object with the
    terrain's custom properties, in grey clay (api._build_blender's own steps, without rocks). mesh_res: the rings
    drawn again at that many vertices per level side (mesh.MESH_RES is 512: stride 2 on levels of 1024 cells; 1024
    is stride 1), as api._assemble_terrain builds them; mask_attributes False leaves the masks off the redrawn rings
    (thirty attributes on four times the vertices), which only the material without baked data reads."""
    t = load(case)
    pal = t.info.get('palette')
    if mesh_res:
        from eidoblend.terrain.build import mesh as _mesh
        n = len(t.levels)
        attrs = None
        if mask_attributes:
            stack = [t.masks.level(i) if hasattr(t.masks, 'level') else t.masks[i] for i in range(n)]
            attrs = {k: [m.get(k) for m in stack] for k in sorted(set().union(*[set(m) for m in stack]))}
        t0 = time.time()
        t.ring = _mesh.build_rings(t.levels, [t.fields(i)['h'] for i in range(n)], attrs,
                                   cores=any(lv.role == 'hero' for lv in t.levels), mesh_res=int(mesh_res))
        t.info['mesh_res'] = int(mesh_res)
        log(f'[material scene] {case}: rings at {int(mesh_res)} vertices a side, {len(t.ring.verts):,} vertices, '
            f'{t.ring.triangle_count:,} triangles in {time.time() - t0:.1f} s')
    A._build_blender(t, name or f'{case}_terrain', None, None, False, log)
    t.info['palette'] = pal                               # (building in clay records palette None)
    return t, t.obj


def surface(t, palette='auto', cache=True, options=None):
    """The terrain's SurfaceData, baked with its palette (cache: the surface cache's own root)."""
    return SU.bake_surface(t, palette=palette, cache=cache, options=options, log=log)


def palette_args(t):
    """(palette, strata) as make_terrain passes them for this terrain (a real place: its own palette and strata)."""
    info = t.info
    pal = 'auto'
    strata = None
    if info.get('place'):
        pal = info.get('palette') or 'auto'
        strata = (P.PLACES.get(info['place']) or {}).get('strata')
    return pal, strata


def apply(t, obj, sd, cameras=None, options=None, name=None):
    """The material on the object: with sd the per-texel material (and the far material on rings beyond 1.5 D0 of the
    cameras), with sd None today's attribute material."""
    pal, strata = palette_args(t)
    return S.apply_surface(obj, palette=pal, recipe=t.recipe, strata=strata, options=options, data=sd,
                           cameras=cameras, name=name, log=log)


def view(case, name):
    plan = json.load(open(VIEWS, encoding='utf-8'))[PLAN_OF.get(case, case)]
    for v in plan['views']:
        if v['name'] == name:
            return v
    raise KeyError(f'{case}: no view {name!r} in {VIEWS}')


def aim_camera(cam, eye, target, frame, lens):
    """Point cam from eye so that target lands at frame (0..1 from the left, from the top): the review's rule."""
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    u = (frame[0] - 0.5) * 36.0 / lens
    v = (0.5 - frame[1]) * 36.0 * H / W / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(v)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))


def camera(sc, t, case, name, eye=None, target=None, lens=None):
    """A camera at the judge's view `name` of the case (or at eye looking at target, world metres), the scene's."""
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    if eye is None:
        v = view(case, name)
        ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
        kind, dz = v['cam_z']
        ez = float(t.height_at(ex, ey)) + float(dz) if kind == 'ground' else float(dz)
        target = (v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2])
        frame, lens = v['frame'], float(lens or v['lens'])
        eye = (ex, ey, ez)
    else:
        frame, lens = (0.5, 0.5), float(lens or 35.0)
    cam = bpy.data.objects.get(f'cam_{name}') or bpy.data.objects.new(f'cam_{name}',
                                                                       bpy.data.cameras.new(f'cam_{name}'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    dist = math.dist(eye, target)
    cam.data.clip_start = 0.1 if eye[2] - float(t.height_at(eye[0], eye[1])) < 50 else max(1.0, 0.01 * dist)
    cam.data.clip_end = 4.0 * t.levels[0].side + 40000.0
    aim_camera(cam, eye, target, frame, lens)
    sc.camera = cam
    return cam


_SUN = {}


def light(sc, cam, cache_dir):
    """make_sky daylight with the sun RR.SUN_LEFT_DEG left of the view, as the review lights its views (a later call
    in the same scene reuses its sun lamp)."""
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    os.makedirs(cache_dir, exist_ok=True)
    sun = _SUN.get(sc.name)
    try:
        sun = sun if (sun is not None and sun.name in sc.objects) else None
    except ReferenceError:
        sun = None
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache_dir,
                   quality='film', shadows=False, sun=sun,
                   azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    _SUN[sc.name] = sky.sun
    return sky


def frame(sc, path=None):
    """One render; written to path when given. Returns its seconds."""
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=bool(path))
    return time.time() - t0


def salt(mat, k):
    """k extra no-op nodes on the material's roughness: a different shader source, so a compile measured after it is
    cold (the GPU driver caches compiled sources; node values are uniforms and would not change the source)."""
    nt = mat.node_tree
    grp = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeGroup')
    ng = grp.node_tree
    bsdf = next(n for n in ng.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    sock = bsdf.inputs['Roughness']
    src = sock.links[0].from_socket if sock.links else None
    for _ in range(int(k)):
        m = ng.nodes.new('ShaderNodeMath')
        m.operation = 'ADD'
        m.inputs[1].default_value = 0.0
        if src is not None:
            ng.links.new(src, m.inputs[0])
        else:
            m.inputs[0].default_value = sock.default_value
        src = m.outputs[0]
    ng.links.new(src, sock)


DIST_UNIT = 20000.0                       # region_render's view distance scale, metres
OUTSIDE_UNIT = 4000.0                     # ... and its Hero Outside scale


def region_material(sd):
    """An emission of (Hero Outside / OUTSIDE_UNIT, view distance / DIST_UNIT, 1) through the terrain's reader."""
    mat = bpy.data.materials.new('view_region')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    rd = nt.nodes.new('ShaderNodeGroup')
    rd.node_tree = S.reader_group(sd)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Object'], rd.inputs['Position'])
    rd.inputs['Footprint'].default_value = 1.0
    cam = nt.nodes.new('ShaderNodeCameraData')
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k, (sock, unit) in enumerate(((rd.outputs['Hero Outside'], OUTSIDE_UNIT), (cam.outputs['View Distance'],
                                                                                 DIST_UNIT))):
        m = nt.nodes.new('ShaderNodeMath')
        m.operation = 'DIVIDE'
        nt.links.new(sock, m.inputs[0])
        m.inputs[1].default_value = unit
        nt.links.new(m.outputs[0], comb.inputs[k])
    comb.inputs[2].default_value = 1.0
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(comb.outputs[0], em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def region_render(sc, me, mat, path):
    """(metres outside the outermost hero window, view distance metres, ground mask) per pixel, top row first, from
    region_material on the whole mesh: a one-sample float render with a black world and the Standard view, then the
    scene's own settings, materials and material indices back."""
    import numpy as np
    slots = list(me.materials)
    me.materials.clear()
    me.materials.append(mat)
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    me.polygons.foreach_set('material_index', np.zeros(len(me.polygons), np.int32))
    vs, im = sc.view_settings, sc.render.image_settings
    keep = (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format,
            im.color_depth, im.color_mode, sc.render.film_transparent)
    sc.world = bpy.data.worlds.get('region_black') or bpy.data.worlds.new('region_black')
    sc.world.color = (0.0, 0.0, 0.0)
    vs.view_transform, vs.look, vs.exposure = 'Standard', 'None', 0.0
    sc.eevee.taa_render_samples = 1
    sc.render.film_transparent = True
    im.file_format, im.color_depth, im.color_mode = 'OPEN_EXR', '32', 'RGBA'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]
    (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format, im.color_depth,
     im.color_mode, sc.render.film_transparent) = keep
    me.materials.clear()
    for m in slots:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', idx)
    me.update()
    return px[..., 0] * OUTSIDE_UNIT, px[..., 1] * DIST_UNIT, px[..., 3] > 0.5


def read_png(path):
    """(H, W, 3) display values 0..1 of a written PNG, top row first."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3]


def vram_mib():
    """This process's dedicated GPU memory in MiB, from Windows' "GPU Process Memory" performance counter (what Task
    Manager shows per process); None where that counter does not exist (other systems) or cannot be read."""
    if os.name != 'nt':
        return None
    import subprocess
    cmd = ("$s = (Get-Counter '\\GPU Process Memory(pid_%d*)\\Dedicated Usage' -ErrorAction SilentlyContinue)"
           ".CounterSamples; if ($s) { [math]::Round(($s | Measure-Object -Property CookedValue -Sum).Sum / 1MB) }"
           % os.getpid())
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd], capture_output=True,
                           text=True, timeout=30, creationflags=0x08000000)
        return int(r.stdout.strip()) if r.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def clean(path):
    shutil.rmtree(path, ignore_errors=True)
