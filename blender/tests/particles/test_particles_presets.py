"""make_particles (eidoverse/particles.js) in full: every preset rendered with its sprite, the module header's example,
the light-motes recipe, the keyable uniforms, every option, the motion against the engine's closed form, and the
display match for additive sprites.

  presets     sparks, embers, smoke, dust, snow, magic, stars, muzzle, fire, each on its library sprite (stills
              out/particles_preset_<name>_f048.png)
  header      particles.js's own example: sparks with a spark sprite at origin [0, 1, 0]
  motes       techniques_archive: the 'snow' preset + glow_soft + a warm colour = daylight-visible drifting light motes
              (additive light vanishes against a bright sky; normal blending survives)
  uniforms    size, opacity, color, origin keyed: an opacity burst ("pulse uniforms.opacity.value for a burst") and a
              moving emitter, checked at frames, and rendered across the burst
  options     area (x, y, z), position (the engine's alias), gravity in Blender axes, camera (a fixed basis), lit,
              intensity, time_offset, seed, an unknown preset and an invalid area (both fall back, warned)
  parity      the particle centres the graph makes against particles.js's positionNode in numpy (three's axes), and
              each quad facing the camera
  display     create_particles_compose: the additive sprites' light shown as three's ACESFilmic showed it, under AgX
              (stills with the match off and on)

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/particles/test_particles_presets.py \
        [-- parts=presets,header,motes,uniforms,options,parity,display] [no-render]"""

import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.fx import particles as PA  # noqa: E402
from eidoblend.fx._util import from_three, to_three  # noqa: E402

RENDER = 'no-render' not in S.argv()
PARTS = S.arg('parts', 'presets,header,motes,uniforms,options,parity,display').split(',')
RES = tuple(int(x) for x in S.arg('res', '960x540').split('x'))
SPRITES = {'sparks': 'spark_05', 'embers': 'spark_01', 'smoke': 'smoke_04', 'dust': 'dirt_01', 'snow': 'circle_02',
           'magic': 'magic_02', 'stars': 'star_04', 'muzzle': 'muzzle_02', 'fire': 'flame_05'}


def fresh(end=96, world=(0.004, 0.005, 0.009), sky=None):
    sc = S.clean_scene(24, 1, end)
    S.probe_render(sc, RES, 16)
    S.world(sc, world, sky=sky)
    return sc


def still(name, frame):
    if RENDER:
        S.render_still(os.path.join(S.OUT, f'particles_{name}_f{frame:03d}.png'), frame)


def instances(ob, frame):
    """(centres (n, 3), rotations (n, 3, 3), scales (n,)) of the quads the graph instanced at frame."""
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    C, R, Sc = [], [], []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob:
            M = inst.matrix_world
            C.append(tuple(M.translation))
            R.append(np.array(M.to_3x3().normalized()))
            Sc.append(M.to_scale().x)
    return np.array(C), np.array(R), np.array(Sc)


def engine_centres(P, emit3, vel3, seed, t):
    """particles.js positionNode (centre, no corner), three's axes, float64."""
    tL = np.mod(t * (P.get('speed', 1) or 1) / P['lifetime'] + seed[:, 0], 1.0)
    age = tL * P['lifetime']
    g = np.asarray(P['gravity'], float)
    grav = g[None] * (0.5 * age * age)[:, None]
    a2 = t * 1.2 + seed[:, 0] * 6.2832
    wob = seed[:, 1]
    drift = np.stack([np.sin(a2) * wob, np.cos(a2 * 0.7) * wob * 0.4, np.cos(a2) * wob], 1)
    sw = float(P.get('swirl', 0) or 0)
    ang = age * sw
    swirl = np.stack([np.cos(ang) * sw * 0.15, np.zeros_like(ang), np.sin(ang) * sw * 0.15], 1)
    off = emit3 + vel3 * age[:, None] + grav + drift + swirl
    if P.get('flame') or P.get('converge'):
        conv = 1.0 - tL * float(P.get('converge') if P.get('converge') is not None else 0.85)
        off = np.stack([off[:, 0] * conv, off[:, 1], off[:, 2] * conv], 1)
    return off


def attrs(ob):
    me = ob.data
    out = {}
    for nm in ('iEmit', 'iVel', 'iSeed'):
        a = np.empty(len(me.vertices) * 3, np.float32)
        me.attributes[nm].data.foreach_get('vector', a)
        out[nm] = a.reshape(-1, 3).astype(np.float64)
    return out


# ------------------------------------------------------------------------------------------------------ parts ---

# each preset framed the way it is used: its emitter where its motion reads, a backdrop it shows against (glowing
# light on dark; grey smoke on a darker dusk; white snow on night), the camera at the distance its size was tuned for
NIGHT = (0.004, 0.005, 0.009)
STAGES = {
    #           origin           camera             aim               lens  world / sky                         floor
    'sparks': ((0, 0, 0.30), (0.0, -2.6, 0.75), (0, 0, 0.55), 35.0, dict(world=NIGHT), True),
    'embers': ((0, 0, 0.20), (0.0, -5.2, 1.35), (0, 0, 1.55), 35.0, dict(world=NIGHT), True),
    'smoke': ((0, 0, 0.20), (0.0, -9.5, 2.2), (0, 0, 3.0), 35.0,
              dict(sky=((0.020, 0.026, 0.040), (0.075, 0.068, 0.062))), True),
    'dust': ((0, 0, 1.40), (0.0, -3.6, 1.35), (0, 0, 1.40), 35.0, dict(world=(0.010, 0.009, 0.008)), True),
    'snow': ((0, 0, 9.00), (0.0, -6.0, 1.7), (0, 0, 2.2), 35.0,
             dict(sky=((0.004, 0.006, 0.014), (0.020, 0.026, 0.045))), True),
    'magic': ((0, 0, 0.30), (0.0, -3.4, 1.05), (0, 0, 1.15), 35.0, dict(world=NIGHT), True),
    'stars': ((0, 0, 1.50), (0.0, 0.0, 1.5), (0, 10.0, 5.5), 35.0, dict(world=(0.002, 0.003, 0.008)), False),
    'muzzle': ((0, 0, 1.00), (0.0, -1.9, 1.05), (0, 0, 1.0), 35.0, dict(world=NIGHT), False),
    'fire': ((0, 0, 0.05), (0.0, -1.9, 0.55), (0, 0, 0.36), 35.0, dict(world=NIGHT), False),   # no floor: see below
}


# (the fire's 0.5 m flame quads reach below their emitter: on a bare floor the floor cuts them along straight lines,
# as it did in the engine; scenes set the fire on logs, as the campfire test in tests/fx does)
def part_presets():
    for name in PA.PRESETS:
        origin, cam_at, aim, lens, w, has_floor = STAGES[name]
        sc = fresh(96, w.get('world', NIGHT), w.get('sky'))
        if has_floor:
            S.floor(30.0, (0.03, 0.03, 0.035), 0.6)
        if name in ('smoke', 'dust', 'snow'):
            S.sun('key', (-1.0, -2.0, 2.5), (1.0, 0.96, 0.9), 2.5)
        p = PA.make_particles(name, origin=origin, map='auto', seed=3)
        S.camera('cam', cam_at, aim, lens)
        C, _R, _Sc = instances(p.object, 48)
        S.check(f'preset {name}: {len(C)} sprites (the preset count {PA.PRESETS[name]["count"]}), on '
                f'{PA.SPRITES[name]}', len(C) == PA.PRESETS[name]['count'] and np.isfinite(C).all())
        still(f'preset_{name}', 48)


def part_header():
    """const tex = await loadImageTexture(ASSETS.spark); makeParticles({ scene, camera, preset: 'sparks', map: tex,
    origin: [0, 1, 0] })."""
    sc = fresh(48)
    S.floor(20.0, (0.03, 0.03, 0.035), 0.5)
    p = PA.make_particles('sparks', origin=tuple(from_three(np.array([0.0, 1.0, 0.0]))), map='spark_05')
    S.camera('cam', (0.0, -3.4, 1.4), (0.0, 0.0, 1.1), 35.0)
    S.check('header: sparks at three [0, 1, 0] = Blender (0, 0, 1)', np.allclose(tuple(p.object.location),
                                                                             (0, 0, 1)))
    still('header_sparks', 30)


def part_motes():
    sc = fresh(96, sky=((0.25, 0.42, 0.85), (0.75, 0.82, 0.95)))
    S.sun('sun', (-1.0, -1.5, 2.0), (1.0, 0.97, 0.9), 4.0)
    S.floor(40.0, (0.18, 0.2, 0.12), 0.8)
    PA.make_particles('snow', origin=(0, 0, 1.6), map='glow_soft', color=0xffd28a, size=0.06, count=260, seed=4,
                      name='motes')
    PA.make_particles('sparks', origin=(1.5, 0, 1.0), map='spark_05', seed=5, name='sparks_in_daylight')
    S.camera('cam', (0.0, -4.2, 1.25), (0.35, 0.0, 1.2), 35.0)
    still('motes_daylight', 48)


def part_uniforms():
    sc = fresh(96)
    S.floor(20.0, (0.03, 0.03, 0.035), 0.5)
    p = PA.make_particles('magic', origin=(-1.0, 0, 1.0), map='magic_05', seed=6)
    u = p.uniforms
    # an opacity burst: dark, a flash at 36, fading by 60
    for f, v in ((1, 0.0), (30, 0.0), (36, 1.0), (60, 0.15)):
        u.opacity.value = v
        u.opacity.key(f)
    # a moving emitter (origin) and a size swell and a colour shift
    u.origin.value = (-1.0, 0.0, 1.0)
    u.origin.key(1)
    u.origin.value = (1.0, 0.0, 1.4)
    u.origin.key(72)
    u.size.value = 0.08
    u.size.key(1)
    u.size.value = 0.14
    u.size.key(72)
    u.color.value = 0x9b5cff
    u.color.key(1)
    u.color.value = '#5cf0ff'
    u.color.key(72)
    sc.frame_set(36)
    S.check('uniforms: the opacity burst peaks at 36', abs(u.opacity.value - 1.0) < 1e-6)
    sc.frame_set(48)
    S.check('uniforms: halfway through the fade at 48', 0.4 < u.opacity.value < 0.75, f'{u.opacity.value:.3f}')
    S.check('uniforms: the emitter moves (origin = the object location, keyed)', abs(p.object.location.x) < 0.5)
    C1, _, s1 = instances(p.object, 1)
    C2, _, s2 = instances(p.object, 72)
    S.check('uniforms: the cloud follows the moving origin', C2[:, 0].mean() - C1[:, 0].mean() > 1.5,
            f'{C1[:, 0].mean():.2f} -> {C2[:, 0].mean():.2f}')
    S.check('uniforms: size swells (instance scale)', s2.mean() > 1.4 * s1.mean() * 0.9)
    S.camera('cam', (0.0, -4.0, 1.5), (0.0, 0.0, 1.6), 35.0)
    for f in (24, 36, 48, 72):
        still(f'uniforms_burst', f)


def part_options():
    sc = fresh(48)
    cam = S.camera('cam', (0.0, -5.0, 1.0), (0.0, 0.0, 1.0), 35.0)
    a = PA.make_particles('sparks', origin=(0, 0, 0), area=(2.0, 0.2, 0.0), seed=7, name='opt_area', up=0.0,
                          spread=0.0, gravity=(0, 0, 0))
    C, _, _ = instances(a.object, 1)
    S.check('area (x, y, z) in Blender axes: wide in X, thin in Y and Z',
            np.ptp(C[:, 0]) > 1.5 and np.ptp(C[:, 1]) < 0.45 and np.ptp(C[:, 2]) < 0.05,
            f'extents {np.ptp(C, 0).round(3)}')
    g = PA.make_particles('dust', position=(3.0, 0, 0), seed=8, name='opt_position', gravity=(1.0, 0, 0))
    S.check('position (the engine\'s alias of origin)', np.allclose(tuple(g.object.location), (3, 0, 0)))
    S.check('gravity override in Blender axes: +X', np.allclose(PA.from_three(g.params['gravity']), (1, 0, 0)))
    f1 = PA.make_particles('fire', origin=(0, 0, 0), seed=9, name='opt_fixed_cam', camera=cam)
    _, R, _ = instances(f1.object, 10)
    nrm = R[:, :, 2]
    view = np.array(cam.matrix_world.to_3x3())[:, 2]
    S.check('camera=: the quads face the given camera (fire spins in plane)', np.abs(nrm @ view).min() > 0.999)
    lit = PA.make_particles('smoke', origin=(0, 0, 0), seed=10, name='opt_lit', lit=True)
    S.check('lit=True: smoke shaded by the lights (Diffuse BSDF)',
            any(n.bl_idname == 'ShaderNodeBsdfDiffuse' for n in lit.material.node_tree.nodes))
    dim = PA.make_particles('fire', origin=(0, 0, 0), seed=9, name='opt_intensity', intensity=0.4)
    S.check('intensity scales the emission (it is in the material)', dim.params['intensity'] == 0.4)
    s1 = PA.make_particles('embers', seed=11, name='opt_seed_a')
    s2 = PA.make_particles('embers', seed=11, name='opt_seed_b')
    S.check('seed: the same buffers every run', np.allclose(attrs(s1.object)['iSeed'], attrs(s2.object)['iSeed']))
    t0 = PA.make_particles('snow', seed=12, name='opt_t0')
    t1 = PA.make_particles('snow', seed=12, name='opt_t1', time_offset=2.0)
    Ca, _, _ = instances(t0.object, 49)
    Cb, _, _ = instances(t1.object, 1)
    S.check('time_offset: 2 s ahead = frame 49 of the same emitter', float(np.abs(Ca - Cb).max()) < 1e-4)
    u = PA.make_particles('nope', seed=13, name='opt_unknown')
    S.check('an unknown preset falls back to sparks', u.params['count'] == PA.PRESETS['sparks']['count'])
    bad = PA.make_particles('sparks', seed=14, name='opt_bad_area', area='wide')
    C, _, _ = instances(bad.object, 1)
    S.check('an invalid area falls back to the preset\'s (warned), no NaN', np.isfinite(C).all())
    # the engine's options dict as a scene.js wrote it (three's axes), its group as `scene`, and map='auto'
    o3 = PA.make_particles(opts={'preset': 'sparks', 'origin': [0.5, 1.0, -2.0], 'count': 300, 'up': 0.0,
                                 'spread': 0.0, 'gravity': [0.0, 0.0, 0.0], 'area': [0.5, 0.1, 0.2],
                                 'wobble': 0.0, 'name': 'opt_dict'}, seed=15)
    C, _, _ = instances(o3.object, 1)
    ext = np.ptp(C, 0)
    S.check("opts={...} in three's axes: origin [0.5, 1, -2] -> (0.5, 2, 1); area [x .5, y .1, z .2] -> X wide, "
            "Y (three's z) .2, Z (three's y, x0.6) thin", np.allclose(tuple(o3.object.location), (0.5, 2.0, 1.0)) and
            o3.params['count'] == 300 and ext[0] > ext[1] > ext[2] and ext[2] < 0.13, f'extents {ext.round(3)}')
    grp = bpy.data.objects.new('opt_group', None)
    sc.collection.objects.link(grp)
    grp.location = (4.0, 0.0, 0.0)
    pg = PA.make_particles('embers', scene=grp, origin=(0, 0, 1.0), seed=16, name='opt_in_group')
    bpy.context.view_layer.update()
    S.check("scene=<an object> (the engine's group): parented, origin in its frame",
            pg.object.parent == grp and np.allclose(tuple(pg.object.matrix_world.translation), (4, 0, 1)))
    coll = bpy.data.collections.new('opt_coll')
    sc.collection.children.link(coll)
    pc = PA.make_particles('dust', scene=coll, seed=17, name='opt_in_coll')
    S.check('scene=<a collection>: linked there', pc.object.name in coll.objects)
    pa = PA.make_particles('fire', map='auto', seed=18, name='opt_auto')
    imgs = [n.image.name for n in pa.material.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage']
    S.check("map='auto': the preset's sprite (fire -> flame_05)", any(i.startswith('flame_05') for i in imgs), str(imgs))


def part_parity():
    sc = fresh(96)
    S.camera('cam', (0.5, -4.0, 1.2), (0.0, 0.0, 0.8), 35.0)
    worst = 0.0
    for name in PA.PRESETS:
        p = PA.make_particles(name, origin=(0.3, -0.2, 0.5), seed=21, name=f'par_{name}')
        A = attrs(p.object)
        emit3, vel3, seed = to_three(A['iEmit']), to_three(A['iVel']), A['iSeed']
        P = dict(PA.PRESETS[name])
        for f in (1, 37, 90):
            t = (f - sc.frame_start) / 24.0
            C, R, Sc = instances(p.object, f)
            ref = from_three(engine_centres(P, emit3, vel3, seed, t)) + np.array([0.3, -0.2, 0.5])
            err = float(np.abs(C - ref).max())
            worst = max(worst, err)
        S.check(f'parity {name}: the centres = particles.js positionNode (frames 1, 37, 90)', worst < 2e-4,
                f'max {worst:.2e} m')
        cam = sc.camera
        view = np.array(cam.matrix_world.to_3x3())[:, 2]
        S.check(f'parity {name}: every quad faces the camera', np.abs(R[:, :, 2] @ view).min() > 0.999)
        bpy.data.objects.remove(p.object)
    # every motion override flows into the graph (three's axes for the reference; gravity given in Blender's)
    over = dict(speed=1.7, lifetime=1.3, up=0.9, spread=0.4, grow=0.6, wobble=0.3, swirl=2.0, converge=0.5,
                rotate=0.8, twinkle=0.5, area=0.3)
    p = PA.make_particles('sparks', origin=(0, 0, 0), seed=22, name='par_custom', gravity=(0.5, 0.2, -2.0), **over)
    A = attrs(p.object)
    P = dict(PA.PRESETS['sparks'])
    P.update(over)
    P['gravity'] = (0.5, -2.0, -0.2)                   # Blender (0.5, 0.2, -2.0) in three's axes
    worst = 0.0
    for f in (1, 29, 77):
        C, R, _ = instances(p.object, f)
        ref = from_three(engine_centres(P, to_three(A['iEmit']), to_three(A['iVel']), A['iSeed'], (f - 1) / 24.0))
        worst = max(worst, float(np.abs(C - ref).max()))
    S.check('parity with every motion override (speed, lifetime, up, spread, grow, wobble, swirl, converge, rotate, '
            'gravity, area)', worst < 2e-4, f'max {worst:.2e} m')
    q = PA.make_particles('magic', seed=23, name='par_blend', blending='normal')
    S.check('blending override: magic drawn as normal (dithered) matter', q.material.surface_render_method == 'DITHERED')


def part_display():
    """The additive sprites under AgX, then with create_particles_compose (three's ACES for their light)."""
    for match in (False, True):
        sc = fresh(48)
        sc.view_settings.look = 'None'
        S.floor(20.0, (0.03, 0.03, 0.035), 0.5)
        for i, (nm, spr) in enumerate((('fire', 'flame_05'), ('sparks', 'spark_05'), ('magic', 'magic_02'))):
            PA.make_particles(nm, origin=(-1.4 + i * 1.4, 0, 0.15 if nm == 'fire' else 0.6), map=spr, seed=30 + i,
                              name=f'disp_{nm}')
        S.camera('cam', (0.0, -4.6, 1.2), (0.0, 0.0, 0.8), 35.0)
        if match:
            tree = PA.create_particles_compose(sc)
            S.check('display: a compositor with the match group after Render Layers',
                    any(n.bl_idname == 'CompositorNodeGroup' for n in tree.nodes) and
                    sc.view_layers[0].eevee.use_pass_transparent)
        still('display_' + ('aces_match' if match else 'agx'), 30)


def main():
    t0 = time.time()
    for part in PARTS:
        print(f'[particles] part {part}', flush=True)
        globals()['part_' + part]()
    print(f'[particles] all in {time.time() - t0:.1f} s', flush=True)
    ok = S.summary('particles')
    sys.exit(0 if ok else 1)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    print('FAIL exception')
    sys.exit(1)
