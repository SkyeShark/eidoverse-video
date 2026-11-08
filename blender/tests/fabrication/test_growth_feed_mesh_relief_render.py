"""Probe renders of what the other fabrication probes do not show: the keyed growth over time, the live filament feed,
the dispenser, a free service loop and a mesh carved as a relief. One Blender run, one GPU slot.

  growth   out/manufacturing_example.blend (written by test_fabrication_render.py) reopened as a plain file before
           eidoblend is imported: the lathe sleeve printing layer by layer and the aluminium pocket being milled, each
           from a close camera at eight times on the file's own keys -> out/growth_print_t*.png,
           out/growth_pocket_t*.png (480 x 270) and out/growth_print_sheet.png, out/growth_pocket_sheet.png
  feed     the FDM printing the fork bracket in orange: the reel paying out into the carrier liner, and the short PTFE
           entries at the head with the filament core inside, at 2 s and 9 s (the head has travelled, the reel turned)
           -> out/feed_reel_t*.png, out/feed_head_t*.png
  spool    the standalone dispenser playing its filament-feed sample -> out/feed_spool.png
  loop     a free PTFE tube shaped by service_loop (300 mm between points 120 mm apart) with an orange core
           -> out/feed_service_loop.png
  mesh     the relief CNC carving the fork bracket sample, placed in stock coordinates, as a relief in hardwood
           (relief_from_mesh: its upper visible envelope): finished by the planner as the WebGPU edition plans it
           (out/mesh_relief_plain_t20.png), then with lift_over_steps, mid-roughing and finished
           (out/mesh_relief_lifted_t06.png, _t20.png)

Checks (numeric): the saved file's bead and pocket only grow / deepen between the sampled times; the head entries end on
the inlet at both times and the reel turned; the dispenser fed; the service loop has its length; on the bracket's flats
the finished stock lies within its scallop of the target, and lift_over_steps keeps the cutter out of the walls that the
plain planner's straight moves cut into.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/fabrication/test_growth_feed_mesh_relief_render.py [-- --no-render] [-- --only growth,feed]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
ONLY = set(ARGS[ARGS.index('--only') + 1].split(',')) if '--only' in ARGS else {'growth', 'feed', 'spool', 'loop', 'mesh'}
LINES = []


def check(name, ok, detail=''):
    line = f"{'PASS' if ok else 'FAIL'} {name}" + (f'  ({detail})' if detail else '')
    print(line, flush=True)
    LINES.append((ok, line))
    return ok


def render(scene, path, frame=None):
    if frame is not None:
        scene.frame_set(frame)
    scene.render.filepath = path
    if RENDER:
        bpy.ops.render.render(write_still=True)
        print(f"[render] {path} {'written' if os.path.exists(path) else 'MISSING'}", flush=True)
    return path


def aim(cam, target, offset, fov=30, clip=.005):
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov)
    cam.data.clip_start = clip
    cam.location = Vector(target) + Vector(offset)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (Vector(target) - cam.location).to_track_quat('-Z', 'Y')


def sheet(paths, cols, out):
    """A contact sheet of equal PNG frames, left to right, top to bottom (Blender's own image IO)."""
    if not RENDER or not all(os.path.exists(p) for p in paths):
        return None
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = math.ceil(len(imgs) / cols)
    canvas = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        a = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(h, w, 4)[::-1]                    # Blender's rows run bottom-up
        r, c = divmod(k, cols)
        canvas[r * h:(r + 1) * h, c * w:(c + 1) * w] = a
        bpy.data.images.remove(im)
    out_im = bpy.data.images.new('sheet', cols * w, rows * h, alpha=False)
    out_im.pixels.foreach_set(canvas[::-1].ravel())
    out_im.filepath_raw = out
    out_im.file_format = 'PNG'
    out_im.save()
    bpy.data.images.remove(out_im)
    print(f'[sheet] {out}', flush=True)
    return out


def settings(scene, w=960, h=540, samples=16):
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_settings.view_transform = 'AgX'
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = samples
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False


# ------------------------------------------------------------------------------------------------- growth ---
if 'growth' in ONLY:
    blend = os.path.join(OUT, 'manufacturing_example.blend')
    if not os.path.exists(blend):
        check('the saved manufacturing example exists (run test_fabrication_render.py first)', False, blend)
    else:
        bpy.ops.wm.open_mainfile(filepath=blend)
        scene = bpy.context.scene
        settings(scene, 480, 270, 16)
        fps = scene.render.fps / scene.render.fps_base
        robots = {o.get('robot_id'): o for o in bpy.data.objects if o.name.startswith('robot|')}

        def base_of(rid):
            g = robots[rid]
            return next(o for o in g.children_recursive if o.get('module_id') == 'gantry_base')

        sun = next((o for o in bpy.data.objects if o.type == 'LIGHT' and o.data.type == 'SUN'), None)
        if sun is not None:
            sun.data.use_shadow = True                  # contact reads in the close views, as test_fabrication_render
        bead = bpy.data.objects['FDM deposited bead']
        pocket = next(o for o in bpy.data.objects if o.name.startswith('CNC swept flat-end stock'))
        cam_data = bpy.data.cameras.new('growth cam')
        cam = bpy.data.objects.new('growth cam', cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
        times = (0.5, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 18.0)
        for name, rid, offset, look, ob in (
                ('print', 'manufacturing/fdm', (.055, -.095, .06), (0, 0, .06), bead),
                ('pocket', 'manufacturing/cnc', (.085, -.15, .125), (0, -.004, .074), pocket)):
            bpy.context.view_layer.update()
            target = base_of(rid).matrix_world @ Vector(look)
            aim(cam, target, offset, fov=30, clip=.004)
            paths, sizes = [], []
            for t in times:
                f = scene.frame_start + int(round(t * fps))
                scene.frame_set(f)
                dg = bpy.context.evaluated_depsgraph_get()
                me = ob.evaluated_get(dg).to_mesh()
                if name == 'print':
                    sizes.append(len(me.vertices))
                else:                                   # the lowest top vertex (the skirt's foot and floor sit at 0)
                    co = np.empty(len(me.vertices) * 3, np.float32)
                    me.vertices.foreach_get('co', co)
                    z = co.reshape(-1, 3)[:, 2]
                    sizes.append(float(z[z > 1e-6].min()))
                ob.evaluated_get(dg).to_mesh_clear()
                paths.append(render(scene, os.path.join(OUT, f'growth_{name}_t{t:04.1f}.png'), f))
            if name == 'print':
                check('the saved file\'s bead grows at every sampled time', all(a < b for a, b in zip(sizes, sizes[1:])),
                      ', '.join(f'{n // 16}' for n in sizes) + ' chords')
            else:
                check('the saved file\'s pocket deepens or holds at every sampled time',
                      all(b <= a + 1e-7 for a, b in zip(sizes, sizes[1:])) and sizes[-1] < sizes[0],
                      ', '.join(f'{(.02 - v) * 1000:.1f}' for v in sizes) + ' mm deep')
            sheet(paths, 4, os.path.join(OUT, f'growth_{name}_sheet.png'))

# ----------------------------------------------------------------------------------- the rest: the package ---
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
if ONLY & {'feed', 'spool', 'loop', 'mesh'}:
    from eidoblend import fabrication as fab  # noqa: E402
    from eidoblend.characters.robotics import make_robot  # noqa: E402
    from eidoblend.characters.robotics.studio import frame_camera, make_camera, studio  # noqa: E402
    from eidoblend.fabrication.machine import world_matrix  # noqa: E402

    def fresh(grid=False):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.fps = 24
        st = studio(sc, grid=grid, shadows=True)
        settings(sc)
        return sc, st

    def evaluated_box(objects):
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in objects:
            if o.type != 'MESH':
                continue
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            if me is not None and len(me.vertices):
                co = np.empty(len(me.vertices) * 3, np.float32)
                me.vertices.foreach_get('co', co)
                m = np.array(oe.matrix_world)
                p = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
                pts.append(p)
            oe.to_mesh_clear()
        p = np.concatenate(pts)
        return Vector(p.min(axis=0)), Vector(p.max(axis=0))

if 'feed' in ONLY:
    scene, _ = fresh()
    printer = make_robot('fdm', scene=scene, filament='#e2742b', accent='#267c82')
    job = fab.print(printer, fab.manufacturing_sample('bracket', as_parts=True), size=.04, infill=.25, duration=12)
    f = printer.filament
    cam = make_camera(30, 'feed cam', scene)
    scene.camera = cam
    turns, ends = [], []
    for t in (2.0, 9.0):
        job.seek(t)
        bpy.context.view_layer.update()
        inlet = world_matrix(printer.roots['extruder_fixed']) @ Vector((0, 0, .115))
        end = world_matrix(printer.roots['gantry_base']) @ Vector(f.tubes[-1].sample(1))
        ends.append((end - inlet).length)
        turns.append(f.rotation)
        lo, hi = evaluated_box([f.strand.mesh, printer.roots['filament_reel']] +
                               [o for o in printer.roots['filament_reel'].children_recursive if o.type == 'MESH'])
        frame_camera(cam, [(lo, hi)], direction=Vector((-.9, -1.2, .55)), margin=1.25)
        cam.data.clip_start = .005
        render(scene, os.path.join(OUT, f'feed_reel_t{t:02.0f}.png'))
        lo, hi = evaluated_box([c.mesh for c in f.tubes[2:]])
        lo2, hi2 = evaluated_box([o for o in [printer.roots['extruder_fixed']] +
                                  list(printer.roots['extruder_fixed'].children_recursive) if o.type == 'MESH'])
        box = (Vector(np.minimum(lo, lo2)), Vector(np.maximum(hi, hi2)))
        frame_camera(cam, [box], direction=Vector((.75, -1.3, .45)), margin=1.1)
        cam.data.clip_start = .005
        render(scene, os.path.join(OUT, f'feed_head_t{t:02.0f}.png'))
    check('the head entry stays seated on the inlet while the head travels', max(ends) < 1e-6,
          f'{max(ends) * 1000:.6f} mm')
    check('the reel turned with the consumed filament', turns[1] > turns[0] > 0,
          f'{math.degrees(turns[0]):.2f} -> {math.degrees(turns[1]):.2f} deg; {f.consumed_length * 1000:.1f} mm fed')

if 'spool' in ONLY:
    scene, _ = fresh()
    spool = make_robot('spool', scene=scene, filament='#2c59bd')
    fab.ensure_filament(spool)
    spool.sample('filament-feed', 6.0)
    cam = make_camera(30, 'spool cam', scene)
    scene.camera = cam
    frame_camera(cam, [spool.group], direction=Vector((.9, -1.5, .55)), margin=1.15)
    check('the dispenser fed its filament (reel turned, strand embedded in the winding)',
          spool.filament.rotation > 0 and 0 < spool.filament.payout.embedded_depth < .000875,
          f'{spool.filament.consumed_length * 1000:.0f} mm fed, row {spool.filament.payout.row:.2f}')
    render(scene, os.path.join(OUT, 'feed_spool.png'))

if 'loop' in ONLY:
    scene, _ = fresh(grid=True)
    pts = fab.service_loop((0, 0, .002), (.12, 0, .002), .3, up=(0, 0, 1))
    tube = fab.create_ptfe_tube(points=pts, outer_diameter=.004, inner_diameter=.002, segments=96, name='service loop')
    core = fab.create_ptfe_tube(points=pts, outer_diameter=.00175, inner_diameter=0, segments=96, color='#e2742b',
                                name='service loop core')
    check('service_loop gives the asked length', abs(tube.length - .3) < 1e-6, f'{tube.length * 1000:.3f} mm')
    cam = make_camera(30, 'loop cam', scene)
    scene.camera = cam
    lo, hi = evaluated_box([tube.mesh])
    frame_camera(cam, [(lo, hi)], direction=Vector((.35, -1.5, .45)), margin=1.2)
    render(scene, os.path.join(OUT, 'feed_service_loop.png'))

if 'mesh' in ONLY:
    scene, _ = fresh()
    cnc = make_robot('cnc_relief', scene=scene, accent='#547b68')
    # the inspector's way with a supplied mesh (viewer.js): fitted into three's Box3 (-.032, .004, -.055) ..
    # (.032, .019, .055), carved at 192 cells
    src = fab.fit_source_geometry(fab.manufacturing_sample('bracket', as_parts=True),
                                  bounds=((-.032, -.055, .004), (.032, .055, .019)))
    cam = make_camera(36, 'mesh relief cam', scene)
    scene.camera = cam
    gouges = {}
    # the WebGPU planner as it is (straight moves between tips 1 mm apart cut into the walls), then lift_over_steps
    for lift, times in ((False, (20.0,)), (True, (6.0, 20.0))):
        carving = fab.carve(cnc, src, material='wood', duration=20, resolution=192, lift_over_steps=lift)
        bpy.context.view_layer.update()
        frame_camera(cam, [carving.mesh], direction=Vector((.8, -.8, 1.05)), margin=1.5)
        for t in times:
            state = carving.seek(t)
            print(f'[mesh] lift={lift} t={t}: stage {state.stage}', flush=True)
            render(scene, os.path.join(OUT, f"mesh_relief_{'lifted' if lift else 'plain'}_t{t:02.0f}.png"))
        # the finished stock against the sampled target: how far below it, and how close on the flats
        target = carving.program['target']
        xs = np.linspace(-.03, .03, 61)
        ys = np.linspace(-.054, .054, 109)
        pts = [(x, y) for y in ys for x in xs]
        h = np.array(carving.inspect_heights(pts, progress=carving.path.length))
        want = np.array([target(x, y) for x, y in pts])
        gouges[lift] = float((want - h).max())
        flat = np.ones(len(pts), dtype=bool)             # the same height everywhere within the ball's reach
        for k in range(12):
            dx, dy = .0035 * math.cos(k * math.pi / 6), .0035 * math.sin(k * math.pi / 6)
            flat &= np.abs(np.array([target(x + dx, y + dy) for x, y in pts]) - want) < 1e-9
        excess = float((h - want)[flat].max())
        check(f"lift={lift}: on the bracket's flat top and the floor the finish lies within its scallop of the target",
              0 <= excess < 2.5e-4, f'worst {excess * 1e6:.1f} um over {int(flat.sum())} flat points')
        carving.dispose()
    check('lift_over_steps keeps the cutter out of the bracket\'s walls (the plain planner cuts in, as the WebGPU one)',
          gouges[False] > .001 and gouges[True] < .00025,
          f'deepest cut below the target {gouges[False] * 1000:.2f} mm plain, {gouges[True] * 1000:.2f} mm lifted')

fails = [ln for ok, ln in LINES if not ok]
with open(os.path.join(OUT, 'growth_feed_mesh_relief_results.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(ln for _, ln in LINES) + f'\n{len(LINES) - len(fails)} passed, {len(fails)} failed\n')
print(f'[growth_feed_mesh_relief] {len(LINES) - len(fails)} passed, {len(fails)} failed', flush=True)
sys.exit(1 if fails else 0)
