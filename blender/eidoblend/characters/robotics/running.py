"""eidoblend.characters.robotics.running: running.js createRunningController, in Blender.

The humanoid's and quadruped's reviewed running gaits (metadata/<family>_running.json): every frame of a clip holds the
locomotion root's base position, yaw and pitch and each gait joint's angle; the controller writes LOCAL matrices
(rest_matrices from the authoring scene, then the joint turn about joint_axes_blender) onto the actual modular chain,
so mirrored (reflected) modules keep their handedness. The data is in the kit's authoring axes, which are Blender's:
the WebGPU edition conjugates every matrix into three's +Y up; this edition writes them as they are.

    ctl = create_running_controller(nodes, quadruped, data)   nodes: {glTF node name: object}
    ctl.apply(clip, t)      the pose at t seconds (clamped to the clip) -> the frame record
    ctl.frame(clip, t)      {'time', 'base', 'yaw', 'pitch', 'joints'} linearly interpolated
    ctl.restore()           every node back to its loaded transform
    ctl.bounds(clip)        (min, max) world box the clip's root sweeps, +0.5 m around, + the body's height
    ctl.duration(clip)      seconds; ctl.data the JSON
"""

from __future__ import annotations

import math

from mathutils import Matrix, Vector


class RunningController:
    def __init__(self, nodes: dict, quadruped: bool, data: dict):
        self.data, self.nodes, self.quadruped = data, nodes, quadruped
        self.rest = {n: Matrix(rows) for n, rows in data['rest_matrices'].items() if n in nodes}
        self.original = {n: o.matrix_basis.copy() for n, o in nodes.items()}
        self.axes = {n: Vector(a).normalized() for n, a in data['joint_axes_blender'].items()}
        for name in data['clips']['circle']['frames'][0]['joints']:
            if name not in nodes:
                raise KeyError('Missing gait joint ' + name)
        if data['root'] not in nodes:
            raise KeyError('Missing locomotion root')

    def duration(self, clip):
        return self.data['clips'][clip]['duration']

    def frame(self, clip, time):
        c = self.data['clips'][clip]
        fs = c['frames']
        u = max(0.0, min(1.0, time / c['duration'])) * (len(fs) - 1)
        i = min(len(fs) - 2, int(math.floor(u)))
        a, b = fs[i], fs[i + 1]
        w = u - i
        lerp = lambda x, y: x + (y - x) * w  # noqa: E731
        return {'time': time,
                'base': [lerp(v, b['base'][k]) for k, v in enumerate(a['base'])],
                'yaw': lerp(a['yaw'], b['yaw']),
                'pitch': lerp(a.get('pitch', 0.0), b.get('pitch', 0.0)),
                'joints': {n: lerp(v, b['joints'][n]) for n, v in a['joints'].items()}}

    def apply(self, clip, time):
        f = self.frame(clip, time)
        root = self.data['root']
        pivot = Vector(self.data.get('root_pivot') or (0.0, 0.0, 0.0))
        for name, m in self.rest.items():
            local = m.copy()
            if name in f['joints']:
                local = local @ Matrix.Rotation(f['joints'][name], 4, self.axes[name])
            if name == root:
                local = (Matrix.Translation(Vector(f['base'])) @ Matrix.Rotation(f['yaw'], 4, 'Z')
                         @ Matrix.Translation(pivot) @ Matrix.Rotation(f['pitch'], 4, 'X')
                         @ Matrix.Translation(-pivot) @ local)
            self.nodes[name].matrix_basis = local
        return f

    def restore(self):
        for n, m in self.original.items():
            self.nodes[n].matrix_basis = m

    def bounds(self, clip):
        pts = [Vector(f['base']) for f in self.data['clips'][clip]['frames']]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return lo - Vector((0.5, 0.5, 0.0)), hi + Vector((0.5, 0.5, 0.9 if self.quadruped else 1.65))


def create_running_controller(nodes: dict, quadruped: bool, data: dict) -> RunningController:
    return RunningController(nodes, quadruped, data)
