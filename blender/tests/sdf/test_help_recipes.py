"""The engine help()'s own samples and recipe patterns, built with the Blender edition and rendered.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 10 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_help_recipes.py

SdfRaymarchLoader.help() taught the API with a minimal recipe (two spheres joined into a peanut, in the engine's
contract: map + shade, no surface), a custom-uniforms sample (sdSphere(p, uRadius), shade returns uColor, the radius
driven per frame), and five recipe patterns: a character body, a crystal / gem, a tentacle, a hollow shell and a
repeating prop. Each is written here as the help described it, in GLSL against the engine's library.

out/help_recipes.png: the peanut with shade() as its base colour (shade_as='albedo', the default for a map + shade
spec) and as emission ('emission', the engine's unlit look), the uniform sphere at two frames of its bake, and the
two Agent API samples of the source file's comments (the header's body + head creature, the TSL section's sphere).
out/help_patterns.png: the five patterns. PASS lines: each builds a closed mesh; the shade-derived materials carry
shade()'s colours; the keyed uniform changes the radius per frame; the animated patterns move; a Python SDF reads
S.time and S.uniform() during a bake.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf import SDF_NP as S  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache_help')
A = C.args()
RENDER = A.get('render', '1') == '1'


def closed(obj):
    q = obj.contour.quads
    e = np.sort(np.stack([q, np.roll(q, -1, axis=1)], -1).reshape(-1, 2), axis=1)
    _u, cnt = np.unique(e, axis=0, return_counts=True)
    return float(np.mean(cnt == 2))


def evaluated_verts(obj, frame):
    sc = bpy.context.scene
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


# ================================================================================ 1. the help's samples ======
sc = C.stage(1280, 540, 16, world_color=(0.42, 0.45, 0.5), world_strength=0.7, sun_energy=3.0,
             floor_color=(0.2, 0.2, 0.21))
sc.frame_start, sc.frame_end = 1, 24

# '── Minimal recipe ──', verbatim: bounds, quality, map and shade as the help printed them
PEANUT = dict(
    bounds={'min': [-1.5, -1, -1.5], 'max': [1.5, 1, 1.5]},
    quality='balanced',
    map=r"""
      vec2 map(vec3 p) {
        // Two spheres smoothly joined into a peanut
        float a = sdSphere(p - vec3(-0.4, 0.0, 0.0), 0.5);
        float b = sdSphere(p - vec3( 0.4, 0.0, 0.0), 0.5);
        return vec2(smin(a, b, 0.3), 1.0);
      }""",
    shade=r"""
      vec3 shade(vec3 p, vec3 n, float mat) {
        vec3 L = normalize(vec3(0.5, 0.9, 0.4));
        return vec3(0.85, 0.45, 0.25) * (0.4 + 0.6 * max(0.0, dot(n, L)));
      }""",
)
pa = sdf.create_sdf_object(PEANUT, name='help_peanut_albedo', cache_dir=CACHE, location=(-3.0, 0.0, 0.0), scale=0.6)
pa.place_on_ground(0.0)
pe = sdf.create_sdf_object(PEANUT, shade_as='emission', name='help_peanut_emission', cache_dir=CACHE,
                           location=(-1.4, 0.0, 0.0), scale=0.6)
pe.place_on_ground(0.0)
# the file header's Agent API sample (a body sphere and a head sphere, smin 0.1) and the TSL section's sphere, both
# in the engine's map + shade contract
HEADER = sdf.create_sdf_object(
    bounds={'min': [-0.6, -0.6, -0.6], 'max': [0.6, 0.9, 0.6]}, quality='balanced',
    map=r"""vec2 map(vec3 p) {
        float body = sdSphere(p, 0.4);
        float head = sdSphere(p - vec3(0.0, 0.55, 0.0), 0.2);
        return vec2(smin(body, head, 0.1), 1.0); }""",
    shade=r"""vec3 shade(vec3 p, vec3 n, float mat) {
        vec3 L = normalize(vec3(0.5, 0.8, 0.3));
        float diff = max(0.0, dot(n, L));
        float amb = 0.3 + 0.2 * (n.y * 0.5 + 0.5);
        return vec3(0.7, 0.5, 0.3) * (amb + diff * 0.8); }""",
    name='help_header_creature', cache_dir=CACHE, location=(1.6, 0.0, 0.0))
HEADER.place_on_ground(0.0)
TSLS = sdf.create_sdf_object(
    bounds={'min': [-0.5, -0.5, -0.5], 'max': [0.5, 0.5, 0.5]}, quality='balanced',
    map='vec2 map(vec3 p) { return vec2(sdSphere(p, 0.4), 1.0); }',
    shade=r"""vec3 shade(vec3 p, vec3 n, float mat) {
        vec3 L = normalize(vec3(0.5, 0.8, 0.3));
        float diff = max(0.0, dot(n, L));
        return vec3(0.7, 0.5, 0.3) * (0.3 + diff * 0.8); }""",
    name='help_tsl_sphere', cache_dir=CACHE, location=(2.85, 0.0, 0.0),
    maxSteps=48, surfEps=0.003, stepScale=0.8, maxDist=20.0)          # the engine's camelCase overrides
TSLS.place_on_ground(0.0)
C.check('header samples build', closed(HEADER) > 0.999 and closed(TSLS) > 0.999,
        f'creature {HEADER.stats["quads"]} quads, sphere {TSLS.stats["quads"]} quads')
sp = TSLS.spec
C.check('maxSteps / surfEps / stepScale / maxDist override the preset',
        (sp.max_steps, sp.surf_eps, sp.step_scale, sp.max_dist) == (48, 0.003, 0.8, 20.0),
        f'{sp.max_steps}, {sp.surf_eps}, {sp.step_scale}, {sp.max_dist} (balanced: 128, 0.001, 0.85, 100)')
C.check('minimal recipe: closed peanut', closed(pa) > 0.999, f'{pa.stats["quads"]} quads')
# the shade-derived channels: albedo = shade() head-on (its hand light kept), or emission = shade()
alb = pa.program.surface_eval(pa.contour.verts, project=1)['albedo']
emi = pe.program.surface_eval(pe.contour.verts, project=1)
ratio = alb[:, 1] / np.maximum(alb[:, 0], 1e-6)
C.check("shade_as='albedo' takes shade()'s colours", 0.84 < float(alb[:, 0].max()) <= 0.851 and
        float(alb[:, 0].min()) > 0.85 * 0.4 - 0.01 and float(np.abs(ratio - 0.45 / 0.85).max()) < 0.01,
        f'base colour {alb.min(axis=0).round(3).tolist()} .. {alb.max(axis=0).round(3).tolist()} '
        f'(shade(): (0.85, 0.45, 0.25) x 0.4 .. 1.0)')
C.check("shade_as='emission' is the engine's unlit look", float(emi['albedo'].max()) == 0.0 and
        abs(float(emi['emission'][:, 0].max()) - 0.85) < 0.01, f'emission max {emi["emission"].max(axis=0).round(3).tolist()}')

# '── Custom uniforms ──': the radius and colour are uniforms (the engine's {value: ...} form), the radius driven
# per frame like `sdf.material.uniforms.uRadius.value = 0.5 + 0.2 * Math.sin(t)`
uni = sdf.create_sdf_object(
    map='vec2 map(vec3 p) { return vec2(sdSphere(p, uRadius), 1.0); }',
    shade='vec3 shade(vec3 p, vec3 n, float m) { return uColor; }',
    uniforms={'uRadius': {'value': 0.5}, 'uColor': {'value': 0xff7a3c, 'type': 'color'}},
    bounds={'min': [-0.75, -0.75, -0.75], 'max': [0.75, 0.75, 0.75]}, quality='fast', carrier='vertex',
    name='help_uniforms', cache_dir=CACHE, location=(0.1, 0.0, 0.75))
uni.bake(1, 24, step=1, controls=lambda frame, t: {'uRadius': 0.5 + 0.2 * math.sin(t * 2.0)}, log=None)
r = {}
for f in (1, 9, 24):
    v = evaluated_verts(uni.object, f)
    r[f] = float(np.linalg.norm(v, axis=1).mean())
want = {f: 0.5 + 0.2 * math.sin((f - 1) / 24.0 * 2.0) for f in r}
C.check('custom uniforms: the keyed radius per frame', all(abs(r[f] - want[f]) < 0.01 for f in r),
        ', '.join(f'f{f} {r[f]:.3f} m (want {want[f]:.3f})' for f in r))

# a Python SDF reads its program's time and uniforms while it is baked (TSL's time / uniform nodes)


def bob_map(p):
    c = S.vec3(0.0, 0.3 + 0.15 * float(S.sin(S.time * 3.0)), 0.0)
    return S.sd_sphere(p - c, S.uniform('uR')), 1.0


bob = sdf.create_sdf_object(map=bob_map, uniforms={'uR': 0.18}, bounds={'min': [-0.3, 0.0, -0.3], 'max': [0.3, 0.7, 0.3]},
                            cells=48, carrier='vertex', name='help_python_time', cache_dir=CACHE, location=(0, 6, 0))
bob.bake(1, 3, time_scale=12.0, controls=lambda frame, t: {'uR': 0.1 + 0.04 * frame}, log=None)
cz = {}
for f in (1, 2, 3):
    v = evaluated_verts(bob.object, f)
    cz[f] = (float(v[:, 2].mean()), float((v[:, 0].max() - v[:, 0].min()) / 2))
fps = 24.0
ok = all(abs(cz[f][0] - (0.3 + 0.15 * math.sin(12.0 * (f - 1) / fps * 3.0))) < 0.01 and
         abs(cz[f][1] - (0.1 + 0.04 * f)) < 0.01 for f in cz)
C.check('a Python map reads S.time and S.uniform() in a bake', ok,
        ', '.join(f'f{f}: centre z {cz[f][0]:.3f}, radius {cz[f][1]:.3f}' for f in cz))
bob.object.hide_render = True

if RENDER:
    cam = C.camera((-0.1, -6.4, 1.6), (-0.1, 0.0, 0.55), lens=32)
    for f in (1, 9):
        sc.frame_set(f)
        p = os.path.join(C.OUT, f'help_recipes_f{f:02d}.png')
        C.check(f'help recipes render, frame {f}', C.render(p), p)
    C.sheet([os.path.join(C.OUT, 'help_recipes_f01.png'), os.path.join(C.OUT, 'help_recipes_f09.png')],
            os.path.join(C.OUT, 'help_recipes.png'), cols=1)

# ============================================================================== 2. the recipe patterns =========
sc = C.stage(1280, 540, 16, world_color=(0.42, 0.45, 0.5), world_strength=0.7, sun_energy=3.0,
             floor_color=(0.2, 0.2, 0.21))
sc.frame_start, sc.frame_end = 1, 3
# a polished floor: the meshes stand in the scene's reflections as well as its shadows
bpy.data.objects['floor'].data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.12

# '• Character body: capsule (torso) + 4 sdCap2 (limbs) + 2 sdSphere (head/eyes), all union'd with smin(k=0.05) for
#   soft attach. Animate by varying limb endpoints with sin(uTime).'
BODY_MAP = r"""
vec2 map(vec3 p) {
    float sw = sin(uTime * 2.0);
    float torso = sdCapsule(p, vec3(0.0, 0.62, 0.0), vec3(0.0, 1.02, 0.0), 0.17);
    float legL = sdCap2(p, vec3(-0.09, 0.6, 0.0), vec3(-0.13, 0.06, 0.08 * sw), 0.08, 0.05);
    float legR = sdCap2(p, vec3( 0.09, 0.6, 0.0), vec3( 0.13, 0.06, -0.08 * sw), 0.08, 0.05);
    float armL = sdCap2(p, vec3(-0.2, 0.98, 0.0), vec3(-0.42, 0.66 + 0.12 * sw, 0.12), 0.06, 0.04);
    float armR = sdCap2(p, vec3( 0.2, 0.98, 0.0), vec3( 0.42, 0.66 - 0.12 * sw, 0.12), 0.06, 0.04);
    float head = sdSphere(p, vec3(0.0, 1.3, 0.0), 0.15);
    float d = smin(torso, legL, 0.05);
    d = smin(d, legR, 0.05);
    d = smin(d, armL, 0.05);
    d = smin(d, armR, 0.05);
    d = smin(d, head, 0.05);
    vec2 body = vec2(d, 1.0);
    float eyes = min(sdSphere(p, vec3(-0.055, 1.33, 0.12), 0.035), sdSphere(p, vec3(0.055, 1.33, 0.12), 0.035));
    return opU(body, vec2(eyes, 2.0));
}"""
BODY_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    if (mat > 1.5) { SdfSurface e = sdfSurface(vec3(0.02), 0.08); e.coat = 1.0; return e; }
    SdfSurface s = sdfSurface(mix(vec3(0.15, 0.45, 0.75), vec3(0.95, 0.8, 0.3), smoothstep(0.55, 0.65, p.y)), 0.45);
    s.subsurface = 0.15;
    return s;
}"""

# '• Crystal/gem: sdOctahedron OR sdEllipsoid (radii != equal) + tiny spheres at vertices via opSmoothU, animated
#   emissive.' The library never had an sdOctahedron (the help named one), so the gem brings its own in `extra`.
GEM_EXTRA = r"""
float sdOctahedron(vec3 p, float s) {
    p = abs(p);
    float m = p.x + p.y + p.z - s;
    vec3 q;
    if (3.0 * p.x < m) q = p.xyz;
    else if (3.0 * p.y < m) q = p.yzx;
    else if (3.0 * p.z < m) q = p.zxy;
    else return m * 0.57735027;
    float k = clamp(0.5 * (q.z - q.y + s), 0.0, s);
    return length(vec3(q.x, q.y - s + k, q.z - k));
}"""
GEM_MAP = r"""
vec2 map(vec3 p) {
    vec3 q = opRotateY(p - vec3(0.0, 0.62, 0.0), uTime * 0.6);
    vec2 gem = vec2(sdOctahedron(q * vec3(1.0, 0.62, 1.0), 0.34), 1.0);     // stretched in y: still a bound
    float tips = 1e9;
    tips = min(tips, sdSphere(q, vec3( 0.34, 0.0, 0.0), 0.045));
    tips = min(tips, sdSphere(q, vec3(-0.34, 0.0, 0.0), 0.045));
    tips = min(tips, sdSphere(q, vec3(0.0, 0.0,  0.34), 0.045));
    tips = min(tips, sdSphere(q, vec3(0.0, 0.0, -0.34), 0.045));
    tips = min(tips, sdSphere(q, vec3(0.0,  0.34 / 0.62, 0.0), 0.045));
    tips = min(tips, sdSphere(q, vec3(0.0, -0.34 / 0.62, 0.0), 0.045));
    return opSmoothU(gem, vec2(tips, 2.0), 0.03);
}"""
GEM_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    SdfSurface s = sdfSurface(vec3(0.55, 0.12, 0.85), 0.12);
    s.coat = 1.0;
    s.specular = 0.8;
    if (mat > 1.5) {
        s.albedo = vec3(1.0, 0.85, 0.4);
        s.emission = vec3(4.0, 2.6, 0.9) * (0.6 + 0.4 * sin(uTime * 4.0));
    }
    return s;
}"""

# '• Tentacle: chain of sdCap2 with each segment's centerpoint computed from sin(uTime + segmentIndex), smin them.'
TENT_MAP = r"""
vec3 joint(int i) {
    float s = float(i) / 7.0;
    return vec3(0.16 * s * sin(uTime * 1.7 + float(i) * 0.8), float(i) * 0.16, 0.12 * s * cos(uTime * 1.3 + float(i)));
}
vec2 map(vec3 p) {
    float d = 1e9;
    for (int i = 0; i < 7; i++) {
        float r1 = mix(0.11, 0.015, float(i) / 7.0), r2 = mix(0.11, 0.015, float(i + 1) / 7.0);
        float seg = sdCap2(p, joint(i), joint(i + 1), r1, r2);
        d = i == 0 ? seg : smin(d, seg, 0.05);
    }
    return vec2(d, 1.0);
}"""
TENT_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    float band = 0.5 + 0.5 * sin(p.y * 40.0);
    SdfSurface s = sdfSurface(mix(vec3(0.55, 0.06, 0.1), vec3(0.75, 0.18, 0.2), band), 0.4);
    s.subsurface = 0.3;
    return s;
}"""

# '• Hollow shell: opSmoothSub(innerSphere, outerSphere, k=0.05).' (a window is cut so the hollow shows)
SHELL_MAP = r"""
vec2 map(vec3 p) {
    vec3 c = vec3(0.0, 0.42, 0.0);
    float shell = opSmoothSub(sdSphere(p - c, 0.36), sdSphere(p - c, 0.4), 0.05);
    shell = opSub(sdBox(p - c - vec3(0.24, 0.16, 0.24), vec3(0.17)), shell);
    return vec2(shell, 1.0);
}"""
SHELL_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    float inner = smoothstep(0.37, 0.39, length(p - vec3(0.0, 0.42, 0.0)));
    SdfSurface s = sdfSurface(mix(vec3(0.9, 0.35, 0.1), vec3(0.92, 0.9, 0.85), inner), 0.35);
    return s;
}"""

# '• Repeating prop: domain mod p = mod(p + period/2, period) - period/2 to get an infinite grid of one shape (cheap
#   forest, fence).' A fence: the posts repeat every 0.3 m; the bounds end mid-gap, so no post is cut.
FENCE_MAP = r"""
vec2 map(vec3 p) {
    vec2 q = mod(p.xz + 0.15, 0.3) - 0.15;
    float post = sdRoundBox(vec3(q.x, p.y - 0.3, q.y), vec3(0.025, 0.28, 0.025), 0.01);
    float rails = min(sdBox(vec3(q.x, p.y - 0.47, q.y - 0.035), vec3(0.2, 0.02, 0.008)),
                      sdBox(vec3(q.x, p.y - 0.2, q.y - 0.035), vec3(0.2, 0.02, 0.008)));
    return vec2(min(post, rails), 1.0);
}"""
FENCE_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    float g = fbm(p * vec3(6.0, 40.0, 6.0));
    return sdfSurface(mix(vec3(0.32, 0.2, 0.11), vec3(0.55, 0.38, 0.22), g), 0.75);
}"""

PATTERNS = [
    ('help_body', dict(map=BODY_MAP, surface=BODY_SURF, bounds={'min': [-0.62, 0.0, -0.3], 'max': [0.62, 1.47, 0.3]}),
     (-2.9, 0.0), True),
    ('help_gem', dict(extra=GEM_EXTRA, map=GEM_MAP, surface=GEM_SURF,
                      bounds={'min': [-0.62, 0.0, -0.62], 'max': [0.62, 1.25, 0.62]}), (-1.55, 0.0), True),
    ('help_tentacle', dict(map=TENT_MAP, surface=TENT_SURF, bounds={'min': [-0.35, -0.12, -0.35], 'max': [0.35, 1.2, 0.35]}),
     (-0.4, 0.0), True),
    ('help_shell', dict(map=SHELL_MAP, surface=SHELL_SURF, bounds={'min': [-0.45, 0.0, -0.45], 'max': [0.45, 0.85, 0.45]}),
     (0.75, 0.0), False),
    ('help_fence', dict(map=FENCE_MAP, surface=FENCE_SURF, cut_by_bounds=True,
                        bounds={'min': [-0.75, 0.0, -0.45], 'max': [0.75, 0.62, 0.45]}), (2.3, 0.3), False),
]
objs = {}
for name, spec, (x, y), animated in PATTERNS:
    o = sdf.create_sdf_object(spec, name=name, quality='high', cache_dir=CACHE, location=(x, y, 0.0), time=0.4, log=None)
    o.place_on_ground(0.0)
    objs[name] = o
    C.check(f'{name}: closed mesh', closed(o) > 0.999, f'{o.stats["quads"]} quads, voxel {o.voxel * 1000:.1f} mm')
    if animated:
        # the pattern's animation: the surface built at t = 0.4 is off the field at t = 1.7 where something moved
        pick = np.random.default_rng(1).choice(len(o.contour.verts), min(30000, len(o.contour.verts)), replace=False)
        a = o.program.dist(o.contour.verts[pick])[0]
        o.program.set_uniform('uTime', 1.7)
        b = o.program.dist(o.contour.verts[pick])[0]
        o.program.set_uniform('uTime', 0.4)
        C.check(f'{name}: animated by uTime', float(np.abs(a - b).max()) > 0.005,
                f'the t=0.4 surface is up to {np.abs(a - b).max() * 1000:.1f} mm off the field at t=1.7')
gem_e = objs['help_gem'].program.surface_eval(objs['help_gem'].contour.verts, project=1)
C.check('gem tips are emissive', float(gem_e['emission'].max()) > 1.0 and float((gem_e['mat'] > 1.5).mean()) > 0.02,
        f'{(gem_e["mat"] > 1.5).mean() * 100:.1f}% of vertices on the tips, emission max {gem_e["emission"].max():.2f}')
fence = objs['help_fence']
xs = fence.contour.verts[:, 0]
C.check('fence: the repeated posts fill the bounds', len(np.unique(np.round(xs[fence.contour.verts[:, 1] > 0.55] / 0.3))) == 5,
        'five posts along x')
if RENDER:
    C.camera((-0.2, -6.2, 1.9), (-0.2, 0.0, 0.5), lens=32)
    p = os.path.join(C.OUT, 'help_patterns.png')
    C.check('patterns render', C.render(p), p)
msg = sdf.help()
C.check('help() prints', 'create_sdf_object' in msg, f'{len(msg)} characters')
C.summary()
