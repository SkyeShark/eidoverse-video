"""The vehicles' real lamps: the light their emissive parts would throw, as Blender lights parented to the body.

The engine's lamps were colours on a raymarched surface: they glowed but lit nothing (a raymarched SDF cannot light
its scene). In EEVEE a lamp can: make() parents these lights to the vehicle, placed at the emissive parts of each
map() (positions in the SDF's three.js frame, as the map() wrote them):

    headlights   spot lights at the lamp faces, aimed ahead and 5 degrees down, warm white
    tail lamps   small red point lights just behind the lenses
    underglow    (cyberpunk) two long area lights along the rocker strips, facing the ground, coloured by the
                 car's uPaint through drivers, so a repaint or a keyed colour reaches the ground glow too
    afterburners (fighter jet) an orange point light behind each plume

Their power is set for the daylight levels eidoblend scenes use (a sun of 3 to 5 W/m2): there, as on a real street,
a headlight's pool on the road is faint, the underglow is a soft tint under the sills and an afterburner warms the
ground beneath the nozzles. For dusk and night shots raise lamp_power (make(lamp_power=8), the real ratio of a low
beam to a dimmed sky); make(lamps=False) leaves them out; car.set_lamps(False) hides them. The lights keep the scene's own light threshold out of the way with a custom cutoff distance (a weak light is
otherwise culled by EEVEE's light_threshold).
"""

from __future__ import annotations

import math

# (role, light type, three position, three aim direction, colour (linear), watts, extra)
_WARM = (1.0, 0.93, 0.82)
_RED = (1.0, 0.06, 0.03)
_ORANGE = (1.0, 0.45, 0.12)

LAMPS = {
    'modern': [
        ('head', 'SPOT', (0.58, 0.68, 2.25), (0.0, -0.09, 1.0), _WARM, 12.0, {'spot': 55.0, 'blend': 0.45}),
        ('head', 'SPOT', (-0.58, 0.68, 2.25), (0.0, -0.09, 1.0), _WARM, 12.0, {'spot': 55.0, 'blend': 0.45}),
        ('tail', 'POINT', (0.58, 0.68, -2.26), (0.0, 0.0, -1.0), _RED, 1.0, {}),
        ('tail', 'POINT', (-0.58, 0.68, -2.26), (0.0, 0.0, -1.0), _RED, 1.0, {}),
    ],
    'cyber': [
        ('head', 'SPOT', (0.45, 0.74, 2.26), (0.0, -0.09, 1.0), _WARM, 12.0, {'spot': 60.0, 'blend': 0.5}),
        ('head', 'SPOT', (-0.45, 0.74, 2.26), (0.0, -0.09, 1.0), _WARM, 12.0, {'spot': 60.0, 'blend': 0.5}),
        ('tail', 'POINT', (0.66, 0.74, -2.24), (0.0, 0.0, -1.0), _RED, 1.0, {}),
        ('tail', 'POINT', (-0.66, 0.74, -2.24), (0.0, 0.0, -1.0), _RED, 1.0, {}),
        ('underglow', 'AREA', (0.55, 0.185, 0.0), (0.0, -1.0, 0.0), 'uPaint', 10.0, {'size': (0.05, 1.9)}),
        ('underglow', 'AREA', (-0.55, 0.185, 0.0), (0.0, -1.0, 0.0), 'uPaint', 10.0, {'size': (0.05, 1.9)}),
    ],
    'sleek': [
        # the sphere lamps' hand-tuned centres at pre-scale (x 1.5), on their front faces
        ('head', 'SPOT', (0.146 * 1.5, 0.311 * 1.5, 1.080 * 1.5 + 0.10), (0.0, -0.09, 1.0), _WARM, 10.0,
         {'spot': 55.0, 'blend': 0.45}),
        ('head', 'SPOT', (-0.154 * 1.5, 0.310 * 1.5, 1.072 * 1.5 + 0.10), (0.0, -0.09, 1.0), _WARM, 10.0,
         {'spot': 55.0, 'blend': 0.45}),
        ('tail', 'POINT', (0.151 * 1.5, 0.286 * 1.5, -1.077 * 1.5 - 0.10), (0.0, 0.0, -1.0), _RED, 1.0, {}),
        ('tail', 'POINT', (-0.152 * 1.5, 0.281 * 1.5, -1.079 * 1.5 - 0.10), (0.0, 0.0, -1.0), _RED, 1.0, {}),
    ],
    'jet': [
        # behind each plume's tip (the plume ellipsoid ends at z = -1.5 - 1.4 - 0.4 = -3.3): outside the mesh, so its
        # own surface does not shadow it
        ('afterburner', 'POINT', (0.65, -0.05, -3.42), (0.0, 0.0, -1.0), _ORANGE, 60.0, {'radius': 0.12}),
        ('afterburner', 'POINT', (-0.65, -0.05, -3.42), (0.0, 0.0, -1.0), _ORANGE, 60.0, {'radius': 0.12}),
    ],
}


def _three(v):
    return (v[0], -v[2], v[1])


def _aim_rotation(d3):
    """Euler rotation pointing a light's -Z along the three direction d3."""
    from mathutils import Vector
    d = Vector(_three(d3)).normalized()
    return d.to_track_quat('-Z', 'Y').to_euler()


def _drive_color(light, car_object, prop):
    """light.color[i] = car_object[prop][i]: the lamp follows the live uniform (set or keyed)."""
    for i in range(3):
        fc = light.driver_add('color', i)
        drv = fc.driver
        drv.type = 'AVERAGE'
        var = drv.variables.new()
        var.name = 'c'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = car_object
        var.targets[0].data_path = f'["{prop}"][{i}]'


def add_lamps(car, power=1.0, collection=None):
    """The lamps of car.kind, parented to car.object; returns the light objects."""
    import bpy
    coll = collection or (car.object.users_collection[0] if car.object.users_collection else
                          bpy.context.scene.collection)
    out = []
    for k, (role, kind, pos, aim, color, watts, extra) in enumerate(LAMPS[car.kind]):
        name = f'{car.object.name}_{role}{k}'
        ld = bpy.data.lights.new(name, kind)
        ld.energy = float(watts) * float(power)
        if isinstance(color, str):
            v = car.object.get(color)
            ld.color = tuple(float(c) for c in v[:3]) if v is not None else (1.0, 1.0, 1.0)
        else:
            ld.color = color
        if kind == 'SPOT':
            ld.spot_size = math.radians(extra.get('spot', 50.0))
            ld.spot_blend = extra.get('blend', 0.4)
            ld.shadow_soft_size = extra.get('radius', 0.04)
            ld.show_cone = False
        elif kind == 'AREA':
            ld.shape = 'RECTANGLE'
            sx, sy = extra.get('size', (0.1, 1.0))
            ld.size, ld.size_y = sx, sy
        else:
            ld.shadow_soft_size = extra.get('radius', 0.03)
        # the lamp's reach, its custom influence distance (a weak light's own reach ends where its power falls under
        # the scene's light_threshold)
        try:
            ld.use_custom_distance = True
            ld.cutoff_distance = 40.0
        except AttributeError:
            pass
        ob = bpy.data.objects.new(name, ld)
        coll.objects.link(ob)
        ob.parent = car.object
        ob.location = _three(pos)
        ob.rotation_euler = _aim_rotation(aim)
        ob['sdf_vehicle_lamp'] = role
        if isinstance(color, str):
            _drive_color(ld, car.object, color)
        out.append(ob)
    return out
