"""eidoblend.sets.wake_another_one.hall.look: the hall's look over its layout. Blender.

    from eidoblend.sets.wake_another_one.hall.look import Look
    lk = Look(layout, sky='sky', trees=True, bake=True).run()     # after build.Layout(...).run(), in the same scene
    gpu_reset(); lk.sky.bake(f, f)                               # the sky, for the camera you render (Hall.bake_sky)

Called by hall.build(). In order:
  materials   every material of the layout is REBUILT IN PLACE under its own name (_mats: layered over CC0 scans fetched
              by ID), so every mesh that used a flat colour now has a layered one; new ones for the new parts
  geometry    plain boxes get bevels, a wear band, baked cavity and UVs in metres (_kit); the racks, the roller tracks,
              the strip lights, the lectern, the pendant, the chain link and the dock are rebuilt with real sections
              (_shell, _machines); the lectern's printer is new (printer_ctl["feed"]). Every empty, every driven
              object, its name, origin and parenting stay as the layout made them
  light       the strip lights as CONTINUOUS rows, and NO STRIP LAMP CASTS A SHADOW (68 shadowed lamps cost about 50 s
              a 1080p frame, unshadowed about 4 s). Over the hero aisle the rows' diffuse light is BAKED (emitting
              boxes under the two rows, read by a fine volume probe: shaded bays, grounded cartons) and the lamps give
              highlights only; everywhere else the lamps light plainly and one wide lamp looks up at the roof. The
              dock's low sun keeps its shadow (warm against the lamps: the camera's balance is in the lights' colours);
              it and everything that moves stay out of the bake. Five mirror probes cover the hall. A thin haze with a
              switch, look_ctl["haze"] (2.4 to 3.5 s a frame)
  outdoors    after the probe bake: the sky family's sky (sky='sky') or a CC0 photo sky (sky='hdri'), seen whole by
              the lens through the door and giving light at sky_fill (0.06: a sky at full strength leaks into the
              hall), and the yard. The sky family's sky is baked for a camera: Hall.bake_sky again for each camera
              (it resets the GPU's draw state the volume probe bake leaves, or the sky would bake black)
  settings    EEVEE with ray tracing, fast GI, motion blur and volumes set for a 248 m hall; depth of field on the
              close cameras
Options (Look(...) keywords): strip 36 (W per metre of row), ribbon 1.3 (the baked rows), far_lamp 0.6 (the plain
lamps), bounce 1.0 (the lamp that looks up), sun 13, sky_gain 2.4 and sky_clamp 12 (the photo sky), sky_fill 0.06,
haze 0.0012, drum_lamp 0.35, exposure 0, samples 32.
"""

import math
import os
import subprocess
import sys
import time
import types

import bpy
from mathutils import Matrix, Vector

from .... import common
from . import _kit as kit
from . import _machines as machines
from . import _mats as mats
from . import _shell as shell
from ._kit import MB

PI = math.pi
RAD = math.radians
SKY = dict(clouds='clear', ambient=0.35)
HDRI = dict(id='syferfontein_18d_clear_puresky', res='4k')
# the render settings the hall is lit for
EEVEE = {'gi_cubemap_resolution': '1024', 'gi_irradiance_pool_size': '512', 'volumetric_tile_size': '16',
         'volumetric_samples': 32, 'volumetric_sample_distribution': 0.85, 'use_volumetric_shadows': False,
         'volumetric_shadow_samples': 32, 'use_volume_custom_range': True, 'fast_gi_method': 'GLOBAL_ILLUMINATION',
         'fast_gi_distance': 1.2, 'use_bokeh_jittered': True, 'motion_blur_max': 64, 'shadow_pool_size': '1024',
         'shadow_ray_count': 2, 'shadow_step_count': 12, 'use_overscan': True, 'overscan_size': 3.0, 'use_raytracing': True,
         'ray_tracing_method': 'SCREEN', 'use_fast_gi': True, 'clamp_surface_indirect': 10.0, 'gi_diffuse_bounces': 3,
         'motion_blur_steps': 1}
RAY = {'resolution_scale': '1', 'screen_trace_thickness': 0.05, 'screen_trace_quality': 0.5, 'trace_max_roughness': 0.5,
       'use_denoise': True, 'denoise_spatial': True, 'denoise_temporal': True, 'denoise_bilateral': True}
DOF = {'cam_pendant': 2.8, 'cam_line_long': 5.6, 'cam_line_long_b': 5.6, 'cam_drums': 4.0, 'cam_cabinet_lock': 2.8,
       'cam_cabinet_window': 4.0, 'cam_sun_tray': 2.8, 'cam_sun_tray_b': 2.8, 'cam_office': 4.0}
# THE COLOUR SCHEME: the machines' white and teal plus one safety colour; nothing bare white, nothing one value. Every
# colour of the hall's painted steel is one of these constants
WHITE = mats.srgb('#d9e0df')
TEAL = mats.srgb('#398b91')
ZINC = (0.60, 0.62, 0.64)
GREASE = (0.022, 0.019, 0.016)
ENAMEL = mats.srgb('#e5dfd2')                             # the equipment's warm off-white enamel: lectern, cabinet, printer
DEEP_TEAL = tuple(c * 0.6 for c in TEAL)                  # the racks' uprights: the machines' teal, darker
YELLOW = mats.srgb('#d6a21f')                             # the safety yellow: crane, guards, barriers, bollards
LINE_YELLOW = (0.60, 0.39, 0.06)                          # the floor lines' traffic paint
HAZARD_BLACK = (0.022, 0.022, 0.024)                      # the black of the black-and-yellow
CHIP_W = dict(amount=0.5, primer=(0.34, 0.35, 0.36), metal=(0.56, 0.57, 0.58), metal_rough=0.34)
# THE CAMERA IS BALANCED TO THE HALL'S LAMPS: the balance is in the LIGHTS' colours, not in the view, so every emitter
# keeps the colour it was made with. Lamps of 4500 K seen by a camera set a little warmer read clean and slightly cool;
# the low sun at the dock (3000 K) reads warm gold beside them
WB_K, LAMP_K, SUN_K = 4460.0, 4500.0, 3000.0


# ======================================================================================================== the post hooks
def upright_holes(g, S, X):
    """a pallet rack upright's punching: two columns of slots at 50 mm on the faces that look along the row's depth"""
    u, v, _w = g.xyz(X['uv'])
    nx = g.math('ABSOLUTE', g.xyz(g.tc('Normal'))[0])
    du = g.math('ABSOLUTE', g.sub(g.math('ABSOLUTE', u), 0.017))
    dv = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', v, 0.05)), 0.5)), 0.05)
    q = g.math('MAXIMUM', g.sub(dv, 0.0075), 0.0)
    dist = g.sub(g.math('SQRT', g.add(g.mul(du, du), g.mul(q, q))), 0.0048)
    hole = g.mul(g.ramp(dist, -0.0004, 0.0004, 1.0, 0.0), g.ramp(nx, 0.85, 0.95))
    rim = g.mul(g.ramp(g.math('ABSOLUTE', dist), 0.0, 0.0016, 1.0, 0.0), g.ramp(nx, 0.85, 0.95))
    S['C'] = g.mixc(hole, S['C'], (0.008, 0.008, 0.009))
    S['R'] = g.mixf(hole, S['R'], 0.9)
    S['M'] = g.mixf(hole, S['M'], 0.0)
    S['R'] = g.mixf(g.mul(rim, 0.6), S['R'], 0.22)                     # the punched edge is burnished
    S['H'] = g.add(S['H'], g.mul(hole, -0.0025))


def roller_wear(g, S, X):
    """a conveyor roller: fine rings turned into it by every carton that ever crossed, the middle run brighter"""
    x, y, z = g.xyz(X['P'])
    rings = g.noise(g.vec(g.mul(x, 420.0), g.mul(y, 5.0), g.mul(z, 5.0)), 1.0, 2.0, 0.5)
    band = g.ramp(g.math('ABSOLUTE', x), 0.30, 0.41, 1.0, 0.0)
    S['R'] = g.add(S['R'], g.ramp(rings, 0.2, 0.8, -0.07, 0.09))
    S['R'] = g.sub(S['R'], g.mul(band, 0.05))
    S['C'] = g.scale(S['C'], g.ramp(band, 0.0, 1.0, 0.93, 1.05, smooth=False))
    S['H'] = g.add(S['H'], g.mul(rings, 0.00001))


def tread(g, S, X):
    """chequer plate: raised lozenges in two directions"""
    u, v, _w = g.xyz(X['uv'])
    a = g.math('SINE', g.mul(g.add(u, v), 2.0 * PI / 0.036))
    b = g.math('SINE', g.mul(g.sub(u, v), 2.0 * PI / 0.036))
    lo = g.ramp(g.mul(a, b), 0.55, 0.8)
    S['H'] = g.add(S['H'], g.mul(lo, 0.0016))
    S['R'] = g.mixf(lo, S['R'], g.mul(S['R'], 0.6))                    # the tops are walked bright
    S['C'] = g.scale(S['C'], g.ramp(lo, 0.0, 1.0, 0.92, 1.12, smooth=False))


def hand_edge(g, S, X):
    """the lectern's top: years of forearms have polished the reader's edge and left a film further up"""
    _x, y, _z = g.xyz(X['P'])
    front = g.mul(g.ramp(y, -0.23, -0.12, 1.0, 0.0), g.ramp(X['n_mid'], 0.2, 0.8, 0.5, 1.0))
    S['R'] = g.mixf(g.mul(front, 0.7), S['R'], 0.16)
    S['C'] = g.scale(S['C'], g.ramp(front, 0.0, 1.0, 1.0, 1.10, smooth=False))


def fork_wear_for(levels):
    def fork_wear(g, S, X):
        """a rack upright: its punching, and its paint knocked off where trucks reach it: the foot, and the hand's
        breadth over each beam level where fork tines and loads go in"""
        upright_holes(g, S, X)
        z = g.xyz(X['P'])[2]
        band = g.ramp(z, 0.02, 0.5, 1.0, 0.0)
        for lv in levels:
            band = g.math('MAXIMUM', band, g.mul(g.ramp(z, lv - 0.02, lv + 0.05), g.ramp(z, lv + 0.1, lv + 0.42, 1.0, 0.0)))
        hit = g.mul(band, g.ramp(g.add(g.mul(g.noise(X['P'], 150.0, 3.0, 0.65), 0.6), g.mul(g.noise(X['P'], 21.0, 2.0, 0.5), 0.55)), 0.52, 0.66))
        bare = g.mul(band, g.ramp(g.noise(X['P'], 44.0, 3.0, 0.6), 0.60, 0.68))
        S['C'] = g.mixc(hit, S['C'], (0.33, 0.34, 0.35))
        S['C'] = g.mixc(bare, S['C'], (0.56, 0.57, 0.58))
        S['R'] = g.mixf(hit, S['R'], 0.6)
        S['R'] = g.mixf(bare, S['R'], 0.34)
        S['M'] = g.mixf(bare, S['M'], 1.0)
    return fork_wear


def hazard(g, S, X):
    """black-and-yellow: diagonal bands 70 mm wide across whatever carries the paint"""
    x, y, z = g.xyz(g.geo('Position'))
    band = g.ramp(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', g.add(g.add(x, y), z), 0.14)), 0.5)), 0.245, 0.255)
    paint = g.sub(1.0, g.clamp(g.mul(S['M'], 4.0))) if isinstance(S['M'], bpy.types.NodeSocket) else 1.0   # not where it is worn to steel
    S['C'] = g.mixc(g.mul(band, paint), S['C'], HAZARD_BLACK)


def balanced(k):
    from ....look import lighting as LT
    a_, b_ = LT.blackbody_rgb(k), LT.blackbody_rgb(WB_K)
    c_ = [a_[i] / b_[i] for i in range(3)]
    return tuple(v / max(c_) for v in c_)


def num(x):
    s = f'{x:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def drv(target, path, expr, variables, index=-1):
    """a SIMPLE-EXPRESSION driver (it evaluates without Python)"""
    fc = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    for old in list(d.variables):
        d.variables.remove(old)
    for vn, vid, vpath in variables:
        v = d.variables.new()
        v.name, v.type = vn, 'SINGLE_PROP'
        v.targets[0].id = vid
        v.targets[0].data_path = vpath
    d.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    if not d.is_simple_expression:
        raise RuntimeError(f'not a simple expression: {expr}')
    return fc


def gpu_reset():
    """the GPU's draw state back to its defaults. A volume probe bake (lightprobe_cache_bake) leaves the depth test on
    (LESS_EQUAL, depth writes on), and the sky family's offscreen bake, which does not set its own, then bakes its camera
    layer black; call this between the two (Hall.bake_sky does)"""
    import gpu
    gpu.state.depth_test_set('NONE')
    gpu.state.depth_mask_set(False)
    gpu.state.blend_set('NONE')
    gpu.state.face_culling_set('NONE')


def hdri_path(fetch=True):
    """the photo sky's .hdr in the shared library (cache/hdris/<id>_<res>/hdri.hdr), fetched once with fetch_hdri.py
    (EIDO_NO_FETCH=1 forbids the download)"""
    d = common.cache_dir('hdris', f"{HDRI['id']}_{HDRI['res']}")
    p = os.path.join(d, 'hdri.hdr')
    if os.path.isfile(p) or not fetch:
        return p
    cmd = [os.environ.get('PYTHON') or ('python' if os.name == 'nt' else 'python3'), os.path.join(common.REPO, 'fetch_hdri.py'),
           HDRI['id'], HDRI['res']]
    if os.environ.get('EIDO_NO_FETCH') == '1':
        raise FileNotFoundError(f'{p} is not in the library; fetch it in that folder with: {" ".join(cmd[1:])}')
    os.makedirs(d, exist_ok=True)
    subprocess.run(cmd, cwd=d, capture_output=True, text=True, creationflags=0x08000000 if sys.platform == 'win32' else 0)
    if not os.path.isfile(p):
        raise FileNotFoundError(f'{p}: fetch_hdri.py {HDRI["id"]} {HDRI["res"]} did not write it')
    return p


# ======================================================================================================== the look
class Look:
    """the look over a built Layout (`lay`, its scene). sky: 'sky' (the sky family's, the default), 'hdri' (the CC0
    photo sky) or None (the layout's world stays); trees: SeedThree trees in the yard; bake: bake the volume probes;
    camera: the camera the sky family's sky is baked for first (default cam_aisle_out); the module's head lists the
    other options. run() -> self; .M (materials), .sky (the Sky to bake again for another camera, or None),
    .report"""

    def __init__(self, lay, sky='sky', trees=True, bake=True, camera=None, log=print, **opt):
        self.lay, self.L, self.SC = lay, lay.L, lay.SC
        self.sky_kind, self.trees, self.bake = sky, trees, bake
        self.camera = camera
        self.log = log
        self.opt = dict(strip=36.0, ribbon=1.3, far_lamp=0.6, bounce=1.0, sun=13.0, sky_gain=2.4, sky_clamp=12.0,
                        sky_fill=0.06, haze=0.0012, drum_lamp=0.35, exposure=0.0, samples=32)
        unknown = set(opt) - set(self.opt)
        if unknown:
            raise TypeError(f'hall look: no option {sorted(unknown)}; the options: {sorted(self.opt)}')
        self.opt.update(opt)
        self.T0 = time.time()
        self.report = {'steps': []}
        self.M = {}
        self.sky = None
        self._models = {}

    def say(self, *a):
        self.log('[look %6.1f s] ' % (time.time() - self.T0) + ' '.join(str(x) for x in a))

    def step(self, what):
        self.say(what)
        self.report['steps'].append([round(time.time() - self.T0, 1), what])

    # ------------------------------------------------------------------------------------------------ helpers
    def new_ob(self, name, data, collection, loc=(0, 0, 0), rz=0.0, parent=None):
        o = bpy.data.objects.new(name, data)
        collection.objects.link(o)
        o.location = loc
        o.rotation_euler = (0, 0, rz)
        if parent is not None:
            o.parent = parent
        return o

    def empty(self, name, loc, collection, parent=None, size=0.08, kind='PLAIN_AXES'):
        o = self.new_ob(name, None, collection, loc, 0.0, parent)
        o.empty_display_type, o.empty_display_size = kind, size
        return o

    @staticmethod
    def swap_mesh(ob, me):
        """a new mesh on an object that keeps its name, origin, parenting and drivers"""
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            nm = old.name
            bpy.data.meshes.remove(old)
            me.name = nm
        return ob

    def import_model(self, asset):
        """the objects of a CC0 Poly Haven model (fetched by ID into the shared library once), in no collection: the
        first call imports it, later calls hand out copies that share its meshes"""
        if asset in self._models:
            twin = {o: o.copy() for o in self._models[asset]}
            for o, c in twin.items():
                if o.parent in twin:
                    c.parent = twin[o.parent]
            return list(twin.values())
        from ....harness import assets
        path = assets.fetch_model_file(asset, res='2k')
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        obs = [o for o in bpy.data.objects if o not in before]
        for o in obs:
            for c in list(o.users_collection):
                c.objects.unlink(o)
        self._models[asset] = obs
        return obs

    def finish_named(self, name, bevel=0.0025, inset=0.014, cavity=0.10, ground=None):
        me = bpy.data.meshes.get(name)
        if me is None:
            self.say('   (no mesh named %s: skipped)' % name)
            return
        kit.finish(me, bevel=bevel, inset=inset, cavity=cavity, ground=ground, log=self.say)

    # ------------------------------------------------------------------------------------------------ run
    def run(self):
        lay = self.lay
        mats.setup(os.path.dirname(bpy.data.filepath) if bpy.data.filepath else None, self.say)
        C = lay.C
        self.C_LOOK = bpy.data.collections.new('look_assets')              # what the look's instancers show (not drawn)
        C['assets'].children.link(self.C_LOOK)
        self.C_AIR = bpy.data.collections.new('look_light_and_air')        # the strip lights, the probes, the haze
        C['hall'].children.link(self.C_AIR)
        self.step('1. materials: every layout material rebuilt in place, layered over a scan')
        self.materials()
        self.X = types.SimpleNamespace(
            M=self.M, L=self.L, OBJ=bpy.data.objects, MESH=bpy.data.meshes, C_SHELL=C['hall_shell'], C_RACKS=C['racks'],
            C_MODULE=C['line_module'], C_MACH=C['machinery'], C_DOCK=C['dock'], C_LOOK=self.C_LOOK, C_CAB=C['meter_cabinet'],
            new_ob=self.new_ob, swap_mesh=self.swap_mesh, import_model=self.import_model, say=self.say,
            HX0=lay.HX0, HX1=lay.HX1, HY0=lay.HY0, HY1=lay.HY1, RZ=self.L['hall']['roof_z'], WT=self.L['hall']['wall_t'],
            trees=[])
        self.step('2a. the shell: outer masses, purlins, the floor\'s lines, the walls, the roof\'s deck')
        self.shell()
        self.step('2b. the racks: punched uprights, braced frames on bolted footplates, step beams on connectors, decks')
        self.racks()
        self.step('2c. the roller tracks: turned rollers on hexagon axles in bearing caps, side frames, screwed kerbs')
        self.tracks()
        self.step('2d. the strip lights: continuous rows of 1.5 m luminaires on hangers')
        self.strip_lights()
        self.step('2e. the station: the lectern, its printer, the pendant')
        self.station()
        self.step('2f. the returns cage: woven chain link')
        self.chain_link()
        self.step('2g. the dock: the door, the yard, the services')
        door = shell.dock_door(self.X)
        shell.yard(self.X, trees=self.trees)
        shell.services(self.X, door)
        bpy.data.objects['dock_threshold'].data.materials[0] = self.M['tread_plate']
        self.step('2h. the machines, the cartons and every other built mesh')
        self.the_rest()
        self.step('3. light: continuous strip rows, the dock sun, the outdoors, probes, haze')
        self.light()
        self.step('4. render settings, depth of field, the printer\'s camera')
        self.settings()
        if self.bake:
            self.step('5. baking the volume probes (the haze, the sun and what moves left out)')
            self.bake_probes()
        # the outdoors after the bake: the probes need no sky (the bake-only blind closes the door)
        self.step('6. the outdoors: %s' % self.sky_kind)
        self.outdoors()
        if self.sky is not None:
            cam = self.camera or self.SC.camera
            self.SC.camera = cam
            gpu_reset()
            self.sky.bake(self.SC.frame_current, self.SC.frame_current, log=lambda *m: None)
        self.report['seconds'] = round(time.time() - self.T0, 1)
        self.say('the look:', self.report.get('light', {}), self.report['seconds'], 's')
        return self

    # ------------------------------------------------------------------------------------------------ 1. materials
    def materials(self):
        L, M = self.L, self.M
        lay = self.lay
        lay_mats = mats.layered
        M['machine_white'] = lay_mats('machine_white', 'Metal049A', tile=0.55, tint=ENAMEL, rough=0.36, chips=CHIP_W, dirt=0.65,
                                      dust=0.32, scratches=0.35, smudges=0.3)
        M['machine_teal'] = lay_mats('machine_teal', 'Metal049A', tile=0.55, tint=TEAL, rough=0.36,
                                     chips=dict(amount=0.55, primer=(0.40, 0.43, 0.42), metal=(0.56, 0.57, 0.58)), dirt=0.65,
                                     dust=0.35, scratches=0.4, smudges=0.3)
        M['steel_galv'] = lay_mats('steel_galv', 'Metal049A', tile=0.5, tint=ZINC, rough=0.37, metal=1.0, normal=0.35, spangle=1.0,
                                   polish=0.6, dirt=0.65, dust=0.35, scratches=0.25, smudges=0.2, fine=0.5)
        M['steel_dark'] = lay_mats('steel_dark', 'Metal027', tile=0.45, rough=0.48, metal='map', normal=0.6, polish=0.7, dirt=0.5,
                                   dust=0.45, scratches=0.35, smudges=0.35, fine=0.5)
        M['rubber_black'] = lay_mats('rubber_black', 'Rubber004', tile=0.28, tint=(0.020, 0.020, 0.021), rough=0.74, normal=0.8,
                                     dirt=0.4, dirt_col=(0.10, 0.09, 0.08), dust=0.5, scratches=0.15, smudges=0.4, world_var=False)
        # the racks: uprights deep teal, chipped to primer and steel at the feet and where fork tines touch; beams and
        # decks pale galvanised, so the cartons stay the heroes
        M['rack_upright'] = lay_mats('rack_upright', 'Metal049A', tile=0.5, tint=DEEP_TEAL, rough=0.40, normal=0.35,
                                     chips=dict(amount=0.5, primer=(0.33, 0.34, 0.35), metal=(0.56, 0.57, 0.58)), dirt=0.7, dust=0.3,
                                     scratches=0.4, smudges=0.15, post=fork_wear_for(L['racks']['levels_z']))
        M['rack_beam'] = lay_mats('rack_beam', 'Metal049A', tile=0.5, tint=(0.66, 0.68, 0.70), rough=0.38, metal=1.0, normal=0.35,
                                  spangle=0.8, polish=0.5, dirt=0.7, dust=0.6, scratches=0.4, smudges=0.2)
        M['cabinet_grey'] = lay_mats('cabinet_grey', 'Metal049A', tile=0.5, tint=ENAMEL, rough=0.42,
                                     chips=dict(amount=0.16, primer=(0.42, 0.40, 0.36)), dirt=0.7, dust=0.6, scratches=0.4, smudges=0.5)
        M['drum_white'] = lay_mats('drum_white', 'Plastic010', tile=0.2, tint=(0.78, 0.775, 0.74), rough=0.40, normal=0.4, var=0.4,
                                   world_var=False, dirt=0.8, dust=0.0, scratches=0.25, smudges=0.3)
        M['drum_ink'] = lay_mats('drum_ink', 'Plastic010', tile=0.2, tint=(0.012, 0.012, 0.013), rough=0.5, normal=0.3, var=0.3,
                                 world_var=False, dirt=0.0, dust=0.0, scratches=0.2, smudges=0.2)
        M['plastic_white'] = lay_mats('plastic_white', 'Plastic010', tile=0.22, tint=(0.76, 0.73, 0.66), rough=0.40, normal=0.5,
                                      polish=0.5, dirt=0.7, dust=0.45, scratches=0.35, smudges=0.6, fine=0.44)
        M['plastic_teal'] = lay_mats('plastic_teal', 'Plastic010', tile=0.22, tint=TEAL, rough=0.42, normal=0.5, polish=0.9,
                                     dirt=0.8, dust=0.1, scratches=0.5, smudges=0.9, world_var=False, fine=0.5)
        M['steel_brushed'] = lay_mats('steel_brushed', 'Metal009', tile=0.3, rough=0.30, metal=1.0, normal=0.5, polish=0.9, dirt=0.6,
                                      dust=0.12, scratches=0.5, smudges=0.7, world_var=False, post=hand_edge)
        M['steel_zinc'] = lay_mats('steel_zinc', 'Metal009', tile=0.3, tint=(0.66, 0.67, 0.68), rough=0.27, metal=1.0, normal=0.25,
                                   var=0.0, world_var=False, polish=0.5, dirt=0.85, dirt_col=GREASE, dust=0.0, scratches=0.0,
                                   smudges=0.0, grain=0.0, post=roller_wear)
        M['track_pit'] = lay_mats('track_pit', 'Concrete034', '2k', tile=1.2, tint=(0.085, 0.083, 0.080), rough=0.86, normal=0.8,
                                  var=0.0, world_var=False, dirt=0.0, dust=0.0, scratches=0.0, smudges=0.0, grain=0.0)
        M['tread_plate'] = lay_mats('tread_plate', 'Metal049A', tile=0.5, tint=ZINC, rough=0.40, metal=1.0, normal=0.3, spangle=0.6,
                                    polish=0.7, dirt=0.8, dust=0.5, scratches=0.5, smudges=0.2, post=tread)
        M['chain_galv'] = lay_mats('chain_galv', 'Metal049A', tile=0.4, tint=ZINC, rough=0.36, metal=1.0, normal=0.2, spangle=0.4,
                                   polish=0.0, dirt=0.0, dust=0.0, scratches=0.0, smudges=0.0)
        M['yard_concrete'] = lay_mats('yard_concrete', 'Concrete034', '2k', tile=2.4, rough=0.8, normal=1.0, dirt=0.6, dust=0.4,
                                      scratches=0.0, smudges=0.0)
        M['paper_placeholder'] = lay_mats('paper_placeholder', 'Paper001', tile=0.3, tint=(0.80, 0.78, 0.72), rough=0.7, normal=0.7,
                                          var=0.4, world_var=False, dirt=0.25, dust=0.0, scratches=0.0, smudges=0.2)
        # the cartons: a white coated board, its insert moulded fibre
        M['carton_board'] = lay_mats('carton_board', 'Paper001', tile=0.45, tint=(0.70, 0.68, 0.62), rough=0.62, normal=0.5,
                                     var=0.5, world_var=False, dirt=0.4, dust=0.35, scratches=0.0, smudges=0.3)
        M['carton_insert'] = lay_mats('carton_insert', 'Paper001', tile=0.25, tint=(0.42, 0.38, 0.31), rough=0.85, normal=1.0,
                                      var=0.6, world_var=False, dirt=0.3, dust=0.2, scratches=0.0, smudges=0.0)
        lanes_floor = {'fixed': [(2.95, 1.35)]}
        LANES = lay.LANES
        if len(LANES) > 1:
            lanes_floor['periodic'] = (LANES[1] + 3.0, abs(LANES[1] - LANES[2]) if len(LANES) > 2 else 7.8, 1.35, -7.6)
        lanes_floor['cross'] = [(lay.HX0 + 2.0, 5.9, 18.3, 2.3)]          # the cross aisle between the racks' ends and the dock wall
        racks_x = [(-6.5, -4.3, [-6.5, -4.3]), (6.2, 7.3, [6.2]), (-71.5, -70.4, [-70.4])]
        M['hall_concrete'] = mats.floor('hall_concrete', L, racks_x, lanes_floor)
        M['floor_line_paint'] = mats.floor_paint('floor_line_paint', colour=LINE_YELLOW)
        M['floor_hazard_paint'] = mats.floor_paint('floor_hazard_paint', colour=LINE_YELLOW, stripes=0.30)
        M['hall_wall_panel'] = mats.wall_liner('hall_wall_panel')
        M['hall_roof'] = mats.wall_liner('hall_roof', lap_v=-1000.0, scuff=False, value=0.66)
        M['safety_yellow'] = lay_mats('safety_yellow', 'Metal049A', tile=0.5, tint=YELLOW, rough=0.42,
                                      chips=dict(amount=0.8, primer=(0.30, 0.30, 0.31), metal=(0.50, 0.51, 0.52)), dirt=0.8, dust=0.35,
                                      scratches=0.6, smudges=0.3)
        M['column_paint'] = lay_mats('column_paint', 'Metal049A', tile=0.5, tint=(0.56, 0.585, 0.60), rough=0.45, chips=dict(amount=0.35),
                                     dirt=0.6, dust=0.45, scratches=0.3, smudges=0.2)
        M['wall_concrete'] = lay_mats('wall_concrete', 'Concrete034', '4k', tile=2.4, tint=(0.68, 0.68, 0.665), rough=0.62, normal=0.3,
                                      dirt=0.7, dust=0.25, scratches=0.0, smudges=0.3, post=mats.dado)
        M['plastic_grey'] = lay_mats('plastic_grey', 'Plastic010', tile=0.3, tint=(0.36, 0.38, 0.40), rough=0.45, normal=0.5, dirt=0.6,
                                     dust=0.4, scratches=0.3, smudges=0.4)
        M['belt_webbing'] = lay_mats('belt_webbing', 'Rubber004', tile=0.06, tint=(0.035, 0.035, 0.04), rough=0.8, normal=1.0, var=0.5,
                                     world_var=False, dirt=0.3, dust=0.0, scratches=0.0, smudges=0.0)
        M['plate_alu'] = lay_mats('plate_alu', 'Metal009', tile=0.3, tint=(0.74, 0.75, 0.76), rough=0.36, metal=0.5, normal=0.4, var=0.4,
                                  world_var=False, polish=0.3, dirt=0.5, dust=0.0, scratches=0.4, smudges=0.5, fine=0.5)
        M['brass'] = lay_mats('brass', 'Metal009', tile=0.2, tint=(0.78, 0.57, 0.22), rough=0.30, metal=1.0, normal=0.4, var=0.4,
                              world_var=False, polish=0.6, dirt=0.6, dust=0.0, scratches=0.6, smudges=0.6, fine=0.4)
        # the station is seen from a hand's width: the machines' paint, hardly chipped (a lectern is not a truck's target)
        M['station_white'] = lay_mats('station_white', 'Metal049A', tile=0.55, tint=ENAMEL, rough=0.36, chips=dict(CHIP_W, amount=0.08),
                                      dirt=0.6, dust=0.3, scratches=0.4, smudges=0.45)
        M['curtain_white'] = lay_mats('curtain_white', 'Metal049A', tile=0.5, tint=(0.64, 0.66, 0.68), rough=0.36, metal=1.0, normal=0.35,
                                      spangle=0.7, polish=0.5, dirt=0.8, dust=0.5, scratches=0.5, smudges=0.3)   # the shutter's laths
        M['hazard_yellow'] = lay_mats('hazard_yellow', 'Metal049A', tile=0.5, tint=YELLOW, rough=0.42,
                                      chips=dict(amount=0.8, primer=(0.30, 0.30, 0.31), metal=(0.50, 0.51, 0.52)), dirt=0.8, dust=0.35,
                                      scratches=0.6, smudges=0.3, post=hazard)
        M['cable_grey'] = lay_mats('cable_grey', 'Rubber004', tile=0.28, tint=(0.33, 0.34, 0.35), rough=0.6, normal=0.6, dirt=0.4,
                                   dust=0.6, scratches=0.1, smudges=0.3, world_var=False)
        M['trailer_white'] = lay_mats('trailer_white', 'Metal049A', tile=0.8, tint=(0.66, 0.67, 0.68), rough=0.40, chips=dict(amount=0.3),
                                      dirt=0.8, dust=0.3, scratches=0.4, smudges=0.4)
        M['yard_field'] = mats.field('yard_field')
        M['dock_apron'] = mats.yard('dock_apron')
        from ....look import lighting as LT
        self.LAMP_RGB, self.SUN_RGB = balanced(LAMP_K), balanced(SUN_K)
        M['strip_light_glow'] = mats.emitter('strip_light_glow', self.LAMP_RGB, 7.0, falloff=(0, 0.029))
        M['office_frosted_glow'] = mats.frosted_office('office_frosted_glow', LT.blackbody_rgb(3300.0), 2.6)
        M['glass_placeholder'] = mats.glass('glass_placeholder')
        M['printer_led'] = mats.emitter('printer_led', (0.35, 1.0, 0.75), 3.0, body=(0.2, 0.6, 0.45))
        self.report['materials'] = sorted(M)
        self.say('materials:', len(M), 'images:', len(bpy.data.images))

    # ------------------------------------------------------------------------------------------------ 2a. the shell
    def shell(self):
        lay, M, L = self.lay, self.M, self.L
        HX0, HX1, HY0, HY1 = lay.HX0, lay.HX1, lay.HY0, lay.HY1
        WT_, RZ = L['hall']['wall_t'], L['hall']['roof_z']
        D = L['dock']
        CS = lay.C['hall_shell']
        mb = MB()
        TH = 3.0                                                # thick masses outside the 0.3 m shell: nothing sees them
        mb.span((HX0 - TH, HY0 - TH, -TH), (HX1 + TH, HY1 + WT_, -0.14))                              # the ground under the slab
        mb.span((HX0 - TH, HY0 - TH, -0.14), (HX0 - WT_, HY1 + WT_, RZ + TH))                         # west
        mb.span((HX1 + WT_, HY0 - TH, -0.14), (HX1 + TH, HY1 + TH, RZ + TH))                          # east
        mb.span((HX0 - WT_, HY0 - TH, -0.14), (HX1 + WT_, HY0 - WT_, RZ + TH))                        # the far end
        mb.span((HX0 - WT_, HY0 - WT_, RZ + 0.25), (HX1 + WT_, HY1 + WT_, RZ + TH))                   # over the roof
        # behind the dock wall the hall is closed too, but for a TUNNEL in front of the door: the sun comes down it from +Y,
        # 10 degrees toward +X and 17.8 degrees up, so the tunnel is 1.2 m wider than the door on the east and 1.3 m higher
        mb.span((HX0 - TH, HY1 + WT_, -0.14), (D['door_x'][0] - 2.5, HY1 + TH, RZ + TH))              # west of the door
        mb.span((D['door_x'][1] + 1.2, HY1 + WT_, -0.14), (HX1 + WT_, HY1 + TH, RZ + TH))             # east of it
        mb.span((D['door_x'][0] - 2.5, HY1 + WT_, D['door_h'] + 1.3), (D['door_x'][1] + 1.2, HY1 + TH, RZ + TH))   # over it
        mass = self.new_ob('hall_outer_mass', mb.mesh('hall_outer_mass', [M['yard_concrete']]), CS)
        mass['note'] = 'thick masses outside the hall\'s shell and under its floor: the volume probe\'s outermost samples end in them'
        mass.visible_camera = False
        mb = MB()
        x = HX1 - 1.2
        while x > HX0 + 0.5:                                    # purlins under the deck, along the hall
            mb.prism([(-0.03, -0.20), (0.03, -0.20), (0.03, -0.185), (0.004, -0.185), (0.004, -0.012), (0.03, -0.012), (0.03, 0.0), (-0.03, 0.0)],
                     HY0 + 0.05, HY1 - 0.05, 'y', 0, at=(x, RZ))
            x -= 2.4
        pur = self.new_ob('hall_purlins', mb.mesh('hall_purlins', [M['steel_galv']]), CS)
        kit.finish(pur.data, bevel=0.002, inset=0.01, cavity=0.0, log=self.say)
        for nm in ('hall_floor', 'hall_walls', 'hall_roof', 'dock_apron', 'meter_window_glass'):
            kit.uv_metres(bpy.data.meshes[nm])
        LN, GA = L['line'], L['gantry']
        LE = LN['lectern']
        MK = LN['marks']
        segs = [((x, GA['rail_y'][0]), (x, GA['rail_y'][1]), MK['line_w']) for x in (MK['x_a'], MK['x_b'], GA['rail_x'][0] - 0.25)]
        sx_, sy_ = LE['x'], LE['y'] - LE['stand_back']                                               # the station's standing place
        segs += [((sx_ - 0.35, sy_ - 0.28), (sx_ + 0.35, sy_ - 0.28), 0.04), ((sx_ - 0.35, sy_ + 0.28), (sx_ + 0.35, sy_ + 0.28), 0.04),
                 ((sx_ - 0.33, sy_ - 0.30), (sx_ - 0.33, sy_ + 0.30), 0.04), ((sx_ + 0.33, sy_ - 0.30), (sx_ + 0.33, sy_ + 0.30), 0.04)]
        self.swap_mesh(bpy.data.objects['line_floor_lines'], self.painted_lines('line_floor_lines_new', segs, M['floor_line_paint']))
        # black-and-yellow at the dock's edge: a band across the door inside the threshold, broken where the main track runs out
        MX, MHW = lay.MX, lay.MHW
        ye = HY1 - 0.55
        edge = [((D['door_x'][0] + 0.05, ye), (MX - MHW - 0.09, ye), 0.30), ((MX + MHW + 0.09, ye), (D['door_x'][1] - 0.05, ye), 0.30)]
        self.new_ob('dock_edge_hazard', self.painted_lines('dock_edge_hazard', edge, M['floor_hazard_paint']), lay.C['dock'])
        shell.walls(self.X)

    @staticmethod
    def painted_lines(name, segs, material, z=0.002):
        """floor lines as a mesh whose UV says where the paint's edges are (_mats.floor_paint): segs [((x0, y0), (x1, y1),
        width)]; each is two strips, edge to middle to edge; UV = (metres in from the nearer edge, metres along)"""
        verts, faces, uvs = [], [], []
        for a, b, w in segs:
            A, B = Vector((a[0], a[1], z)), Vector((b[0], b[1], z))
            d = B - A
            ln = d.length
            d.normalize()
            n = Vector((-d.y, d.x, 0.0))
            n0 = len(verts)
            for t, v in ((A, 0.0), (B, ln)):
                for s, u in ((-0.5, 0.0), (0.0, w / 2), (0.5, 0.0)):
                    verts.append(tuple(t + n * (s * w)))
                    uvs.append((u, v))
            faces += [(n0, n0 + 3, n0 + 4, n0 + 1), (n0 + 1, n0 + 4, n0 + 5, n0 + 2)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        layer = me.uv_layers.new(name='UVMap')
        for lp in me.loops:
            layer.data[lp.index].uv = uvs[lp.vertex_index]
        me.materials.append(material)
        me.update()
        return me

    # ------------------------------------------------------------------------------------------------ 2b. the racks
    def racks(self):
        lay, M, RK = self.lay, self.M, self.L['racks']
        DEPTH, BAY, POST_H = RK['depth'], RK['bay'], RK['post_h']
        RMATS = [M['rack_upright'], M['rack_beam'], M['steel_galv']]
        mb = MB()
        for xc in (-0.045, -DEPTH + 0.045):
            mb.box((xc, 0.0, 0.006 + (POST_H - 0.006) / 2), (0.09, 0.07, POST_H - 0.006), 0)           # the upright
            mb.box((xc, 0.0, 0.003), (0.17, 0.125, 0.006), 2)                                        # its footplate
            for sx in (-0.064, 0.064):
                mb.bolt((xc + sx, 0.0, 0.0105), 0.011, 0.009, 'z', 2)                                # anchors
                mb.cyl((xc + sx, 0.0, 0.019), 0.005, 0.012, 'z', 8, 2)                               # the stud above the nut
            mb.box((xc, 0.0, POST_H + 0.002), (0.094, 0.074, 0.004), 2)                              # a cap
        SPAN = DEPTH - 0.18
        ZB = (0.35, 1.3, 2.9, 4.5)
        for z in ZB:                                                                                 # horizontals (channels)
            mb.box((-DEPTH / 2, -0.012, z), (SPAN, 0.022, 0.04), 2)
            for xc in (-0.09 - 0.012, -DEPTH + 0.09 + 0.012):
                mb.bolt((xc, -0.012 - 0.015, z), 0.007, 0.006, 'y', 2, washer=False)
        for i in range(len(ZB) - 1):                                                                 # diagonals, turn about
            dz = ZB[i + 1] - ZB[i] - 0.06
            ln = math.hypot(SPAN, dz)
            ang = math.atan2(dz, SPAN) * (1 if i % 2 == 0 else -1)
            mb.box((-DEPTH / 2, 0.012, (ZB[i] + ZB[i + 1]) / 2), (ln, 0.022, 0.035), 2, ry=-ang)
        frame_me = mb.mesh('rack_frame', RMATS)
        kit.finish(frame_me, bevel=0.002, inset=0.012, cavity=0.08, ground=0.0, log=self.say)
        frame_ob = self.new_ob('asset_rack_frame', frame_me, self.C_LOOK)
        mb = MB()
        for zt in RK['levels_z']:
            for side, xa, xb, xf in ((1, -0.055, -0.005, 0.0), (-1, -DEPTH + 0.005, -DEPTH + 0.055, -DEPTH)):
                mb.span((xa, 0.037, zt - 0.10), (xb, BAY - 0.037, zt), 1)                             # the beam
                xl = xa - 0.014 if side > 0 else xb                                                  # the ledge its deck sits on
                mb.span((xl, 0.045, zt - 0.046), (xl + 0.014, BAY - 0.045, zt - 0.026), 1)
                zlo = max(zt - 0.195, 0.012)                                                          # (the lowest beams sit near the floor)
                for ya, yb, ys in ((0.0015, 0.047, 0.035), (BAY - 0.047, BAY - 0.0015, BAY - 0.039)):   # connectors at both ends
                    mb.span((xf - 0.0045 * (side < 0), ya, zlo), (xf + 0.0045 * (side > 0), yb, zt + 0.012), 1)
                    mb.span((min(xa, xf), ys, zlo), (max(xb, xf), ys + 0.004, zt + 0.012), 1)
                    ym = (ya + yb) / 2
                    for zr in (zt - 0.045, zt - 0.145):                                               # hook rivets
                        if zr < zlo + 0.012:
                            continue
                        mb.cyl((xf + side * 0.0065, ym, zr), 0.007, 0.004, 'x', 10, 2)
                    mb.cyl((xf + side * 0.012, ym, zt - 0.095), 0.004, 0.022, 'x', 8, 2)                # the safety pin
                    mb.cyl((xf + side * 0.022, ym, zt - 0.102), 0.0028, 0.016, 'z', 6, 2)               # its bent end
            w = (BAY - 0.09) / 3                                                                     # three deck panels a bay
            for k in range(3):
                mb.span((-DEPTH + 0.057, 0.045 + w * k + 0.0015, zt - 0.026), (-0.057, 0.045 + w * (k + 1) - 0.0015, zt - 0.0012), 2)
                mb.span((-DEPTH + 0.057, 0.045 + w * k + 0.0015, zt - 0.05), (-DEPTH + 0.059, 0.045 + w * (k + 1) - 0.0015, zt - 0.026), 2)
        bay_me = mb.mesh('rack_bay', RMATS)
        kit.finish(bay_me, bevel=0.0018, inset=0.011, cavity=0.07, log=self.say)
        bay_ob = self.new_ob('asset_rack_bay', bay_me, self.C_LOOK)
        n_frames = n_bays = 0
        guard_rows = []
        for row in RK['rows']:
            y_lo, y_hi = max(row['y'][0], lay.HY0 + 1.0), row['y'][1]
            if row['face_x'] < lay.HX0:
                continue
            sgn = 1 if row['faces'] == '+x' else -1
            fx = row['face_x']
            m0, m1 = math.ceil((y_lo + 0.6) / BAY), math.floor((y_hi + 0.6) / BAY)
            ys = [-0.6 + BAY * m for m in range(m0, m1 + 1)]
            kit.instance_on_points('rack_%s_frames' % row['name'], [(fx, y, 0.0) for y in ys], frame_ob, lay.C['racks'], 0.0 if sgn > 0 else PI)
            kit.instance_on_points('rack_%s_bays' % row['name'], [(fx, y if sgn > 0 else y + BAY, 0.0) for y in ys[:-1]], bay_ob,
                                   lay.C['racks'], 0.0 if sgn > 0 else PI)
            guard_rows.append((row['name'], [(fx, y, 0.0) for y in ys], 0.0 if sgn > 0 else PI))
            n_frames += len(ys)
            n_bays += len(ys) - 1
        shell.guards(self.X, guard_rows)
        old = bpy.data.objects['rack_frames']
        self.swap_mesh(old, bpy.data.meshes.new('rack_frames_replaced'))
        old['note'] = 'the layout\'s plain frames, replaced by rack_<row>_frames and rack_<row>_bays (instances of look_assets)'
        self.report['racks'] = {'frames': n_frames, 'bays': n_bays, 'frame_faces': len(frame_me.polygons), 'bay_faces': len(bay_me.polygons)}
        self.say('racks:', self.report['racks'])

    # ------------------------------------------------------------------------------------------------ 2c. the tracks
    def tracks(self):
        lay, M, L = self.lay, self.M, self.L
        T = L['line']['track']
        MT = L['main_track']
        RR, RL = T['roller_d'] / 2, (2 * T['half_width']) - 0.08
        mb = MB()
        mb.cyl((0, 0, 0), RR, RL, 'x', 28, 0)
        for s in (-1, 1):
            mb.cyl((s * (RL / 2 + 0.003), 0, 0), RR * 0.80, 0.006, 'x', 20, 1)
            mb.cyl((s * (RL / 2 + 0.013), 0, 0), 0.0075, 0.016, 'x', 6, 2)
        roller_me = mb.mesh('roller', [M['steel_zinc'], M['rubber_black'], M['steel_galv']])
        kit.finish(roller_me, bevel=0.0015, inset=0.012, cavity=0.03, log=self.say)
        roller_ob = self.new_ob('asset_roller', roller_me, self.C_LOOK)
        TMATS = [M['steel_galv'], M['track_pit'], M['steel_dark']]

        def track(mb, px, py, x0, x1, y0, y1, axis, gap=None):
            """the layout's flush roller track with real parts: the pit (open sheets: the detail pass leaves them), kerbs
            screwed to the floor, the inner frames the axles sit in; the rollers are points for the instancers (px:
            rollers lying along x, py: along y)"""
            d, r, p = T['pit_depth'], T['roller_d'] / 2, T['roller_pitch']
            cw, ch = T['curb_w'], T['curb_h']
            mb.quad([(x0, y0, -d), (x1, y0, -d), (x1, y1, -d), (x0, y1, -d)], 1)
            mb.quad([(x0, y0, 0), (x1, y0, 0), (x1, y0, -d), (x0, y0, -d)], 1)
            mb.quad([(x1, y0, 0), (x1, y1, 0), (x1, y1, -d), (x1, y0, -d)], 1)
            mb.quad([(x1, y1, 0), (x0, y1, 0), (x0, y1, -d), (x1, y1, -d)], 1)
            mb.quad([(x0, y1, 0), (x0, y0, 0), (x0, y0, -d), (x0, y1, -d)], 1)
            if axis == 'y':
                k = math.floor((y0 + r) / p - 0.5) + 1
                while (k + 0.5) * p <= y1 - r - 0.004:
                    px.append(((x0 + x1) / 2, (k + 0.5) * p, -r))
                    k += 1
                for xs, side in ((x0 - cw / 2, 0), (x1 + cw / 2, 1)):
                    segs = [(y0, y1)]
                    if gap and side == 0:
                        segs = [(y0, gap[0]), (gap[1], y1)]
                    for a, b in segs:
                        if b - a > 0.01:
                            mb.span((xs - cw / 2, a, 0), (xs + cw / 2, b, ch), 0)
                            yy = math.ceil((a + 0.06) / 0.3) * 0.3 - 0.15
                            while yy < b - 0.05:
                                if yy > a + 0.05:
                                    mb.cyl((xs, yy, ch + 0.0006), 0.0065, 0.0016, 'z', 12, 2)
                                yy += 0.3
                for xi in (x0 + 0.010, x1 - 0.010):                                # the frames that carry the axles
                    mb.span((xi - 0.006, y0 + 0.003, -0.072), (xi + 0.006, y1 - 0.003, -0.004), 2)
            else:
                k = math.floor((x0 + r) / p - 0.5) + 1
                while (k + 0.5) * p <= x1 - r - 0.004:
                    py.append(((k + 0.5) * p, (y0 + y1) / 2, -r))
                    k += 1
                for ys in (y0 - cw / 2, y1 + cw / 2):
                    mb.span((x0, ys - cw / 2, 0), (x1, ys + cw / 2, ch), 0)
                    xx = math.ceil((x0 + 0.06) / 0.3) * 0.3 - 0.15
                    while xx < x1 - 0.05:
                        if xx > x0 + 0.05:
                            mb.cyl((xx, ys, ch + 0.0006), 0.0065, 0.0016, 'z', 12, 2)
                        xx += 0.3
                for yi in (y0 + 0.010, y1 - 0.010):
                    mb.span((x0 + 0.003, yi - 0.006, -0.072), (x1 - 0.003, yi + 0.006, -0.004), 2)

        def track_object(ob, build, collection, parent=None):
            mb, px, py = MB(), [], []
            build(mb, px, py)
            me = mb.mesh(ob.name + '_new', TMATS)
            kit.finish(me, bevel=0.002, inset=0.012, cavity=0.06, log=self.say)
            self.swap_mesh(ob, me)
            if px:
                kit.instance_on_points(ob.name + '_rollers', px, roller_ob, collection, 0.0, parent)
            if py:
                kit.instance_on_points(ob.name + '_rollers_across', py, roller_ob, collection, PI / 2, parent)
            return len(px) + len(py)

        OBJ = bpy.data.objects
        hw = T['half_width']
        MX, MHW, MY0 = lay.MX, lay.MHW, lay.MY0
        n_roll = track_object(OBJ['line_track'], lambda mb, px, py: track(mb, px, py, -hw, hw, T['y0'], T['y1'], 'y', gap=(-hw, hw)),
                              lay.C['line_module'])

        def main_tracks(mb, px, py):
            track(mb, px, py, MX - MHW, MX + MHW, MY0, MT['y_turn'] + MHW, 'y')
            track(mb, px, py, MT['x_end'] - 0.6, MX - MHW, MT['y_turn'] - MHW, MT['y_turn'] + MHW, 'x')
            for _n, lane, _r, _x, Y0 in lay.LINES:
                if lane == 0:
                    track(mb, px, py, MX + MHW, -hw, Y0 - hw, Y0 + hw, 'x')

        n_roll += track_object(OBJ['main_track'], main_tracks, lay.C['machinery'])
        n_roll += track_object(OBJ['inbound_track'], lambda mb, px, py: track(mb, px, py, -hw, hw, MY0, T['y0'], 'y'), lay.C['machinery'])
        self.report['rollers'] = {'on_the_hero_and_main_tracks': n_roll, 'faces_each': len(roller_me.polygons)}

    # ------------------------------------------------------------------------------------------------ 2d. strip lights
    def strip_lights(self):
        lay, M, H = self.lay, self.M, self.L['hall']
        LZ, RZ = H['lights_z'], H['roof_z']
        MOD = 1.5
        mb = MB()
        mb.prism([(-0.036, 0.0), (0.036, 0.0), (0.036, 0.034), (0.022, 0.068), (-0.022, 0.068), (-0.036, 0.034)], -MOD / 2 + 0.002, MOD / 2 - 0.002, 'y', 0)
        mb.span((-0.029, -MOD / 2 + 0.012, -0.011), (0.029, MOD / 2 - 0.012, 0.0005), 1)                 # the opal lens
        for s in (-1, 1):
            mb.span((-0.038, s * (MOD / 2 - 0.008) - 0.006, -0.012), (0.038, s * (MOD / 2 - 0.008) + 0.006, 0.07), 0)   # end caps
        lum_me = mb.mesh('luminaire', [M['plastic_white'], M['strip_light_glow']])
        kit.finish(lum_me, bevel=0.0025, inset=0.008, cavity=0.03, log=self.say)
        lum_ob = self.new_ob('asset_luminaire', lum_me, self.C_LOOK)
        mb = MB()
        mb.cyl((0, 0, (RZ - 0.2 - LZ - 0.07) / 2 + 0.07), 0.0025, RZ - 0.2 - LZ - 0.07, 'z', 6, 0)
        mb.box((0, 0, 0.078), (0.05, 0.03, 0.016), 0)
        hang_ob = self.new_ob('asset_luminaire_hanger', mb.mesh('luminaire_hanger', [M['steel_galv']]), self.C_LOOK)
        kit.uv_metres(hang_ob.data)
        self.LIGHT_ROWS = [x for x in H['light_rows_x'] if not (x < lay.HX0 or (lay.small and x < lay.LANES[-1] - 4))]
        lum_pts, hang_pts = [], []
        N_MOD = int((lay.HY1 - 1.0 - (lay.HY0 + 1.0)) // MOD)
        self.ROW_Y1 = lay.HY1 - 1.0
        self.ROW_Y0 = self.ROW_Y1 - N_MOD * MOD
        for x in self.LIGHT_ROWS:
            for k in range(N_MOD):
                lum_pts.append((x, self.ROW_Y1 - MOD * (k + 0.5), LZ))
                if k % 2 == 0:
                    hang_pts.append((x, self.ROW_Y1 - MOD * (k + 0.5), LZ))
        kit.instance_on_points('strip_light_rows', lum_pts, lum_ob, lay.C['hall_shell'])
        kit.instance_on_points('strip_light_hangers', hang_pts, hang_ob, lay.C['hall_shell'])
        old = bpy.data.objects['strip_lights']
        self.swap_mesh(old, bpy.data.meshes.new('strip_lights_replaced'))
        old['note'] = 'the layout\'s boxes, replaced by strip_light_rows (continuous rows) and strip_light_hangers'
        self.report['luminaires'] = {'rows': len(self.LIGHT_ROWS), 'modules': len(lum_pts), 'row_y': [self.ROW_Y0, self.ROW_Y1]}

    # ------------------------------------------------------------------------------------------------ 2e. the station
    def station(self):
        lay, M, L = self.lay, self.M, self.L
        LE, GA = L['line']['lectern'], L['gantry']
        OBJ = bpy.data.objects
        lx, ly, TOPH = LE['x'], LE['y'], LE['top_h']
        SM = [M['station_white'], M['steel_galv'], M['steel_dark'], M['machine_teal']]      # (3: the teal trim: the shelf's rim, the head plate)
        mb = MB()
        mb.box((lx, ly, 0.006), (0.50, 0.42, 0.012), 1)                                              # the foot plate
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.bolt((lx + sx * 0.215, ly + sy * 0.175, 0.0165), 0.011, 0.009, 'z', 1)
                mb.cyl((lx + sx * 0.215, ly + sy * 0.175, 0.025), 0.005, 0.012, 'z', 8, 1)
        mb.box((lx, ly, 0.012 + (TOPH - 0.072) / 2), (0.08, 0.08, TOPH - 0.072), 0)                   # the column
        for sx in (-1, 1):                                                                           # gussets at its foot
            mb.prism([(sx * 0.04, 0.012), (sx * 0.15, 0.012), (sx * 0.04, 0.13)], ly - 0.003, ly + 0.003, 'y', 0, at=(lx, 0.0))
            mb.prism([(sx * 0.04, 0.012), (sx * 0.13, 0.012), (sx * 0.04, 0.13)], lx - 0.003, lx + 0.003, 'x', 0, at=(ly, 0.0))
        mb.span((lx - 0.26, ly - 0.15, 0.54), (lx + 0.26, ly + 0.15, 0.545), 0)                       # the shelf: a folded tray
        for a, b in (((lx - 0.26, ly - 0.15), (lx + 0.26, ly - 0.147)), ((lx - 0.26, ly + 0.147), (lx + 0.26, ly + 0.15)),
                     ((lx - 0.26, ly - 0.15), (lx - 0.257, ly + 0.15)), ((lx + 0.257, ly - 0.15), (lx + 0.26, ly + 0.15))):
            mb.span((a[0], a[1], 0.545), (b[0], b[1], 0.56 if a[1] != ly + 0.147 else 0.60), 3)
        for sx in (-1, 1):                                                                           # shelf brackets
            mb.prism([(0.04, 0.54), (0.14, 0.54), (0.04, 0.44)], lx + sx * 0.03 - 0.002, lx + sx * 0.03 + 0.002, 'x', 0, at=(ly, 0.0))
            mb.prism([(-0.04, 0.54), (-0.14, 0.54), (-0.04, 0.44)], lx + sx * 0.03 - 0.002, lx + sx * 0.03 + 0.002, 'x', 0, at=(ly, 0.0))
        mb.box((lx, ly, TOPH - 0.045), (0.16, 0.14, 0.012), 3, rx=RAD(LE['tilt']))                    # the head plate under the top
        # the printer stands on a side table at the station's right hand, lower than the lectern's top (its own top at
        # 0.92 m), so the long lenses down the line pass over it
        PRX, PRY, PRZ = lx + 0.50, ly + 0.02, 0.78                                                  # the printer's platform (level)
        mb.span((lx + 0.04, PRY - 0.02, PRZ - 0.045), (PRX + 0.14, PRY + 0.02, PRZ - 0.005), 0)       # its arm from the column
        mb.box((PRX, PRY, PRZ - 0.0025), (0.34, 0.28, 0.005), 0)
        st_z0 = 0.62
        st_dx, st_dz = (PRX - 0.02) - (lx + 0.04), (PRZ - 0.05) - st_z0
        mb.box(((lx + 0.04 + PRX - 0.02) / 2, PRY, (st_z0 + PRZ - 0.05) / 2), (math.hypot(st_dx, st_dz), 0.024, 0.024), 0, ry=-math.atan2(st_dz, st_dx))
        mb.cyl((lx + 0.048, ly + 0.048, 0.40), 0.0045, 0.72, 'z', 8, 2)                               # the printer's lead down the column
        lect_me = mb.mesh('line_lectern_new', SM)
        kit.finish(lect_me, bevel=0.0025, inset=0.013, cavity=0.08, ground=0.0, log=self.say)
        self.swap_mesh(OBJ['line_lectern'], lect_me)
        w, d = LE['top_w'], LE['top_d']                                                             # the sloped top
        mb = MB()
        mb.span((-w / 2, -d / 2, -0.012), (w / 2, d / 2, 0), 0)
        mb.span((-w / 2, -d / 2, 0), (w / 2, -d / 2 + 0.012, 0.022), 0)                               # the lip at the reader's edge
        mb.span((-w / 2, d / 2 - 0.05, 0), (w / 2, d / 2 - 0.045, 0.010), 0)                          # the pencil groove's rail
        mb.cyl((0, -d / 2 + 0.002, -0.006), 0.0075, w, 'x', 16, 0)                                    # the rolled edge under the lip
        for sx in (-1, 1):                                                                           # folded sides
            mb.span((sx * w / 2 - 0.002 * (sx > 0), -d / 2, -0.034), (sx * w / 2 + 0.002 * (sx < 0), d / 2, -0.012), 0)
        mb.span((-w / 2, d / 2 - 0.002, -0.034), (w / 2, d / 2, -0.012), 0)
        top_me = mb.mesh('line_lectern_top_new', [M['steel_brushed']])
        kit.finish(top_me, bevel=0.002, inset=0.016, cavity=0.05, log=self.say)
        self.swap_mesh(OBJ['line_lectern_top'], top_me)
        # the printer: a compact sheet printer, its slot and tray toward the station (-Y). Local frame: the body's foot
        PM_ = [M['plastic_white'], M['steel_dark'], M['rubber_black'], M['machine_teal'], M['printer_led'], M['steel_galv']]
        BW, BD = 0.30, 0.24
        SLOT_Z0, SLOT_Z1, SLOT_W = 0.096, 0.106, 0.222
        mb = MB()
        mb.box((0, 0, 0.0445), (BW, BD, 0.079), 0)                                                    # the lower shell
        mb.box((0, 0, 0.0855), (BW - 0.008, BD - 0.008, 0.003), 1)                                    # the seam's shadow gap
        yf, yb = -BD / 2 + 0.002, BD / 2 - 0.002
        mb.span((-BW / 2 + 0.002, yf + 0.03, 0.087), (BW / 2 - 0.002, yb, 0.137), 0)                  # the upper shell: back block,
        mb.span((-BW / 2 + 0.002, yf, 0.087), (-SLOT_W / 2, yf + 0.03, 0.137), 0)                     # left cheek,
        mb.span((SLOT_W / 2, yf, 0.087), (BW / 2 - 0.002, yf + 0.03, 0.137), 0)                       # right cheek,
        mb.span((-SLOT_W / 2, yf, SLOT_Z1), (SLOT_W / 2, yf + 0.03, 0.137), 0)                        # the lip over the slot,
        mb.span((-SLOT_W / 2, yf, 0.087), (SLOT_W / 2, yf + 0.03, SLOT_Z0), 0)                        # and under it
        mb.span((-SLOT_W / 2 + 0.001, yf + 0.0285, SLOT_Z0 + 0.0005), (SLOT_W / 2 - 0.001, yf + 0.0305, SLOT_Z1 - 0.0005), 1)   # the slot's dark back
        mb.cyl((0, yf + 0.016, SLOT_Z1 + 0.001), 0.0032, SLOT_W - 0.008, 'x', 12, 5)                  # the exit shaft,
        for xr in (-0.084, -0.028, 0.028, 0.084):
            mb.cyl((xr, yf + 0.016, SLOT_Z1 + 0.001), 0.0072, 0.016, 'x', 20, 2)                      # its four rubber wheels
            mb.cyl((xr, yf + 0.009, SLOT_Z0 - 0.0005), 0.004, 0.012, 'x', 12, 0)                      # and the idlers that pinch the sheet
        for xr in (-0.105, 0.105):                                                                   # the sheet's width, marked on the lip
            mb.span((xr - 0.0006, yf - 0.0004, SLOT_Z1 + 0.004), (xr + 0.0006, yf + 0.0006, SLOT_Z1 + 0.014), 1)
        mb.span((-BW / 2 + 0.0015, yf - 0.0004, 0.0868), (BW / 2 - 0.0015, yf + 0.0006, 0.0876), 1)   # the parting line
        mb.box((0, 0.012, 0.1385), (0.20, 0.15, 0.003), 0)                                            # the lid panel
        mb.box((0, 0.012, 0.1402), (0.06, 0.012, 0.0012), 3)                                          # its teal pull
        mb.span((-BW / 2 + 0.012, yf - 0.0006, 0.012), (BW / 2 - 0.012, yf + 0.001, 0.052), 0)        # the cassette's front
        mb.span((-0.05, yf - 0.0016, 0.026), (0.05, yf + 0.0004, 0.038), 1)                           # its finger pull
        mb.cyl((BW / 2 - 0.026, yf - 0.0004, 0.122), 0.0035, 0.002, 'y', 12, 4)                       # the status light
        mb.cyl((BW / 2 - 0.044, yf - 0.0004, 0.122), 0.0045, 0.002, 'y', 14, 1)                       # a button beside it
        for i in range(7):                                                                           # vents on the right side
            mb.span((BW / 2 - 0.0008, -0.06 + 0.018 * i, 0.100), (BW / 2 + 0.0004, -0.06 + 0.018 * i + 0.008, 0.128), 1)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.cyl((sx * 0.12, sy * 0.09, 0.0025), 0.011, 0.005, 'z', 14, 2)                      # feet
        mb.cyl((0.09, BD / 2 + 0.006, 0.03), 0.0045, 0.016, 'y', 8, 1)                                # its plug at the back
        pr_me = mb.mesh('line_printer', PM_)
        kit.finish(pr_me, bevel=0.0035, inset=0.012, cavity=0.03, ground=0.0, log=self.say)
        printer = self.new_ob('line_printer', pr_me, lay.C['line_module'], (PRX, PRY, PRZ))
        printer['note'] = 'the lectern\'s printer: its slot and tray face -Y, toward the station. One on every line'
        TRAY_L, TILT = 0.165, RAD(-10.0)                                                            # the tray rises away from the slot
        mb = MB()
        mb.span((-0.115, -TRAY_L, -0.003), (0.115, 0.0, 0.0), 0)
        for sx in (-1, 1):
            mb.span((sx * 0.115 - 0.003 * (sx > 0), -TRAY_L, 0.0), (sx * 0.115 + 0.003 * (sx < 0), 0.0, 0.007), 0)
        mb.span((-0.04, -TRAY_L - 0.002, 0.0), (0.04, -TRAY_L + 0.002, 0.012), 0)                     # the end stop
        for xr in (-0.084, -0.042, 0.0, 0.042, 0.084):                                               # the ribs a sheet slides out on
            mb.span((xr - 0.0018, -TRAY_L + 0.010, 0.0), (xr + 0.0018, -0.008, 0.0011), 0)
        for sx in (-1, 1):                                                                           # the tray's hinge knuckles
            mb.cyl((sx * 0.095, 0.001, -0.0015), 0.004, 0.022, 'x', 12, 0)
        tray_me = mb.mesh('line_printer_tray', [M['plastic_white']])
        kit.finish(tray_me, bevel=0.0018, inset=0.008, cavity=0.02, log=self.say)
        HINGE = (0.0, yf - 0.001, SLOT_Z0 - 0.004)                                                   # in the printer's frame
        tray = self.new_ob('line_printer_tray', tray_me, lay.C['line_module'], HINGE, 0.0, printer)
        tray.rotation_euler = (TILT, 0.0, 0.0)
        # the sheet's way (A5, 210 x 148 mm, its long side across): hero line only; a sheet rides sheet_path
        SHEET = (0.210, 0.148)
        ctl = self.empty('printer_ctl', (PRX + 0.25, PRY, PRZ + 0.3), lay.C['machinery'], lay.HERO_ROOT, kind='CUBE', size=0.06)
        ctl['feed'] = 0.0
        ctl.id_properties_ui('feed').update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=(
            'THE LECTERN\'S PRINTER: 0 = a sheet is inside, its leading edge at the slot; 1 = it lies on the tray (at '
            'sheet_out). One sheet per 0 -> 1; set it back to 0 for the next'))
        ctl.property_overridable_library_set('["feed"]', True)
        lay.controls['printer_ctl'] = ctl
        rest_y = HINGE[1] - (SHEET[1] / 2 + 0.006) * math.cos(TILT)                                   # the sheet's centre at rest
        rest_z = HINGE[2] - (SHEET[1] / 2 + 0.006) * math.sin(TILT) + 0.0012
        start_y, start_z = yf + SHEET[1] / 2 + 0.004, (SLOT_Z0 + SLOT_Z1) / 2
        out = self.empty('sheet_out', (PRX, PRY + rest_y, PRZ + rest_z), lay.C['machinery'], lay.HERO_ROOT, size=0.05)
        out.rotation_euler = (TILT, 0.0, 0.0)
        out['note'] = 'where a fed sheet comes to rest on the tray: its centre; local +X its long side, +Y its short side, +Z up'
        path = self.empty('sheet_path', (PRX, PRY + start_y, PRZ + start_z), lay.C['machinery'], lay.HERO_ROOT, size=0.05)
        path['note'] = 'the sheet\'s travel, driven by printer_ctl["feed"]: parent a sheet here (its centre at this origin, flat in XY)'
        q = [('q', ctl, '["feed"]')]
        drv(path, 'location', f'{num(PRY + start_y)}+({num(rest_y - start_y)})*q', q, 1)
        drv(path, 'location', f'{num(PRZ + start_z)}+({num(rest_z - start_z)})*q', q, 2)
        drv(path, 'rotation_euler', f'{num(TILT)}*q', q, 0)
        self.report['printer'] = {'body_world': [PRX, PRY, PRZ], 'sheet': SHEET, 'property': 'printer_ctl["feed"] 0..1'}
        self.PR = (PRX, PRY, PRZ)
        # the pendant: a moulded two-shell station on its cable, a guarded push button
        P_ = GA['pendant']
        PMATS = [M['plastic_teal'], M['rubber_black'], M['steel_galv']]
        mb = MB()
        mb.span((-0.035, -0.0275, -0.12), (0.035, -0.0005, 0.12), 0)                                  # the front shell
        mb.span((-0.035, 0.0012, -0.12), (0.035, 0.0275, 0.12), 0)                                    # the back shell
        mb.box((0, 0.00035, 0), (0.066, 0.0018, 0.236), 1)                                            # the gasket between them
        mb.cyl((0, 0, 0.13), 0.016, 0.03, 'z', 24, 1)                                                 # the gland
        for i, rr in enumerate((0.0125, 0.011, 0.0095, 0.008)):                                      # its strain relief
            mb.cyl((0, 0, 0.151 + 0.012 * i), rr, 0.010, 'z', 16, 1)
        mb.cyl((0, 0, (P_['hang_z'] + P_['z'] + 0.12) / 2 - P_['z']), 0.006, P_['hang_z'] - P_['z'] - 0.12, 'z', 10, 1)   # the cable
        bz = P_['button_z'] - P_['z']
        mb.cyl((0, -0.0295, bz), 0.0245, 0.005, 'y', 40, 1)                                           # the big button's guard ring
        mb.cyl((0, -0.0290, -0.03), 0.0135, 0.004, 'y', 28, 1)                                        # the small button's bezel
        mb.cyl((0, -0.0305, -0.03), 0.0105, 0.005, 'y', 28, 2)                                        # the small button (fixed)
        for sx in (-1, 1):
            for sz in (-1, 1):
                mb.cyl((sx * 0.027, -0.0279, sz * 0.108), 0.0034, 0.0014, 'y', 12, 2)                 # shell screws
        mb.span((-0.012, -0.0284, 0.086), (0.012, -0.0272, 0.098), 1)                                 # a blank badge recess
        pend_me = mb.mesh('pendant_body_new', PMATS)
        kit.finish(pend_me, bevel=0.0035, inset=0.009, cavity=0.025, log=self.say)
        mb = MB()
        mb.cyl((0, -0.006, 0), 0.018, 0.012, 'y', 40, 0)
        mb.cyl((0, -0.0125, 0), 0.0145, 0.0012, 'y', 40, 0)                                           # a slight crown
        btn_me = mb.mesh('pendant_button_new', [M['plastic_white']])
        kit.finish(btn_me, bevel=0.0016, inset=0.004, cavity=0.0, log=self.say)
        for o in list(OBJ):
            if o.type == 'MESH' and o.data.name.startswith('pendant_body'):
                self.swap_mesh(o, pend_me)
            elif o.type == 'MESH' and o.data.name.startswith('pendant_button'):
                self.swap_mesh(o, btn_me)
        pend_me.name, btn_me.name = 'pendant_body', 'pendant_button'

    # ------------------------------------------------------------------------------------------------ 2f. chain link
    def chain_link(self):
        RC = self.L['returns_cage']
        gx0, gx1 = RC['x']
        gy0, gy1 = RC['y']
        gh = RC['h']
        mb = MB()

        def woven(a, b, z0, z1, pitch=0.07, wire=0.0032):
            """chain link as it is woven: every wire a zigzag that hooks its neighbours at each bend, over and under"""
            W = math.hypot(b[0] - a[0], b[1] - a[1])
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            ux, uy = (b[0] - a[0]) / W, (b[1] - a[1]) / W
            nx_, ny_ = -uy, ux
            nw, nz = int(W / pitch), int((z1 - z0) / pitch)
            ln = pitch * math.sqrt(2) + wire
            for k in range(nw):
                for j in range(nz):
                    right = (j + k) % 2 == 0
                    um = (k + 0.5) * pitch + (W - nw * pitch) / 2
                    zm = z1 - (j + 0.5) * pitch
                    off = 0.0013 * (1 if (j % 2 == 0) == right else -1)
                    c = (a[0] + ux * um + nx_ * off, a[1] + uy * um + ny_ * off, zm)
                    mb.box(c, (wire, ln, wire), 0, ang - PI / 2, (PI / 4) * (1 if right else -1))
            for i in range(len(mb.sm) - nw * nz * 6, len(mb.sm)):
                mb.sm[i] = True

        corners = [(gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1)]
        woven(corners[0], corners[1], 0.05, gh)
        woven(corners[0], (gx0, gy0 + 1.6), 0.05, gh)
        woven((gx0, gy0 + 3.0), corners[3], 0.05, gh)
        woven((gx0 + 0.25, gy0 + 1.62), (gx0 + 1.55, gy0 + 2.55), 0.05, gh)
        link_me = mb.mesh('cage_chain_link_new', [self.M['chain_galv']], recalc=False)
        kit.uv_metres(link_me)
        self.swap_mesh(bpy.data.objects['cage_chain_link'], link_me)
        self.report['chain_link_faces'] = len(link_me.polygons)

    # ------------------------------------------------------------------------------------------------ 2h. the rest
    def the_rest(self):
        lay, M, L = self.lay, self.M, self.L
        OBJ = bpy.data.objects
        machines.crane(self.X)                                                    # the crane's six meshes, each in its own frame
        machines.cabinet(self.X, shell.TRAY_Z)
        # the meter's own lamp: a strip inside the cabinet over its window (the hall's baked light cannot enter a 66 mm
        # window); it reaches 0.3 m and casts nothing
        MC_ = L['meter_cabinet']
        ld = bpy.data.lights.new('meter_drum_lamp', 'AREA')
        ld.shape, ld.size, ld.size_y = 'RECTANGLE', 0.36, 0.012
        ld.energy = float(self.opt['drum_lamp'])
        ld.use_temperature, ld.color = False, self.LAMP_RGB
        ld.use_shadow = False
        ld.use_custom_distance, ld.cutoff_distance = True, 0.30
        o = self.new_ob('meter_drum_lamp', ld, lay.C['meter_cabinet'], ((MC_['x'][0] + MC_['x'][1]) / 2, MC_['y'][1] - 0.02, MC_['window_z'] + 0.075))
        o.rotation_euler = (RAD(-25.0), 0.0, 0.0)
        # the pendant's mast: a tube on a bolted flange, a gusseted arm, the control's cable clipped along it down to a box
        PN = L['gantry']['pendant']
        mx_, my_, hz_ = PN['mast_x'], PN['y'], PN['hang_z']
        mb = MB()
        mb.cyl((mx_, my_, (hz_ + 0.05) / 2 + 0.006), 0.03, hz_ + 0.05 - 0.012, 'z', 20, 0)
        mb.cyl((mx_, my_, 0.006), 0.11, 0.012, 'z', 24, 0)
        mb.cyl((mx_, my_, hz_ + 0.052), 0.033, 0.006, 'z', 20, 0)                                     # its cap
        for k in range(4):
            a = PI / 4 + k * PI / 2
            mb.bolt((mx_ + math.cos(a) * 0.08, my_ + math.sin(a) * 0.08, 0.0165), 0.010, 0.009, 'z', 1)
        mb.span((mx_, my_ - 0.02, hz_), (PN['x'] + 0.03, my_ + 0.02, hz_ + 0.04), 0)                   # the arm
        mb.prism([(mx_ + 0.03, hz_), (mx_ + 0.12, hz_), (mx_ + 0.03, hz_ - 0.09)], my_ - 0.003, my_ + 0.003, 'y', 0)   # its gusset
        mb.cyl((PN['x'], my_, hz_ - 0.012), 0.012, 0.024, 'z', 12, 1)                                 # the cable's gland
        mb.tube([(PN['x'], my_ + 0.026, hz_ + 0.02), (mx_ + 0.05, my_ + 0.026, hz_ + 0.02), (mx_ + 0.0, my_ + 0.036, hz_ - 0.03),
                 (mx_, my_ + 0.036, 1.32)], 0.006, 8, 2)                                              # the cable along the arm and mast
        for z in (hz_ - 0.25, 2.0, 1.6):
            mb.box((mx_, my_ + 0.036, z), (0.03, 0.016, 0.012), 1)                                    # its clips
        mb.box((mx_, my_ + 0.055, 1.22), (0.09, 0.05, 0.14), 3)                                       # the junction box on the mast
        mb.cyl((mx_, my_ + 0.055, 1.30), 0.011, 0.02, 'z', 6, 1)
        mast_me = mb.mesh('line_pendant_mast_new', [M['station_white'], M['steel_galv'], M['rubber_black'], M['plastic_grey']])
        kit.finish(mast_me, bevel=0.002, inset=0.01, cavity=0.05, ground=0.0, log=self.say)
        self.swap_mesh(OBJ['line_pendant_mast'], mast_me)
        # the hood stack's base: a framed steel deck with locating ribs, rubber landing strips, feet bolted to the floor
        ST = L['line']['stack']
        ya_, yb_ = ST['y0'] + ST['col_pitch'] / 2, ST['y0'] - ST['col_pitch'] * (ST['cols'] - 0.5)
        sx0, sx1, bh = ST['x'] - 0.475, ST['x'] + 0.475, ST['base_h']
        mb = MB()
        mb.span((sx0 + 0.02, yb_ + 0.02, bh - 0.006), (sx1 - 0.02, ya_ - 0.02, bh), 0)                # the deck plate
        for a, b in (((sx0, yb_), (sx1, yb_ + 0.04)), ((sx0, ya_ - 0.04), (sx1, ya_)), ((sx0, yb_ + 0.04), (sx0 + 0.04, ya_ - 0.04)),
                     ((sx1 - 0.04, yb_ + 0.04), (sx1, ya_ - 0.04))):
            mb.span((a[0], a[1], 0.0), (b[0], b[1], bh), 0)                                           # its frame
        for c in range(ST['cols'] + 1):
            y = ya_ - ST['col_pitch'] * c
            y = min(max(y, yb_ + 0.012), ya_ - 0.012)
            mb.span((sx0 + 0.04, y - 0.012, bh), (sx1 - 0.04, y + 0.012, bh + 0.02), 0)               # locating ribs
            if c < ST['cols']:
                for sx in (-0.3, 0.3):
                    mb.span((ST['x'] + sx - 0.05, y - ST['col_pitch'] + 0.08, bh), (ST['x'] + sx + 0.05, y - 0.08, bh + 0.004), 1)   # landing strips
        for x in (sx0 - 0.03, sx1 + 0.03):
            for y in (yb_ + 0.12, (ya_ + yb_) / 2, ya_ - 0.12):
                mb.box((x, y, 0.004), (0.06, 0.10, 0.008), 0)                                         # feet
                mb.bolt((x, y, 0.013), 0.010, 0.008, 'z', 0)
        base_me = mb.mesh('line_hood_stack_base_new', [M['steel_galv'], M['rubber_black']])
        kit.finish(base_me, bevel=0.003, inset=0.016, cavity=0.06, ground=0.0, log=self.say)
        self.swap_mesh(OBJ['line_hood_stack_base'], base_me)
        for nm, kw in (('cage_posts', dict(bevel=0.002, inset=0.01, ground=0.0)),
                       ('dock_threshold', dict(bevel=0.002, inset=0.012, cavity=0.0)),
                       ('office_window', dict(bevel=0.003, inset=0.014)),
                       ('ph_clipboard', dict(bevel=0.0008, inset=0.004, cavity=0.02)),
                       ('ph_cards', dict(bevel=0.0006, inset=0.004, cavity=0.02)), ('ph_notebook', dict(bevel=0.001, inset=0.004, cavity=0.02)),
                       ('ph_pencils', dict(bevel=0.0004, inset=0.002, cavity=0.0)), ('meter_drum_housing', dict(bevel=0.001, inset=0.006, cavity=0.0)),
                       ('carton_base', dict(bevel=0.0015, inset=0.012, cavity=0.06, ground=0.0)),
                       ('carton_collar', dict(bevel=0.001, inset=0.006, cavity=0.04)),
                       ('carton_hood', dict(bevel=0.0015, inset=0.012, cavity=0.04))):
            self.finish_named(nm, **kw)
        kit.uv_metres(bpy.data.meshes['carton_insert'])
        for k in range(L['meter_cabinet']['digits']):
            self.finish_named('meter_drum_%d' % k, bevel=0.0012, inset=0.006, cavity=0.02)
        gl = OBJ['meter_window_glass']
        gl.hide_render = False                                                    # real glass now (thin, smudged)

    # ------------------------------------------------------------------------------------------------ 3. light
    def light(self):
        from ....look import lighting as LT
        lay, M, L, H, opt = self.lay, self.M, self.L, self.L['hall'], self.opt
        OBJ = bpy.data.objects
        HX0, HX1, HY0, HY1 = lay.HX0, lay.HX1, lay.HY0, lay.HY1
        RZ, WT_, LZ = H['roof_z'], H['wall_t'], H['lights_z']
        D = L['dock']
        C_AIR = self.C_AIR
        for nm in ('fill_a', 'fill_b'):
            o = OBJ.get(nm)
            if o:
                bpy.data.objects.remove(o)
        STRIP = float(opt['strip'])                              # Blender watts per metre of row
        SEG_NEAR, SEG_FAR, NEAR_Y = 12.0, 48.0, -72.0            # near the hero aisle a light per 12 m; elsewhere one per 48 m
        PROBE_Y0 = -14.4                                         # where the fine probe over the hero aisle ends
        FAR_K = float(opt['far_lamp'])                           # a plain lamp's power against a baked row's
        n_lights, seg_len = 0, 0.0
        ROW_Y0, ROW_Y1 = self.ROW_Y0, self.ROW_Y1
        for i, x in enumerate(self.LIGHT_ROWS):
            # a row is ONE unbroken line of light: its pieces butt end to end, so a point under it sees the same light
            near_row = x > -11.5
            hero_row = x > -10.0                                   # the two rows over the hero aisle
            cuts = [ROW_Y1]
            if hero_row and ROW_Y0 < PROBE_Y0:                     # three pieces over the fine probe's stretch
                cuts += [ROW_Y1 - (ROW_Y1 - PROBE_Y0) * (k + 1) / 3 for k in range(3)]
            if near_row and ROW_Y0 < NEAR_Y:
                top = cuts[-1]
                n = max(1, int(round((top - NEAR_Y) / SEG_NEAR)))
                cuts += [top - (top - NEAR_Y) * (k + 1) / n for k in range(n)]
            rest = cuts[-1] - ROW_Y0
            if rest > 0.01:
                n = max(1, int(round(rest / (SEG_NEAR if (near_row and ROW_Y0 >= NEAR_Y) else SEG_FAR))))
                cuts += [cuts[-1] - rest * (k + 1) / n for k in range(n)]
            for j in range(len(cuts) - 1):
                ya, yb = cuts[j], cuts[j + 1]
                ln, yc = ya - yb, (ya + yb) / 2
                if ln < 0.01:
                    continue
                near = near_row and yc > NEAR_Y
                ld = bpy.data.lights.new('strip_r%02d_s%02d' % (i, j), 'AREA')
                ld.shape = 'RECTANGLE'
                ld.size, ld.size_y = 0.058, ln
                ld.energy = STRIP * ln
                ld.use_temperature, ld.color = False, self.LAMP_RGB
                ld.spread = RAD(170.0)
                ld.use_custom_distance, ld.cutoff_distance = True, 62.0 + ln / 2
                ld.volume_factor = 0.0                             # the air takes its light from the probes and the sun
                # NO STRIP LAMP CASTS A SHADOW. Over the hero aisle (the two rows, as far as the fine probe reaches)
                # the lamps give the highlights only: the DIFFUSE light there is BAKED (the ribbons below, read by the
                # fine probe with its occlusion). Everywhere else the lamps light plainly, without shadow: the hall's
                # coarse probe cannot store the rows' light
                ld.use_shadow = False
                baked = hero_row and yb >= PROBE_Y0 - 0.01
                ld.diffuse_factor, ld.specular_factor = (0.0 if baked else 1.0), 1.0
                if not baked:
                    # a plain lamp is a highbay's beam, 40 degrees to either side: it lights its own two lanes, and
                    # reaches the hero aisle's floor no further than the rack row beside it would let it
                    ld.spread = RAD(80.0)
                    ld.energy = STRIP * ln * FAR_K
                o = self.new_ob(ld.name, ld, C_AIR, (x, yc, LZ - 0.014))
                o.hide_select = True
                n_lights += 1
                seg_len = ln if near else seg_len
        # what the floor throws back up at the roof: ONE wide lamp at 6 m that looks up (it lights nothing below it, casts
        # nothing, gives no highlight); the coarse probe stores too little of the plain lamps' bounce
        ld = bpy.data.lights.new('hall_floor_bounce', 'AREA')
        ld.shape, ld.size, ld.size_y = 'RECTANGLE', HX1 - HX0, HY1 - HY0
        ld.energy = float(opt['bounce']) * 0.5 * (HX1 - HX0) * (HY1 - HY0)
        ld.use_temperature, ld.color = False, (0.97, 0.98, 1.0)
        ld.use_shadow, ld.diffuse_factor, ld.specular_factor, ld.volume_factor = False, 1.0, 0.0, 0.0
        o = self.new_ob(ld.name, ld, C_AIR, ((HX0 + HX1) / 2, (HY0 + HY1) / 2, 6.0))
        o.rotation_euler = (PI, 0.0, 0.0)
        o.hide_select = True
        # the ribbons: what the volume probes read as the rows' light. Each row's flux over a strip RIB_W wide so the
        # bake's surfels cannot miss it; CLOSED BOXES, each face its own emitter (down: the row's light; sides: a third,
        # the spill that lights walls and carton fronts; up: an eighth, onto the deck); no camera, no mirror probe and no
        # shadow sees them; only under the two hero rows, over the fine probe's stretch
        RIB_W, RIB_H = 0.9, 0.22
        RIBBON = float(opt['ribbon']) * STRIP / (PI * RIB_W)
        mb = MB()
        for x in self.LIGHT_ROWS:
            if x > -10.0:
                mb.span((x - RIB_W / 2, max(ROW_Y0, PROBE_Y0), LZ - 0.03 - RIB_H), (x + RIB_W / 2, ROW_Y1, LZ - 0.03), 0)
        rib_mats = []
        for nm_, share in (('strip_light_bake', 1.0), ('strip_light_bake_side', 0.33), ('strip_light_bake_up', 0.125)):
            M[nm_] = mats.emitter(nm_, self.LAMP_RGB, RIBBON * share, body=(0.0, 0.0, 0.0))
            rib_mats.append(M[nm_])
        rib_me = mb.mesh('strip_light_bake_ribbons', rib_mats)
        for p in rib_me.polygons:
            p.material_index = 0 if p.normal.z < -0.5 else 2 if p.normal.z > 0.5 else 1
        rib = self.new_ob('strip_light_bake_ribbons', rib_me, C_AIR)
        rib.visible_camera = rib.visible_shadow = False
        rib.hide_probe_sphere = rib.hide_probe_plane = True
        rib.hide_select = True
        sun = OBJ['sun_dock']
        sun.data.energy = float(opt['sun'])
        sun.data.use_temperature, sun.data.color = False, self.SUN_RGB
        sun.data.angle = RAD(0.53)
        sun.data.volume_factor = 0.0
        sun.data.use_shadow, sun.data.use_shadow_jitter = True, False            # one shadow map, drawn once a frame
        self.sun = sun
        if self.sky_kind not in ('sky', 'earth', 'hdri', None):
            raise ValueError(f"hall look: sky {self.sky_kind!r}: 'sky' (the sky family), 'hdri' or None")
        # haze: the air of a long hall
        mb = MB()
        mb.span((HX0 + 0.05, HY0 + 0.05, 0.03), (HX1 - 0.05, HY1 - 0.02, RZ - 0.02))
        hz_mat = bpy.data.materials.new('hall_haze')
        hz_mat.use_nodes = True
        hz_mat.node_tree.nodes.clear()
        pv = hz_mat.node_tree.nodes.new('ShaderNodeVolumePrincipled')
        pv.inputs['Color'].default_value = (0.90, 0.93, 0.97, 1.0)
        pv.inputs['Density'].default_value = float(opt['haze'])
        pv.inputs['Anisotropy'].default_value = 0.35
        ho = hz_mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        hz_mat.node_tree.links.new(pv.outputs[0], ho.inputs['Volume'])
        haze = self.new_ob('hall_haze', mb.mesh('hall_haze', [hz_mat]), C_AIR)
        haze.hide_probe_volume = True
        haze.visible_shadow = False
        haze.hide_select = True
        self.haze = haze
        # A BLIND IN THE DOOR FOR THE BAKE ONLY: with it the volume probes store no sight of the sky inside the hall (the
        # sky's light would come in as a slope down the line); no camera, mirror probe or shadow sees it
        mb = MB()
        mb.span((D['door_x'][0] - 0.3, HY1 + WT_ + 0.02, 0.0), (D['door_x'][1] + 0.3, HY1 + WT_ + 0.12, D['door_h'] + 0.3))
        bl_mat = mats.material('dock_bake_blind')
        bl_mat.use_nodes = True
        bl_mat.node_tree.nodes.clear()
        bn_, bo_ = bl_mat.node_tree.nodes.new('ShaderNodeBsdfDiffuse'), bl_mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        bn_.inputs['Color'].default_value = (0.25, 0.25, 0.25, 1.0)
        bl_mat.node_tree.links.new(bn_.outputs[0], bo_.inputs['Surface'])
        blind = self.new_ob('dock_door_bake_blind', mb.mesh('dock_door_bake_blind', [bl_mat]), C_AIR)
        blind.visible_camera = blind.visible_shadow = False
        blind.hide_probe_sphere = blind.hide_probe_plane = True
        blind.hide_select = True
        # probes
        self.PROBES = []

        def volume_probe(name, lo, hi, spacing, wall, samples, surfels):
            lay_ = LT.room_probe_layout(lo, hi, wall, spacing)
            ob = LT.add_volume_probe(self.SC, name, lay_['centre'], lay_['size'], resolution=lay_['resolution'], samples=samples,
                                     collection=C_AIR)
            d_ = ob.data
            d_.surfel_density = surfels
            d_.capture_distance = 120.0
            d_.escape_bias = min(d_.escape_bias, lay_['escape'])
            d_.clamp_indirect = 0.0                                              # no clamp: the rows' emitters are brighter than 10
            for k_, v_ in (('dilation_radius', 2.5), ('dilation_threshold', 0.5)):   # a sample inside a wall takes its neighbours' light
                for nm_ in (k_, 'grid_' + k_):
                    if hasattr(d_, nm_):
                        setattr(d_, nm_, v_)
            self.PROBES.append(ob)
            self.say('   probe %s: %s samples, spacing %s m' % (name, lay_['resolution'], [round(s, 2) for s in lay_['spacing']]))
            return ob

        volume_probe('hall_probe', (HX0, HY0, 0.0), (HX1, HY1, RZ), 3.0, 3.0, 2048, 2)   # 2 surfels a metre
        ap = volume_probe('hall_probe_aisle', (-7.2, max(HY0 + 2, -14.0), 0.0), (HX1, HY1, RZ), 0.45, 0.30, 4096, 14)
        # ALONG THE LINE THE AISLE PROBE'S SAMPLES STAND 0.4 m APART, ON MULTIPLES OF 0.4: a third of the tray pitch, so
        # every unit has its samples in the same places and the light on unit 7 is read as on unit 1
        ap.location.y, ap.scale.y = 5.0, 19.4                    # y -14.4 .. 24.4: 96 samples at -14.0, -13.6, ... 24.0
        for nm_ in ('resolution_y', 'grid_resolution_y'):
            if hasattr(ap.data, nm_):
                setattr(ap.data, nm_, 96)
        # mirror probes: every surface of the hall lies in one's box (floor to roof), or it would mirror the WORLD (with a
        # real sky outdoors the roof and the far floor turn sky blue). Three close ones on the hero aisle, two long ones
        for nm, c, box in (('refl_line', (2.2, 4.0, 1.7), (16.0, 26.0, 22.8)), ('refl_station', (2.4, -8.0, 1.7), (16.0, 22.0, 22.8)),
                           ('refl_dock', (0.5, 18.5, 1.8), (16.0, 12.0, 22.8)), ('refl_far_aisle', (0.0, -121.5, 2.0), (15.2, 205.0, 22.4)),
                           ('refl_west_floor', (-39.5, -100.0, 2.0), (64.4, 249.0, 22.4))):
            sp = LT.add_sphere_probe(self.SC, nm, c, box=box, collection=C_AIR)
            sp.data.clip_start, sp.data.clip_end = 0.3, 120.0
        self.report['light'] = {'strip_lights': n_lights, 'segment_m': round(seg_len, 2), 'watts_per_metre': STRIP, 'kelvin': LAMP_K,
                                'white_balance_kelvin': WB_K, 'sun_strength': float(opt['sun']), 'sun_kelvin': SUN_K,
                                'sky': self.sky_kind, 'haze_density': pv.inputs['Density'].default_value}

    def outdoors(self):
        """the world: seen whole through the door by the lens, felt only a little inside (sky_fill)"""
        to_sun = -self.lay.SUN_DIR
        opt = self.opt
        if self.sky_kind in ('sky', 'earth'):
            self.sky = self.sky_family(to_sun)
        elif self.sky_kind == 'hdri':
            w, _gain, _el = mats.world_sky('hall_outdoors', hdri_path(), tuple(to_sun), gain=float(opt['sky_gain']),
                                           clamp=float(opt['sky_clamp']), fill=float(opt['sky_fill']))
            self.SC.world = w

    def sky_family(self, to_sun):
        """the sky family's Earth sky (eidoblend.sky.make_sky), its hour and azimuth solved so its sun stands where the
        dock's sun is, with a lamp of its own that lights nothing (the dock sun draws the patch); the lens sees it whole
        (its camera layer) and it lights at sky_fill (its ambient)"""
        from ....sky import make_sky
        from ...town.world import sky_hours
        lamp = bpy.data.objects.get('hall_sky_sun')
        if lamp is None:
            lamp = bpy.data.objects.new('hall_sky_sun', bpy.data.lights.new('hall_sky_sun', 'SUN'))
            self.C_AIR.objects.link(lamp)
        lamp.data.use_shadow = False
        lamp.hide_render = True                                   # (the sky family keys it; the hall's sun is sun_dock)
        hours, az = sky_hours(-to_sun)
        cam = self.camera or self.SC.camera or self.lay.cams.get('cam_aisle_out')
        cache = os.path.join(bpy.app.tempdir or os.path.dirname(bpy.data.filepath or '.'), 'hall_sky')
        s = make_sky(self.SC, camera=cam, world='earth', hours=hours, clouds=SKY['clouds'], sun=lamp, cache_dir=cache,
                     quality='draft', ambient=float(self.opt['sky_fill']), azimuth=az, audio=False, weather_fx=False)
        self.say(f'   the sky family: hour {hours:.3f}, azimuth base {az:.4f} rad')
        return s

    # ------------------------------------------------------------------------------------------------ 4. settings
    def settings(self):
        lay, opt = self.lay, self.opt
        SC = self.SC
        E, R_, V = SC.eevee, SC.render, SC.view_settings
        R_.engine = 'BLENDER_EEVEE'
        for k, v in EEVEE.items():
            if hasattr(E, k):
                setattr(E, k, v)
        for k, v in RAY.items():
            if hasattr(E.ray_tracing_options, k):
                setattr(E.ray_tracing_options, k, v)
        E.taa_render_samples = int(opt['samples'])
        E.volumetric_start, E.volumetric_end = 0.3, 270.0        # the hall is 248 m long
        # THE AIR HAS A SWITCH, because it is the dearest thing left in a frame: look_ctl["haze"] 1 = the haze is drawn
        # (the long views need their air), 0 = it is not (a close shot loses nothing)
        lctl = self.empty('look_ctl', (lay.HX1 - 1.0, lay.HY1 - 1.0, 2.6), self.C_AIR, kind='CUBE', size=0.12)
        lctl['haze'] = 1.0
        lctl.id_properties_ui('haze').update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=(
            'THE HALL\'S AIR: 1 = the haze is rendered (wide views), 0 = it is not (close shots: about 2.5 to 3.5 s less a '
            'frame at 1080p)'))
        lctl.property_overridable_library_set('["haze"]', True)
        drv(self.haze, 'hide_render', '1-q if q>0.5 else 1', [('q', lctl, '["haze"]')])
        lay.controls['look_ctl'] = lctl
        R_.use_motion_blur, R_.motion_blur_shutter, R_.motion_blur_position = True, 0.5, 'CENTER'
        R_.filter_size = 1.5
        V.view_transform, V.look, V.exposure, V.gamma = 'AgX', 'AgX - Base Contrast', float(opt['exposure']), 1.0
        for name, f in DOF.items():
            o = bpy.data.objects.get(name)
            if o is not None and o.type == 'CAMERA':
                o.data.dof.use_dof, o.data.dof.aperture_fstop = True, f
        PRX, PRY, PRZ = self.PR
        cd = bpy.data.cameras.new('cam_printer')
        cd.sensor_width, cd.lens, cd.clip_start, cd.clip_end = 36.0, 70.0, 0.1, 800.0
        cam = self.new_ob('cam_printer', cd, lay.C['cameras'], (PRX + 0.06, PRY - 0.66, PRZ + 0.36))
        aim = Vector((PRX, PRY - 0.20, PRZ + 0.075))
        zax = (cam.location - aim).normalized()
        xax = Vector((0, 0, 1)).cross(zax).normalized()
        cam.rotation_euler = Matrix((xax, zax.cross(xax), zax)).transposed().to_euler()
        cd.dof.focus_distance = (aim - cam.location).length
        cd.dof.use_dof, cd.dof.aperture_fstop = True, 4.0
        lay.cams['cam_printer'] = cam
        cd = bpy.data.cameras.new('cam_line_85')                                  # 85 mm down the hero line, at a body's eye
        cd.sensor_width, cd.lens, cd.clip_start, cd.clip_end = 36.0, 85.0, 0.1, 800.0
        cam = self.new_ob('cam_line_85', cd, lay.C['cameras'], (5.0, -5.8, 1.05))
        zax = (cam.location - Vector((0.16, 4.08, 0.61))).normalized()
        xax = Vector((0, 0, 1)).cross(zax).normalized()
        cam.rotation_euler = Matrix((xax, zax.cross(xax), zax)).transposed().to_euler()
        lay.cams['cam_line_85'] = cam
        # the meter cabinet stands 80 mm off the wall's dado (flush it reads as sunk into the wall), with its own cameras
        cab_off = Vector((-0.08, 0.0, 0.0))
        for o in list(lay.C['meter_cabinet'].objects) + [bpy.data.objects.get(n) for n in ('cam_drums', 'cam_cabinet_window', 'cam_cabinet_lock')]:
            if o is not None and o.parent is None:
                o.location = o.location + cab_off

    # ------------------------------------------------------------------------------------------------ 5. the bake
    def bake_probes(self):
        """the volume probes baked WITHOUT the sun (its bounce, baked, lies as a warm slope down the whole line; the patch
        is its own) and without what moves (the crane's parts, the hoods, the cartons that ride the tracks: baked, their
        shade would stay where they stood); then the trees' own probe (SeedThree's: a back-lit crown without one glows
        evenly, like frosted glass), the sun on"""
        from ....look import lighting as LT
        crane = ('crane_bridge', 'crane_trolley', 'crane_ring', 'crane_pad', 'crane_belt')
        moving = [o for o in bpy.data.objects if (o.type == 'MESH' and o.data is not None and o.data.name.split('.')[0] in crane)
                  or ('hood' in o.name and 'stack' not in o.name) or o.name.startswith(('stream_box', 'line_00_tray_'))]
        for o in moving:
            o.hide_probe_volume = True
        self.report['moving_objects_kept_out_of_the_bake'] = len(moving)
        sun_e = self.sun.data.energy
        self.sun.data.energy = 0.0
        self.report['probe_bake_seconds'] = LT.bake_light_probes(self.SC, probes=self.PROBES, exclude=[self.haze])
        self.sun.data.energy = sun_e
        self.say('baked:', self.report['probe_bake_seconds'])
        if getattr(self.X, 'trees', None):
            from ....trees import make_seed_tree
            before = {o.name for o in bpy.data.objects if o.type == 'LIGHT_PROBE'}
            for t in self.X.trees:
                for o in [t['object']] + list(t['object'].children_recursive):
                    o.hide_probe_volume = False
            t_p = time.time()
            make_seed_tree.light_probe(self.X.trees, spacing=3.0)
            new_probes = [o for o in bpy.data.objects if o.type == 'LIGHT_PROBE' and o.name not in before]
            for o in new_probes:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                self.lay.C['dock'].objects.link(o)
            self.report['tree_probe'] = {'seconds': round(time.time() - t_p, 1), 'objects': [o.name for o in new_probes]}
