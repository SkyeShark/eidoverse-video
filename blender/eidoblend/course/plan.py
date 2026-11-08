"""eidoblend.course.plan: the course maths of eidoverse/terrain_base.js, in three's axes (plain Python, no bpy).

plan_course(config) runs the template's terrain branch exactly as the engine does (the same cursor walk, the same box
centres, sizes and tilts, the same telemetry segments, the same errors and log lines) and returns a Plan: the pieces
in three's axes (Y up, the course running toward -Z from the bottom edge at z = 1.5) and the segment table. builder.py
turns a Plan into Blender objects (three (x, y, z) -> Blender (x, -z, y): the course runs along +Y there).
test_course_parity.py runs terrain_base.js itself under deno and compares every piece and segment.

TERRAIN_CONFIG (the engine's schema; snake_case keys are accepted too):
    {'type': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 100}                       the default
    {'type': 'ramp', 'angleDeg': 33, 'horizLen': 28}
    {'type': 'stairs_pyramid', 'rise', 'run', 'numUp', 'numDown', 'plateauWidth': 3.0}
    {'type': 'ramp_pyramid', 'angleDeg', 'horizLen', 'plateauWidth': 3.0}
    {'type': 'obstacle_course', 'segments': [...]}   kinds: flat {length} | bump {height, depth, width 1.0} |
        dome {radius 0.40} | stairs {rise, run, num, dir 'up'|'down'} | wall {height 0.9, depth 0.35, width 3.0} |
        gap {length} | ladder {height 2.5, depth 0.5, width 3.0} | ramp {angleDeg, horizLen, dir}
    'groundExtent': 120   the ground plane's side (m)
"""
import math

FIRST_Z = 1.5            # the terrain's bottom edge, three z
WIDTH = 3.0              # the course's width (three x)
RAMP_THICKNESS = 0.5
RAIL_W = 0.5             # the ladder's rail spacing
PRECOURSE_Z = 6.0        # the precourse flat starts here (three z); the character starts at z = 5


def _num(v, digits=5):
    """_locNum: finite -> rounded to `digits` decimals, else None"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits)


def _snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def _camel(k):
    parts = k.split('_')
    return parts[0] + ''.join(p[:1].upper() + p[1:] for p in parts[1:])


def normalize_config(cfg):
    """accept the engine's camelCase keys or snake_case ones; returns a camelCase copy (the engine's spelling)"""
    if cfg is None:
        return {'type': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 100}
    out = {}
    for k, v in cfg.items():
        if k == 'segments':
            v = [{_camel(sk): sv for sk, sv in s.items()} for s in v]
        out[_camel(k)] = v
    return out


class Piece:
    """One mesh of the course, in three's axes: kind 'box' (size sx, sy, sz; rotation about X: rot_x), 'dome' (a top
    hemisphere of `radius` with its centre on the floor) or 'cylinder' (a rung: radius, length along three X).
    role: ground | step | ramp | plateau | slab | bump | wall | ladder | dome | rail | rung | bench.
    collider: 'cuboid' (half extents in three's axes, with the mesh's rotation) | 'ball' | None (visual fixtures)."""

    def __init__(self, kind, role, center, size=None, rot_x=0.0, rot_z=0.0, radius=None, length=None,
                 collider='cuboid', segment=None, material='obstacle'):
        self.kind, self.role = kind, role
        self.center = tuple(float(c) for c in center)
        self.size = tuple(float(s) for s in size) if size else None
        self.rot_x, self.rot_z = float(rot_x), float(rot_z)
        self.radius, self.length = radius, length
        self.collider = collider
        self.segment = segment
        self.material = material

    def half(self):
        return tuple(s / 2 for s in self.size) if self.size else None

    def as_dict(self):
        return {'kind': self.kind, 'role': self.role, 'center': self.center, 'size': self.size, 'rot_x': self.rot_x,
                'rot_z': self.rot_z, 'radius': self.radius, 'length': self.length, 'collider': self.collider,
                'segment': self.segment, 'material': self.material}


class Plan:
    def __init__(self, config):
        self.config = config
        self.pieces = []
        self.segments = []
        self.log = []
        self.tag = ''
        self.final_floor = 0.0
        self.end_z = FIRST_Z
        self.ground_extent = float(config.get('groundExtent') or 120)


def _tag(tc):
    if tc.get('type') == 'ramp':
        return '[rapier-terrain-ramp%d]' % round(tc['angleDeg'])
    rise, run = tc.get('rise'), tc.get('run')
    if rise is None or run is None:            # the engine prints NaN here (obstacle courses, ramp pyramids)
        return '[rapier-terrain-stairsNaNxNaN]'
    return '[rapier-terrain-stairs%dx%d]' % (_js_round(rise * 100), _js_round(run * 100))


def _js_round(v):
    return int(math.floor(v + 0.5))


def _seg_record(index, kind, label, start_z, end_z, start_y, end_y, seg=None):
    seg = seg or {}
    return {'index': index, 'kind': kind, 'dir': seg.get('dir'), 'label': label, 'startZ': _num(start_z),
            'endZ': _num(end_z), 'startY': _num(start_y), 'endY': _num(end_y), 'length': _num(start_z - end_z),
            'rise': _num(seg.get('rise')), 'run': _num(seg.get('run')), 'num': seg.get('num'),
            'angleDeg': _num(seg.get('angleDeg')), 'height': _num(seg.get('height')),
            'depth': _num(seg.get('depth')), 'radius': _num(seg.get('radius'))}


def plan_course(config=None):
    """TERRAIN_CONFIG -> Plan (pieces in three's axes, the telemetry segments, the template's log lines)."""
    tc = normalize_config(config)
    P = Plan(tc)
    P.tag = _tag(tc)
    P.pieces.append(Piece('plane', 'ground', (0, 0, 0), (P.ground_extent, 0, P.ground_extent), collider='ground',
                          material='ground'))
    P.segments.append({'index': -1, 'kind': 'flat', 'dir': None, 'label': 'precourse_flat', 'startZ': 6,
                       'endZ': FIRST_Z, 'startY': 0, 'endY': 0, 'length': 6 - FIRST_Z, 'rise': None, 'run': None,
                       'num': None, 'angleDeg': None, 'height': None, 'depth': None, 'radius': None})
    t = tc.get('type')
    if t == 'stairs':
        RISE, RUN, NUM = tc['rise'], tc['run'], tc['num']
        for i in range(NUM):
            h = RISE * (i + 1)
            z = FIRST_Z - i * RUN
            P.pieces.append(Piece('box', 'step', (0, h / 2, z), (WIDTH, h, RUN)))
        P.end_z = FIRST_Z - (NUM - 1) * RUN - RUN / 2
        P.final_floor = RISE * NUM
        P.log.append('%s stairs %dx %sm x %sm, angle %d deg' % (P.tag, NUM, RISE, RUN,
                                                                 int(math.atan2(RISE, RUN) * 180 / math.pi)))
    elif t == 'ramp':
        ang = tc['angleDeg'] * math.pi / 180
        hl = tc['horizLen']
        rise = hl * math.tan(ang)
        L = math.sqrt(hl ** 2 + rise ** 2)
        th = RAMP_THICKNESS
        c, s = math.cos(ang), math.sin(ang)
        y_off = (th / 2) * c - (L / 2) * s
        z_off = (th / 2) * s + (L / 2) * c
        P.pieces.append(Piece('box', 'ramp', (0, -y_off, FIRST_Z - z_off), (WIDTH, th, L), rot_x=ang))
        P.end_z = FIRST_Z - hl
        P.final_floor = rise
        P.log.append('%s ramp %s deg horiz=%sm rise=%.2fm' % (P.tag, tc['angleDeg'], hl, rise))
    elif t == 'stairs_pyramid':
        RISE, RUN = tc['rise'], tc['run']
        NUM_UP, NUM_DOWN = tc['numUp'], tc['numDown']
        PW = tc.get('plateauWidth') if tc.get('plateauWidth') is not None else 3.0
        for i in range(NUM_UP):
            h = RISE * (i + 1)
            z = FIRST_Z - i * RUN
            P.pieces.append(Piece('box', 'step', (0, h / 2, z), (WIDTH, h, RUN)))
        peak = RISE * NUM_UP
        last_up_z = FIRST_Z - (NUM_UP - 1) * RUN
        plateau_z = last_up_z - RUN / 2 - PW / 2
        P.pieces.append(Piece('box', 'plateau', (0, peak / 2, plateau_z), (WIDTH, peak, PW)))
        down_start = plateau_z - PW / 2 - RUN / 2
        end_z = plateau_z - PW / 2
        for i in range(NUM_DOWN):
            h = peak - (i + 1) * RISE
            if h <= 0:
                break
            z = down_start - i * RUN
            P.pieces.append(Piece('box', 'step', (0, h / 2, z), (WIDTH, h, RUN)))
            end_z = z - RUN / 2
        P.end_z = end_z
        P.log.append('%s pyramid stairs: %dup + %sm plateau + %ddown @ %sm x %sm, peak=%.2fm'
                     % (P.tag, NUM_UP, PW, NUM_DOWN, RISE, RUN, peak))
    elif t == 'ramp_pyramid':
        ang = tc['angleDeg'] * math.pi / 180
        hl = tc['horizLen']
        rise = hl * math.tan(ang)
        L = math.sqrt(hl ** 2 + rise ** 2)
        th = RAMP_THICKNESS
        c, s = math.cos(ang), math.sin(ang)
        PW = tc.get('plateauWidth') if tc.get('plateauWidth') is not None else 3.0
        y_off = (th / 2) * c - (L / 2) * s
        z_off = (th / 2) * s + (L / 2) * c
        P.pieces.append(Piece('box', 'ramp', (0, -y_off, FIRST_Z - z_off), (WIDTH, th, L), rot_x=ang))
        peak_z = FIRST_Z - hl
        P.pieces.append(Piece('box', 'plateau', (0, rise / 2, peak_z - PW / 2), (WIDTH, rise, PW)))
        down_z = peak_z - PW
        y_off_d = (th / 2) * c + (L / 2) * s
        z_off_d = -(th / 2) * s + (L / 2) * c
        P.pieces.append(Piece('box', 'ramp', (0, rise - y_off_d, down_z - z_off_d), (WIDTH, th, L), rot_x=-ang))
        P.end_z = down_z - hl
        P.log.append('%s pyramid ramp: %s deg up + %sm plateau + %s deg down, peak=%.2fm'
                     % (P.tag, tc['angleDeg'], PW, tc['angleDeg'], rise))
    elif t == 'obstacle_course':
        _obstacle_course(P, tc.get('segments') or [])
    else:
        raise ValueError('unknown TERRAIN_CONFIG.type: %s' % t)
    return P


def _obstacle_course(P, segments):
    cz = FIRST_Z
    cy = 0.0
    for si, seg in enumerate(segments):
        sz, sy = cz, cy
        k = seg.get('kind')
        if k == 'flat':
            if cy > 0.001:
                ln = seg['length']
                P.pieces.append(Piece('box', 'slab', (0, cy / 2, cz - ln / 2), (WIDTH, cy, ln), segment=si))
            cz -= seg['length']
        elif k == 'bump':
            h, d = seg['height'], seg['depth']
            w = seg.get('width') if seg.get('width') is not None else 1.0
            P.pieces.append(Piece('box', 'bump', (0, cy + h / 2, cz - d / 2), (w, h, d), segment=si))
            cz -= d
        elif k == 'dome':
            r = seg.get('radius') if seg.get('radius') is not None else 0.40
            P.pieces.append(Piece('dome', 'dome', (0, cy, cz - r), radius=r, collider='ball', segment=si))
            cz -= 2 * r
        elif k == 'stairs':
            rise, run, num = seg['rise'], seg['run'], seg['num']
            up = (seg.get('dir') or 'up') == 'up'
            for i in range(num):
                top = (cy + rise * (i + 1)) if up else (cy - rise * (i + 1))
                if top <= 0.001:
                    continue
                z = cz - i * run - run / 2
                P.pieces.append(Piece('box', 'step', (0, top / 2, z), (WIDTH, top, run), segment=si))
            cz -= num * run
            cy = (cy + rise * num) if up else (cy - rise * num)
        elif k == 'wall':
            h = seg.get('height') if seg.get('height') is not None else 0.9
            d = seg.get('depth') if seg.get('depth') is not None else 0.35
            w = seg.get('width') if seg.get('width') is not None else 3.0
            P.pieces.append(Piece('box', 'wall', (0, cy + h / 2, cz - d / 2), (w, h, d), segment=si))
            cz -= d
        elif k == 'gap':
            cz -= seg['length']
        elif k == 'ladder':
            h = seg.get('height') if seg.get('height') is not None else 2.5
            d = seg.get('depth') if seg.get('depth') is not None else 0.5
            w = seg.get('width') if seg.get('width') is not None else 3.0
            P.pieces.append(Piece('box', 'ladder', (0, cy + h / 2, cz - d / 2), (w, h, d), segment=si))
            for sx in (-RAIL_W / 2, RAIL_W / 2):
                P.pieces.append(Piece('box', 'rail', (sx, cy + h / 2, cz + 0.09), (0.06, h, 0.06), collider=None,
                                      segment=si, material='rail'))
            ry = cy + 0.25
            while ry < cy + h - 0.05:
                P.pieces.append(Piece('cylinder', 'rung', (0, ry, cz + 0.09), radius=0.028, length=RAIL_W,
                                      rot_z=math.pi / 2, collider=None, segment=si, material='rail'))
                ry += 0.28
            cz -= d
            cy += h
        elif k == 'ramp':
            ang = seg['angleDeg'] * math.pi / 180
            hl = seg['horizLen']
            up = (seg.get('dir') or 'up') == 'up'
            rise = hl * math.tan(ang)
            L = math.sqrt(hl * hl + rise * rise)
            th = RAMP_THICKNESS
            c, s = math.cos(ang), math.sin(ang)
            tilt = ang if up else -ang
            if up:
                center = (0, cy + rise / 2 - (th / 2) * c, cz - hl / 2 + (th / 2) * s)
            else:
                center = (0, cy - rise / 2 - (th / 2) * c, cz - hl / 2 - (th / 2) * s)
            P.pieces.append(Piece('box', 'ramp', center, (WIDTH, th, L), rot_x=tilt, segment=si))
            cz -= hl
            cy = (cy + rise) if up else (cy - rise)
        else:
            raise ValueError('obstacle_course: unknown segment kind: %s' % k)
        label = '%d:%s%s' % (si, k, (':' + seg['dir']) if seg.get('dir') else '')
        P.segments.append(_seg_record(si, k, label, sz, cz, sy, cy, seg))
        if cy < -0.001:
            raise ValueError('obstacle_course: cursorY went negative (%.3f) after segment %r: a descent segment '
                             'outsized the running height. Rebalance the course so cumulative rise stays >= 0.'
                             % (cy, seg))
    P.end_z = cz
    P.final_floor = cy
    P.log.append('%s obstacle_course: %d segments, traveled %.2fm, final floor Y=%.2f'
                 % (P.tag, len(segments), FIRST_Z - cz, cy))


def segment_at(segments, z):
    """_locTerrainAt: the segment whose [endZ, startZ] (three z) holds z, or None"""
    for s in segments:
        if z <= s['startZ'] + 1e-4 and z >= s['endZ'] - 1e-4:
            return s
    return None
