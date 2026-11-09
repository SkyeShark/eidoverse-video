"""createWaterSim for Blender 5.2: eidoverse/fluid_water.js's Eulerian free-surface water, baked to a mesh sequence.

    from eidoblend.fx.water3d import create_water_sim
    water = create_water_sim(grid_size=(64, 64, 48), world_size=(2.0, 2.0, 1.5), domain_center=(0, 0, 0.75),
                             column_depth=0.62, smooth_surface=True, cache_dir='//water_cache')
    water.bake(1, 180)                     # steps once per frame, meshes phi = 0, writes <cache>/<name>_####.ply
    water.surface_mesh                     # the object that plays the sequence (Geometry Nodes, no Python)

Blender axes in the API: grid_size, world_size and domain_center are (x, y, z) with z up. The engine's
gridSize [64, 48, 64] over worldSize [2, 1.5, 2] (three, y up) is grid_size (64, 64, 48) over (2, 2, 1.5).
Emitters and spheres are Blender points and velocities; the solver runs in three's axes inside.
"""

from __future__ import annotations

import os
import time

import numpy as np

from .._util import abspath, frame_file, scene_fps
from . import surface as SF
from .material import LOOK_KEYS, build_water_material, set_look
from .solver import WaterSolver, check_cubic

DEFAULTS = dict(
    # the grid and the box, Blender (x, y, z): the engine's gridSize [64, 48, 64] / worldSize [2, 1.5, 2]
    grid_size=(64, 64, 48),
    world_size=(2.0, 2.0, 1.5),
    domain_center=(0.0, 0.0, 0.0),
    gravity=9.8,
    fixed_step=1 / 120,
    max_sub_steps=8,
    # pressure: multigrid (paper section 3.7), damped Jacobi smoother; mg_levels 1 = plain Jacobi
    mg_levels=4, mg_cycles=2, mg_pre=2, mg_post=1, mg_coarse=4, mg_omega=0.8,
    pressure_iters=80,
    extrapolation_passes=6,
    # 'phi' is the engine's (an air cell takes the velocity of its neighbours deeper in phi); 'bfs' takes the velocity
    # of the water nearest it in steps (the Blender edition's, part of DROP_SOLVER below)
    extrapolation='phi',
    # redistancing: off, as in the engine (its central-difference kernel is unstable, and its notes name Godunov
    # upwinding as the condition for turning it on). reinit_scheme='godunov' is that kernel; DROP_SOLVER runs it
    # every substep for water dropped onto water, where it keeps phi a distance below the falling body. It is not
    # the default: in the 128^3 pour it lost about 6 litres around the end of the stream, where the engine's solver
    # held the 30 litres poured (measured; see the guide)
    reinit_every=0,
    reinit_iters=8,
    reinit_scheme='central',
    max_trace_cells=3.0,
    max_speed=6.0,
    # volume control (Kim et al. 2007): a PI controller on total volume as a divergence source
    volume_control=True, volume_target=None, vc_kp=1.2, vc_ki=0.5, vc_max_rate=0.35, vc_every=4,
    # colliders
    walls=True,                    # the analytic tank (floor + 4 sides, top open)
    inside_domain=False,           # the camera is inside the liquid domain (the material shows back faces)
    collider_meshes=(),            # Blender objects, voxelised once (ray parity, as the engine's BVH pass)
    max_spheres=0,                 # dynamic collider slots (set_spheres / bake(track_spheres=...))
    max_emitters=0,                # emitter slots (set_emitters)
    measure_volume=False,
    vel_smooth=0.25,
    vel_damping=0.0,
    initial_level=None,            # still water this deep (m above the domain floor) instead of the column
    column_width=0.42, column_height=0.72, column_depth=1.0,
    # the engine's raymarcher (the surface is a mesh here; kept so engine configs port verbatim)
    raymarch_steps=96, bisection_steps=4, march_mode='fixed', march_iters=128,
    # look
    deep_color='#06283d', shallow_color='#2f8f9d', sky_color='#9db8c9', absorption=2.2, surface_opacity=0.93,
    key_light_dir=(0.4, 0.8, 0.45),
    emissive_color='#2ffbe0', emissive_strength=0.0, emissive_falloff=5.0,
    foam_color='#ffffff', foam_strength=0.0, foam_width=0.10, foam_shore=1.0,
    surface_bias=0.0, smooth_surface=False, render_blur=0,
    sparkle_strength=0.0, sparkle_scale=26.0, sparkle_speed=1.4,
    warmup_seconds=0.0,
    # the Blender edition's own
    extend_phi_into_solids=None,   # None = on with baked colliders, into walls and the baked field (never spheres):
                                   # walls-only and sphere scenes run the engine's solver exactly
    shading='lit',                 # 'lit' (film: refraction, real reflections) | 'engine' (the WebGPU unlit look)
    engine_display='standard',     # engine shading: match the engine's untonemapped sRGB canvas under AgX | None
    thickness_mode='normal',       # 'normal' (any camera) | 'view' (the scene camera's ray, as the engine)
    mesh_adaptivity=0.0,           # OpenVDB polygon reduction on flat water (0 = none)
    roughness=0.04,                # the water's specular roughness (the engine's spec exponent was fixed)
    body='tint',                   # lit shading: 'tint' (all refracting, depth-tinted) | 'stochastic' (the SWE water's split)
    foam_churn=0.0,                # lit shading: white water where the flow shears, fast water meeting slow (a jet's
                                   # plunge, a landing, a crown's root); 0 = the engine's foam only
    churn_speed=2.0,               # the speed difference (m/s) at which churn foam saturates
    refraction_thickness='slab',   # lit shading: EEVEE's refraction model through the baked water path ('slab' |
                                   # 'sphere' | 'none' = EEVEE's own default, which flipped a pool between frames)
    foam_pick='lace',              # lit shading: foam picked per surface point ('lace', a 3D noise: coherent foam whose
                                   # edges alone dither) or per sample ('dither', white noise: grainy at 64 samples)
    foam_scale=90.0,               # lace: noise frequency per metre (90 = lace about a centimetre across)
    write_grids=False,             # also write <name>_grids_####.vdb (phi, velocity, pressure, divergence)
)

# the three options that make the solver the engine's exactly: its redistancing off and its phi-weighted velocity
# extrapolation. These are the defaults; the name stays so a call can say so (create_water_sim(**ENGINE_SOLVER, ...)).
ENGINE_SOLVER = dict(reinit_every=0, reinit_scheme='central', extrapolation='phi')
# the Blender edition's solver for water dropped onto water (create_water_sim(**DROP_SOLVER, ...)): Godunov
# redistancing every substep and the breadth-first velocity extrapolation keep a falling body in free fall until it
# meets the pool (measured: test_water3d_drop_ball.py). They erode thin water, so pours keep the engine's solver.
DROP_SOLVER = dict(reinit_every=1, reinit_scheme='godunov', extrapolation='bfs')

_CAMEL = {'gridSize': 'grid_size', 'worldSize': 'world_size', 'domainCenter': 'domain_center'}
# the engine's double-underscore debug hooks: the solver ones act; the render ones map to the grids file
DEBUG_KEYS = ('__no_clamp', '__no_reinit', '__no_pressure', '__no_multigrid', '__debug_phi', '__debug_fields',
              '__bisect')


def _snake(k):
    if k in _CAMEL:
        return _CAMEL[k]
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


class Uniforms:
    """The engine's api.uniforms, snake_case and holding values (the engine's `uniforms.volTarget.value = 40` is
    `uniforms.vol_target = 40` here): the solver's live values (read every substep: gravity, vel_damping, max_speed,
    vel_smooth, mg_omega, vol_target, vc_kp, vc_ki, vc_max_rate; dt and time read only), the look values (written
    through to the material's named nodes), surface_bias (a render-side field op: frames meshed after the change use
    it) and the domain's fixed world_size / wall_m (read only, three axes and uvw, as the engine's)."""

    _SIM = ('dt', 'time', 'gravity', 'vel_damping', 'max_speed', 'vel_smooth', 'mg_omega', 'vol_target', 'vc_kp',
            'vc_ki', 'vc_max_rate')
    _READ_ONLY = ('world_size', 'wall_m')

    def __init__(self, water):
        object.__setattr__(self, '_w', water)

    def __getattr__(self, k):
        w = object.__getattribute__(self, '_w')
        if k in Uniforms._SIM:
            return w.solver.U[k]
        if k in LOOK_KEYS or k == 'surface_bias':
            return w.params[k]
        if k == 'world_size':
            return tuple(w.params['world3'])
        if k == 'wall_m':
            return w.solver.wallM
        raise AttributeError(k)

    def __setattr__(self, k, v):
        w = object.__getattribute__(self, '_w')
        if k in Uniforms._SIM:
            w.solver.U[k] = float(v)
        elif k in LOOK_KEYS:
            w.params[k] = v
            if w.material is not None:
                set_look(w.material, k, v, w.scene)
        elif k == 'surface_bias':
            w.params[k] = float(v)
        elif k in Uniforms._READ_ONLY:
            raise AttributeError(f'{k} is fixed when the solver is built')
        else:
            raise AttributeError(k)


class WaterSim:
    """What create_water_sim returns. The engine's API: surface_mesh (also surface_object), uniforms, params,
    sim_time, step, warmup, measure_volume, set_emitters, set_spheres, reset, dispose. The Blender edition's:
    material, bake (the frame loop, with fill_target for pours), capture (mesh the current state for one frame),
    attach_player (play what was meshed), surface_arrays (the mesh and its shading attributes as arrays),
    emitter_flux (the live emitters' inflow, m^3/s), set_solver (switch to DROP_SOLVER and back between frames),
    set_inside_domain (a camera under the water, per shot) and solver (the GPU state)."""

    def __init__(self, scene, o, name, cache_dir, log):
        import bpy
        self.scene = scene
        self.params = o
        self.name = name
        self.cache_dir = abspath(cache_dir)
        self.log = log
        gb = tuple(int(v) for v in o['grid_size'])
        wb = tuple(float(v) for v in o['world_size'])
        cb = tuple(float(v) for v in o['domain_center'])
        # three axes inside: (x, y up, z) = Blender (x, z, -y)
        o['grid3'] = (gb[0], gb[2], gb[1])
        o['world3'] = (wb[0], wb[2], wb[1])
        self.center3 = np.array([cb[0], cb[2], -cb[1]], dtype=np.float64)
        check_cubic(o['grid3'], o['world3'], log)
        self.solver = WaterSolver(o, log=log)
        self.uniforms = Uniforms(self)
        self.material = None
        self._spheres_local = np.zeros((0, 4))
        self._baked = []
        if o['collider_meshes']:
            occ = self._bake_colliders(list(o['collider_meshes']))
            self.solver.set_solid(occ)
        self.solver.build()
        self.solver.init()
        self.solver.capture_volume_target()
        fs = scene.frame_start
        self.material = build_water_material(name + '_water', o, o['world3'], self.center3, scene_fps(scene), fs,
                                             time_offset=float(o['warmup_seconds']), scene=scene)
        me = bpy.data.meshes.new(name)
        self.surface_mesh = bpy.data.objects.new(name, me)
        scene.collection.objects.link(self.surface_mesh)
        self.surface_mesh.visible_shadow = False             # the engine's raymarched surface cast none
        me.materials.append(self.material)

    @property
    def surface_object(self):
        return self.surface_mesh

    @property
    def sim_time(self):
        return self.solver.sim_time

    # ------------------------------------------------------------------------------------------------
    # coordinates
    # ------------------------------------------------------------------------------------------------
    def _local3(self, x, y, z):
        return np.array([x, z, -y], dtype=np.float64) - self.center3

    @staticmethod
    def _vel3(vx, vy, vz):
        return np.array([vx, vz, -vy], dtype=np.float64)

    # ------------------------------------------------------------------------------------------------
    # the engine's API
    # ------------------------------------------------------------------------------------------------
    def step(self, delta=1 / 60):
        """Advance like the engine's step(delta): delta capped at 1/30 s, at most max_sub_steps substeps."""
        return self.solver.step(delta)

    def warmup(self, seconds=None):
        self.solver.warmup(self.params['warmup_seconds'] if seconds is None else float(seconds))
        return self

    def measure_volume(self):
        """Liquid volume in m^3 from the GPU sensor (needs measure_volume or volume_control)."""
        return self.solver.measure_volume()

    def emitter_flux(self):
        """The live emitters' nominal inflow in m^3/s: each sphere's cross-section times its speed (water
        leaves the stamped sphere at the speed it drives). What a pour adds per second, for a fill target."""
        e = self.solver.emitters
        live = e[0, :self.solver.NEMI, 3] > 0
        if not live.any():
            return 0.0
        r = e[0, :self.solver.NEMI, 3][live]
        sp = np.linalg.norm(e[1, :self.solver.NEMI, :3][live], axis=1)
        return float((np.pi * r * r * sp).sum())

    def set_emitters(self, emitters):
        """[{x, y, z, r, vx, vy, vz}] in Blender metres and m/s; r <= 0 (or a missing slot) disables it.
        Entries past max_emitters are ignored."""
        pos, vel = [], []
        for e in (emitters or []):
            if e and float(e.get('r', 0)) > 0:
                pos.append([*self._local3(e['x'], e['y'], e['z']), float(e['r'])])
                vel.append([*self._vel3(e.get('vx', 0.0), e.get('vy', 0.0), e.get('vz', 0.0)), 0.0])
            else:
                pos.append([0, 0, 0, -1.0])
                vel.append([0, 0, 0, 0.0])
        self.solver.set_emitters_local(np.array(pos).reshape(-1, 4), np.array(vel).reshape(-1, 4))

    def set_spheres(self, spheres):
        """Dynamic colliders [{x, y, z, r}] in Blender metres, refreshed per frame (VRM bones, props)."""
        rows = []
        for s in (spheres or []):
            if s and float(s.get('r', 0)) > 0:
                rows.append([*self._local3(s['x'], s['y'], s['z']), float(s['r'])])
            else:
                rows.append([0, 0, 0, -1.0])
        arr = np.array(rows, dtype=np.float64).reshape(-1, 4)
        self._spheres_local = arr[: self.solver.NSPH]
        self.solver.set_spheres_local(arr)

    def reset(self):
        """Back to the initial state (the column or the still layer), target re-measured."""
        self.solver.reset()
        return self

    def set_solver(self, reinit_every=None, reinit_scheme=None, extrapolation=None, reinit_iters=None):
        """Switch the redistancing and the velocity extrapolation from the next substep, e.g. from the engine's
        solver for a pour to DROP_SOLVER the frame a body of water is dropped: water.set_solver(**DROP_SOLVER)."""
        self.solver.set_solver(reinit_every, reinit_scheme, extrapolation, reinit_iters)
        return self

    def set_inside_domain(self, on=True):
        """The engine's insideDomain, switchable per shot: a camera under the water sees the surface's back faces
        and the water between it and them absorbs (lit shading)."""
        from .material import set_inside_domain
        self.params['inside_domain'] = bool(on)
        if self.material is not None and self.material.get('w3d_shading') == 'lit':
            set_inside_domain(self.material, bool(on))
        elif self.material is not None:
            self.material.use_backface_culling = not on
        return self

    def dispose(self):
        self.solver.dispose()

    # ------------------------------------------------------------------------------------------------
    # colliders: the engine's bakeColliders (ray parity along +X from every cell centre)
    # ------------------------------------------------------------------------------------------------
    def _bake_colliders(self, roots):
        import bpy
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        NX, NY, NZ = self.params['grid3']
        W = np.array(self.params['world3'], dtype=np.float64)
        dg = bpy.context.evaluated_depsgraph_get()
        meshes = []
        for r in roots:
            for ob in [r] + list(r.children_recursive):
                if ob.type == 'MESH' and ob not in meshes:
                    meshes.append(ob)
        occ = np.zeros((NZ, NY, NX), dtype=np.float32)
        xs3 = (np.arange(NX) + 0.5) / NX * W[0] - W[0] / 2 + self.center3[0]       # cell centres (Blender x)
        trees = []
        x_lo = xs3[0] - 1.0
        for ob in meshes:
            ev = ob.evaluated_get(dg)
            trees.append((BVHTree.FromObject(ev, dg), ob.matrix_world.copy(), ob.matrix_world.inverted()))
            x_lo = min(x_lo, min((ob.matrix_world @ Vector(c)).x for c in ob.bound_box) - 1.0)
        t0 = time.time()
        for k in range(NZ):
            z3 = (k + 0.5) / NZ * W[2] - W[2] / 2 + self.center3[2]
            for j in range(NY):
                y3 = (j + 0.5) / NY * W[1] - W[1] / 2 + self.center3[1]
                o_w = Vector((x_lo, -z3, y3))
                row = np.zeros(NX, dtype=bool)
                for bvh, M, Mi in trees:
                    o_l = Mi @ o_w
                    d_l = (Mi.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
                    hits = []
                    p = o_l
                    for _ in range(4096):
                        loc, _n, _i, dist = bvh.ray_cast(p, d_l)
                        if loc is None:
                            break
                        hits.append((M @ loc).x)
                        # step past the face by more than float32's spacing at this distance from the origin
                        # (a fixed 1e-6 re-hit the same face of a 24 m slab and broke the parity)
                        p = loc + d_l * (1e-5 + 2e-6 * max(abs(loc.x), abs(loc.y), abs(loc.z)))
                    if hits:
                        h = np.sort(np.array(hits))
                        cnt = len(h) - np.searchsorted(h, xs3, side='right')        # crossings beyond each centre
                        row |= (cnt & 1).astype(bool)
                occ[k, j, row] = 1.0
        filled = int(occ.sum())
        self.log(f'[water3d] baked {len(meshes)} collider mesh(es) -> {filled}/{NX * NY * NZ} solid cells '
                 f'({filled / (NX * NY * NZ) * 100:.1f}%) in {time.time() - t0:.1f} s')
        return occ

    # ------------------------------------------------------------------------------------------------
    # the bake (the Blender edition's frame loop) and the surface
    # ------------------------------------------------------------------------------------------------
    def _soft(self):
        o = self.params
        return SF.SolidSoft(o['world3'], self.solver.DX, self.solver.wallM, o['walls'], self.solver.solid_np,
                            self._spheres_local if self.solver.NSPH else None)

    def surface_arrays(self, camera_location=None):
        """(verts, tris, quads, {'thick', 'ring', 'speed', 'shear', 'exit', 'bed'}) of the current state, Blender world
        coordinates (surface.py says what each attribute holds)."""
        o = self.params
        soft = self._soft()
        field = SF.render_field(self.solver.phi(), o, self.solver.DX, soft)
        verts, tris, quads = SF.mesh_field(field, o['world3'], self.center3, o['mesh_adaptivity'])
        grid = SF.Grid(field, o['world3'])
        thick, ring, _nrm, exit_len, bed = SF.vertex_attributes(verts, grid, soft, o, self.solver.DX, o['world3'],
                                                                self.center3, camera_b=camera_location)
        vel = self.solver.velocity()
        speed = SF.vertex_speed(verts, vel, o['world3'], self.center3)
        shear = SF.vertex_shear(verts, vel, soft, o['world3'], self.center3, self.solver.DX)
        return verts, tris, quads, {'thick': thick, 'ring': ring, 'speed': speed, 'shear': shear, 'exit': exit_len,
                                    'bed': bed}

    def capture(self, frame):
        """Mesh the current state into <cache>/<name>_<frame>.ply (a manual loop's per-frame call)."""
        os.makedirs(self.cache_dir, exist_ok=True)
        cam = self.scene.camera
        cam_loc = np.array(cam.matrix_world.translation) if (cam is not None
                                                             and self.params['thickness_mode'] == 'view') else None
        verts, tris, quads, attrs = self.surface_arrays(cam_loc)
        SF.write_ply(frame_file(self.cache_dir, self.name, frame, 'ply'), verts, tris, quads, attrs)
        if self.params['write_grids']:
            self._write_grids(frame)
        self._baked.append(int(frame))
        return len(verts), len(tris) + len(quads)

    def _write_grids(self, frame):
        """phi, velocity (face samples, three axes), pressure and divergence as an OpenVDB file for inspection
        (the Blender edition of the engine's __debugPhi / __debugFields heatmaps)."""
        import openvdb as vdb
        S = self.solver
        b2 = lambda a: np.ascontiguousarray(a.transpose(2, 0, 1)[:, ::-1, :])      # noqa: E731
        h = S.DX
        c = self.center3
        W = np.array(self.params['world3'])
        tr = vdb.createLinearTransform([[h, 0, 0, 0], [0, h, 0, 0], [0, 0, h, 0],
                                        [-W[0] / 2 + c[0] + h / 2, -W[2] / 2 - c[2] + h / 2,
                                         -W[1] / 2 + c[1] + h / 2, 1]])
        grids = []
        for nm, arr in (('phi', S.phi()), ('pressure', S.pressure()), ('divergence', S.divergence())):
            g = vdb.FloatGrid()
            g.copyFromArray(b2(arr).astype(np.float32))
            g.name = nm
            g.transform = tr
            grids.append(g)
        v = S.velocity()
        vb = np.stack([v[..., 0], -v[..., 2], v[..., 1]], axis=-1)                   # to Blender axes
        gv = vdb.Vec3SGrid()
        gv.copyFromArray(np.ascontiguousarray(vb.transpose(2, 0, 1, 3)[:, ::-1, :, :]).astype(np.float32))
        gv.name = 'velocity'
        gv.transform = tr
        grids.append(gv)
        vdb.write(frame_file(self.cache_dir, self.name + '_grids', frame, 'vdb'), grids=grids)

    def bake(self, frame_start=None, frame_end=None, controls=None, track_spheres=(), mesh_frames=None,
             log=None, fill_target=None, fill_rate=None, fill_kp=None):
        """Warm up (warmup_seconds), then per frame: track spheres, controls(frame, t, water), advance 1/fps,
        and mesh the surface into <cache>/<name>_####.ply. mesh_frames limits the meshing to a set of frames
        (probes); the simulation still runs every frame. track_spheres = [(object, radius) or (armature,
        radius, bone_name)] feeds those positions every frame. Then the Geometry Nodes player plays the sequence.

        fill_target drives the volume controller's target while emitters run (the engine leaves this to the
        scene): 'measured' is the engine's documented workflow (the target follows the measured volume, then
        holds what was reached); 'poured' adds each frame's emitter_flux() / fps to the target, plus a sphere's
        volume when an emitter switches on (a one-frame stamp is mostly that sphere), so the controller also
        restores what thin sheets lose in the air and on landing (measured on a 2-cell jet into a basin:
        'measured' stalled at 4 litres of 19 poured). fill_rate and fill_kp raise vc_max_rate and vc_kp while
        emitters run and until the volume is back within 2 % of the target; then the controller's integral is
        cleared (a bumpless hand-over to holding: the integral wound up during a long fill overshot by 10 %)."""
        log = log or self.log
        U = self.solver.U
        rate0, kp0 = U['vc_max_rate'], U['vc_kp']
        adding = False
        boosted = False
        was_live = np.zeros(max(self.solver.NEMI, 1), dtype=bool)
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = scene_fps(sc)
        os.makedirs(self.cache_dir, exist_ok=True)
        if self.params['warmup_seconds'] > 0 and self.solver.sim_time == 0.0:
            self.warmup(self.params['warmup_seconds'])
        want = None if mesh_frames is None else set(int(f) for f in mesh_frames)
        t0 = time.time()
        tm = 0.0
        for f in range(fs, fe + 1):
            t = (f - fs) / fps
            if track_spheres or self.params['thickness_mode'] == 'view':
                sc.frame_set(f)
            if track_spheres:
                sph = []
                for item in track_spheres:
                    ob, r = item[0], item[1]
                    if len(item) > 2 and item[2]:
                        pb = ob.pose.bones[item[2]]
                        p = ob.matrix_world @ pb.head
                    else:
                        p = ob.matrix_world.translation
                    sph.append(dict(x=p[0], y=p[1], z=p[2], r=r))
                self.set_spheres(sph)
            if controls:
                controls(f, t, self)
            if fill_target and self.params['volume_control']:
                flux = self.emitter_flux()
                nemi = self.solver.NEMI
                live = self.solver.emitters[0, :nemi, 3] > 0 if nemi else np.zeros(1, dtype=bool)
                if flux > 0:
                    if fill_target == 'measured':
                        U['vol_target'] = max(self.measure_volume(), 1e-4)
                    elif fill_target == 'poured':
                        base = U['vol_target'] if (adding or self.solver.target_valid) else \
                            max(self.measure_volume(), 1e-4)
                        r_new = self.solver.emitters[0, :nemi, 3][live & ~was_live[:nemi]] if nemi else []
                        U['vol_target'] = base + flux / fps + float(sum(4 / 3 * np.pi * r ** 3 for r in r_new))
                    else:
                        raise ValueError(f"fill_target must be 'measured', 'poured' or None, not {fill_target!r}")
                    self.solver.target_valid = True
                    adding = True
                else:
                    adding = False                                # the pour stopped: hold what was reached
                was_live[:nemi] = live
                if fill_rate is not None or fill_kp is not None:
                    behind = False
                    if not adding and self.solver.target_valid:
                        v_now = self.measure_volume()
                        behind = abs(v_now - U['vol_target']) > 0.02 * U['vol_target']
                    boost = adding or behind
                    U['vc_max_rate'] = float(fill_rate) if (boost and fill_rate is not None) else rate0
                    U['vc_kp'] = float(fill_kp) if (boost and fill_kp is not None) else kp0
                    if boosted and not boost:
                        self.solver.reset_controller()           # caught up: hold from a clean integral
                    boosted = boost
            self.solver.advance(1.0 / fps)
            if want is None or f in want:
                t1 = time.time()
                nv, nf = self.capture(f)
                tm += time.time() - t1
                if want is not None or (f - fs) % 24 == 0:
                    vol = self.solver.measure_volume() if self.params['measure_volume'] else None
                    log(f'[water3d] frame {f} sim {self.solver.sim_time:.2f} s  mesh {nv} verts {nf} faces'
                        + (f'  volume {vol:.4f} m3' if vol is not None else '') + f'  {time.time() - t0:.1f} s')
        self.attach_player(fs, fe)
        log(f'[water3d] baked frames {fs}..{fe} in {time.time() - t0:.1f} s (meshing {tm:.1f} s) -> '
            f'{self.cache_dir}')
        return self

    def attach_player(self, frame_start, frame_end):
        """Geometry Nodes: Import PLY <cache>/<name>_<frame clamped to the bake>.ply, smooth, the water material."""
        from .._nodes import new_group
        tree, gi, go = new_group(self.name + '.player', 'GeometryNodeTree',
                                 [('Geometry', 'NodeSocketGeometry')], [('Geometry', 'NodeSocketGeometry')])
        N, L = tree.nodes, tree.links
        tm = N.new('GeometryNodeInputSceneTime')
        lo = N.new('ShaderNodeMath')
        lo.operation = 'MAXIMUM'
        lo.inputs[1].default_value = float(frame_start)
        L.new(tm.outputs['Frame'], lo.inputs[0])
        hi = N.new('ShaderNodeMath')
        hi.operation = 'MINIMUM'
        hi.inputs[1].default_value = float(frame_end)
        L.new(lo.outputs[0], hi.inputs[0])
        fl = N.new('ShaderNodeMath')
        fl.operation = 'FLOOR'
        L.new(hi.outputs[0], fl.inputs[0])
        vts = N.new('FunctionNodeValueToString')
        vts.data_type = 'INT'
        vts.inputs['Padding'].default_value = 4
        L.new(fl.outputs[0], vts.inputs['Value'])
        join = N.new('GeometryNodeStringJoin')
        a = N.new('FunctionNodeInputString')
        a.string = os.path.join(self.cache_dir, self.name + '_')
        bnode = N.new('FunctionNodeInputString')
        bnode.string = '.ply'
        # Join Strings concatenates its multi-input links in reverse creation order (round one, checked)
        L.new(bnode.outputs[0], join.inputs['Strings'])
        L.new(vts.outputs[0], join.inputs['Strings'])
        L.new(a.outputs[0], join.inputs['Strings'])
        imp = N.new('GeometryNodeImportPLY')
        L.new(join.outputs[0], imp.inputs['Path'])
        smooth = N.new('GeometryNodeSetShadeSmooth')
        L.new(imp.outputs[0], smooth.inputs['Geometry'])
        setm = N.new('GeometryNodeSetMaterial')
        L.new(smooth.outputs[0], setm.inputs['Geometry'])
        setm.inputs['Material'].default_value = self.material
        L.new(setm.outputs[0], go.inputs[0])
        mod = self.surface_mesh.modifiers.get('water3d_player') or self.surface_mesh.modifiers.new('water3d_player',
                                                                                                    'NODES')
        mod.node_group = tree
        return tree


def create_water_sim(scene=None, name='water3d', cache_dir='//water3d_cache', log=print, **options):
    """The engine's createWaterSim(renderer, options): options are DEFAULTS' keys (snake_case, Blender axes; the
    engine's camelCase names are accepted too and keep the engine's meaning, so an engine config ports verbatim:
    gridSize [64, 48, 64], worldSize [2, 1.5, 2] and domainCenter [0, 0.75, 0] are three.js axes, y up, and become
    grid_size (64, 64, 48), world_size (2, 2, 1.5), domain_center (0, 0, 0.75)). Builds the GPU solver, voxelises
    collider_meshes, runs the initial state and measures the volume target. Returns a WaterSim."""
    import bpy
    o = dict(DEFAULTS)
    for k, v in options.items():
        if k.startswith('__'):
            sk = '__' + _snake(k[2:])
            if sk not in DEBUG_KEYS:
                raise TypeError(f'create_water_sim: unknown debug option {k!r}')
        else:
            sk = k if k in DEFAULTS else _snake(k)
            if sk not in DEFAULTS:
                raise TypeError(f'create_water_sim: unknown option {k!r}')
            if k in ('gridSize', 'worldSize'):                 # three (x, y up, z) -> Blender (x, y, z up)
                v = (v[0], v[2], v[1])
            elif k == 'domainCenter':
                v = (v[0], -v[2], v[1])
        o[sk] = v
    if o.get('__debug_phi') or o.get('__debug_fields'):
        # the engine painted min-phi / |div| / p heatmaps along the view ray; here the raw grids go to OpenVDB
        o['write_grids'] = True
        log('[water3d] __debugPhi/__debugFields: writing <name>_grids_####.vdb (phi, velocity, pressure, '
            'divergence) for inspection instead of the engine\'s heatmap shader')
    if o.get('__bisect'):
        log('[water3d] __bisect is the engine raymarcher\'s draw ladder; the surface here is a mesh (ignored)')
    o['collider_meshes'] = list(o['collider_meshes'] or [])
    sc = scene or bpy.context.scene
    return WaterSim(sc, o, name, cache_dir, log)


def configure_eevee(scene, samples=64):
    """The render settings the water's look needs: ray-traced refraction and reflections on."""
    e = scene.eevee
    e.use_raytracing = True
    e.ray_tracing_method = 'SCREEN'
    e.taa_render_samples = int(samples)
    return scene
