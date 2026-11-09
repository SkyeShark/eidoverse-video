"""Parity of the Blender particle morph with the WebGPU engine's particle_morph.js, number for number. Renders nothing.

1. The CPU side. morph_parity_dump.mjs runs the engine's own particle_morph.js in Deno with Math.random replaced by a
   seeded mulberry32 stream and dumps what it builds: neuralNet / neuronGraph (custom and default options),
   fromPoints up- and down-sampling, makeParticleMorph's per-instance buffers (iFrom, iTo, iSeed) before and after
   morph() swaps the segment and updateTarget() replaces one, the uniforms, the colours, and the stream's next draw.
   This test replays the same calls on the same stream (eidoblend.fx.particle_morph.JSRandom) and compares.
2. The GPU side. The engine's positionNode (TSL), transcribed in numpy in three's axes straight from the JS, against
   the Geometry Nodes graph's output (the cloud's 'Points Only' switch) at several segments, factors, turbulences,
   spins, vortices and times: the axes, the curl and the vortex.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01 && bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/particles/test_morph_parity.py
The dump is rebuilt with Deno when it is missing (deno on PATH, the main checkout's node_modules/three/build)."""

import json
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx._util import from_three, to_three, color as lin  # noqa: E402

DUMP = os.path.join(S.OUT, 'parity', 'morph_parity.json')


def dump():
    if not os.path.isfile(DUMP):
        three = os.path.join(S.MAIN, 'node_modules', 'three', 'build')
        r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A',
                            os.path.join(S.HERE, 'morph_parity_dump.mjs'), three], cwd=S.REPO, capture_output=True,
                           text=True)
        print(r.stdout[-400:], r.stderr[-400:])
    with open(DUMP, encoding='utf-8') as f:
        return json.load(f)


def close(name, ours_blender, theirs_three, tol=0.0):
    """Compare our Blender points with the engine's three-frame floats (float32 values, exactly when tol = 0)."""
    a = to_three(np.asarray(ours_blender, np.float64).reshape(-1, 3)).astype(np.float32)
    b = np.asarray(theirs_three, np.float64).reshape(-1, 3).astype(np.float32)
    if a.shape != b.shape:
        return S.check(name, False, f'shape {a.shape} vs {b.shape}')
    err = float(np.abs(a.astype(np.float64) - b.astype(np.float64)).max()) if len(a) else 0.0
    return S.check(name, err <= tol, f'max |diff| {err:.3g} over {len(a)} points')


def engine_position(frm3, to3, seed, m, turb, spin, vortex, cs, cst, t):
    """particle_morph.js positionNode (without the billboard corner), three's axes, float64."""
    me = np.clip(m, 0, 1)
    me = me * me * (3 - 2 * me)
    b0 = frm3 + (to3 - frm3) * me
    ca, sa = math.cos(spin), math.sin(spin)
    base = np.stack([b0[:, 0] * ca + b0[:, 2] * sa, b0[:, 1], b0[:, 2] * ca - b0[:, 0] * sa], 1)
    venv = vortex * math.sin(m * 3.14159265) * (seed[:, 0] * 0.8 + 0.6)
    cv, sv = np.cos(venv), np.sin(venv)
    bv = np.stack([base[:, 0] * cv + base[:, 2] * sv, base[:, 1], base[:, 2] * cv - base[:, 0] * sv], 1)
    env = turb * math.sin(m * 3.14159265)
    p = bv * cs + t * 0.35 + seed[:, :1] * 12.0
    disp = np.stack([np.sin(p[:, 1]) - np.cos(p[:, 2]), np.sin(p[:, 2]) - np.cos(p[:, 0]),
                     np.sin(p[:, 0]) - np.cos(p[:, 1])], 1) * seed[:, 2:3]
    return bv + disp * env * cst


def graph_points(m):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = m.object.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        P = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', P)
    finally:
        ev.to_mesh_clear()
    return P.reshape(-1, 3)


def options(nn, ng, up):
    """The options beyond the parity: the engine's opts dict, a fixed camera, set_targets, time_offset, and the
    Blender edition's own_colors, pairing, align, center and live."""
    from eidoblend.fx import particle_targets as PT
    sc = bpy.context.scene
    sc.frame_set(1)
    m = PM.make_particle_morph(opts={'count': 800, 'targets': [nn, ng], 'color': 0xff7a30, 'size': 0.03,
                                     'opacity': 0.5, 'blending': 'normal', 'name': 'opts_morph'})
    u = m.uniforms
    S.check("the engine's opts dict: count, colour, size, opacity, blending, name",
            m.count == 800 and abs(u.size.value - 0.03) < 1e-7 and abs(u.opacity.value - 0.5) < 1e-7 and
            m.blending == 'normal' and m.object.name == 'opts_morph' and m.material.surface_render_method == 'DITHERED')
    cd = bpy.data.cameras.new('fixed')
    cam = bpy.data.objects.new('fixed', cd)
    sc.collection.objects.link(cam)
    cam.location = (3.0, -4.0, 2.0)
    S.aim(cam, cam.location, (0, 0, 0))
    mc = PM.make_particle_morph(count=300, targets=[up, up], camera=cam, name='cam_morph')
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    Z = [np.array(i.matrix_world.to_3x3().normalized())[:, 2] for i in dg.object_instances
         if i.is_instance and i.parent is not None and i.parent.original == mc.object]
    view = np.array(cam.matrix_world.to_3x3())[:, 2]
    S.check('camera=: every quad faces the given camera', len(Z) == 300 and np.abs(np.array(Z) @ view).min() > 0.999)
    mc.set_targets([ng, nn])
    mc.uniforms.points_only.value = True
    P = graph_points(mc)
    S.check('set_targets: both replaced (resampled) and drawn', np.abs(P - mc.targets[0].points).max() < 1e-4 and
            len(mc.targets) == 2)
    mt = PM.make_particle_morph(count=500, targets=[nn, ng], time_offset=1.0, seed=3, name='toff_morph')
    mt.uniforms.points_only.value = True
    mt.morph(0, 1, 0.5, 0.8)
    sc.frame_set(1)
    P = graph_points(mt)
    sd = mt._seed_attr.astype(np.float32).astype(np.float64)
    ref = from_three(engine_position(to_three(mt.targets[0].points.astype(np.float64)),
                                     to_three(mt.targets[1].points.astype(np.float64)), sd, 0.5, 0.8, 0, 0, 1.3, 0.5,
                                     1.0))
    S.check('time_offset 1 s: the curl at t = 1 on the first frame', float(np.abs(P - ref).max()) < 2e-4)
    red = PT.Target(np.asarray(nn)[:500]).tinted(0xff0000)
    for own, want in ((1.0, 'red'), (0.0, 'engine')):
        mo = PM.make_particle_morph(count=500, targets=[red, red], own_colors=own, color=0x00ff00, name=f'own_{own}')
        mo.uniforms.points_only.value = True
        bpy.context.view_layer.update()
        ev = mo.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        C = np.empty(len(me.vertices) * 4, np.float32)
        me.attributes['p_color'].data.foreach_get('color', C)
        ev.to_mesh_clear()
        C = C.reshape(-1, 4)[:, :3].mean(0)
        S.check(f'own_colors={own}: {want} colours', (C[0] > 0.9 and C[1] < 0.05) if own else (C[1] > 0.9 and
                                                                                               C[0] < 0.05), str(C))
    mp = PM.make_particle_morph(count=600, targets=['sphere', 'cube'], pairing='height', name='pair_morph')
    S.check("pairing='height': particle i is the i-th highest in every target",
            all(np.all(np.diff(t.points[:, 2]) <= 1e-6) for t in mp.targets))
    ma = PM.make_particle_morph(count=600, targets=[PT.target('sphere', 600) + (2, 3, 4), 'cube', 'text:A'],
                                align='centroid', center='auto', name='align_morph')
    c0 = ma.targets[0].centroid()                       # 600 random points on a sphere: near (2, 3, 4), not on it
    S.check("align='centroid': every target on the first's centroid", all(np.allclose(t.centroid(), c0, atol=1e-4)
                                                                           for t in ma.targets), str(c0.round(3)))
    S.check("center='auto': spin and vortex turn about it", np.allclose(ma.uniforms.center.value, c0, atol=1e-4))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 5))
    cube = bpy.context.object
    ml = PM.make_particle_morph(count=400, targets=[cube, 'sphere'], live=True, name='live_morph')
    S.check('live=True: an object target is bound live', ml.targets[0].live is not None and
            ml.targets[1].live is None)
    # the engine's scene: a group: an object parents the cloud (static targets in its frame), a collection holds it
    grp = bpy.data.objects.new('morph_group', None)
    sc.collection.objects.link(grp)
    grp.location = (0.0, 6.0, 0.0)
    mg = PM.make_particle_morph(count=300, targets=[up, up], scene=grp, name='group_morph')
    mg.uniforms.points_only.value = True
    bpy.context.view_layer.update()
    ev = mg.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    Pw = P.reshape(-1, 3) @ np.array(mg.object.matrix_world)[:3, :3].T + np.array(mg.object.matrix_world)[:3, 3]
    S.check("scene=<an object> (the engine's group): the cloud is its child, the targets in its frame",
            mg.object.parent == grp and np.allclose(Pw, mg.targets[0].points + np.array([0.0, 6.0, 0.0]), atol=1e-5))
    coll = bpy.data.collections.new('morph_coll')
    sc.collection.children.link(coll)
    mk = PM.make_particle_morph(count=200, targets=[up, up], scene=coll, name='coll_morph')
    S.check('scene=<a collection>: the cloud is linked there', mk.object.name in coll.objects)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 9))
    box = bpy.context.object
    mv = PM.make_particle_morph(count=400, targets=[box, 'sphere'], target_opts={'mode': 'vertices'}, shadows=True,
                                render='sphere', sphere_subdiv=2, name='opts2_morph')
    corners = np.abs(mv.targets[0].points - np.array([0, 0, 9])).max(1)
    S.check("target_opts={'mode': 'vertices'} reach every object target; shadows=True casts; sphere_subdiv",
            np.allclose(corners, 1.0, atol=0.011) and mv.object.visible_shadow and
            any(n.bl_idname == 'GeometryNodeMeshIcoSphere' and n.inputs['Subdivisions'].default_value == 2
                for n in mv.node_group.nodes), f'corner distance {corners.min():.3f}..{corners.max():.3f}')
    m3 = PM.make_particle_morph(count=300, targets=[nn, ng, up], name='guard_morph')
    m3.morph(2, 1, 0.3)
    m3.morph(0, 9, 0.6)
    S.check("morph() to an index with no target keeps that slot (the engine's `if (targets[idx])`)",
            (m3.uniforms.from_idx.value, m3.uniforms.to_idx.value) == (0, 1) and abs(m3.uniforms.morph.value - 0.6)
            < 1e-6, str((m3.uniforms.from_idx.value, m3.uniforms.to_idx.value)))
    # setTargets assigns targets[i] for each i of the new list only: a shorter list keeps the targets past its end
    keep2 = m3.targets[2].points.copy()
    m3.set_targets([ng, nn])
    S.check("set_targets with a shorter list: the engine's targets[i] = arr[i]; the target past it stays",
            len(m3.targets) == 3 and np.allclose(m3.targets[2].points, keep2) and
            np.allclose(m3.targets[0].points, np.asarray(ng)[::10]),          # 3000 -> 300: the engine's stride
            f'{len(m3.targets)} targets')
    try:
        m3.update_target(5, nn)
        gap = False
    except IndexError:
        gap = True
    m3.update_target(3, up)
    S.check('update_target: one past the last adds a target; a gap is refused with a clear error',
            gap and len(m3.targets) == 4)


def main():
    S.clean_scene(24, 1, 48)
    J = dump()
    rnd = PM.JSRandom(12345)
    S.check('stream: the first three draws', np.allclose([rnd(), rnd(), rnd()], J['first_randoms'], rtol=0, atol=0),
            str(J['first_randoms']))
    nn = PM.neural_net(count=3000, layers=[4, 7, 5, 3], random=rnd)
    nn_def = PM.neural_net(count=2000, random=rnd)
    ng = PM.neuron_graph(count=3000, nodes=40, k=3, random=rnd)
    ng_def = PM.neuron_graph(count=2000, random=rnd)
    up_three = [[0, 0, 0], [1, 2, 3], [-1, 0.5, 2], [0.3, -0.2, 0.1]]
    up = PM.from_points(from_three(np.array(up_three, np.float64)), 500, random=rnd)
    down = PM.from_points(nn, 1000, random=rnd)
    close('neuralNet layers [4,7,5,3]', nn, J['nn'])
    close('neuralNet defaults', nn_def, J['nn_def'])
    close('neuronGraph nodes 40 k 3', ng, J['ng'])
    close('neuronGraph defaults', ng_def, J['ng_def'])
    close('fromPoints upsampling (cycle + 1 cm jitter)', up, J['up'])
    close('fromPoints downsampling (stride)', down, J['down'])

    # three's own draws: 4 per UUID (the Scene passed in; inside makeParticleMorph, after the targets and seeds, its
    # geometry, material and InstancedMesh: 12). The replay skips them; the morph's own draws must be the rest.
    C = J['calls']
    S.check('the stream before makeParticleMorph', rnd.n == C['before_make'], f"{rnd.n} vs {C['before_make']}")
    rnd.n = C['after_scene']
    n_before = rnd.n
    m = PM.make_particle_morph(count=1500, targets=[nn, ng, up], random=rnd, name='parity_morph')
    S.check("makeParticleMorph's own draws (3 targets x 3 n, then 3 n seeds)",
            rnd.n - n_before == C['after_make'] - C['after_scene'] - 12, f'{rnd.n - n_before}')
    rnd.n = C['after_make']
    close('makeParticleMorph iFrom (target 0)', m.targets[0].points, J['morph_from0'])
    close('makeParticleMorph iTo (target 1)', m.targets[1].points, J['morph_to0'])
    seed = np.asarray(J['morph_seed'], np.float64).reshape(-1, 3)
    S.check('makeParticleMorph iSeed (phase, size, turbulence)',
            np.abs(m._seed_attr.astype(np.float32) - seed.astype(np.float32)).max() == 0,
            f'max {np.abs(m._seed_attr - seed).max():.3g}')
    m.morph(1, 2, 1.3)
    u = m.uniforms
    close('morph(1, 2, ..) swaps the segment: From', m.targets[u.from_idx.value].points, J['morph_from1'])
    close('morph(1, 2, ..) swaps the segment: To', m.targets[u.to_idx.value].points, J['morph_to1'])

    def eff_turb():
        mm = u.morph.value
        return u.turb.value * (math.sin(mm * math.pi) if u.turb_auto.value else 1.0)
    S.check('morph(1, 2, 1.3): factor clamped to 1, turbulence sin(pi m)',
            abs(u.morph.value - J['morph_u']['morph']) < 1e-12 and abs(eff_turb() - J['morph_u']['turb']) < 1e-6,
            f"ours ({u.morph.value}, {eff_turb():.3g}) engine ({J['morph_u']['morph']}, {J['morph_u']['turb']:.3g})")
    m.morph(1, 2, 0.25, 0.8)
    S.check('morph(1, 2, 0.25, 0.8): turbulence as given',
            abs(u.morph.value - J['morph_u2']['morph']) < 1e-7 and abs(eff_turb() - J['morph_u2']['turb']) < 1e-7,
            f"ours ({u.morph.value}, {eff_turb()}) engine {J['morph_u2']}")
    n_before = rnd.n
    m.update_target(2, down, random=rnd)
    close('updateTarget(2, ..) re-uploads the active To', m.targets[2].points, J['morph_to2'])
    S.check("updateTarget's own draws", rnd.n - n_before == C['after_update'] - C['before_update'],
            f'{rnd.n - n_before}')
    cols = J['colors']
    S.check('default colours 0x66ccff -> 0xff66cc (linear, as three.Color)',
            np.allclose(m._values['color'], cols['color'], atol=1e-6) and
            np.allclose(m._values['color2'], cols['color2'], atol=1e-6),
            f"{np.round(m._values['color'], 5)} {np.round(m._values['color2'], 5)}")
    S.check('default size 0.014, opacity 1', abs(u.size.value - cols['size']) < 1e-7 and
            abs(u.opacity.value - cols['opacity']) < 1e-7)
    rnd.n = C['before_make2']
    m2 = PM.make_particle_morph(count=10, targets=[up, up], color=0xff7a30, random=rnd, name='parity_morph2')
    S.check('one colour given: color2 = color', np.allclose(m2._values['color'], J['colors_one']['color'], atol=1e-6)
            and np.allclose(m2._values['color2'], J['colors_one']['color2'], atol=1e-6))
    seed2 = np.asarray(J['morph2_seed'], np.float64).reshape(-1, 3).astype(np.float32)
    S.check('second morph: its seeds', np.abs(m2._seed_attr.astype(np.float32) - seed2).max() == 0)
    S.check("second morph: its own draws", rnd.n - C['before_make2'] == C['after_make2'] - C['before_make2'] - 12,
            f"{rnd.n - C['before_make2']}")
    rnd.n = C['end']
    S.check('the stream: the next draw after it all', abs(rnd() - J['last_random']) == 0,
            f"next draw {J['last_random']}")

    # ---- the graph against the engine's positionNode
    sc = bpy.context.scene
    g = PM.make_particle_morph(count=1500, targets=[nn[:1500] if len(nn) >= 1500 else nn, ng, up], seed=7,
                               name='parity_graph', curl={'scale': 1.4, 'strength': 0.55})
    g.uniforms.points_only.value = True
    T3 = [to_three(t.points.astype(np.float64)) for t in g.targets]
    sd = g._seed_attr.astype(np.float32).astype(np.float64)
    worst = 0.0
    for (fi, ti, mm, tb, sp, vx, frame) in ((0, 1, 0.0, 0.0, 0.0, 0.0, 1), (0, 1, 0.37, 0.6, 0.0, 0.0, 13),
                                            (1, 2, 0.5, 1.0, 0.4, 0.0, 30), (2, 0, 0.71, 0.3, -1.1, 3.0, 47),
                                            (0, 2, 1.0, 0.9, 2.0, 6.0, 5), (1, 0, 0.12, 0.45, 0.0, 5.0, 21)):
        sc.frame_set(frame)
        g.uniforms.from_idx.value, g.uniforms.to_idx.value = fi, ti
        g.uniforms.morph.value, g.uniforms.turb.value, g.uniforms.turb_auto.value = mm, tb, False
        g.uniforms.spin.value, g.uniforms.vortex.value = sp, vx
        P = graph_points(g)
        t = (frame - sc.frame_start) / (sc.render.fps / sc.render.fps_base)
        ref = from_three(engine_position(T3[fi], T3[ti], sd, mm, tb, sp, vx, 1.4, 0.55, t))
        err = float(np.abs(P - ref).max())
        worst = max(worst, err)
        S.check(f'graph = engine positionNode: {fi}->{ti} m {mm} turb {tb} spin {sp} vortex {vx} frame {frame}',
                err < 2e-4, f'max |diff| {err:.2e} m')
    # the default turbulence computed in the graph: sin(pi m) at any (sub-)frame, as the engine's per-frame default
    g.uniforms.turb.value, g.uniforms.turb_auto.value = 1.0, True
    g.uniforms.morph.value, g.uniforms.spin.value, g.uniforms.vortex.value = 0.3, 0.0, 0.0
    sc.frame_set(9)
    P = graph_points(g)
    ref = from_three(engine_position(T3[1], T3[0], sd, 0.3, math.sin(0.3 * math.pi), 0.0, 0.0, 1.4, 0.55,
                                     8 / 24.0))
    S.check('Turb Auto: turbulence = sin(pi m), the engine default', float(np.abs(P - ref).max()) < 2e-4,
            f'max |diff| {float(np.abs(P - ref).max()):.2e}')
    options(nn, ng, up)
    ok = S.summary('morph parity')
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
