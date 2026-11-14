"""test_plain.py: the harness-rest ports that need no Blender, checked against the engine's own JavaScript.

    python blender/tests/pipeline2/test_plain.py            # from the worktree root; needs deno for the parity parts

  A  audit_core.js's own suite (audit_core_test.mjs) run under Deno on this machine: the expectations ported below
  B  ledger.py (audit_core.js ported): the suite's cases that need no scene, on synthetic leaves
  C  gpu_check.mjs's suite (gpu_check_test.mjs, run under Deno) and its cases on gpu_check.classify
  D  [KIT_INFO]: model_preview.classify_kit against the preview script's own kit heuristic (fetch_model.py's JS)
  E  render_common.mjs: getCameraAtTime and alphaComposite against the module's own source
  F  html_mesh: the painter (layout size, borders, the overflow clip, inputs) on images
  G  the palette's showpiece nudge (render_scene.mjs's trigger table) on synthetic scenes
Prints PASS / FAIL per check; exit 0 when all pass.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, 'out', 'plain')
sys.path.insert(0, os.path.join(ROOT, 'blender'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'tests'))
import _where  # noqa: E402  (the checkout that holds node_modules/: this one, or a worktree's main checkout)

THREE = os.path.join(str(_where.main_checkout()), 'node_modules', 'three', 'build', 'three.module.js')
DENO = shutil.which('deno')
results = []


def check(name, ok, msg=''):
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}: {msg}", flush=True)


def deno(script_path, *args, timeout=120):
    r = subprocess.run([DENO, 'run', '--no-config', '--no-lock', '-A', script_path, *args], capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=timeout, cwd=OUT)
    return r.returncode, r.stdout, r.stderr


def file_url(p):
    return 'file:///' + os.path.abspath(p).replace('\\', '/')


# ------------------------------------------------------------------------------------------------------- A ---
def part_a():
    if not DENO or not os.path.exists(THREE):
        return check('A audit_core_test.mjs', False, f'deno {DENO} / three {THREE} missing')
    src = open(os.path.join(ROOT, 'eidoverse', 'audit_core_test.mjs'), encoding='utf-8').read()
    src = src.replace("'npm:three@0.184.0'", repr(file_url(THREE)))
    src = src.replace("'./audit_core.js'", repr(file_url(os.path.join(ROOT, 'eidoverse', 'audit_core.js'))))
    p = os.path.join(OUT, 'audit_core_test_local.mjs')
    open(p, 'w', encoding='utf-8').write(src)
    rc, out, err = deno(p)
    oks = len(re.findall(r'^\s+ok ', out, re.M))
    check('A audit_core_test.mjs passes under Deno', rc == 0 and 'ALL PASS' in out,
          f'{oks} ok lines; ' + (out.strip().splitlines()[-1] if out.strip() else err[-300:]))


# ------------------------------------------------------------------------------------------------------- B ---
def part_b():
    from eidoblend.harness import ledger as L

    def leaf(i, x, size=1.0, prov=None, vis=True, tris=12, owner=None, dims=None):
        h = size / 2
        return L.make_leaf(i, i, ((x - h, -h, -h), (x + h, h, h)), dims or (size, size, size), tris, vis, False,
                           prov, owner or i)

    def recs(leaves, nodes=(), policy=None, **kw):
        inv = L.build_inventory(leaves, **kw)
        decl = L.map_declarations(inv, nodes)
        return inv, decl, L.coverage_records(decl, inv, policy or L.snapshot_policy({}))
    # 2. collision without provenance never merges; same provenance + embedding merges; touching stays apart
    n1 = len(L.build_inventory([leaf('a', 0), leaf('b', 0.2)])['bodies'])
    n2 = len(L.build_inventory([leaf('a', 0, prov='kitA'), leaf('b', 0.2, prov='kitA')])['bodies'])
    n3 = len(L.build_inventory([leaf('a', 0, prov='kitA'), leaf('b', 1.0, prov='kitA')])['bodies'])
    check('B2 identity: no provenance 2, embedded kit 1, touching kit 2', (n1, n2, n3) == (2, 1, 2), f'{(n1, n2, n3)}')
    # 3. an invisible enclosing hull glues nothing
    inv = L.build_inventory([leaf('p0', -5), leaf('p1', 0), leaf('p2', 5), leaf('hull', 0, 20, vis=False)])
    check('B3 3 props + a hidden 20 m hull = 4 bodies', len(inv['bodies']) == 4, f"{len(inv['bodies'])}")
    # 4. sharding a flag over every leaf of a body equals flagging its parent
    lv = [leaf('a', 0, prov='kitB', owner='a'), leaf('b', 0.2, prov='kitB', owner='b')]
    inv = L.build_inventory(lv)
    whole = L.map_declarations(inv, [{'label': 'asset', 'flags': {'allow_intersect': True}, 'leaf_ids': {'a', 'b'}}])
    shard = L.map_declarations(inv, [{'label': 'a', 'flags': {'allowIntersect': True}, 'leaf_ids': {'a'}},
                                     {'label': 'b', 'flags': {'allow_intersect': True}, 'leaf_ids': {'b'}}])
    fw, fs = whole['union_by_flag']['allow_intersect'], shard['union_by_flag']['allow_intersect']
    check('B4 parent flag and per-leaf flags both full=1 partial=0',
          (len(fw['full']), len(fw['partial']), len(fs['full']), len(fs['partial'])) == (1, 0, 1, 0),
          f"{len(fw['full'])}/{len(fw['partial'])} and {len(fs['full'])}/{len(fs['partial'])}")
    # 5. alias spellings union under the sensor
    lv = [leaf('a', 0), leaf('b', 5), leaf('c', 10), leaf('d', 15)]
    nodes = [{'label': 'a', 'flags': {'allow_intersect': 1}, 'leaf_ids': {'a'}},
             {'label': 'b', 'flags': {'no_clipping_check': True}, 'leaf_ids': {'b'}},
             {'label': 'c', 'flags': {'assembly': 'x'}, 'leaf_ids': {'c'}}]
    _i, decl, _r = recs(lv, nodes)
    u = decl['union_by_sensor'].get('clipping')
    check('B5 the clipping sensor spans all three alias spellings', u and len(u['full']) == 3, f"{u and len(u['full'])}")
    # 6. ballast cannot dilute systemic coverage
    lv = [leaf('real', 0)] + [leaf(f'h{i}', 100 + 5 * i, vis=False) for i in range(50)]
    _i, _d, rs = recs(lv, [{'label': 'real', 'flags': {'no_support_check': True}, 'leaf_ids': {'real'}}])
    sysr = next((r for r in rs if r['check'] == 'coverage.sensor.support'), None)
    check('B6 support coverage 100% of PHYSICAL bodies despite 50 hidden', sysr and sysr['metrics']['fraction'] == 1
          and sysr['outcome'] == 'WARN', f"{sysr and sysr['metrics']}")
    # 8. L is rotation invariant (dims are local extents x scale)
    a = L.make_leaf('m', 'm', ((-5, -.5, -.5), (5, .5, .5)), (10, 1, 1), 12)
    b = L.make_leaf('m', 'm', ((-3.9, -3.9, -.5), (3.9, 3.9, .5)), (10, 1, 1), 12)     # the box yawed 45 deg
    check('B8 L identical at 0 and 45 deg yaw', abs(a['L'] - b['L']) < 1e-9 and a['L'] == 1.0, f"{a['L']} {b['L']}")
    # 9. a truthy non-boolean global is recorded, in the engine's words
    _i, _d, rs = recs([leaf('a', 0)], policy=L.snapshot_policy({'_noMotionCheck': 1}))
    hit = next((r for r in rs if r['check'] == 'motion.envelope' and r['outcome'] == 'SKIPPED'), None)
    check('B9 _no_motion_check = 1: SKIPPED with "non-boolean number"', hit and 'non-boolean number' in hit['message'],
          hit['message'] if hit else 'missing')
    # 10. degenerate geometry is inventoried, not physical
    inv = L.build_inventory([L.make_leaf('pt', 'pt', ((0, 0, 0), (0, 0, 0)), (0, 0, 0), 0), leaf('box', 5)])
    check('B10 a zero-extent zero-triangle mesh: 2 bodies, 1 physical',
          len(inv['bodies']) == 2 and len(inv['physical_bodies']) == 1, f"{len(inv['bodies'])}/{len(inv['physical_bodies'])}")
    # 11. a lone declaration reaches the digest, with the review gate
    lv = [leaf('lone_sign', 0)] + [leaf(f'b{i}', 10 + 5 * i) for i in range(30)]
    _i, _d, rs = recs(lv, [{'label': 'lone_sign', 'flags': {'noFacingCheck': True}, 'leaf_ids': {'lone_sign'}}])
    led = L.create_ledger()
    for r in rs:
        led.record(**r)
    txt = L.digest_from_ledger(led)
    check('B11 1-of-31 no_facing_check in the digest, review gate inside',
          'no_facing_check' in txt and 'lone_sign' in txt and 'REVIEW GATE' in txt, '')
    # 12. clean semantics
    def clean(rs):
        lg = L.create_ledger()
        for r in rs:
            lg.record(**r)
        return lg.is_clean()
    c1 = clean(recs([leaf('a', 0)])[2])
    c2 = clean(recs([leaf('a', 0)], policy=L.snapshot_policy({'_no_auto_placement_check': True}))[2])
    c3 = clean(recs([leaf('a', 0)], [{'label': 'a', 'flags': {'allow_intersect': True}, 'leaf_ids': {'a'}}])[2])
    check('B12 bare clean, a global disable not clean, a declaration not clean', (c1, c2, c3) == (True, False, False),
          f'{(c1, c2, c3)}')
    # 13. embed_frac clamps (0 and NaN cannot merge touching parts)
    lv = [leaf('a', 0, prov='k'), leaf('b', 1.0, prov='k')]
    n0 = len(L.build_inventory(lv, embed_frac=0)['bodies'])
    nn = len(L.build_inventory(lv, embed_frac=float('nan'))['bodies'])
    check('B13 embed_frac 0 / NaN cannot merge touching parts', (n0, nn) == (2, 2), f'{(n0, nn)}')
    # 14. an explicit registration cannot merge islands; it is recorded
    inv = L.build_inventory([leaf('g0', 0, owner='g0'), leaf('g1', 8, owner='g1')],
                            explicit_bodies=[('claimed_one_body', {'g0', 'g1'})])
    co = inv['coalescence_declarations']
    check('B14 islands stay 2 bodies; one coalescence declaration with 2 islands',
          len(inv['bodies']) == 2 and len(co) == 1 and co[0]['islands'] == 2, f'{co}')
    # the opacity gate does not exist here: switching it off is recorded as having no effect
    _i, _d, rs = recs([leaf('a', 0)], policy=L.snapshot_policy({'_noOpacityCheck': True}))
    op = [r for r in rs if r['check'] == 'opacity']
    check('B+ _no_opacity_check: recorded INFO, nothing unobserved', op and op[0]['outcome'] == 'PASS'
          and 'no such check' in op[0]['message'], op[0]['message'][:90] if op else 'missing')
    # the sweep that replaced the all-pairs loop gives the all-pairs answer
    import random
    rnd = random.Random(5)
    lv = [L.make_leaf(f'l{i}', 'x', ((x, y, 0), (x + s, y + s, s)), (s, s, s), 12, True, False, 'kit')
          for i, (x, y, s) in enumerate((rnd.uniform(0, 150), rnd.uniform(0, 3), rnd.uniform(0.2, 2)) for _ in range(300))]
    inv = L.build_inventory(lv)
    par = list(range(len(lv)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i in range(len(lv)):
        for j in range(i + 1, len(lv)):
            if L.overlap_fraction(lv[i]['box'], lv[j]['box']) >= 0.25:
                par[find(j)] = find(i)
    brute = len({find(i) for i in range(len(lv))})
    check('B+ the x-sweep merges exactly as the all-pairs loop (300 random boxes)', brute == len(inv['bodies']),
          f"sweep {len(inv['bodies'])} bodies, all pairs {brute}")


# ------------------------------------------------------------------------------------------------------- C ---
def part_c():
    from eidoblend.harness import gpu_check as G
    if DENO:
        r = subprocess.run([DENO, 'test', '--no-config', '--no-lock', '-A',
                            os.path.join(ROOT, 'eidoverse', 'gpu_check_test.mjs')], capture_output=True, text=True,
                           timeout=120, cwd=OUT)
        m = re.search(r'(\d+) passed.*?(\d+) failed', r.stdout + r.stderr)
        check('C gpu_check_test.mjs passes under Deno', r.returncode == 0, m.group(0) if m else (r.stderr[-200:]))

    def cls(info):
        w = []
        out = G.classify(dict(info), w.append)
        return out['backend'], w
    b, w = cls({'description': 'NVIDIA GeForce RTX 5090', 'is_fallback_adapter': False})
    check('C1 hardware accepted, no warning', b == 'hardware' and not w, f'{b} {w}')
    b, w = cls({'vendor': '0', 'device': '0', 'description': 'D3D12 (NVIDIA GeForce RTX 5090 Laptop GPU)',
                'is_fallback_adapter': False})
    check('C2 Mesa D3D12 with zero vendor/device ids is hardware', b == 'hardware' and not w, b)
    b, w = cls({'description': 'Adapter 0', 'is_fallback_adapter': True})
    check('C3 a software fallback with an unfamiliar name warns (CPU)', b == 'software' and len(w) == 1 and 'CPU' in w[0], b)
    names = ['llvmpipe (LLVM 21)', 'lavapipe', 'Google SwiftShader', 'Microsoft Basic Render Driver', 'WARP', 'softpipe']
    got = [cls({'description': n, 'is_fallback_adapter': False}) for n in names]
    check('C4 known software names are software even with the flag false',
          all(b == 'software' and len(w) == 1 for b, w in got), f'{[b for b, _ in got]}')
    got = [cls(i) for i in ({'description': 'Unidentified driver'}, {'is_fallback_adapter': False})]
    check('C6 unverifiable adapters are unknown and warn', all(b == 'unknown' and len(w) == 1 for b, w in got),
          f'{[b for b, _ in got]}')
    b, w = cls({'description': 'Adapter 0', 'is_fallback_adapter': True})
    b2, _ = cls({'description': 'AMD Radeon', 'is_fallback_adapter': False})
    check('C7 legacy info: a fallback flag alone makes software; AMD hardware', (b, b2) == ('software', 'hardware'),
          f'{b} {b2}')


# ------------------------------------------------------------------------------------------------------- D ---
KIT_CASES = [
    ['bananas_a', 'bananas_b', 'bananas_c', 'bananas_d', 'banana_single'],
    ['coffee_cart', 'mug_01', 'mug_02', 'sign'],
    ['door_centered_large_01', 'door_left_small_02', 'window_round_a', 'window_round_b', 'cornice_01', 'cornice_02',
     'cornice_03', 'pillar', 'roof_tile'],
    ['searsia_lucida_a_LOD0', 'searsia_lucida_b_LOD0', 'searsia_lucida_c_LOD1'],
    ['desk', 'chair', 'lamp'],
    ['beaker_s', 'beaker_m', 'beaker_l', 'flask'],
    ['crate_small', 'pipe_elbow_01', 'post_tall'],
    ['part.001', 'part.002', 'thing'],
]


def part_d():
    from eidoblend.harness import model_preview as MP
    src = open(os.path.join(ROOT, 'fetch_model.py'), encoding='utf-8').read()
    js = src[src.index('_PREVIEW_SCENE_DENO_JS = r"""'):]
    block = js[js.index('if (parts.length >= 2) {'):js.index("} catch (e) { console.error('[preview] kit-detect")]
    dump = ('const lines = [];\nconst console = { log: (s) => lines.push(s) };\n'
            'for (const parts of JSON.parse(Deno.args[0])) {\n' + block + '\n lines.push("--"); }\n'
            'globalThis.console.log(JSON.stringify(lines));\n')
    p = os.path.join(OUT, 'kit_info_dump.mjs')
    open(p, 'w', encoding='utf-8').write(dump)
    if not DENO:
        return check('D [KIT_INFO] parity', False, 'no deno')
    # Blender appends '.001' to a duplicate name; three keeps the file's names: compare on the names as filed
    cases = [[re.sub(r'\.\d{3}$', '', n) for n in c] for c in KIT_CASES]
    rc, out, err = deno(p, json.dumps(cases))
    if rc != 0:
        return check('D [KIT_INFO] parity', False, err[-300:])
    js_lines = json.loads(out.strip().splitlines()[-1])
    per, cur = [], []
    for ln in js_lines:
        if ln == '--':
            per.append(cur[0] if cur else None)
            cur = []
        else:
            cur.append(ln)

    def key(line):
        if line is None:
            return None
        m = re.match(r'\[KIT_INFO\] (LIKELY A MODULAR KIT / ASSET-LIBRARY: )?(\d+) named parts(, (\d+)% in repeated '
                     r'variant-families)? \(([^)]*)\)', line)
        return (bool(m.group(1)), m.group(2), m.group(4), m.group(5)) if m else line
    bad = []
    for c, jl in zip(KIT_CASES, per):
        pl = MP.classify_kit(c)
        if key(pl) != key(jl):
            bad.append((c, key(pl), key(jl)))
    check('D [KIT_INFO] classification, percentages and family lists match the preview script on '
          f'{len(KIT_CASES)} name sets', not bad, f'{bad[:2]}' if bad else
          f"e.g. {key(MP.classify_kit(KIT_CASES[0]))}")
    o = MP.origin_words((-0.5, -0.3, 0.0), (0.5, 0.3, 1.2))
    o2 = MP.origin_words((-0.5, -0.3, -0.6), (0.5, 0.3, 0.6))
    o3 = MP.origin_words((1.0, 1.0, 2.0), (2.0, 2.0, 3.0))
    check('D [ORIGIN_INFO] BASE / CENTERED / OUTSIDE in Z-up words', 'at the BASE: z=0' in o and 'CENTERED' in o2
          and 'OUTSIDE' in o3 and 'Lateral: X center, Y center' in o, o[:80])


# ------------------------------------------------------------------------------------------------------- E ---
def part_e():
    from eidoblend.harness import render_common as RC
    import numpy as np
    src = open(os.path.join(ROOT, 'eidoverse', 'render_common.mjs'), encoding='utf-8').read()

    def fn(name):
        i = src.index(f'export function {name}')
        j = src.index('\n}\n', i) + 3
        return src[i + len('export '):j]
    path = [{'time': 0, 'position': [0, 1.6, 6], 'target': [0, 1, 0]},
            {'time': 2, 'position': [3, 2, 4]},
            {'time': 5, 'position': [-2, 1.2, 3], 'target': [0.5, 0.8, 0]}]
    ts = [-1, 0, 0.5, 1.0, 1.999, 2, 3.3, 5, 7]
    rng = np.random.default_rng(3)
    frame = rng.integers(0, 256, (6, 7, 4), dtype=np.uint8)
    a = rng.integers(0, 256, (6, 7), dtype=np.uint8)
    a[0, :] = 0
    ui = np.concatenate([(rng.random((6, 7, 3)) * a[..., None]).astype(np.uint8), a[..., None]], axis=2)
    dump = (fn('getCameraAtTime') + '\n' + fn('alphaComposite') + '\n'
            'const P = JSON.parse(Deno.args[0]);\n'
            'const cams = P.ts.map((t) => getCameraAtTime(t, P.path, [0, 1.2, 3], [0, 0, 0]));\n'
            'const one = getCameraAtTime(1, [P.path[1]], [9, 9, 9], [8, 8, 8]);\n'
            'const none = getCameraAtTime(1, [], [9, 9, 9], [8, 8, 8]);\n'
            'const f = new Uint8Array(P.frame), u = new Uint8Array(P.ui), d = new Uint8Array(f.length);\n'
            'alphaComposite(f, u, d);\n'
            'console.log(JSON.stringify({cams, one, none, comp: Array.from(d)}));\n')
    p = os.path.join(OUT, 'render_common_dump.mjs')
    open(p, 'w', encoding='utf-8').write(dump)
    if not DENO:
        return check('E render_common parity', False, 'no deno')
    rc, out, err = deno(p, json.dumps({'ts': ts, 'path': path, 'frame': frame.ravel().tolist(),
                                       'ui': ui.ravel().tolist()}))
    if rc != 0:
        return check('E render_common parity', False, err[-300:])
    js = json.loads(out.strip().splitlines()[-1])
    worst = 0.0
    for t, jc in zip(ts, js['cams']):
        pc = RC.get_camera_at_time(t, path, [0, 1.2, 3], [0, 0, 0])
        for k in ('position', 'target'):
            worst = max(worst, max(abs(x - y) for x, y in zip(pc[k], jc[k])))
    one = RC.get_camera_at_time(1, [path[1]], [9, 9, 9], [8, 8, 8])
    none = RC.get_camera_at_time(1, [], [9, 9, 9], [8, 8, 8])
    check('E getCameraAtTime: 9 times, a single key, no keys', worst < 1e-12 and one == js['one'] and none == js['none'],
          f'worst difference {worst:.1e}')
    dest = np.zeros_like(frame)
    RC.alpha_composite(frame, ui, dest)
    diff = np.abs(dest.astype(int).ravel() - np.array(js['comp'])).max()
    check('E alphaComposite: premultiplied over, truncated, alpha 255 where covered', diff == 0,
          f'max byte difference {diff}')


# ------------------------------------------------------------------------------------------------------- F ---
def part_f():
    import numpy as np
    from eidoblend.harness.html_mesh import El, html_to_image, layout, css_color
    card = El('div', style='display: inline-block; background: rgba(0,0,0,0.85); padding: 20px; color: orange; '
                           'font: 600 64px VT323; border: 4px solid #ff9a3c; border-radius: 16px', text='HELLO')
    b = layout(card)
    im = np.asarray(html_to_image(card))
    want_w = b.w
    check('F1 a card is its border box: padding + border + text', im.shape[1] == math.ceil(want_w)
          and im.shape[0] == math.ceil(b.h) and b.h > 64 + 40, f'{im.shape[1]}x{im.shape[0]} px')
    mid = im[im.shape[0] // 2, 2]
    check('F2 the 4 px border is the border colour', abs(int(mid[0]) - 0xff) < 30 and abs(int(mid[1]) - 0x9a) < 40
          and mid[3] > 200, f'{mid.tolist()}')
    corner = im[0, 0]
    check('F3 the rounded corner is transparent', corner[3] < 40, f'{corner.tolist()}')
    clip = El('div', style='width: 300px; height: 40px; overflow: hidden; font: 30px Exo2; color: white; '
                           'line-height: 40px', text='one two three four five six seven eight nine ten eleven')
    outer = El('div', style='width: 300px; padding-bottom: 60px', children=[clip])
    im2 = np.asarray(html_to_image(outer))
    below = im2[45:, :, 3].max()
    inside = im2[:40, :, 3].max()
    check('F4 overflow hidden clips the element\'s own wrapped lines', inside > 200 and below == 0,
          f'alpha inside {inside}, below the box {below}')
    rng = El('input', type='range', min=0, max=10, value=5, style='width: 200px; height: 20px; accent-color: #2050ff')
    im3 = np.asarray(html_to_image(rng))
    thumb = im3[10, 100]
    check('F5 a range input draws its thumb at the value (accent colour at the middle)',
          thumb[2] > 200 and thumb[0] < 80, f'{thumb.tolist()}')
    check('F6 CSS colours: rgba, names, transparent', css_color('rgba(255, 0, 0, 0.5)') == (255, 0, 0, 128)
          and css_color('orange') == (255, 165, 0, 255) and css_color('transparent') is None, '')


# ------------------------------------------------------------------------------------------------------- G ---
def part_g():
    from eidoblend.harness import showpiece as A

    class O:
        def __init__(self, n, m=None):
            self.name = n
            self.material_slots = [type('S', (), {'material': type('M', (), {'name': m})()})()] if m else []

    class Sc:
        def __init__(self, objs):
            self.objects = objs
    bar = Sc([O('bar_counter', 'wood'), O('coffee_mug', 'ceramic'), O('stool')])
    n = A.showpiece_nudge(bar, 30.0, ['eidoblend.harness.assets'])
    check('G1 a 30 s bar scene with a coffee mug and no showpiece: liquid named', n and any('fx.swe' in h for h in n[1]),
          (n[1] if n else 'none'))
    n2 = A.showpiece_nudge(bar, 10.0, [])
    check('G2 under 15 s: no nudge (full-length productions only)', n2 is None, '')
    n3 = A.showpiece_nudge(bar, 30.0, ['eidoblend.fx.particles'])
    check('G3 a scene that used a showpiece family: no nudge', n3 is None, '')
    n4 = A.showpiece_nudge(Sc([O('cube'), O('plane')]), 30.0, [], brief='a curtain blows in the wind at dawn')
    check('G4 the brief counts: a curtain asks for cloth', n4 and any('fx.cloth' in h for h in n4[1]), (n4[1] if n4 else ''))
    n5 = A.showpiece_nudge(Sc([O('cube')]), 30.0, [])
    check('G5 nothing matches: the general menu, no specific fit', n5 and n5[1] == [] and 'under-used' in n5[0], '')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g):
        try:
            f()
        except Exception as e:                                      # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f.__name__, False, f'{type(e).__name__}: {e}')
    n = sum(1 for _, ok in results if ok)
    print(f'\n{n}/{len(results)} checks passed', flush=True)
    sys.exit(0 if n == len(results) else 1)
