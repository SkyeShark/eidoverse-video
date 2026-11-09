"""eidoblend.characters.maneuvers.verbs: the controller's parkour moves aimed at objects in the scene.

    from eidoblend.characters.maneuvers import vault_over, climb_onto, scramble_up, climb_ladder, jump_across, cross
    vault_over(walk, cover)                        # walk up to it, square up, vault() (the clip fitted to the cover)
    climb_onto(walk, block)                        # climbLedge (or climbWallUp's route over 1.35 m)
    scramble_up(walk, wall, rate=0.45)             # the wall scramble, chained into the mantle
    climb_ladder(walk, rungs, wall)                # the rungs measured, the climb rung for rung, the mantle at the top
    jump_across(walk, landing, height=0.5)         # to the takeoff edge, then jump() its measured distance
    cross(walk, cover, gait='run')                 # run through it: the auto-trigger picks the move, as on a walkTo

The WebGPU engine starts these two ways: the controller's auto-trigger while a walk crosses an obstacle (vault, mount,
scramble, gap jump), or the explicit calls (vault(), climbLedge(), jump({distance, height}), climbLadder({height,
firstRung, rungSpacing}), climbWall()) that act "on whatever obstacle is ahead along the heading", the body put there
by the scene. Each verb here is one queued command that does the putting: when it starts it measures the object from
where the body then stands (targets.measure_obstacle / measure_ladder), walks to `run_up` in front of its near face with
the auto-trigger off (it would read the same obstacle first), turns square to it, and starts the explicit move with the
measured numbers; the auto-trigger is set back as it was after. The moves, their clips, root paths and contact IK are
the controller's (eidoblend.characters.controller.maneuvers).
"""

import math

from mathutils import Vector

from ..controller.film import FollowPath, Locomotion, Maneuver, TurnTo, _Cmd
from .targets import forward, measure_ladder, measure_obstacle, _others, _rays

RUN_UP = {'vault': 0.6, 'climb_ledge': 0.5, 'climb_wall': 0.5, 'climb_ladder': 0.55, 'jump': 0.15}
LADDER_GAP = 0.09            # the controller's climb puts the rungs' line this far in front of the wall (terrain_base)


def _log(loco, msg):
    (getattr(loco, 'log', None) or print)(msg)


class Approach(_Cmd):
    """walk to run_up in front of a measured face, square up to it, start a move (the module's doc)"""

    def __init__(self, label, measure, move, run_up, gait='walk', speed=None, kw=None):
        self.label, self.measure, self.move, self.run_up = label, measure, move, run_up
        self.gait, self.speed, self.kw = gait, speed, kw

    def start(self, loco):
        c = loco.ctrl
        f = c.feet_world_position
        info = self.measure(loco, (f.x, f.y))
        self.info = info
        self.subs = []
        if info is None:
            _log(loco, f'[{self.label}] nothing to aim at from ({f.x:.2f}, {f.y:.2f})')
            return
        p, n = info['point'], info['normal']
        spot = (p.x + n.x * self.run_up, p.y + n.y * self.run_up)
        if math.dist((f.x, f.y), spot) > 0.04:
            self.subs.append(FollowPath([spot], speed=self.speed, gait=self.gait, arrive=0.02))
        self.subs.append(TurnTo(heading=info['heading']))
        kw = self.kw(info) if callable(self.kw) else dict(self.kw or {})
        self.subs.append(Maneuver(self.move, **kw))
        self.auto_was = c.auto_maneuvers
        c.auto_maneuvers = False
        _log(loco, f"[{self.label}] the face at ({p.x:.3f}, {p.y:.3f}) facing {math.degrees(info['heading']):.1f} deg, "
                   f"{info.get('rise', 0.0):.2f} m up: from ({spot[0]:.2f}, {spot[1]:.2f}), {self.move}({kw})")

    def step(self, loco, dt):
        c = loco.ctrl
        while self.subs:
            sub = self.subs[0]
            if not sub.started:
                if isinstance(sub, Maneuver):
                    c.auto_maneuvers = self.auto_was        # the move's chained parts (a mantle) as the controller has them
                sub.start(loco)
                sub.started = True
            inp = sub.step(loco, dt)
            if inp is not None:
                return inp
            self.subs.pop(0)
        if hasattr(self, 'auto_was'):
            c.auto_maneuvers = self.auto_was
        return None


def _queue(loco, cmd):
    if not isinstance(loco, Locomotion):
        raise TypeError('the maneuver verbs direct a Locomotion (eidoblend.characters.controller): the moves are the '
                        "controller's")
    loco._queue.append(cmd)
    return loco


def _obstacle(obj):
    def m(loco, xy):
        return measure_obstacle(obj, xy)
    return m


def vault_over(loco, cover, run_up=None, gait='walk', speed=None):
    """vault(): over the cover the body walks up to (the clip's take-off and landing fitted to it; one hand on its top)"""
    return _queue(loco, Approach('vault_over', _obstacle(cover), 'vault', RUN_UP['vault'] if run_up is None else run_up,
                                 gait, speed))


def climb_onto(loco, block, run_up=None, gait='walk', speed=None):
    """climbLedge(): up onto the block (climbLedge to 1.35 m, climbWallUp's route to 2.3 m: the hands on the lip, the
    feet onto the top)"""
    return _queue(loco, Approach('climb_onto', _obstacle(block), 'climb_ledge',
                                 RUN_UP['climb_ledge'] if run_up is None else run_up, gait, speed))


def scramble_up(loco, wall, rate=0.34, time_scale=1.1, run_up=None, gait='walk', speed=None):
    """climbWall({rate, timeScale}): the wall scramble (climbWallUp looped, palms and toes on the face) up the wall,
    chained into the mantle over its top"""
    return _queue(loco, Approach('scramble_up', _obstacle(wall), 'climb_wall',
                                 RUN_UP['climb_wall'] if run_up is None else run_up, gait, speed,
                                 {'rate': rate, 'time_scale': time_scale}))


def climb_ladder(loco, rungs, wall=None, rate=0.55, time_scale=1.0, standoff=None, run_up=None, gait='walk',
                 speed=None):
    """climbLadder({height, firstRung, rungSpacing, rate, timeScale}): the ladder's rungs measured (measure_ladder: its
    first rung, its spacing, the wall's top), the body walked to run_up (0.55 m, the example's) in front of them and
    squared up, the climb rung for rung, chained into the mantle. The rungs are solids to the feet (the controller's
    contact_world: every visible mesh, unless one was given); keep them and the rails out of the walking world, as the
    course does (their flat wall is what the controller walks against)"""
    def measure(loco_, xy):
        lad = measure_ladder(rungs, wall, ground_z=_ground_z(rungs, xy))
        gap = lad.get('wall_gap')
        if gap is not None and abs(gap - LADDER_GAP) > 0.02:
            _log(loco_, f'[climb_ladder] the rungs stand {gap * 100:.1f} cm off the wall; the controller grips them '
                        f'{LADDER_GAP * 100:.0f} cm off it (terrain_base\'s build)')
        c = loco_.ctrl
        if getattr(c, 'contact_world', None) is None:
            from ..controller import CollisionWorld
            c.contact_world = CollisionWorld()
        # the run-up is measured from the wall's face, as the example's trigger (0.55 m) is
        p = lad['line'] - lad['normal'] * (lad.get('wall_gap') or LADDER_GAP)
        return {'point': Vector((p.x, p.y, lad['line'].z)), 'normal': lad['normal'], 'heading': lad['heading'],
                'rise': lad['height'], 'ladder': lad}

    def kw(info):
        lad = info['ladder']
        out = {'height': lad['height'], 'first_rung': lad['first_rung'], 'rung_spacing': lad['rung_spacing'],
               'rate': rate, 'time_scale': time_scale}
        if standoff is not None:
            out['standoff'] = standoff
        return out
    return _queue(loco, Approach('climb_ladder', measure, 'climb_ladder',
                                 RUN_UP['climb_ladder'] if run_up is None else run_up, gait, speed, kw))


def _ground_z(objs, xy):
    hit = _rays(_others(objs)).cast((xy[0], xy[1], 50.0), (0, 0, -1), 100.0)
    return hit[0].z if hit else 0.0


def takeoff_edge(xy, heading, objs=None, step=0.04, reach=6.0, drop=0.3):
    """where the ground in front of xy along heading falls away (over `drop` lower than at xy): the gap's near edge ->
    its distance from xy, or None"""
    rays = _rays(_others(objs) if objs is not None else _others([]))
    f = forward(heading)
    z0 = rays.cast((xy[0], xy[1], 50.0), (0, 0, -1), 100.0)
    z0 = z0[0].z if z0 else 0.0
    d = 0.0
    while d < reach:
        d += step
        h = rays.cast((xy[0] + f.x * d, xy[1] + f.y * d, z0 + 1.0), (0, 0, -1), 50.0)
        if h is None or h[0].z < z0 - drop:
            return d - step
    return None


def jump_across(loco, landing, height=0.45, land_in=0.45, run_up=None, gait='walk', speed=None):
    """jump({distance, height}): to `run_up` (15 cm) before the edge the ground falls away at, square to the landing,
    a leap of the measured distance (the landing's near face + land_in onto it) and `height`"""
    st = {}

    def measure(loco_, xy):
        # the landing's near face: above the ground for a ledge, below it for a trench's far wall
        ob = measure_obstacle(landing, xy, heights=(-0.3, -0.15, 0.12, 0.25, 0.4))
        if ob is None:
            return None
        d_edge = takeoff_edge(xy, ob['heading'], [landing])
        if d_edge is None:
            _log(loco_, '[jump_across] no edge between the body and the landing: it walks on over')
            return None
        f = forward(ob['heading'])
        edge = Vector((xy[0], xy[1], 0.0)) + f * d_edge
        st['span'] = (ob['point'] - edge).dot(f)
        # aimed at the edge (the run-up is measured from it), squared to the landing
        return {'point': Vector((edge.x, edge.y, 0.0)), 'normal': -f, 'heading': ob['heading'],
                'rise': ob['rise'], 'landing': ob}

    def kw(info):
        return {'distance': st['span'] + (RUN_UP['jump'] if run_up is None else run_up) + land_in, 'height': height}
    return _queue(loco, Approach('jump_across', measure, 'jump', RUN_UP['jump'] if run_up is None else run_up, gait,
                                 speed, kw))


class Cross(_Cmd):
    """walk or run through an obstacle with the auto-trigger on: the controller picks the move from its own scan (a
    vault, a mount, a scramble, a gap jump), as it does on a walkTo"""

    def __init__(self, obj, beyond=1.5, gait='walk', speed=None):
        self.obj, self.beyond, self.gait, self.speed = obj, beyond, gait, speed

    def start(self, loco):
        c = loco.ctrl
        f = c.feet_world_position
        ob = measure_obstacle(self.obj, (f.x, f.y))
        self.sub = None
        if ob is None:
            _log(loco, '[cross] nothing to cross')
            return
        fw = forward(ob['heading'])
        end = ob['point'] + fw * (ob['depth'] + self.beyond)
        self.auto_was = c.auto_maneuvers
        c.auto_maneuvers = True
        self.sub = FollowPath([(end.x, end.y)], speed=self.speed, gait=self.gait)
        _log(loco, f"[cross] through '{self.obj.name}' ({ob['rise']:.2f} m up, {ob['depth']:.2f} m deep) to "
                   f'({end.x:.2f}, {end.y:.2f}), {self.gait}')

    def step(self, loco, dt):
        if self.sub is None:
            return None
        if not self.sub.started:
            self.sub.start(loco)
            self.sub.started = True
        inp = self.sub.step(loco, dt)
        if inp is None:
            loco.ctrl.auto_maneuvers = self.auto_was
        return inp


def cross(loco, obj, beyond=1.5, gait='walk', speed=None):
    """through the obstacle and on `beyond` m past it, the auto-trigger deciding the move (the engine's walkTo)"""
    return _queue(loco, Cross(obj, beyond, gait, speed))
