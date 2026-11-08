"""eidoblend.xr.choreo: a piece's data, sampled out of a built .blend into the JSON an XR page plays.

The renderer's scenes are scripts; the XR page reuses their DATA (tools-guides/webxr.md). A built .blend is all keys and
baked caches, so the data reads straight out of it, at any frame, in three's axes:

    from eidoblend.xr import choreo
    track = choreo.sample_tracks(scene, ['crow_peck', 'crow_caw', 'cam'], step=2)   # {'fps', 'track': {name: [[t, x, y, z]]}}
    choreo.write(scene, 'work/<id>/vr/choreo.json', names=['crow_peck', 'cam'], step=2)

write() adds the timeline markers (cues: name, t, the camera a marker binds) and the property tracks the GLB cannot carry
(light intensity and colour, emission strength, visibility; eidoblend.xr.motion.property_tracks), which the XR page
template applies by name every frame.
"""
from __future__ import annotations

import json
import os

import bpy

from ..common import to_three


def sample_tracks(scene, names, step=2, three_axes=True, rotation=False):
    """{'fps', 'frame_start', 'step', 'track': {name: [[t, x, y, z] (+ [qx, qy, qz, qw] with rotation)]}}: each
    object's world position every `step` frames, t in seconds from the first frame."""
    sc = scene
    fps = sc.render.fps / sc.render.fps_base
    keep = sc.frame_current
    track = {n: [] for n in names}
    try:
        for f in range(sc.frame_start, sc.frame_end + 1, max(1, int(step))):
            sc.frame_set(f)
            t = round((f - sc.frame_start) / fps, 5)
            for n in names:
                ob = sc.objects[n]
                m = ob.matrix_world
                x, y, z = m.translation
                p = to_three(x, y, z) if three_axes else (x, y, z)
                row = [t] + [round(v, 5) for v in p]
                if rotation:
                    q = m.to_quaternion()
                    if three_axes:
                        # a rotation's axis maps like a direction: (ax, ay, az) -> (ax, az, -ay); three order x, y, z, w
                        row += [round(q.x, 6), round(q.z, 6), round(-q.y, 6), round(q.w, 6)]
                    else:
                        row += [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]
                track[n].append(row)
    finally:
        sc.frame_set(keep)
    return {'fps': fps, 'frame_start': sc.frame_start, 'step': int(step), 'axes': 'three' if three_axes else 'blender',
            'track': track}


def markers(scene):
    """[{'name', 't', 'frame', 'camera'}] of the timeline markers (camera cuts and cues), in time order."""
    fps = scene.render.fps / scene.render.fps_base
    out = []
    for m in sorted(scene.timeline_markers, key=lambda m: m.frame):
        out.append({'name': m.name, 'frame': m.frame, 't': round((m.frame - scene.frame_start) / fps, 5),
                    'camera': m.camera.name if m.camera else None})
    return out


def write(scene, path, names=(), step=2, props=True, rotation=True):
    """The choreography JSON for a page: tracks of `names`, markers, and the property tracks. Returns the dict."""
    from . import motion
    out = sample_tracks(scene, list(names), step, rotation=rotation) if names else \
        {'fps': scene.render.fps / scene.render.fps_base, 'frame_start': scene.frame_start, 'step': int(step),
         'axes': 'three', 'track': {}}
    out['markers'] = markers(scene)
    if props:
        out['props'] = motion.property_tracks(scene, step=1)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    return out
