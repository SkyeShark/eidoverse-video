# build_tandem.py - DAISY hero prop: the 1890s safety tandem, built headless in Blender 5.2.
#
#   blender --background --factory-startup --python work/daisy/props/blender/build_tandem.py -- [--stage geo|full] [--looks]
#
# Stages: geo  = model + hierarchy + look renders with placeholder shaders (fast form check)
#         full = geo + layered source materials + Cycles bake to atlases + GLB export + look renders of the baked asset
import sys, os, math, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector, Matrix
import tgeo, tparts
from tgeo import B, V

REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
PROPS = os.path.abspath(os.path.join(HERE, '..'))
OUT_GLB = os.path.join(PROPS, 'tandem.glb')
LOOKS = os.path.join(PROPS, 'probes', 'looks')
BAKE = os.path.join(HERE, 'tandem_bake')
HDRI = os.path.join(REPO, 'work', 'launch', 'assets', 'hdri.hdr')

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STAGE = 'geo'
LOOK_SET = 'all'
for i, a in enumerate(argv):
    if a == '--stage':
        STAGE = argv[i + 1]
    if a == '--looks':
        LOOK_SET = argv[i + 1]
T0 = time.time()


LOGF = os.path.join(HERE, 'tandem_build.log')


def log(*a):
    msg = '[tandem %6.1fs] ' % (time.time() - T0) + ' '.join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOGF, 'a', encoding='utf-8') as f:
        f.write(time.strftime('%H:%M:%S ') + msg + chr(10))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


def empty(coll, name, pos, parent=None, parent_pos=None):
    ob = bpy.data.objects.new(name, None)
    coll.objects.link(ob)
    ob.empty_display_type = 'PLAIN_AXES'
    ob.empty_display_size = 0.03
    rel = pos - (parent_pos if parent_pos is not None else V(0, 0, 0))
    ob.location = B(rel)
    ob.parent = parent
    return ob


def build(sc):
    coll = bpy.data.collections.new('tandem')
    sc.collection.children.link(coll)
    tgeo.set_coll(coll)
    L = tparts.layout()
    kit = tparts.Kit(coll)
    rT = tparts.ringR(L['pitch'], L['timingTeeth'])
    rD = tparts.ringR(L['pitch'], L['driveTeeth'])
    rS = tparts.ringR(L['pitch'], L['sprocketTeeth'])
    timing = tparts.belt(L['rearBB'], rT, L['frontBB'], rT, L['pitch'], L['timingTeeth'], L['timingTeeth'])
    drive = tparts.belt(L['rearHub'], rS, L['rearBB'], rD, L['pitch'], L['sprocketTeeth'], L['driveTeeth'])

    def local(fn, *a, **k):
        n0 = len(kit.objs)
        r = fn(*a, **k)
        for ob in kit.objs[n0:]:
            ob['local'] = 1
        return r

    log('frame'); tparts.build_frame(kit, L)
    log('steering'); st = tparts.build_steering(kit, L)
    log('hardware'); tparts.build_frame_hardware(kit, L)
    log('saddles')
    sitF, sitR = V(*L['frontSit']), V(*L['rearSit'])
    sf = tparts.build_saddle(kit, L, 'saddle_front', sitF)
    sr = tparts.build_saddle(kit, L, 'saddle_rear', sitR)
    tparts.build_seat_pin(kit, L, 'seat_pin_front', L['frontBB'], sf['clip'], L['fscY'])
    tparts.build_seat_pin(kit, L, 'seat_pin_rear', L['rearBB'], sr['clip'], L['RSC'][1])
    log('stoker bars'); sg = tparts.build_stoker_bar(kit, L)
    log('wheels')
    local(tparts.build_wheel, kit, L, 'wheel_front', L['frontSpokes'], False, 'wheel_front')
    local(tparts.build_wheel, kit, L, 'wheel_rear', L['rearSpokes'], True, 'wheel_rear', sprocket_rot=drive['rotA'])
    log('cranks')
    local(tparts.build_crankset, kit, L, 'crank_front', 'crank_front',
          [{'teeth': L['timingTeeth'], 'petals': 8, 'z': L['zTiming'], 'rot': timing['rotB'], 'rIn': 0.024}])
    local(tparts.build_crankset, kit, L, 'crank_rear', 'crank_rear',
          [{'teeth': L['timingTeeth'], 'petals': 8, 'z': L['zTiming'], 'rot': timing['rotA'], 'rIn': 0.024},
           {'teeth': L['driveTeeth'], 'petals': 10, 'z': L['zDrive'], 'rot': drive['rotB'], 'rIn': 0.027}])
    log('pedals')
    for piv, side in (('pedal_front_R', 1), ('pedal_front_L', -1), ('pedal_rear_R', 1), ('pedal_rear_L', -1)):
        local(tparts.build_pedal, kit, piv, piv, side)
    log('chain link'); local(tparts.build_chain_link, kit, L)

    # ── pivots (identity rotations; three.js spins them about their local axes) ──
    Q = V(*L['Q']); FH = V(*L['frontHub']); RH = V(*L['rearHub']); FB = V(*L['frontBB']); RB = V(*L['rearBB'])
    zp = L['zCrank'] + L['pedalOut']
    root = empty(coll, 'tandem', V(0, 0, 0))
    piv = {'frame': (root, V(0, 0, 0))}
    steer = empty(coll, 'steer', Q, root); piv['steer'] = (steer, Q)
    piv['wheel_front'] = (empty(coll, 'wheel_front', FH, steer, Q), FH)
    piv['wheel_rear'] = (empty(coll, 'wheel_rear', RH, root), RH)
    for nm, bb in (('crank_front', FB), ('crank_rear', RB)):
        cp = empty(coll, nm, bb, root)
        piv[nm] = (cp, bb)
        side = nm.split('_')[1]
        pR, pL = bb + V(0, L['crank'], zp), bb + V(0, -L['crank'], -zp)
        piv['pedal_%s_R' % side] = (empty(coll, 'pedal_%s_R' % side, pR, cp, bb), pR)
        piv['pedal_%s_L' % side] = (empty(coll, 'pedal_%s_L' % side, pL, cp, bb), pL)
    piv['chain'] = (root, V(0, 0, 0))
    empty(coll, 'seat_front', sitF, root)
    empty(coll, 'seat_rear', sitR, root)
    for side in ('L', 'R'):
        g = st['grips'][side]
        empty(coll, 'grip_front_' + side, g['center'], steer, Q)
        g2 = sg[side]
        empty(coll, 'grip_rear_' + side, g2['center'], root)
    for ob in kit.objs:
        p_ob, p_pos = piv[ob['pivot']]
        if not ob.get('local'):
            ob.data.transform(Matrix.Translation(-B(p_pos)))
        ob.parent = p_ob
        ob.location = (0, 0, 0)
    # layout + belts travel with the asset (glTF extras -> three.js userData)
    extras = {
        'layout': {k: (list(v) if isinstance(v, (tuple, list)) else v) for k, v in L.items() if isinstance(v, (int, float, tuple, list))},
        'belts': {'timing': timing, 'drive': drive, 'zTiming': L['zTiming'], 'zDrive': L['zDrive']},
        'grips': {k: {'center': list(v['center']), 'axis': list(v['axis'])} for k, v in
                  [('front_' + s, st['grips'][s]) for s in ('L', 'R')] + [('rear_' + s, sg[s]) for s in ('L', 'R')]},
        'version': 1,
    }
    root['daisy_tandem'] = json.dumps(extras)
    log('objects:', len(kit.objs), 'tris:', sum(len(o.data.polygons) for o in kit.objs))
    return kit, root, L, extras


# ───────────────────────────── placeholder shading ─────────────────────────────
PLACEHOLDER = {
    'enamel': ((0.075, 0.009, 0.012), 0.0, 0.3), 'nickel': ((0.62, 0.58, 0.50), 1.0, 0.15), 'japanned': ((0.02, 0.02, 0.02), 0.0, 0.25),
    'copper': ((0.75, 0.40, 0.25), 1.0, 0.3), 'leather': ((0.20, 0.08, 0.03), 0.0, 0.55), 'gum': ((0.40, 0.35, 0.27), 0.0, 0.8),
    'wood': ((0.45, 0.23, 0.08), 0.0, 0.35), 'cork': ((0.45, 0.28, 0.13), 0.0, 0.85), 'vulcanite': ((0.02, 0.018, 0.016), 0.0, 0.4),
    'chainsteel': ((0.10, 0.09, 0.08), 0.8, 0.45), 'spoke': ((0.62, 0.58, 0.50), 1.0, 0.2),
}


def placeholder_mats(kit):
    mats = {}
    for ob in kit.objs:
        k = ob['smat']
        if k not in mats:
            m = bpy.data.materials.new('ph_' + k)
            bsdf = m.node_tree.nodes['Principled BSDF']
            c, met, rough = PLACEHOLDER[k]
            bsdf.inputs['Base Color'].default_value = (*c, 1)
            bsdf.inputs['Metallic'].default_value = met
            bsdf.inputs['Roughness'].default_value = rough
            if k == 'enamel':
                bsdf.inputs['Coat Weight'].default_value = 1.0
                bsdf.inputs['Coat Roughness'].default_value = 0.1
            mats[k] = m
        ob.data.materials.clear()
        ob.data.materials.append(mats[k])


# ───────────────────────────── look renders ────────────────────────────────────
def setup_look(sc, samples=96):
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type in ('OPTIX',)
    sc.cycles.device = 'GPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new('look_world')
    sc.world = w
    nt = w.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDRI)
    mapn = nt.nodes.new('ShaderNodeMapping')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], mapn.inputs['Vector'])
    mapn.inputs['Rotation'].default_value = (0, 0, math.radians(200))
    nt.links.new(mapn.outputs['Vector'], env.inputs['Vector'])
    bg = nt.nodes['Background']
    bg.inputs['Strength'].default_value = 0.9
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    # low warm sun, from behind-left of the side camera
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy = 3.2
    sun.color = (1.0, 0.78, 0.55)
    sun.angle = math.radians(1.2)
    so = bpy.data.objects.new('sun', sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(72), 0, math.radians(-40))
    # ground: warm sand, receives shadow
    me = bpy.data.meshes.new('ground')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6.0)
    bm.to_mesh(me); bm.free()
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    b = gm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.33, 0.24, 0.16, 1)
    b.inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    cam = bpy.data.cameras.new('cam')
    cam.lens = 50
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    sc.camera = co
    return co


def aim(co, eye_bike, target_bike, lens=50):
    if lens < 0:                      # negative lens = orthographic with that ortho scale
        co.data.type = 'ORTHO'
        co.data.ortho_scale = -lens
    else:
        co.data.type = 'PERSP'
        co.data.lens = lens
    eye, tgt = B(eye_bike), B(target_bike)
    co.location = eye
    d = (tgt - eye).normalized()
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


LOOK_VIEWS = {
    'side_R': (V(0.02, 0.62, 4.1), V(0.02, 0.52, 0), 40),
    'side_L': (V(0.02, 0.62, -4.1), V(0.02, 0.52, 0), 40),
    'q34_front': (V(2.5, 1.05, 2.4), V(0.05, 0.50, 0), 40),
    'q34_rear': (V(-2.6, 1.0, 2.2), V(-0.1, 0.5, 0), 40),
    'top': (V(0.0, 3.6, 0.35), V(0.0, 0.5, 0), 38),
    'close_crank': (V(0.05, 0.42, 0.95), V(-0.05, 0.33, 0.02), 45),
    'close_head': (V(0.95, 0.95, 0.75), V(0.65, 0.72, 0.0), 50),
    'close_saddle': (V(0.30, 1.05, 0.62), V(0.05, 0.76, 0), 50),
    'close_rear': (V(-0.55, 0.55, 0.85), V(-0.75, 0.40, 0.03), 45),
    'close_lug': (V(0.80, 0.80, 0.30), V(0.64, 0.72, 0.0), 60),
    'close_bb': (V(-0.28, 0.40, 0.42), V(-0.41, 0.30, 0.0), 55),
    'close_tyre': (V(1.25, 0.20, 0.45), V(0.95, 0.12, 0.0), 60),
    'ortho_drive': (V(-0.07, 0.30, 3.0), V(-0.07, 0.30, 0.0), -1.35),
    'ortho_side': (V(0.0, 0.55, 5.0), V(0.0, 0.55, 0.0), -2.7),
}


def render_looks(co, tag, which='all'):
    os.makedirs(LOOKS, exist_ok=True)
    outs = []
    for name, (eye, tgt, lens) in LOOK_VIEWS.items():
        if which != 'all' and name not in which.split(','):
            continue
        aim(co, eye, tgt, lens)
        path = os.path.join(LOOKS, '%s_%s.png' % (tag, name))
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        outs.append(path)
        log('look', path)
    return outs


# ─────────────────────── look-only chain (three.js instances it on the GPU) ───────────────
def belt_point(b, s):
    A, rA, Bc, rB = b['A'], b['rA'], b['B'], b['rB']
    dx, dy = Bc[0] - A[0], Bc[1] - A[1]
    D = math.hypot(dx, dy)
    u = (dx / D, dy / D); n = (-u[1], u[0])
    phi = math.asin((rA - rB) / D)
    Ls = D * math.cos(phi)
    arcB = rB * (math.pi - 2 * phi)
    angUp = math.pi / 2 - phi; angLow = -angUp
    Lt = b['L']
    s = s % Lt
    d = lambda a: (u[0] * math.cos(a) + n[0] * math.sin(a), u[1] * math.cos(a) + n[1] * math.sin(a))
    mUp, mLow = d(angUp), d(angLow)
    TAup = (A[0] + rA * mUp[0], A[1] + rA * mUp[1]); TBup = (Bc[0] + rB * mUp[0], Bc[1] + rB * mUp[1])
    TBlow = (Bc[0] + rB * mLow[0], Bc[1] + rB * mLow[1]); TAlow = (A[0] + rA * mLow[0], A[1] + rA * mLow[1])
    if s < Ls:
        k = s / Ls; return (TAup[0] + (TBup[0] - TAup[0]) * k, TAup[1] + (TBup[1] - TAup[1]) * k)
    if s < Ls + arcB:
        a = angUp - (s - Ls) / rB; e = d(a); return (Bc[0] + rB * e[0], Bc[1] + rB * e[1])
    if s < 2 * Ls + arcB:
        k = (s - Ls - arcB) / Ls; return (TBlow[0] + (TAlow[0] - TBlow[0]) * k, TBlow[1] + (TAlow[1] - TBlow[1]) * k)
    a = angLow - (s - 2 * Ls - arcB) / rA; e = d(a); return (A[0] + rA * e[0], A[1] + rA * e[1])


def look_chains(sc, kit, extras, crank=0.0, link=None):
    link = link or [o for o in kit.objs if o['mgroup'] == 'chain'][0]
    coll = bpy.data.collections.new('look_only')
    sc.collection.children.link(coll)
    for key, z in (('timing', extras['belts']['zTiming']), ('drive', extras['belts']['zDrive'])):
        b = extras['belts'][key]
        phase = b['sOff'] + crank * b['teethB'] * b['pp'] / (2 * math.pi)
        for j in range(b['N']):
            s0 = j * b['pp'] + phase
            p0 = belt_point(b, s0); p1 = belt_point(b, s0 + b['pp'])
            th = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
            ob = bpy.data.objects.new('lk_%s_%d' % (key, j), link.data)
            coll.objects.link(ob)
            ob.location = B(V(p0[0], p0[1], z))
            ob.rotation_euler = (0, -th, 0)
    return coll


# ─────────────────────────────────────────────────────────────────────────────
def main():
    sc = reset()
    kit, root, L, extras = build(sc)
    if STAGE == 'geo':
        placeholder_mats(kit)
        look_chains(sc, kit, extras)
        for o in kit.objs:
            if o['mgroup'] == 'chain':
                o.hide_render = True
        co = setup_look(sc, samples=48)
        render_looks(co, 'tandem_geo', LOOK_SET)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'tandem_geo.blend'))
        log('done (geo)')
        return
    import tmats
    joined = tmats.run_full(kit, root, L, extras, sc, BAKE, OUT_GLB, log)
    link = bpy.data.objects.get('tandem__chain')
    look_chains(sc, kit, extras, link=link)
    link.hide_render = True
    co = setup_look(sc, samples=128)
    render_looks(co, 'tandem_baked', LOOK_SET)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'tandem_full.blend'))
    log('done (full)')


main()
