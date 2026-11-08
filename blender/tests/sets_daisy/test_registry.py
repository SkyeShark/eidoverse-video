"""tests/sets_daisy/test_registry.py: the sets registry (eidoblend.sets) and the DAISY package, in plain Python.

    python blender/tests/sets_daisy/test_registry.py

Importing eidoblend.sets and eidoblend.sets.daisy must load no set (no bpy); every DAISY and UNKNOWN FORCE module is
registered with its WebGPU source; the DAISY sets ported here are available; an unknown name and an unported one fail
with messages that say which.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.dont_write_bytecode = True
RESULTS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    RESULTS.append(bool(ok))


from eidoblend import sets                                   # noqa: E402
from eidoblend.sets import daisy                             # noqa: E402

check('importing the registry loads no set and no bpy', 'bpy' not in sys.modules and
      not any(m.startswith('eidoblend.sets.daisy.') or m.startswith('eidoblend.sets.unknown_force.') for m in sys.modules))
names = sets.names()
want = ['daisy.funeral', 'daisy.bridge', 'daisy.corner', 'daisy.ocean'] + \
    [f'unknown_force.{n}' for n in ('city', 'hole', 'quiet_room', 'showroom', 'corridor', 'news', 'race', 'bin')]
check('every set is registered', all(n in names for n in want), f'{len(names)} entries')
libs = sets.names(kind='library')
check('the UNKNOWN FORCE libraries are registered as libraries', set(libs) >= {
    'unknown_force.citykit', 'unknown_force.cn_lib', 'unknown_force.interiors_lib', 'unknown_force.quiet_room_art',
    'unknown_force.showroom_art', 'unknown_force.bin_pages'}, ', '.join(libs))
rows = {r['name']: r for r in sets.list()}
check('each entry names its WebGPU source, and the source exists',
      all(os.path.isfile(os.path.join(HERE, '..', '..', '..', r['source'])) for r in rows.values()),
      ', '.join(n for n, r in rows.items() if not os.path.isfile(os.path.join(HERE, '..', '..', '..', r['source']))))
check('the DAISY sets ported here are available', all(rows[n]['available'] for n in ('daisy.funeral', 'daisy.bridge',
                                                                                     'daisy.corner')))
for n, r in sorted(rows.items()):
    print(f"   {n:30s} {r['kind']:8s} {'ported' if r['available'] else 'not yet':8s} {r['source']}")
try:
    sets.get('daisy.nowhere')
    check('an unknown name raises KeyError', False)
except KeyError as e:
    check('an unknown name raises KeyError naming the registered ones', 'daisy.funeral' in str(e))
missing = [n for n, r in rows.items() if not r['available']]
if missing:
    try:
        sets.get(missing[0])
        check('an unported set raises ImportError', False)
    except ImportError as e:
        check('an unported set raises ImportError naming its WebGPU source', rows[missing[0]]['source'] in str(e),
              str(e))
try:
    sets.build('unknown_force.cn_lib')
    check('build() refuses a library', False)
except TypeError:
    check('build() refuses a library', True)
check('daisy package: the clock and the sections', abs(daisy.BAR - 1.875) < 1e-12 and daisy.SECTIONS['corner']['bars'] == (18, 30)
      and daisy.SUIT_SCALE == 0.87)
reg = sets.register('daisy.test_entry', 'eidoblend.sets.daisy.funeral', film='DAISY', source='eidoverse/sets/funeral.js')
check('register() adds an entry', 'daisy.test_entry' in sets.names() and sets.available('daisy.test_entry'))
del sets.REGISTRY['daisy.test_entry']


# build() places the harness ctx where each builder shape takes it (the fixture's three builders, no Blender)
class FakeCtx:                                                # the harness Ctx: what build() reads of it
    scene = 'the-scene'


ctx = FakeCtx()
for n, entry in (('ctx', 'build_ctx'), ('scene', 'build_scene'), ('opts', 'build_opts')):
    sets.register(f'test.{n}', 'tests.sets_daisy._registry_fixture', entry=entry, film='TEST')
a = sets.build('test.ctx', ctx, seed=3)
b = sets.build('test.scene', ctx, opts={'k': 1})
c = sets.build('test.opts', ctx, opts={'k': 2})
check('build() hands the ctx to a build(ctx) builder', a['ctx'] is ctx and a['seed'] == 3)
check('build() hands ctx.scene to a build(scene) builder', b['scene'] == 'the-scene' and b['opts'] == {'k': 1})
check('build() leaves the ctx out of a build(opts) builder', c == {'opts': {'k': 2}})
check('build() without a ctx passes the options alone', sets.build('test.ctx', seed=4) == {'ctx': None, 'seed': 4})
for n in ('ctx', 'scene', 'opts'):
    del sets.REGISTRY[f'test.{n}']
print(f'[test_registry] {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed')
sys.exit(0 if all(RESULTS) else 1)
