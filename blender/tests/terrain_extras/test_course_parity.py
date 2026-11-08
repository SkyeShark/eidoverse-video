"""eidoblend.course's plan against the engine's own terrain_base.js, piece for piece.

Runs with system Python (no Blender):
    python blender/tests/terrain_extras/test_course_parity.py
It runs terrain_base.js's setup() under deno on a recording stand-in for three.js (course_dump.mjs) for every preset,
the course example, the template's default and two configs the engine refuses, then builds the same with
eidoblend/course/plan.py and compares: every mesh's geometry and parameters, position and rotation (to 1e-12), its
material colour, the telemetry segments (exactly), and the errors. Exit 1 on a mismatch, 2 when deno is missing.
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
sys.path.insert(0, str(WORKTREE / 'blender' / 'eidoblend' / 'course'))
import plan  # noqa: E402  (plain modules: no bpy)
import presets  # noqa: E402

SRC = WORKTREE / 'eidoverse' / 'terrain_base.js'
COLORS = {'obstacle': 0xd97550, 'ground': 0x2a2a2a, 'rail': 0xb8c2cc}
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        FAILS.append(msg)


def configs():
    c = {k: v for k, v in presets.PRESETS.items()}
    c['example_obstacle_course'] = presets.EXAMPLES['obstacle_course']['config']
    c['bad_negative_floor'] = {'type': 'obstacle_course', 'segments': [
        {'kind': 'stairs', 'rise': 0.2, 'run': 0.3, 'num': 2, 'dir': 'up'},
        {'kind': 'stairs', 'rise': 0.2, 'run': 0.3, 'num': 3, 'dir': 'down'}]}
    c['bad_kind'] = {'type': 'obstacle_course', 'segments': [{'kind': 'trampoline', 'length': 1}]}
    c['all_kinds'] = {'type': 'obstacle_course', 'groundExtent': 60, 'segments': [
        {'kind': 'flat', 'length': 1.0}, {'kind': 'dome'}, {'kind': 'bump', 'height': 0.2, 'depth': 0.4, 'width': 2},
        {'kind': 'ladder'}, {'kind': 'flat', 'length': 1.5}, {'kind': 'gap', 'length': 0.8},
        {'kind': 'wall', 'height': 0.4, 'depth': 0.3, 'width': 1.5}, {'kind': 'ramp', 'angleDeg': 12, 'horizLen': 3,
                                                                       'dir': 'down'},
        {'kind': 'stairs', 'rise': 0.15, 'run': 0.3, 'num': 4, 'dir': 'down'}, {'kind': 'flat', 'length': 2}]}
    return c


def close(a, b, tol=1e-12):
    return all(abs(x - y) <= tol * max(1.0, abs(y)) for x, y in zip(a, b))


def expected_geo(p):
    if p.kind == 'box':
        return 'Box', list(p.size)
    if p.kind == 'dome':
        return 'Sphere', [p.radius, 32, 16, 0, math.pi * 2, 0, math.pi / 2]
    if p.kind == 'cylinder':
        return 'Cylinder', [p.radius, p.radius, p.length, 10]
    return 'Plane', [p.size[0], p.size[2]]


def main():
    deno = shutil.which('deno')
    if not deno:
        print('SKIP: deno not on PATH')
        return 2
    cf = configs()
    tmp = Path(tempfile.mkdtemp(prefix='course_parity_'))
    (tmp / 'configs.json').write_text(json.dumps(cf))
    out = tmp / 'engine.json'
    subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', str(HERE / 'course_dump.mjs'), str(SRC),
                    str(tmp / 'configs.json'), str(out)], check=True)
    eng = json.loads(out.read_text())
    for name, cfg in cf.items():
        e = eng[name]
        try:
            P = plan.plan_course(cfg)
            err = None
        except ValueError as ex:
            P, err = None, str(ex)
        if name.startswith('bad_'):
            ok = err is not None and e['error'] is not None and \
                e['error'].split(':')[0] == err.split(':')[0] and ('character_vrm' not in e['error'])
            check(ok, '%-26s both refuse it: engine "%s" / port "%s"' % (name, (e['error'] or '')[:60], (err or '')[:60]))
            continue
        check(e['error'] is not None and 'character_vrm' in e['error'],
              '%-26s the engine built the terrain and stopped at the character (%s)' % (name, e['error']))
        meshes = e['meshes']
        ok_n = len(meshes) == len(P.pieces)
        bad = []
        for i, (m, p) in enumerate(zip(meshes, P.pieces)):
            geo, args = expected_geo(p)
            if m['geo'] != geo or not close(m['args'], args):
                bad.append('%d geo %s%s vs %s%s' % (i, m['geo'], m['args'], geo, args))
                continue
            if p.role == 'ground':
                if not (close(m['pos'], [0, 0, 0]) and close(m['rot'], [-math.pi / 2, 0, 0])):
                    bad.append('ground transform')
            else:
                if not close(m['pos'], p.center):
                    bad.append('%d %s pos %s vs %s' % (i, p.role, m['pos'], p.center))
                if not close(m['rot'], [p.rot_x, 0, p.rot_z]):
                    bad.append('%d %s rot %s vs %s' % (i, p.role, m['rot'], (p.rot_x, p.rot_z)))
            if m['color'] != COLORS[p.material]:
                bad.append('%d colour %s vs %s' % (i, m['color'], COLORS[p.material]))
            fixture = p.role in ('rail', 'rung')
            if fixture != bool(m['userData'].get('noClippingCheck')):
                bad.append('%d fixture flags' % i)
            if p.role not in ('rail', 'rung') and not m['userData'].get('noSupportCheck'):
                bad.append('%d noSupportCheck missing on a terrain piece' % i)
        check(ok_n and not bad, '%-26s %d meshes (port %d)%s' % (name, len(meshes), len(P.pieces),
                                                                 (': ' + '; '.join(bad[:4])) if bad else ''))
        segs_ok = e['segments'] == P.segments
        check(segs_ok, '%-26s %d telemetry segments identical' % (name, len(P.segments)))
        if not segs_ok:
            for a, b in zip(e['segments'], P.segments):
                if a != b:
                    print('   engine', a)
                    print('   port  ', b)
                    break
    # snake_case configs (the Python spelling) plan the same course as the engine's camelCase
    snake = {'type': 'obstacle_course', 'ground_extent': 60, 'segments': [
        {'kind': 'ramp', 'angle_deg': 12, 'horiz_len': 3, 'dir': 'up'}, {'kind': 'flat', 'length': 1},
        {'kind': 'ladder', 'height': 1.5}]}
    camel = {'type': 'obstacle_course', 'groundExtent': 60, 'segments': [
        {'kind': 'ramp', 'angleDeg': 12, 'horizLen': 3, 'dir': 'up'}, {'kind': 'flat', 'length': 1},
        {'kind': 'ladder', 'height': 1.5}]}
    a, b = plan.plan_course(snake), plan.plan_course(camel)
    check([p.as_dict() for p in a.pieces] == [p.as_dict() for p in b.pieces] and a.segments == b.segments
          and a.ground_extent == 60, 'snake_case config keys plan the same course as camelCase')
    s = plan.plan_course(None)
    check(len(s.pieces) == 101 and s.config['type'] == 'stairs', 'no config: the template default (100 stairs)')
    print('%s: %d failing' % ('FAIL' if FAILS else 'PASS', len(FAILS)))
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
