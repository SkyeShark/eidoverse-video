"""eidoblend.sets.town.views: lenses on a built town, in its own metres. Blender (mathutils).

    for name, pos, target, lens in town.views():          # target None: straight down, the image's top toward -x
        views.aim(camera, pos, target, lens)

The lenses of a full-size town (840 x 300 m), scaled to the town's extent in plan (heights kept):
  over_the_main_road_24mm    from 71 m over the main road, looking ahead and down along it
  straight_down_70m_30mm     straight down from 70 m onto roofs, yards and washing
  pull_back_35mm             from 82 m, the town opening out under a long slant
  across_to_the_edge_40mm    from 79 m at the west end, low over the roofs toward the far side
  street_level_main_road_28mm  standing on the main road's pavement
  roofs_at_a_slant_45mm      from 32 m over a block, its roofs and what lives on them
  the_edge_from_60m_35mm     the town's edge thinning out along its tracks
  a_road_end_into_the_plain_35mm   the main road's east end, where its asphalt goes under the track and the plain
and, found where the town put them: a block of shops from across the road, a roof and what is on it, a low house and
its yard.
"""
import math

from mathutils import Vector

BASE = (('over_the_main_road_24mm', (150.0, 2.0, 71.0), (118.0, 0.0, 0.0), 24),
        ('straight_down_70m_30mm', (60.0, 1.0, 70.0), None, 30),
        ('pull_back_35mm', (40.0, -30.0, 82.0), (5.0, 0.0, 60.0), 35),
        ('across_to_the_edge_40mm', (-225.0, -13.0, 79.0), (-200.0, 0.2, 71.1), 40),
        ('street_level_main_road_28mm', (130.0, -17.5, 1.7), (95.0, -11.0, 4.0), 28),
        ('roofs_at_a_slant_45mm', (30.0, -48.0, 32.0), (4.0, -8.0, 8.0), 45),
        ('the_edge_from_60m_35mm', (300.0, 60.0, 60.0), (420.0, 190.0, 0.0), 35))


def aim(cam, pos, target, lens):
    """a camera at pos looking at target (None: straight down, the image's top toward -x), lens in mm"""
    cam.location = pos
    cam.rotation_euler = (0.0, 0.0, math.pi / 2) if target is None else (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def views(town):
    """[(name, pos, target, lens)] for a Town (layout.build's result)"""
    ex, ey = town.extent
    sx, sy = ex / 840.0, ey / 300.0

    def s(p):
        return None if p is None else (p[0] * sx, p[1] * sy, p[2])
    out = [(n, s(p), s(t), L) for n, p, t, L in BASE]
    px = town.paved[0]                                               # the main road where its asphalt ends in the plain
    ym = max(town.ystreets, key=lambda q: q[1])[0]
    out.append(('a_road_end_into_the_plain_35mm', (px - 70.0, ym - 24.0, 16.0), (px - 8.0, ym, 0.0), 35))
    blds = [o for o in town.parts['buildings'] if o.get('tn_in')]

    def nearest(prefix, x, y):
        c = [o for o in blds if o.data.name.startswith(prefix)]
        return min(c, key=lambda o: math.hypot(o.location.x - x, o.location.y - y)) if c else None

    def frame(o):
        """a building's middle, its front's direction, its width, depth, height"""
        f = -1.0 if abs(o.rotation_euler.z) < 0.1 else 1.0
        w, d, h = o['tn_w'], o['tn_d'], o['tn_h']
        return Vector((o.location.x - f * w / 2, o.location.y - f * d / 2, 0.0)), f, w, d, h
    o = nearest('town_A_', 30.0 * sx, -6.0)
    if o:
        c, f, w, d, h = frame(o)
        out.append(('shop_fronts_from_across_the_road_30mm', (c.x + 5.0, c.y + f * (d / 2 + 13.0), 2.6), (c.x, c.y + f * d / 2, 3.0), 30))
        out.append(('a_roof_and_what_is_on_it_40mm', (c.x + w / 2 + 5.0, c.y + f * (d / 2 + 6.0), h + 8.5), (c.x, c.y, h + 0.6), 40))
    o = nearest('town_C_', 20.0 * sx, 60.0 * sy)
    if o:
        c, f, w, d, h = frame(o)
        out.append(('a_low_house_and_its_yard_35mm', (c.x - w / 2 - 9.0, c.y + f * (d / 2 + 12.0), h + 9.0), (c.x, c.y, h * 0.5), 35))
    return out
