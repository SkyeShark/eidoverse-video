"""eidoblend.sets.wake_another_one.hall: the automated factory hall of the WAKE ANOTHER ONE music video, a set of this
edition's own (no WebGPU original). Blender:

    from eidoblend.sets.wake_another_one import hall
    H = hall.build(small=False, look=True, sky='sky', trees=True, bake=True)     # or sets.build('wake_another_one.hall')
    H.cameras['cam_aisle_out']; H.marks['line_00_unit_3']; H.controls['gantry_ctl']
    hall.animate({'run': [(1, 0.0), (240, 3.0)], 'meter': [(1, 3861), (96, 0)], 'travel': [(1, 0.0), (480, 26.2)]})
    H.bake_sky('cam_dock', f0, f1)                       # the sky family's sky, again for each camera and its frames

WHAT IT IS: a hall 79 x 248 m and 13 m high. One hero line runs down a canyon of racks toward the dock door: a flush
roller track with ten cartons on it (units 0..9: a tray each, its hood on), a hood stack, a lectern with a printer and the
crane's hanging control, and an overhead crane (runway, bridge, trolley, a ring with four gripper pads) that lifts the
hoods off one unit after another and stacks them. Behind the racks, the open floor holds lines in rows, each with its own
crane. A main track carries a stream of closed cartons out through the dock door; a mechanical counter (four drums in a
cabinet) shows a number; a returns cage, an office window high on the side wall, and a yard beyond the door with parked
trailers, a fence and SeedThree trees under a low afternoon sun that lays a warm patch across the last unit's tray.

THE CARTON is a plain two-part carton (carton.py): a tray with a collar and a moulded insert, and a hood. A unit's empty
line_NN_unit_K is its tray's frame; a body stands at the carton's body_mark in it (marks: line_00_mark_K).

THE MACHINES are custom properties on control empties, turned into motion by simple-expression drivers (they evaluate
without Python, in the saved file, with no handler). CONTROLS names each; animate() keys them:
    run           gantry_ctl     the hero crane: the whole part the unit it works on (0..9; 10 the fresh carton at unit_0),
                                 the fraction the move (travel, lower, grip, raise, carry to the stack, set down);
                                 0 = ten closed cartons, 10 = units 1..9 open
    along_offset, hoist_offset   gantry_ctl     metres added to the bridge's place and the ring's height
    travel        track_ctl      metres the main track's stream has rolled toward the dock
    swap          track_ctl      0..1: unit_0's open tray rolls out along the spur while a fresh closed carton rolls in
    crowd_run     crowd_ctl      every other line's crane, as run for units 1..9, each row a little after the one before
    press         gantry_pendant the pendant's button, 0 out .. 1 in
    meter         meter_cabinet_ctl  the number the counter shows (0..9999), rolling like an odometer
    feed          printer_ctl    the printer feeds one sheet out onto its tray (0 -> 1); sheet_path carries it
    haze          look_ctl       1 the hall's air is rendered, 0 it is not (a close shot saves 2.5 to 3.5 s a frame)

THE LOOK (look=True; look.py): every surface a layered material over CC0 scans fetched by ID into the shared library
on first use (ambientCG: Concrete034, Metal049A, Metal027, Metal009, Plastic010, Rubber004, Paper001, Asphalt012;
Poly Haven models: power_box_01, fire_alarm, security_camera_01, modular_chainlink_fence), the hall-era geometry kit
private to this set (_kit: bevels, a wear band, baked cavity, UVs in metres). The outdoors is the sky family's sky
(sky='sky': eidoblend.sky.make_sky, its sun solved onto the dock sun) or the named photo option (sky='hdri':
syferfontein_18d_clear_puresky, CC0); the yard's trees are SeedThree's (eidoblend.trees; trees=False leaves them out).
small=True builds two rows of two lanes in a hall cut short at y -45 (a quick build: the test's).
"""

import json
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
CONTROLS = {
    'run': ('gantry_ctl', 'run'), 'along_offset': ('gantry_ctl', 'along_offset'), 'hoist_offset': ('gantry_ctl', 'hoist_offset'),
    'travel': ('track_ctl', 'travel'), 'swap': ('track_ctl', 'swap'), 'crowd_run': ('crowd_ctl', 'crowd_run'),
    'press': ('gantry_pendant', 'press'), 'meter': ('meter_cabinet_ctl', 'meter'), 'feed': ('printer_ctl', 'feed'),
    'haze': ('look_ctl', 'haze'),
}


def layout(path=None):
    """layout.json as a dict (every dimension the build reads)"""
    with open(path or os.path.join(HERE, 'layout.json'), encoding='utf-8') as f:
        return json.load(f)


class Hall:
    """a built hall: collection (the 'hall' collection), parts (its collections by name), cameras, controls (the control
    empties), marks (every unit's tray frame, line_NN_unit_K, and the hero line's body marks), sky (the sky family's
    Sky to bake, or None), report (what the build and the look measured)"""

    def __init__(self, lay, look):
        self.layout = lay.L
        self.collection = lay.C['hall']
        self.parts = dict(lay.C)
        self.cameras = dict(lay.cams)
        self.controls = dict(lay.controls)
        self.marks = {o.name: o for o in bpy.data.objects if o.name.startswith('line_') and ('_unit_' in o.name or '_mark_' in o.name)}
        self.sky = look.sky if look is not None else None
        self.report = {'layout': lay.report, 'look': look.report if look is not None else None}

    def camera(self, name):
        return self.cameras[name]

    def bake_sky(self, camera=None, frame_start=None, frame_end=None, log=None):
        """bake the sky family's sky for `camera` (a name or an object; default the scene's) over the frames (default the
        current one): the GPU's draw state reset first (a volume probe bake leaves it so the sky would bake black).
        Nothing to do with sky='hdri' or None"""
        if self.sky is None:
            return None
        from .look import gpu_reset
        sc = bpy.context.scene
        cam = self.cameras.get(camera, camera) if isinstance(camera, str) else camera
        if cam is not None:
            sc.camera = cam
            self.sky.camera = cam
        f0 = sc.frame_current if frame_start is None else frame_start
        gpu_reset()
        return self.sky.bake(f0, f0 if frame_end is None else frame_end, log=log or (lambda *m: None))


def build(ctx=None, small=False, look=True, sky='sky', trees=True, bake=True, camera=None, scene=None, log=print, **look_opts):
    """build the hall in the scene (ctx: the harness ctx, its scene used; else `scene`, else the current one) -> Hall.
    small: the quick hall; look: the finished look (else the flat-colour layout); sky / trees / bake / camera and the
    look's options (look.py's head): see the module's head"""
    from .build import Layout
    sc = scene or (getattr(ctx, 'scene', None) if ctx is not None else None) or bpy.context.scene
    if bpy.context.scene is not sc:
        bpy.context.window.scene = sc
    lay = Layout(layout(), small=small, scene=sc, log=log).run()
    lk = None
    if look:
        from .look import Look
        lk = Look(lay, sky=sky, trees=trees, bake=bake, camera=camera or lay.cams.get('cam_aisle_out'), log=log, **look_opts).run()
    return Hall(lay, lk)


def animate(keys, interpolation='LINEAR'):
    """key the hall's controls: keys {control: [(frame, value), ...]} with the names of CONTROLS (or 'object.property');
    interpolation of every key ('LINEAR', 'BEZIER', 'CONSTANT') -> {control: number of keys}"""
    out = {}
    for name, pts in keys.items():
        ob_name, prop = CONTROLS[name] if name in CONTROLS else name.split('.', 1)
        ob = bpy.data.objects.get(ob_name)
        if ob is None or prop not in ob:
            raise KeyError(f'hall.animate: no control {name!r} ({ob_name}["{prop}"]) in this scene')
        for f, v in pts:
            ob[prop] = float(v)
            ob.keyframe_insert(f'["{prop}"]', frame=f)
        ad = ob.animation_data
        for fc in _fcurves(ad.action, f'["{prop}"]'):
            for kp in fc.keyframe_points:
                kp.interpolation = interpolation
        out[name] = len(pts)
    return out


def _fcurves(action, path):
    """an action's fcurves on `path` (every slot's channelbag, or the action's own list)"""
    found = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                found += [fc for fc in bag.fcurves if fc.data_path == path]
    if not found and hasattr(action, 'fcurves'):
        found = [fc for fc in action.fcurves if fc.data_path == path]
    return found
