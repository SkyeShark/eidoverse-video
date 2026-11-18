"""The Blender edition's op attributes the level runner reads (run.py _evolves, _post, _takes_ctx), for the runner
test's replayed ops (tests/hydro/runner_test.mjs): every op the registry collects, with its `evolves`, its `post` and
whether its signature takes ctx, as run.py decides each; and every registered recipe's resolve() for its default
knobs (the knob values and the stages as Stage.to_dict(), with each knob's apply run: the stages run_levels receives,
which the floor runs' stages.json does not keep).

    <Blender's python> -I eidoverse/terrain/tests/hydro/blender_ops.py [<out.json>]

Writes tests/out/hydro/blender_ops.json by default. Runs in Blender's own Python (numpy only, no bpy), never the
system Python (PORT_PLAN.md 5.1, C6); the Blender edition is found as tests/parity/_blender.py finds it (blender/
beside eidoverse/ in this checkout, else $EIDO_BLENDER_EDITION) and is only read.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

sys.dont_write_bytecode = True
B.bare_terrain_package()

from eidoblend.terrain import recipes as RC  # noqa: E402
from eidoblend.terrain import run as RUN  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'out', 'hydro', 'blender_ops.json')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    names = sorted(RC._collect_ops().keys()) if hasattr(RC, '_collect_ops') else sorted(RC.op_names())
    ops = {}
    for n in names:
        fn = RUN.get_op(n)
        ops[n] = dict(evolves=RUN._evolves(n), post=RUN._post(n), takes_ctx=RUN._takes_ctx(fn),
                      module=getattr(fn, '__module__', None))
    recipes = {}
    for name in RC.names():
        values, stages = RC.get(name).resolve({})
        recipes[name] = dict(values=B.jsonable(values), stages=[st.to_dict() for st in stages],
                             defaults=B.jsonable(dict(RC.get(name).defaults or {})))
    rec = dict(source='the Blender edition (blender/eidoblend/terrain), by tests/hydro/blender_ops.py', key=B.source_key(),
               versions=B.versions(), evolving=sorted(RUN.EVOLVING), ops=ops, recipes=recipes)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print(f'[blender_ops] {len(ops)} ops -> {out}')


if __name__ == '__main__':
    main()
