"""test_renders.py: the harness-rest ports that make pictures, rendered so they can be looked at (960 x 540, 16 samples).

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh blender/tests/pipeline2/test_renders.py
        [--only hover,kit,windows,recipes,shelf,stairs,clips,rig] [--no-render]

  hover    the stool and clock seated (place_on), then the stool moved 0.3 m: the clock hangs in the air and the
           hovering audit names it (round one's false negative): hover_seated.png, hover_moved.png
  kit      a supplies kit (four Poly Haven models laid out in a row and exported as one GLB, as fetched kits come):
           load_kit, its islands, instances stacked with place_on through their real geometry, an html_mesh sign
           mounted on the wall with mount_on, the placement audits on the result: kit_supplies.png
  windows  a brick facade with six interior-mapped windows (create_interior_window_material, with the glass
           reflection) showing two furnished rooms rendered with render_room_image (PBR walls and floors, a lamp and
           daylight), from two angles (the rooms' parallax): windows_a.png, windows_b.png, room_*.png
  recipes  placement.md's composition recipes as written, on the local catalogue's models: recipes.png
  shelf    placement.md's shelf filling: a worn metal rack's boards found by casting down through it, workshop props
           put on each board with place_inside (aim_z between boards) and snap_to_ground(below=True): shelf.png
  stairs   placement.md's 'character standing on stairs': claude.vrm (a stationary clip) dropped from 5 m with
           snap_to_ground(character, [stair1, stair2, landing]): stairs.png
  clips    play_model_animations(clip='all', weights) and clone_model(independent_actions=True) on the crow: one crow
           walking while it caws (the two clips layered), a clone with its own actions pecking, a clone sharing the
           actions idling; four frames: clips_fNNN.png
  rig      render_common.setup_scene's default rig (the render_*.mjs tools' four lights) on the stool and clock: rig.png
Prints PASS / FAIL per check; os._exit(1) on a failure. LOOK at the PNGs in out/renders/.
"""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out', 'renders')
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.harness import assets  # noqa: E402

results = []
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(ARGS[ARGS.index('--only') + 1].split(',')) if '--only' in ARGS else None


def check(name, ok, msg=''):
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}: {msg}", flush=True)


def fresh(samples=16):
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 540, 100
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Base Contrast'
    return sc


def render(sc, name):
    p = os.path.join(OUT, name)
    if '--no-render' in ARGS:                                       # the scenes' own checks only (no GPU slot)
        print(f'(not rendered: {name})', flush=True)
        return p
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    check(f'render {name}', os.path.exists(p), p)
    return p


def plane(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, uv_scale=1.0):
    me = bpy.data.meshes.new(name)
    sx, sy = size
    me.from_pydata([(-sx / 2, -sy / 2, 0), (sx / 2, -sy / 2, 0), (sx / 2, sy / 2, 0), (-sx / 2, sy / 2, 0)], [],
                   [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (sx * uv_scale, 0), (sx * uv_scale, sy * uv_scale), (0, sy * uv_scale)]):
        loop.uv = (u, v)
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location, ob.rotation_euler = loc, rot
    return ob


def box(name, lo, hi, mat=None):
    """An axis-aligned block from its two corners (stairs, plinths), UVs in metres on every face."""
    me = bpy.data.meshes.new(name)
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    me.from_pydata(v, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, co.y) if abs(n.z) > 0.5 else ((co.y, co.z) if abs(n.x) > 0.5 else (co.x, co.z))
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def area(name, loc, aim, energy, size=0.5, colour=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA')
    d.shape, d.size, d.energy, d.color = 'DISK', size, energy, colour
    ob = bpy.data.objects.new(name, d)
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera(loc, aim, lens=35):
    cd = bpy.data.cameras.new('cam')
    cd.lens = lens
    ob = bpy.data.objects.new('cam', cd)
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def world(rgb, strength):
    w = bpy.data.worlds.new('w')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*rgb, 1)
    bg.inputs['Strength'].default_value = strength
    bpy.context.scene.world = w


def pbr(tex, res='2k'):
    return assets.load_pbr(tex, res=res, maps=('diff', 'normal', 'rough'), repeat=(1, 1))


def room_set(floor_tex='WoodFloor064', wall_tex='PaintedPlaster015', size=6.0, wall_y=1.2):
    """A floor (size x size) and a back wall (size x 3 m) at y = wall_y, wide enough that a 28 mm lens never sees past
    their ends."""
    floor = plane('floor', (size, size), mat=pbr(floor_tex), uv_scale=0.6)
    wall = plane('wall', (size, 3), loc=(0, wall_y, 1.5), rot=(math.pi / 2, 0, 0), mat=pbr(wall_tex), uv_scale=0.5)
    return floor, wall


# ------------------------------------------------------------------------------------------------------ hover ---
def test_hover():
    from eidoblend.placement import place_on, check_hovering
    for tag, move in (('seated', 0.0), ('moved', 0.3)):
        sc = fresh()
        floor, wall = room_set()
        stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='stool')
        clock = assets.import_model(assets.fetch_model_file('alarm_clock_01', res='2k'), name='clock')
        place_on(stool, floor, xy=(0.0, 0.0))
        place_on(clock, stool, xy=(0.03, 0.0))
        stool.location.x += move
        bpy.context.view_layer.update()
        rep = check_hovering(sc)
        named = [r for r in rep if r['obj'] == clock]
        check(f'hover {tag}: the audit {"names" if move else "leaves"} the clock',
              bool(named) == bool(move), f"{[(r['obj'].name, round(r['gap'], 3), r['kind']) for r in rep]}")
        area('key', (-0.9, -1.0, 1.5), (0.1, 0, 0.3), 120, 0.5, (1.0, 0.92, 0.82))
        area('fill', (1.4, -1.2, 0.9), (0.1, 0, 0.3), 25, 1.5, (0.8, 0.88, 1.0))
        world((0.04, 0.045, 0.05), 1.0)
        camera((0.55, -1.55, 0.62), (0.12, 0.0, 0.3), 40)
        render(sc, f'hover_{tag}.png')


# -------------------------------------------------------------------------------------------------------- kit ---
KIT_PARTS = (('wooden_military_crate', '1k', 'crate'), ('metal_jerrycan_green', '1k', 'jerrycan'),
             ('metal_toolbox', '1k', 'toolbox'), ('old_tyre', '1k', 'tyre'))


def make_supplies_kit(path):
    """Four Poly Haven models laid out in a row under one wrapper, exported as one GLB: a kit as fetched kits come."""
    fresh()
    host = bpy.data.objects.new('SuppliesKit', None)
    bpy.context.scene.collection.objects.link(host)
    x = 0.0
    for pid, res, name in KIT_PARTS:
        root = assets.import_model(assets.fetch_model_file(pid, res=res), name=name)
        lo, hi = assets.bounds(root)
        root.location.x += x - lo.x
        root.parent = host
        x += (hi.x - lo.x) + 0.6
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_apply=False)
    return path


def test_kit():
    from eidoblend.harness.html_mesh import El, html_mesh
    from eidoblend.placement import place_on, mount_on, check_hovering, check_clipping, clear_cache
    glb = os.path.join(HERE, 'out', 'kit_supplies.glb')
    make_supplies_kit(glb)
    sc = fresh()
    floor, wall = room_set('Concrete034', 'PaintedPlaster017', size=10.0)
    kit = assets.load_kit(glb)
    check('kit: the supplies kit lists its four models as parts', kit.count == 4, f'{kit.names}')
    groups = kit.island_groups()
    check('kit: four separate pieces, four islands', len(groups) == 4, f'{groups}')
    c1 = kit.get('crate', location=(-0.4, 0.55, 0.0), rotation_z=math.radians(4))
    c2 = kit.get('crate', location=(-0.35, 0.5, 2.0), rotation_z=math.radians(-6))
    can = kit.get('jerrycan', location=(-0.5, 0.45, 3.0), rotation_z=math.radians(20))
    box_ = kit.get('toolbox', location=(0.55, 0.3, 0.0), rotation_z=math.radians(-15))
    tyre_isl = kit.islands()                                    # one instance per piece, standing at the origin
    tyre = next(e for e in tyre_isl if 'tyre' in e.instance_collection.get('eido_kit_parts', []))
    for e in tyre_isl:
        if e is not tyre:
            bpy.data.objects.remove(e)
    tyre.location = (0.9, -0.35, 0.0)
    bpy.context.view_layer.update()
    clear_cache()
    ok = [place_on(c1, floor), place_on(c2, c1), place_on(can, c2), place_on(box_, floor), place_on(tyre, floor)]
    check('kit: instances seated with place_on (crate on the floor, crate on crate, can on top, toolbox, tyre)',
          all(ok), f'{ok}')
    card = El('div', style='display: inline-block; padding: 22px 34px; background: #11161d; color: #f0c040; '
                           'border: 6px solid #f0c040; border-radius: 10px; font: 700 64px Rajdhani-Bold; '
                           'text-transform: uppercase; letter-spacing: 2px',
              children=[El('div', text='Supply depot 7'),
                        El('div', style='font: 400 30px SpaceMono-Regular; color: #c9d4e0', text='fuel - tools - spares')])
    sign = html_mesh(card, out_dir=os.path.join(OUT, 'sign_frames'), name='depot_sign').obj
    sign.location = (0.0, -0.5, 1.5)
    bpy.context.view_layer.update()
    m = mount_on(sign, wall, dir=(0, -1, 0), standoff=0.004)       # the wall's room side faces -Y
    sign.location.x += 0.35                                          # slide along the wall: it stays flush
    sign.location.z += 0.35
    check('kit: the html_mesh sign mounted flat on the wall (mount_on)', m is not None and abs(m['normal'].y + 1) < 1e-3,
          f'{m and tuple(round(v, 3) for v in m["point"])}')
    rep = check_hovering(sc)
    clip = check_clipping(sc)
    deep = [p for p in clip if p.get('deep')]
    check('kit: nothing hovers, nothing deep inside another', not rep and not deep,
          f"hover {[(r['obj'].name, round(r['gap'], 3)) for r in rep]}, deep {len(deep)}")
    area('key', (-1.6, -1.6, 2.4), (0, 0.4, 0.5), 260, 0.6, (1.0, 0.93, 0.85))
    area('fill', (1.8, -1.4, 1.2), (0, 0.4, 0.6), 40, 2.0, (0.82, 0.9, 1.0))
    world((0.03, 0.035, 0.04), 1.0)
    camera((1.25, -2.75, 1.25), (0.05, 0.4, 0.95), 28)
    render(sc, 'kit_supplies.png')


# ---------------------------------------------------------------------------------------------------- windows ---
LOCAL = os.path.join(ROOT, 'eidoverse', 'assets', 'models')


def _into(sc, root):
    for o in [root] + list(root.children_recursive):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        sc.collection.objects.link(o)


def furnish(kind):
    """build(scene) for render_room_image: real props at real scale in the room box (x -1.6..1.6, y 0..3 deep, the
    window at y = 0), imported and stood in the open scene, where they evaluate, then moved into the room's scene;
    the desk lamp stands ON the desk, the store's tins on the rack's boards."""
    def build(sc):
        if kind == 'study':
            desk = assets.import_model(os.path.join(LOCAL, 'corner_desk.glb'), name='study_desk')
            assets.rest_on(desk, 0.0, xy=(-0.35, 2.55))
            dlo, dhi = assets.bounds(desk)
            lamp = assets.import_model(assets.fetch_model_file('desk_lamp_arm_01', res='1k'), name='study_lamp')
            lamp.rotation_euler.z = math.radians(200)
            assets.rest_on(lamp, dhi.z, xy=(dlo.x + 0.22, 2.62))
            books = assets.import_model(os.path.join(LOCAL, 'corner_books.glb'), name='study_books')
            assets.rest_on(books, dhi.z, xy=(dhi.x - 0.25, 2.5))
            stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='study_stool')
            assets.rest_on(stool, 0.0, xy=(-0.2, 1.75))
            tool = assets.import_model(assets.fetch_model_file('metal_toolbox', res='1k'), name='study_toolbox')
            tool.rotation_euler.z = math.radians(-25)
            assets.rest_on(tool, 0.0, xy=(1.05, 2.3))
            parts = (desk, lamp, books, stool, tool)
        else:
            rack = assets.import_model(assets.fetch_model_file('worn_metal_rack', res='1k'), name='store_rack')
            assets.rest_on(rack, 0.0, xy=(-0.85, 2.62))
            can = assets.import_model(assets.fetch_model_file('small_oil_can_01', res='2k'), name='store_can')
            assets.rest_on(can, 0.92, xy=(-1.0, 2.6))
            pot = assets.import_model(assets.fetch_model_file('pot_enamel_01', res='1k'), name='store_pot')
            assets.rest_on(pot, 1.41, xy=(-0.75, 2.6))
            c1 = assets.import_model(assets.fetch_model_file('wooden_military_crate', res='1k'), name='store_crate')
            assets.rest_on(c1, 0.0, xy=(0.65, 2.55))
            c1lo, c1hi = assets.bounds(c1)
            c2 = assets.clone_model(c1, name='store_crate_2')
            c2.rotation_euler.z = math.radians(-7)
            assets.rest_on(c2, c1hi.z, xy=(0.62, 2.55))
            tyre = assets.import_model(assets.fetch_model_file('old_tyre', res='1k'), name='store_tyre')
            assets.rest_on(tyre, 0.0, xy=(0.95, 1.55))
            jc = assets.import_model(assets.fetch_model_file('metal_jerrycan_green', res='1k'), name='store_can2')
            jc.rotation_euler.z = math.radians(30)
            assets.rest_on(jc, 0.0, xy=(-0.1, 2.0))
            parts = (rack, can, pot, c1, c2, tyre, jc)
        for p in parts:
            _into(sc, p)
    return build


def test_windows():
    from eidoblend.harness.interior_window import create_interior_window_material, render_room_image
    sc = fresh()
    rooms = {}
    looks = {'study': dict(wall_material=pbr('PaintedPlaster015'), floor_material=pbr('WoodFloor064'),
                           ceiling_material=pbr('PaintedPlaster017'), lamp=(1.0, 0.8, 0.55), lamp_power=160.0,
                           window_light=260.0),
             'store': dict(wall_material=pbr('PaintedBricks004'), floor_material=pbr('Concrete034'),
                           ceiling_material=pbr('PaintedPlaster017'), lamp=(0.85, 0.92, 1.0), lamp_power=120.0,
                           window_light=200.0)}
    for kind, look in looks.items():
        p = os.path.join(OUT, f'room_{kind}.png')
        if '--no-render' in ARGS:                                   # a stand-in picture, under its own name (never
            from PIL import Image                                   # over a rendered room): the scene's own checks
            p = os.path.join(OUT, f'room_{kind}_standin.png')
            Image.new('RGB', (64, 64), (180, 140, 90)).save(p)
        else:
            render_room_image(p, size=512, build=furnish(kind), **look)
        rooms[kind] = p
        check(f'windows: room picture {kind}', os.path.exists(p), p)
    sc = bpy.context.scene
    for o in list(bpy.data.scenes):
        if o != sc:
            bpy.data.scenes.remove(o)
    plane('facade', (7.0, 4.4), loc=(0, 0, 2.2), rot=(math.pi / 2, 0, 0), mat=pbr('Bricks097'), uv_scale=0.45)
    plane('street', (14, 10), loc=(0, -4, 0), mat=pbr('Asphalt025C'), uv_scale=0.25)
    mats = {k: create_interior_window_material(room=p, depth=0.6, brightness=0.55, reflection=0.6,
                                               name=f'interior_{k}') for k, p in rooms.items()}
    frame_m = bpy.data.materials.new('window_frame')
    frame_m.use_nodes = True
    frame_m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.05, 0.055, 1)
    frame_m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.4
    for row, z in enumerate((1.3, 3.3)):
        for col, x in enumerate((-2.2, 0.0, 2.2)):
            plane(f'window_{row}_{col}', (1.2, 1.4), loc=(x, -0.012, z), rot=(math.pi / 2, 0, 0),
                  mat=mats['study' if (row + col) % 2 == 0 else 'store'])
            for (fx, fz, sx, sz) in ((x, z + 0.73, 1.34, 0.06), (x, z - 0.73, 1.34, 0.08), (x - 0.63, z, 0.06, 1.52),
                                     (x + 0.63, z, 0.06, 1.52), (x, z, 0.04, 1.4)):
                bpy.ops.mesh.primitive_cube_add(size=1, location=(fx, -0.03, fz))
                fr = bpy.context.object
                fr.scale = (sx, 0.05, sz)
                fr.data.materials.append(frame_m)
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy, sun.angle, sun.color = 3.2, math.radians(1.5), (1.0, 0.93, 0.84)
    so = bpy.data.objects.new('sun', sun)
    so.rotation_euler = (math.radians(55), 0, math.radians(-35))
    sc.collection.objects.link(so)
    world((0.35, 0.45, 0.65), 0.55)
    cam = camera((-3.6, -6.5, 1.7), (0.4, 0, 2.3), 32)
    render(sc, 'windows_a.png')
    cam.location = (3.4, -4.2, 2.2)
    cam.rotation_euler = (Vector((-0.6, 0, 2.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    render(sc, 'windows_b.png')


# ---------------------------------------------------------------------------------------------------- recipes ---
def local(name):
    return assets.import_model(os.path.join(LOCAL, name + '.glb'), name=name)


def test_recipes():
    """placement.md's composition recipes, run as written on the local catalogue's own models: the desk on the
    floor, the chair behind it, the laptop centred on it, the mug right of the laptop and snapped down; rubble
    scattered and settled; a bench in a clear spot near the campfire, seated there; the barrel kit's islands."""
    from eidoblend.placement import (place_on, place_against, snap_to_ground, scatter_on, find_clear_spot,
                                     check_hovering, check_clipping, load_kit as placement_kit)
    sc = fresh()
    floor, wall = room_set()
    floor.scale = (2.4, 2.4, 1)
    wall.location.y = 2.4
    wall.scale = (2.4, 1.6, 1)
    bpy.context.view_layer.update()
    desk, chair, laptop, mug = local('corner_desk'), local('corner_chair'), local('corner_laptop'), local('corner_mug')
    desk.location = (-1.2, 1.2, 0)
    ok = [place_on(desk, floor)]
    place_against(chair, desk, 'behind', 0.25)                     # as the recipe has it (+Y, 25 cm of clearance)
    ok.append(place_on(chair, floor))
    ok.append(place_on(laptop, desk, xy='centered'))
    place_against(mug, laptop, 'right', 0.08)
    ok.append(snap_to_ground(mug, [desk]))
    rubble = [local('apocalyptic_destroyed_rubble_debris_concrete_rebar_chunk')]
    rubble[0].scale = (0.35,) * 3                                  # a 0.7 m piece of the slab, not the 1.9 m one
    bpy.context.view_layer.update()
    lo, hi = assets.bounds(rubble[0])
    span = max(hi.x - lo.x, hi.y - lo.y)
    for i in range(3):
        rubble.append(assets.clone_model(rubble[0], name=f'rubble_{i}'))
    gravel = assets.load_pbr('Gravel041', res='1k', maps=('diff', 'normal', 'rough'), repeat=(1, 1))
    clearing = plane('clearing', (2.6, 2.2), loc=(2.3, 1.3, 0.003), mat=gravel, uv_scale=1.2)   # a gravel patch
    bpy.context.view_layer.update()
    scatter_on(rubble, clearing, min_spacing=span * 1.05, rng_seed=7, sink=(0.15, 0.35), tilt_max=0.3)
    print(f'rubble chunk {span:.2f} m across', flush=True)
    fire = local('corner_camp_fire')
    fire.location = (0.4, -0.6, 0)
    ok.append(place_on(fire, floor))
    bench = local('corner_camp_bench')
    spot = find_clear_spot(bench, fire.location, radius=1.6)
    ok.append(spot is not None and place_on(bench, floor, xy=(spot.x, spot.y)))
    check('recipes: every helper call found its surface (desk, chair, laptop, mug, fire, bench)', all(ok), f'{ok}')
    lap_lo, lap_hi = assets.bounds(laptop)
    desk_lo, desk_hi = assets.bounds(desk)
    mug_lo, _m = assets.bounds(mug)
    check('recipes: the laptop and mug rest on the desk top', abs(lap_lo.z - desk_hi.z) < 0.03
          and abs(mug_lo.z - desk_hi.z) < 0.03, f'desk top {desk_hi.z:.3f}, laptop {lap_lo.z:.3f}, mug {mug_lo.z:.3f}')
    kit = placement_kit(os.path.join(LOCAL, 'scifi_barrels_group_of_four.glb'))
    isl = kit.islands()
    check('recipes: the barrel group kit splits into its islands (placement.load_kit)', len(isl) >= 1,
          f'{kit.count} parts, {len(isl)} island(s)')
    for k, e in enumerate(isl[:4]):
        e.location = (-2.1 + 0.75 * k, -1.6, 0.0)
        place_on(e, floor, xy=(-2.1 + 0.75 * k, -1.6))
    rep = [r for r in check_hovering(sc) if r['kind'] != 'near' or r['gap'] >= 0.05]
    deep = [p for p in check_clipping(sc) if p.get('deep')]
    check('recipes: nothing hovers, nothing deep inside another', not rep and not deep,
          f"hover {[(r['obj'].name, round(r['gap'], 3)) for r in rep]}; deep {[(p['ar'].name, p['br'].name) for p in deep]}")
    area('key', (-2.0, -2.2, 2.8), (0, 0.6, 0.6), 420, 1.0, (1.0, 0.93, 0.85))
    area('fill', (2.6, -2.0, 1.6), (0, 0.6, 0.6), 80, 2.5, (0.82, 0.9, 1.0))
    world((0.04, 0.045, 0.05), 1.0)
    camera((0.2, -5.4, 2.3), (0.0, 0.6, 0.55), 24)
    render(sc, 'recipes.png')


# ------------------------------------------------------------------------------------------------------ shelf ---
SHELF_ITEMS = ((('small_oil_can_01', '2k'), ('retro_multimeter', '2k'), ('CheeseBox_01', '1k')),
               (('vintage_hand_drill', '1k'), ('brass_blowtorch', '1k'), ('Camera_01', '1k')),
               (('pot_enamel_01', '1k'), ('old_gas_mask', '1k'), ('magnifying_glass_01', '2k')))


def boards(shelf, xs=(0.5,), step=0.004):
    """The heights of a shelf unit's boards: cast straight down through its footprint (at fractions xs of its
    width, along its middle) and keep the surfaces every cast meets, top first. The engine's guide says to read
    them from the preview; a cast reads them exactly."""
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = assets.bounds(shelf)
    per = []
    for fx in xs:
        x, y, z, hits = lo.x + fx * (hi.x - lo.x), (lo.y + hi.y) / 2, hi.z + 0.1, []
        for _ in range(16):
            ok, loc, _n, _i, _o, _m = sc.ray_cast(dg, Vector((x, y, z)), Vector((0, 0, -1)))
            if not ok:
                break
            hits.append(round(loc.z, 3))
            z = loc.z - step
        per.append(hits)
    common = [h for h in per[0] if all(any(abs(h - g) < 0.01 for g in other) for other in per[1:])]
    return common


def test_shelf():
    from eidoblend.placement import (place_on, place_inside, snap_to_ground, check_hovering, check_clipping,
                                     clear_cache)
    from eidoblend.placement import _world as W
    sc = fresh()
    floor, wall = room_set('Concrete034', 'PaintedPlaster017', size=8.0, wall_y=0.62)
    rack = assets.import_model(assets.fetch_model_file('worn_metal_rack', res='1k'), name='rack')
    place_on(rack, floor, xy=(0.0, 0.3))
    levels = boards(rack, xs=(0.2, 0.5, 0.8))
    inner = sorted(z for z in levels if z < max(levels) - 0.05 and z > 0.2)
    check('shelf: the rack\'s boards found by casting down through it (the outer top, then three boards)',
          len(inner) == 3, f'surfaces {levels}; boards {inner}')
    placed, missed = [], []
    lo, hi = assets.bounds(rack)
    width = hi.x - lo.x
    for k, (row, z) in enumerate(zip(SHELF_ITEMS, inner)):
        for j, (pid, res) in enumerate(row):
            item = assets.import_model(assets.fetch_model_file(pid, res=res), name=pid)
            dx = (j - 1) * width * 0.3
            if j == 1 and k == 1:                                  # the guide's other way: position, then snap below
                item.location = (rack.location.x + dx, rack.location.y, z + 0.12)
                bpy.context.view_layer.update()
                ok = snap_to_ground(item, rack, below=True)
            else:
                ok = place_inside(item, rack, aim_z=z + 0.08, xy_offset=(dx, -0.02))
            (placed if ok else missed).append(item)
    bpy.context.view_layer.update()
    clear_cache()
    on_boards = []
    for item in placed:
        b = W.tight_box(item)
        on_boards.append(min(abs(b[0].z - z) for z in inner))
    check('shelf: nine workshop props put on the boards (place_inside x8, snap_to_ground(below=True) x1), each '
          'within 3 mm of a board', not missed and len(placed) == 9 and max(on_boards) < 0.003,
          f"missed {[m.name for m in missed]}; worst {max(on_boards) * 1000 if on_boards else -1:.1f} mm")
    rep = check_hovering(sc)
    deep = [p for p in check_clipping(sc) if p.get('deep')]
    check('shelf: nothing hovers, nothing deep inside another', not rep and not deep,
          f"hover {[(r['obj'].name, round(r['gap'], 3)) for r in rep]}; deep {len(deep)}")
    area('key', (-1.3, -1.9, 2.3), (0, 0.3, 0.9), 300, 0.8, (1.0, 0.92, 0.82))
    area('fill', (1.6, -1.5, 1.2), (0, 0.3, 0.9), 60, 2.0, (0.82, 0.9, 1.0))
    world((0.03, 0.035, 0.04), 1.0)
    camera((0.55, -2.35, 1.05), (0.0, 0.3, 0.95), 30)
    render(sc, 'shelf.png')


# ----------------------------------------------------------------------------------------------------- stairs ---
def test_stairs():
    from eidoblend.characters import load_vrm, play_vrma_default
    from eidoblend.placement import snap_to_ground, check_hovering, clear_cache
    from eidoblend.placement import _world as W
    sc = fresh()
    sc.render.fps = 24
    floor, wall = room_set('Concrete034', 'PaintedPlaster015', size=8.0, wall_y=0.2)
    stone = pbr('Concrete047A')
    stair1 = box('stair1', (1.0, -2.0, 0.0), (3.0, -1.7, 0.17), stone)
    stair2 = box('stair2', (1.0, -1.7, 0.0), (3.0, -1.4, 0.34), stone)
    landing = box('landing', (1.0, -1.4, 0.0), (3.0, 0.2, 0.51), stone)
    me = load_vrm('claude', name='character', rotation=0.0)
    play_vrma_default(me, 'still_breathe')
    sc.frame_set(12)
    character = me.arm
    character.location = (2, -1, 5)                                # approximate spot (the recipe, as written)
    bpy.context.view_layer.update()
    ok = snap_to_ground(character, [stair1, stair2, landing])
    bpy.context.view_layer.update()
    clear_cache()
    feet = W.tight_box(character)[0].z
    check('stairs: snap_to_ground drops the character from 5 m onto the landing (0.51 m)',
          ok and abs(feet - 0.51) < 0.02, f'lowest point {feet:.3f} m')
    rep = [r for r in check_hovering(sc) if r['obj'] == character]
    check('stairs: the hovering audit leaves her standing', not rep, f'{rep}')
    area('key', (-0.6, -3.6, 2.8), (2.0, -1.0, 1.0), 380, 1.0, (1.0, 0.93, 0.85))
    area('fill', (3.9, -3.2, 1.4), (2.0, -1.0, 1.0), 90, 2.0, (0.82, 0.9, 1.0))
    world((0.04, 0.045, 0.05), 1.0)
    camera((-0.4, -4.6, 1.55), (2.0, -1.0, 1.1), 35)
    render(sc, 'stairs.png')


# ------------------------------------------------------------------------------------------------------- seat ---
def test_seat():
    """scene_placement.js's seating on claude.vrm and the local corner chair: one sat with seat_on, one lowering into
    a second chair with seat_on(transition='stand_to_sit') (a still mid-descent and one after it), one on the floor
    with sit_on_ground, one cheering (emote) turned to the camera (face_camera)."""
    from eidoblend.characters import load_vrm
    from eidoblend.placement import place_on, seat_on, sit_on_ground, emote, face_camera, check_hovering
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 96
    floor, wall = room_set('WoodFloor064', 'PaintedPlaster015', size=8.0, wall_y=1.1)
    camera((0.35, -4.3, 1.25), (0.35, 0.0, 0.62), 35)              # before face_camera, which turns toward it
    chair = local('corner_chair')
    place_on(chair, floor, xy=(-0.55, 0.25))
    chair2 = local('corner_chair')
    chair2.rotation_euler.z = math.radians(-25)
    place_on(chair2, floor, xy=(0.75, 0.3))
    sitter = load_vrm('claude', name='sitter')
    seat_on(sitter, chair)
    lowerer = load_vrm('claude', name='lowerer', location=(0.75, -0.6, 0.0))
    seat_on(lowerer, chair2, transition='stand_to_sit', t=1.0, then='sitting_normal_chair')
    floor_sitter = load_vrm('claude', name='floor_sitter')
    sit_on_ground(floor_sitter, at=(-1.75, -0.35), ground=[floor])
    stander = load_vrm('claude', name='stander', location=(1.85, -0.2, 0.0))
    face_camera(stander, offset=-0.35)
    emote(stander, 'cheer')
    rep = check_hovering(sc)
    seated = {o.name for o in sc.objects if o.get('eido_seated')}
    check('seat: three seated (marked), and the hovering audit names none of them', seated >= {'sitter', 'lowerer',
          'floor_sitter'} and not [r for r in rep if r['obj'].name in seated], f'{sorted(seated)}; hover {rep}')
    area('key', (-1.6, -2.2, 2.6), (0.2, 0.2, 0.6), 520, 1.2, (1.0, 0.92, 0.82))
    area('fill', (2.4, -2.0, 1.4), (0.2, 0.2, 0.6), 110, 2.5, (0.82, 0.9, 1.0))
    world((0.05, 0.055, 0.06), 1.0)
    for tag, f in (('mid', 49), ('end', 90)):
        sc.frame_set(f)
        render(sc, f'seat_{tag}.png')


# ------------------------------------------------------------------------------------------------------ clips ---
CROW = 'crow_bird_animated_corvid_raven_black_cawing_flying_walking'


def test_clips():
    from eidoblend.placement import place_on
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 48
    floor = plane('ground', (8, 8), mat=pbr('Ground037'), uv_scale=0.6)
    a = local(CROW)
    clips = sorted(assets.model_clips(a))
    weights = {c: 0.0 for c in clips}
    weights.update({'Walk': 1.0, 'Caw': 0.7})
    played = assets.play_model_animations(a, clip='all', weights=weights)
    b = assets.clone_model(a, name='crow_pecks', independent_actions=True)
    pb = assets.play_model_animations(b, clip='Peck', offset=0.3)
    c = assets.clone_model(a, name='crow_idles')
    pc = assets.play_model_animations(c, clip='Idle')
    for ob, xy, yaw in ((a, (-0.55, 0.05), 90), (b, (0.1, 0.25), 60), (c, (0.7, -0.05), 120)):
        ob.rotation_euler.z = math.radians(yaw)
        sc.frame_set(1)
        place_on(ob, floor, xy=xy)
    def strips(root):
        return {s.action.name for o in assets.subtree(root) if o.animation_data
                for t in o.animation_data.nla_tracks if not t.mute for s in t.strips if s.action}
    sa, sb = strips(a), strips(b)
    check('clips: one crow plays Walk 1 + Caw 0.7 layered (baked), a clone with its own actions pecks, a clone '
          'sharing them idles', played == ['Caw', 'Walk'] and pb == ['Peck'] and pc == ['Idle'] and not (sa & sb),
          f'{played} {pb} {pc}; walker strips {sorted(sa)}, pecker strips {sorted(sb)}')
    area('key', (-1.2, -1.6, 1.4), (0, 0, 0.15), 160, 0.8, (1.0, 0.93, 0.84))
    area('fill', (1.4, -1.2, 0.8), (0, 0, 0.15), 35, 1.5, (0.82, 0.9, 1.0))
    world((0.30, 0.36, 0.42), 0.6)
    camera((0.05, -2.3, 0.55), (0.05, 0.05, 0.18), 50)
    for f in (6, 12, 18, 24):
        sc.frame_set(f)
        render(sc, f'clips_f{f:03d}.png')


# -------------------------------------------------------------------------------------------------------- rig ---
def test_rig():
    from eidoblend.harness import render_common as RC
    from eidoblend.placement import place_on
    sc = fresh()
    ground = plane('ground', (6, 6), mat=pbr('WoodFloor064'), uv_scale=0.6)
    stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='stool')
    clock = assets.import_model(assets.fetch_model_file('alarm_clock_01', res='2k'), name='clock')
    place_on(stool, ground, xy=(0.0, 0.0))
    place_on(clock, stool, xy=(0.0, 0.0))
    res = RC.setup_scene({'background': '#20242a', 'camera': {'fov': 40, 'position': [0.0, 0.85, 1.55],
                                                               'target': [0.0, 0.3, 0.0]}}, sc)
    kinds = sorted(l.data.type for l in res['lights'])
    check('rig: setup_scene\'s default rig (a sun key, two points, the ambient as world light) and its camera',
          kinds == ['POINT', 'POINT', 'SUN'] and sc.camera == res['camera'], f'{kinds}')
    render(sc, 'rig.png')


if __name__ == '__main__':
    for key, fn in (('hover', test_hover), ('kit', test_kit), ('windows', test_windows), ('recipes', test_recipes),
                    ('shelf', test_shelf), ('stairs', test_stairs), ('seat', test_seat), ('clips', test_clips),
                    ('rig', test_rig)):
        if ONLY and key not in ONLY:
            continue
        try:
            fn()
        except Exception as e:                                      # noqa: BLE001
            traceback.print_exc()
            check(f'{key} (crashed)', False, f'{type(e).__name__}: {e}')
    n = sum(1 for _, ok in results if ok)
    print(f'\n{n}/{len(results)} checks passed', flush=True)
    sys.stdout.flush()
    os._exit(0 if n == len(results) else 1)
