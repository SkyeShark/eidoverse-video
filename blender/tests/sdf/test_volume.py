"""create_sdf_volume: the engine's sample() contract and the Blender-native medium() as Volume objects.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_volume.py [-- render=1]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

1. The conversion, numerically: rays marched through the written grids (numpy, trilinear) against createSdfVolume's
   own march of the same sample() on the GPU: the same transmittance and the same emitted light.
2. A fireball in the engine contract (emissive, absorbing) and a smoke in the medium contract (scattering, lit by
   the sun, shadowing the floor), rendered in EEVEE beside the engine-style march: out/vol_*_eevee.png, *_ref.png,
   *_sheet.png.
3. An animated bake: one .vdb per frame, the Volume plays the sequence (frame numbers through frame_offset).
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
import engine_march as EM  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402

A = C.args()
RENDER = A.get('render', '1') == '1'
CACHE = os.path.join(C.OUT, 'cache')

FIREBALL = r"""
SdfSample sample(vec3 p) {
    vec3 q = p - vec3(0.0, 0.62, 0.0);
    float n = fbm(p * 3.0 + vec3(0.0, -uTime * 0.8, 0.0));
    float r = length(q) + (n - 0.5) * 0.35;
    float d = clamp((0.5 - r) * 6.0, 0.0, 1.0);
    vec3 col = mix(vec3(0.9, 0.22, 0.04), vec3(1.6, 1.1, 0.55), d * d) * 2.2;
    return sdfSample(col, d * 0.09, 0.02);
}"""

SMOKE = r"""
SdfMedium medium(vec3 p) {
    vec3 q = (p - vec3(0.0, 0.55, 0.0)) * vec3(1.0, 1.3, 1.0);
    float n = fbm6(p * 4.0 + vec3(0.0, -uTime * 0.5, 0.0));
    float r = length(q) + (n - 0.5) * 0.35;
    float d = 1.0 - smoothstep(0.25, 0.45, r);
    return sdfMedium(d * 14.0, vec3(0.82, 0.8, 0.78), vec3(0.0));
}"""

BOUNDS = {'min': [-0.75, 0.0, -0.75], 'max': [0.75, 1.3, 0.75]}


def grid_march(vol, grids, origins, dirs, step):
    """Emission-absorption march through the numpy grids (trilinear), in Blender local axes: (radiance, alpha)."""
    dens, emis = grids['density'], grids['emission']
    nx, ny, nz = dens.shape

    def tri(arr, p):
        g = (p - vol.lo) / vol.voxel - 0.5
        i0 = np.floor(g).astype(int)
        f = g - i0
        out = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    ii = np.clip(i0[:, 0] + dx, 0, nx - 1)
                    jj = np.clip(i0[:, 1] + dy, 0, ny - 1)
                    kk = np.clip(i0[:, 2] + dz, 0, nz - 1)
                    w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                    inside = np.all((g + 0.5 > 0) & (g + 0.5 < [nx, ny, nz]), axis=1)
                    v = arr[ii, jj, kk]
                    out = out + (w * inside)[:, None] * (v if v.ndim == 2 else v[:, None])
        return out
    T = np.ones(len(origins))
    L = np.zeros((len(origins), 3))
    inv = 1.0 / np.where(np.abs(dirs) < 1e-12, 1e-12, dirs)
    t0 = np.max(np.minimum((vol.lo - origins) * inv, (vol.hi - origins) * inv), axis=1).clip(0)
    t1 = np.min(np.maximum((vol.lo - origins) * inv, (vol.hi - origins) * inv), axis=1)
    t = t0.copy()
    while True:
        live = t < t1
        if not live.any():
            break
        p = origins + dirs * (t + 0.5 * step)[:, None]
        s = tri(dens, p)[:, 0]
        e = tri(emis, p)
        a = 1.0 - np.exp(-s * step)
        c = np.where(s[:, None] > 1e-9, e / np.maximum(s, 1e-9)[:, None], 0.0)
        L += (live * T * a)[:, None] * c
        T *= np.where(live, 1.0 - a, 1.0)
        t += step
    return L, 1.0 - T


# ---- 1. the conversion, numerically -----------------------------------------------------------------------------
C.stage(480, 270, 4, floor=False, sun=False)
fire = sdf.create_sdf_volume(sample=FIREBALL, bounds=BOUNDS, steps=200, cells=150, name='vol_fire', cache_dir=CACHE,
                             time=0.0)
cam = C.camera((0.0, -3.4, 0.75), (0.0, 0.0, 0.62), lens=50)
ref = EM.march(fire, cam, 96, 54, samples=1)
grids = fire.sample_grids(0.0)
# the same camera rays, in the volume's local Blender frame
sc = bpy.context.scene
fr = cam.data.view_frame(scene=sc)
inv = fire.object.matrix_world.inverted()
o_loc = np.array(inv @ cam.matrix_world.translation)
dirs = []
for j in range(54):
    v = (j + 0.5) / 54
    for i in range(96):
        u = (i + 0.5) / 96
        pc = fr[2] + (fr[1] - fr[2]) * u + (fr[0] - fr[1]) * v
        d = inv.to_3x3() @ (cam.matrix_world.to_3x3() @ pc)
        dirs.append(tuple(d.normalized()))
dirs = np.array(dirs)
L, alpha = grid_march(fire, grids, np.repeat(o_loc[None], len(dirs), 0), dirs, fire.voxel * 0.5)
ref_rgb = ref.reshape(-1, 4)[:, :3]
ref_a = ref.reshape(-1, 4)[:, 3]
hit = ref_a > 0.05
err_a = float(np.abs(alpha[hit] - ref_a[hit]).mean())
err_l = float(np.abs(L[hit] - ref_rgb[hit]).mean() / max(1e-6, ref_rgb[hit].mean()))
C.check('sample() -> density/emission: same opacity as the engine march', err_a < 0.03,
        f'mean |alpha error| {err_a:.4f} over {int(hit.sum())} rays (grid {fire.grid_info["dims"]})')
C.check('sample() -> density/emission: same light as the engine march', err_l < 0.06,
        f'mean relative radiance error {err_l * 100:.2f}%')
C.check('grids pruned', 0.05 < fire.grid_info['occupied'] < 0.9, f'{fire.grid_info["occupied"] * 100:.1f}% of voxels occupied')

# ---- 3. animated bake ---------------------------------------------------------------------------------------------
sc.frame_start, sc.frame_end = 1, 3
fire.bake(1, 3, time_scale=6.0)
vd = fire.object.data
files = [os.path.join(CACHE, f'vol_fire_{f:04d}.vdb') for f in (1, 2, 3)]
C.check('bake wrote one vdb per frame', all(os.path.exists(f) for f in files), ', '.join(os.path.basename(f) for f in files))
C.check('the Volume plays the sequence', vd.is_sequence and vd.frame_start == 1 and vd.frame_duration == 3,
        f'is_sequence {vd.is_sequence}, frames {vd.frame_start}+{vd.frame_duration}, offset {vd.frame_offset}')
sizes = [os.path.getsize(f) for f in files]
C.check('frames differ', len(set(sizes)) > 1, f'sizes {sizes}')
sc.frame_set(2)
dg = bpy.context.evaluated_depsgraph_get()
ev = fire.object.evaluated_get(dg)
grid_names = [g.name for g in ev.data.grids] if ev.data.grids.load() else []
C.check('Blender loads the frame grids', 'density' in grid_names and 'emission' in grid_names, str(grid_names))

# ---- 2. renders ---------------------------------------------------------------------------------------------------
if RENDER:
    for name, kw, rig in (
        ('fire', dict(sample=FIREBALL, steps=200), {'world': 0.05, 'sun': 0.0}),
        # a dusk stage: under AgX a 0.35 grey world and the sunlit floor read as one grey, and the lit smoke had
        # nothing to stand against
        ('smoke', dict(medium=SMOKE, steps=200), {'world': 0.08, 'sun': 5.0}),
    ):
        C.stage(960, 540, 32, world_color=(rig['world'],) * 3, world_strength=1.0, sun=rig['sun'] > 0,
                sun_energy=rig['sun'], sun_rot=(48.0, 0.0, 30.0), floor_color=(0.25, 0.25, 0.25))
        sdf.volume_render_settings(tile_size='2', samples=128, end=30.0)
        vol = sdf.create_sdf_volume(name=f'vol_{name}', bounds=BOUNDS, cells=180, cache_dir=CACHE, **kw)
        vol.place_on_ground(0.0)
        cam = C.camera((1.2, -3.0, 1.0), (0.0, 0.0, 0.6), lens=45)
        eevee = os.path.join(C.OUT, f'vol_{name}_eevee.png')
        C.check(f'{name}: EEVEE render', C.render(eevee), eevee)
        ref = EM.march(vol, cam, 960, 540, samples=2, ambient=(rig['world'] + 0.25 * rig['sun'],) * 3)
        bg = np.full(ref.shape[:2] + (3,), rig['world'], np.float32)
        comp = ref[..., :3] + bg * (1.0 - ref[..., 3:4])        # premultiplied over the world colour
        refp = C.save_linear_png(os.path.join(C.OUT, f'vol_{name}_ref.png'), comp)
        C.sheet([eevee, refp], os.path.join(C.OUT, f'vol_{name}_sheet.png'), cols=2)
C.summary()
