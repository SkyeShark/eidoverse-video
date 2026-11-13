"""Volume fire for Blender 5.2 EEVEE: the port of eidoverse/fluid_grid.js (itself a verbatim port of three.js's
webgpu_volume_fire example).

The solver is the engine's, kernel for kernel, as GLSL compute on the GPU (rgba16float 3D textures, linear
samplers, the same dispatch order and the same constants): curl-noise precompute; then per 1/120 s x simSpeed
substep: advect velocity with buoyancy, thermal and ambient curl turbulence, damping, mesh wind and the border
fade; divergence; Jacobi pressure (an even count); project; advect dye (density decays at 1/smokeLifespan,
temperature at 1/fireLifespan, age by nearest neighbour); emit from the burning mesh's vertices (or seeded
area-weighted samples) with MaterialX-noise flicker. Where emitter points share a voxel, the engine's GPU kept
whichever point's store landed last; here the emission runs in two passes and a hash of the point's index and the
substep's number draws that point, so a bake gives the same grids every time and the look the race gave.

What changes in Blender is the shape of the work, not the physics:
  build    create_volume_fire(mesh=...) makes the Volume object, its material and the fire's two lights;
  bake     fire.bake() steps the sim over the shot (warmup first) and writes one .vdb per frame
           (density with the velocity domain-warp and box-edge fade baked in, temperature, age), and keys the
           lights' flicker, sway and colour per frame;
  playback Blender plays the .vdb sequence itself: scrubbing, re-rendering and multi-pass need no replay.

The look is EEVEE's own volume rendering (froxels, volumetric shadows, real lights): the engine's 16-step
raymarch, its 2-tap key-light shadow, powder and multi-scatter octave are replaced by EEVEE's physically based
scattering. Kept from the engine: the temperature -> colour ramp (fireRamp, hue, glow spread), the emission
formula (fireRamp(T) * T^(6-spread) * intensity * (density + 0.15) * 400/d^2 to the key light), the simplex
detail noise on density (an exact node port of TSL snoise), the fire's light with its ImprovedNoise flicker,
sway and colour noise, split into a surface light and a volume light the way the engine's isVolume did, and
the lava-crack emissive for the burning mesh (Blender's Noise Texture is MaterialX's mx_noise exactly). The
engine's shadowMesh is a shadow caster over the ground (shadow_floor: EEVEE's volumes shadow no surface), and
make_fire_glow puts the fire's glow on the burning mesh, which the engine's volume pass, composited with no
depth test, showed through it.

The engine's look (look='engine', ENGINE_LOOK): the engine showed its fire through three's ACESFilmic, the
Blender edition through AgX; a display match (_look.py) makes the ramp display under the scene's view as it
did under three's ACES, with a few offsets for EEVEE's physically dimmer flame.
"""

from __future__ import annotations

import math
import os
import re
import time

import numpy as np

from . import _look, _noise
from ._util import B2T, T2B, LCG, color, from_three, hue, saturation, smoothstep, frame_file, abspath, scene_fps

# --------------------------------------------------------------------------------------------------
# defaults: the engine's DEFAULTS, snake_case. Sizes are given in BLENDER axes (x, y, z-up).
# --------------------------------------------------------------------------------------------------
DEFAULTS = dict(
    grid_size=(100, 200, 100),     # cells along Blender x, y, z  (engine: [100, 100, 200] along three x, y, z)
    world_size=(12.0, 24.0, 12.0),  # metres                       (engine: [12, 12, 24])
    origin=(0.0, 0.0, 0.0),        # Blender world point at the domain's floor centre (the engine's world origin)
    pressure_iterations=2,         # keep even
    sim_speed=1.2,
    fire_lifespan=1.3,
    smoke_lifespan=3.5,
    turbulence=3.2,
    fire_start_color='#ffe68c',
    fire_mid_color='#ff7305',
    fire_end_color='#ff0000',
    fire_hue=0.0,                  # degrees
    buoyancy=3.0,
    weight=0.15,
    turbulence_decay=0.1,
    turb_frequency=10.0,
    vel_damping=0.25,
    emit_density=7.0,
    emit_temperature=5.5,
    motion_boost=0.25,
    wind_strength=6.5,
    emitter_radius=1.0,
    fire_intensity=40.0,
    mesh_emissive_intensity=0.2,
    fire_glow_spread=5.0,
    asymmetry=0.0,                 # Henyey-Greenstein g -> Principled Volume anisotropy
    point_light_volume_intensity=2.0,
    point_light_surface_intensity=10.0,
    light_near_intensity=10.0,
    light_far_intensity=15.0,
    light_far_distance=10.0,
    saturation_amount=1.1,
    flame_height=3.5,
    emitter_points=None,           # None: the mesh's own vertices (the example); N: N area-weighted samples
    seed=1,
    warmup_seconds=4.0,
    # Blender-side look controls (EEVEE's physical volume needs units the raymarch never had)
    # extinction per metre per unit of simulated density. 0.15 reproduces the engine's smoke brightness:
    # its in-scatter was 0.01 * rho * I/d^2 per metre; EEVEE's is sigma_s * P/(4 pi d^2)/(4 pi) with
    # P = 4 pi I, so sigma = 0.01 * 4 pi ~ 0.13 rho (and the camera ray then stays nearly as clear as the
    # engine's, which barely attenuated it)
    smoke_density=0.15,
    flame_clarity=0.85,            # how much of that extinction burning gas (T >= 0.9) loses
    smoke_color=(0.82, 0.82, 0.82),  # single-scattering albedo of the smoke
    emission_scale=1.0,            # x the engine's per-metre emission (0.01 * fire term)
    light_scale=1.0,               # x the converted light powers (P = 4*pi*candela)
    key_light=None,                # the scene's key light object: its position feeds 400/d^2, as the example's
    key_light_pos=None,            # ... or a fixed Blender position; default = the example's spot position
    detail_noise=True,             # the engine's snoise(p*5.5) density detail, evaluated per shading sample
    # the engine's display under the film's view transform: 'aces' makes the flame and the lava display under
    # the scene's view (AgX) as three's ACESFilmic showed them in the engine (red -> orange -> yellow-white with
    # brightness, where AgX alone runs red -> salmon -> pink), through a per-sample table in the materials;
    # 'aces_compose' matches the volume per pixel in create_fire_compose instead (exact, but it touches every
    # volume in the view layer); None emits the raw ramp. Matched at the scene's exposure, display and look
    # when the fire is created (rebuild after changing them)
    display_match=None,
    display_path=2.0,              # metres of flame a pixel's light gathers over (the table's per-pixel guess)
    # the engine's shadowMesh: the smoke's soft shadow from the key light on the ground at this Blender z (None:
    # none). EEVEE's volumes cast no shadow on surfaces, so, as the engine did, a separate caster carries it: a plane
    # shadow_lift metres over the ground (EEVEE's shadow bias lets a caster closer than about 3 cm cast nothing),
    # seen by shadow rays only, its opacity per texel the smoke's transmittance toward the key light, worked out from
    # every baked frame's grids (shadow_resolution texels across)
    shadow_floor=None,
    shadow_lift=0.05,
    shadow_resolution=128,
    cache_dir='//fire_cache',
    name='fire',
)

# fluid_grid.js's raymarch and light-node options that EEVEE's volume rendering has no knob for: passing one says
# what EEVEE does in its place (volume-fire.md, "Not yet ported")
_PROJECTION = ("the engine's point light coloured the floor through a light colour node (rotating radial noise); "
               "EEVEE ignores light node trees")
ENGINE_ONLY = dict(
    shadow_absorption="the engine's 2-tap shadow march toward the key light scaled the smoke's self-shadow by it; "
                      "EEVEE shadows the smoke with its own extinction (smoke_density) under volumetric shadows "
                      "(configure_eevee_for_fire), and the ground with the same extinction through shadow_floor",
    shadow_ambient="the least light the engine's self-shadowed smoke kept (added to its shadow); in EEVEE the "
                   "shadowed smoke takes the World's light",
    powder_strength="Principled Volume has no powder (edge self-shadowing) term",
    multi_scattering="Principled Volume has no multiple-scattering octave: EEVEE's volume light is single "
                     "scattering under volumetric shadows",
    projection_radius=_PROJECTION, projection_frequency=_PROJECTION, projection_noise_fade=_PROJECTION,
    projection_center_fade=_PROJECTION,
)
GLOW_MODIFIER = 'fire_glow'        # make_fire_glow's Geometry Nodes modifier on the burning mesh

# (folder, stem) of every frame sequence <folder>/<stem>_####.vdb a fire's Volume was pointed at in this Blender session.
# Blender keeps the grids of each .vdb it reads for the rest of the session, by the file's path: a file written again
# at the same path plays the grids read first, through a new Volume datablock, VolumeGrids.unload() or the .blend
# opened again in the same Blender alike. So a bake never writes over frames this session may have read: a fire baked
# again in the same session writes <name>_bake2_####.vdb, then _bake3 ... (VolumeFire._fresh_stem)
_SESSION_SEQUENCES = set()


def _sequence_key(path):
    """(folder, stem) of a frame file <folder>/<stem>_<digits>.<ext>, normalised for comparison; None for any other
    file name"""
    m = re.match(r'^(.+)_\d+\.[^.]+$', os.path.basename(path))
    if m is None:
        return None
    return os.path.normcase(os.path.normpath(os.path.dirname(path))), m.group(1)

# The engine's LOOK under the Blender edition's AgX (create_volume_fire(look='engine'), the default). The
# engine's own numbers (DEFAULTS, look=None) render red-salmon here: AgX runs bright red to salmon and pink
# where the engine's ACES ran it to orange and yellow, and EEVEE's physical volume (smoke that dims the flame
# behind it, no glow through the burning mesh) puts more of the picture in the cool red end of the ramp. These
# offsets, found side by side with the engine's firetest frame, give back its orange tongues and yellow-white
# core: the display match, twice the per-metre emission, T^2 instead of T^1 (spread 4: cool gas dims faster)
# and an end colour a little toward orange. Options passed to create_volume_fire win over them.
ENGINE_LOOK = dict(display_match='aces', display_path=2.0, emission_scale=2.0, fire_glow_spread=4.0,
                   fire_end_color='#ff2a00')

# grid kernels ---------------------------------------------------------------------------------------
_HEAD = r"""
const vec3 GRID = vec3(float(GX), float(GY), float(GZ));
const vec3 WSIZE = vec3(WX, WY, WZ);
#define INSIDE(c) all(lessThan(c, ivec3(GX, GY, GZ)))
vec3 uvw_of(ivec3 c) { return (vec3(c) + 0.5) / GRID; }
"""

_K_CURL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  float freq = uTurbFreq;
  float e = 0.1 / freq;
  vec3 dx = vec3(e, 0.0, 0.0), dy = vec3(0.0, e, 0.0), dz = vec3(0.0, 0.0, e);
  vec3 p = uvw * vec3(WSIZE.x / WSIZE.y, 1.0, WSIZE.z / WSIZE.y);
  vec3 p_x0 = eido_snoise_vec3((p - dx) * freq), p_x1 = eido_snoise_vec3((p + dx) * freq);
  vec3 p_y0 = eido_snoise_vec3((p - dy) * freq), p_y1 = eido_snoise_vec3((p + dy) * freq);
  vec3 p_z0 = eido_snoise_vec3((p - dz) * freq), p_z1 = eido_snoise_vec3((p + dz) * freq);
  float x = p_y1.z - p_y0.z - p_z1.y + p_z0.y;
  float y = p_z1.x - p_z0.x - p_x1.z + p_x0.z;
  float z = p_x1.y - p_x0.y - p_y1.x + p_y0.x;
  imageStore(outTex, c, vec4(vec3(x, y, z) * 5.0, 0.0));
}
"""

_K_ADVECT_VEL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 vel = textureLod(velIn, uvw, 0.0).xyz;
  vec3 prevPos = uvw - (vel / WSIZE) * uDt;
  vec3 newVel = textureLod(velIn, prevPos, 0.0).xyz;
  vec4 dye = textureLod(dyeIn, uvw, 0.0);
  float density = dye.r, temperature = dye.g, age = dye.b;
  float buoyancyForce = (temperature * uBuoyancy - density * uWeight) * WSIZE.y;
  newVel += vec3(0.0, buoyancyForce, 0.0) * uDt;
  vec3 thermalNoisePos = uvw + vec3(0.0, -age * 0.6, age * 0.13) / uTurbFreq;
  float decay = exp(age * -uTurbDecay);
  vec3 thermal = textureLod(curlTex, thermalNoisePos, 0.0).xyz * uTurbulence * temperature * decay;
  vec3 ambientNoisePos = uvw * 0.5 + vec3(0.0, uTime * 0.25, uTime * 0.06) / uTurbFreq;
  vec3 ambient = textureLod(curlTex, ambientNoisePos, 0.0).xyz * (uTurbulence * 0.2) * density;
  newVel += (thermal + ambient) * WSIZE.y * uDt;
  newVel *= max(1.0 - uVelDamping * uDt, 0.0);
  vec3 worldPos = (uvw - 0.5) * WSIZE + vec3(0.0, WSIZE.y / 2.0, 0.0);
  float dist = distance(worldPos, uEmitterPos);
  if (dist < uEmitterRadius) {
    float falloff = smoothstep(0.0, 1.0, 1.0 - dist / uEmitterRadius);
    vec3 windNoisePos = uvw + vec3(0.0, uTime * 0.5, 0.0) / uTurbFreq;
    vec3 windTurb = textureLod(curlTex, windNoisePos, 0.0).xyz * uTurbulence * uEmitterSpeed;
    newVel += (uEmitterVel * uWindStrength + windTurb) * uDt * falloff;
  }
  vec3 edge = min(uvw, vec3(1.0) - uvw);
  newVel *= smoothstep(0.0, 0.08, min(edge.x, min(edge.y, edge.z)));
  imageStore(velOut, c, vec4(newVel, 0.0));
}
"""

_K_DIVERGENCE = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 tx = vec3(1.0 / GRID.x, 0.0, 0.0), ty = vec3(0.0, 1.0 / GRID.y, 0.0), tz = vec3(0.0, 0.0, 1.0 / GRID.z);
  float vR = textureLod(velIn, uvw + tx, 0.0).x, vL = textureLod(velIn, uvw - tx, 0.0).x;
  float vU = textureLod(velIn, uvw + ty, 0.0).y, vD = textureLod(velIn, uvw - ty, 0.0).y;
  float vF = textureLod(velIn, uvw + tz, 0.0).z, vB = textureLod(velIn, uvw - tz, 0.0).z;
  imageStore(outTex, c, vec4((vR - vL + (vU - vD) + (vF - vB)) * 0.5, 0.0, 0.0, 0.0));
}
"""

_K_JACOBI = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 tx = vec3(1.0 / GRID.x, 0.0, 0.0), ty = vec3(0.0, 1.0 / GRID.y, 0.0), tz = vec3(0.0, 0.0, 1.0 / GRID.z);
  float pR = textureLod(pressIn, uvw + tx, 0.0).x, pL = textureLod(pressIn, uvw - tx, 0.0).x;
  float pU = textureLod(pressIn, uvw + ty, 0.0).x, pD = textureLod(pressIn, uvw - ty, 0.0).x;
  float pF = textureLod(pressIn, uvw + tz, 0.0).x, pB = textureLod(pressIn, uvw - tz, 0.0).x;
  float divergence = textureLod(divIn, uvw, 0.0).x;
  imageStore(outTex, c, vec4((pR + pL + pU + pD + pF + pB - divergence) / 6.0, 0.0, 0.0, 0.0));
}
"""

_K_PROJECT = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 tx = vec3(1.0 / GRID.x, 0.0, 0.0), ty = vec3(0.0, 1.0 / GRID.y, 0.0), tz = vec3(0.0, 0.0, 1.0 / GRID.z);
  float pR = textureLod(pressIn, uvw + tx, 0.0).x, pL = textureLod(pressIn, uvw - tx, 0.0).x;
  float pU = textureLod(pressIn, uvw + ty, 0.0).x, pD = textureLod(pressIn, uvw - ty, 0.0).x;
  float pF = textureLod(pressIn, uvw + tz, 0.0).x, pB = textureLod(pressIn, uvw - tz, 0.0).x;
  vec3 gradient = vec3(pR - pL, pU - pD, pF - pB) * 0.5;
  imageStore(velOut, c, vec4(textureLod(velIn, uvw, 0.0).xyz - gradient, 0.0));
}
"""

_K_ADVECT_DYE = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 vel = textureLod(velIn, uvw, 0.0).xyz;
  vec3 prevPos = uvw - (vel / WSIZE) * uDt;
  vec4 dye = textureLod(dyeIn, prevPos, 0.0);
  float density = dye.r * max(1.0 - uDissipation * uDt, 0.0);
  float temperature = dye.g * max(1.0 - uCooling * uDt, 0.0);
  vec3 nearestUVW = (floor(prevPos * GRID) + 0.5) / GRID;
  float age = textureLod(dyeIn, nearestUVW, 0.0).b + uDt;
  temperature = clamp(temperature, 0.0, 12.0);
  if (density <= 0.01) age = 0.0;
  imageStore(dyeOut, c, vec4(density, temperature, age, 1.0));
}
"""

# The engine's emitTeapotPass in two passes, so that a bake gives the same grids every time. The engine's kernel samples
# the dye at each emitter point (the dye before this substep's advection), adds the point's emission and stores the sum
# into the point's voxel. Points that share a voxel store at the same time and the GPU keeps one of them, a different
# one from run to run (three bakes of the teapot gave frame 1 a peak density of 3.26, 3.38 and 3.38). Here the first
# pass works out each point's store exactly as the engine's kernel does and keeps it in `stores` (a texel per point, the
# floats' bits as they are), and each point claims its voxel with an atomic max of its claim (_K_CLAIM); the second
# pass makes the store of the point with the highest claim and nobody else's, and that point resets the claim, so the
# claims are all zero again for the next substep. The claims are a hash of the point's index salted with the substep's
# number, so the store kept is drawn afresh among the voxel's points every substep, as the race drew it. A fixed order
# would not keep the look: the last point in buffer order (what the kernel leaves when its points run one after
# another) bakes the teapot's two seconds with 30 % less smoke than the race, the first with about twice as much,
# because a voxel's points sample the dye at different places and a fixed order picks the same place every time.
_K_CLAIM = r"""
uint eido_fmix32(uint h) {                       // murmur3's 32-bit finaliser: a bijection of the 32-bit integers
  h ^= h >> 16; h *= 0x85EBCA6Bu; h ^= h >> 13; h *= 0xC2B2AE35u; h ^= h >> 16;
  return h;
}
// a point's claim on its voxel in one substep: distinct for every point (a bijection of the index, the salt fixed),
// never 0, the cleared value (the salt's top bit is set and the indices stay below 2^31)
uint eido_claim(int id, int substep) {
  return eido_fmix32(uint(id) ^ (eido_fmix32(uint(substep)) | 0x80000000u));
}
"""

_K_EMIT = r"""
void main() {
  int id = int(gl_GlobalInvocationID.x);
  if (id >= uCount) return;
  uvec4 store = uvec4(0u, 0u, 0u, 0xFFFFFFFFu);        // w: the voxel's flat index, all ones: no store
  vec3 vertexPos = texelFetch(points, ivec2(id % 256, id / 256), 0).xyz;
  vec3 worldPos = (uEmitterMatrix * vec4(vertexPos, 1.0)).xyz;
  vec3 uvw = (worldPos - vec3(0.0, WSIZE.y / 2.0, 0.0)) / WSIZE + 0.5;
  if (uvw.x >= 0.0 && uvw.x <= 1.0 && uvw.y >= 0.0 && uvw.y <= 1.0 && uvw.z >= 0.0 && uvw.z <= 1.0) {
    ivec3 coord = ivec3(uvec3(uvw * GRID));
    float flicker = eido_mx_noise(vertexPos * 9.0 + vec3(0.0, -uTime * 2.5, uTime * 0.7)) * 0.5 + 0.5;
    float baseEmission = uEmitTemperature > 0.0 ? 1.0 : 0.0;
    float emissionFactor = baseEmission + uEmitterSpeed * uMotionBoost;
    float densityVal = uEmitDensity * (1.0 / 120.0) * (flicker * 0.85 + 0.15) * emissionFactor;
    if (densityVal > 0.0 && INSIDE(coord)) {        // (a store past the grid's last voxel is dropped, as the engine's)
      float tempVal = uEmitTemperature * (1.0 / 120.0) * (flicker * 0.85 + 0.15) * emissionFactor;
      vec4 cur = textureLod(dyeIn, uvw, 0.0);
      float newDensity = cur.r + densityVal;
      float newTemp = clamp(cur.g + tempVal, 0.0, 12.0);
      float newAge = mix(cur.b, 0.0, densityVal / max(newDensity, 0.001));
      store = uvec4(floatBitsToUint(newDensity), floatBitsToUint(newTemp), floatBitsToUint(newAge),
                    (uint(coord.z) * uint(GY) + uint(coord.y)) * uint(GX) + uint(coord.x));
      imageAtomicMax(claims, coord, eido_claim(id, uSubstep));
    }
  }
  imageStore(stores, ivec2(id % 256, id / 256), store);
}
"""

_K_EMIT_STORE = r"""
void main() {
  int id = int(gl_GlobalInvocationID.x);
  if (id >= uCount) return;
  uvec4 store = texelFetch(stores, ivec2(id % 256, id / 256), 0);
  if (store.w == 0xFFFFFFFFu) return;
  ivec3 coord = ivec3(int(store.w % uint(GX)), int((store.w / uint(GX)) % uint(GY)), int(store.w / uint(GX * GY)));
  if (imageLoad(claims, coord).x != eido_claim(id, uSubstep)) return;
  imageStore(claims, coord, uvec4(0u));
  imageStore(dyeOut, coord, vec4(uintBitsToFloat(store.x), uintBitsToFloat(store.y), uintBitsToFloat(store.z), 1.0));
}
"""

# the render sample the engine computed per raymarch step (getVolumeSample minus the detail noise, which the
# material evaluates per shading sample): velocity domain warp, then the box-edge fade on density
_K_RENDER = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 uvw = uvw_of(c);
  vec3 noiseDistortion = textureLod(velIn, uvw, 0.0).xyz / WSIZE * 0.15;
  vec3 d = clamp(uvw + noiseDistortion, 0.0, 1.0);
  vec4 s = textureLod(dyeIn, d, 0.0);
  vec3 edge = min(d, vec3(1.0) - d);
  float density = s.r * smoothstep(0.0, 0.06, min(edge.x, min(edge.y, edge.z)));
  imageStore(outTex, c, vec4(density, s.g, s.b, 0.0));
}
"""


def _three_axes(size_b):
    """Blender (x, y, z) extents -> three (x, y, z): (x, z, y) (lengths, no sign)."""
    return (size_b[0], size_b[2], size_b[1])


def _is_animated(ob):
    """Whether the object's world transform can change with the frame: keys or drivers on it or on a parent,
    constraints, or a parent bone (an armature's pose)."""
    while ob is not None:
        ad = ob.animation_data
        if ad is not None and (ad.action is not None or len(ad.drivers) or len(ad.nla_tracks)):
            return True
        if len(ob.constraints) or ob.parent_type == 'BONE':
            return True
        ob = ob.parent
    return False


class VolumeFire:
    """What create_volume_fire returns. Attributes mirror the engine's API object where Blender has a match:

    volume_object   the Volume object playing the baked .vdb sequence (engine: volumeMesh)
    point_light     the fire's light on surfaces (engine: pointLight, isVolume = 0 branch)
    volume_light    the fire's light on the smoke (engine: the same light's isVolume = 1 branch)
    shadow_mesh     the smoke's shadow caster over the ground, with shadow_floor (engine: shadowMesh), else None
    material        the volume material (engine: volumetricMaterial)
    params          the resolved options (engine: params)
    sim_time        seconds of simulation after the last bake (engine: simTime)
    stem            the last bake's frames are <cache_dir>/<stem>_####.vdb: the fire's name, or <name>_bake2, _bake3 ...
                    for a fire baked again in the same Blender session (_SESSION_SEQUENCES)
    bake()          warmup + one step per frame + .vdb + light keys (engine: warmup() then step(dt) per frame)
    make_lava_emissive(material)   the burning mesh's lava cracks (engine: makeLavaEmissive)
    """

    def __init__(self, scene, mesh, o):
        import bpy
        self.scene = scene
        self.mesh = mesh
        self.params = o
        self.sim_time = 0.0
        self.name = o['name']
        self.stem = self.name
        gb = o['grid_size']
        self.G3 = (int(gb[0]), int(gb[2]), int(gb[1]))          # three grid (x, y, z)
        self.W3 = tuple(float(x) for x in _three_axes(o['world_size']))
        self.origin = np.array(o['origin'], dtype=np.float64)
        self.cache_dir = abspath(o['cache_dir'])
        self._lava_values = []
        self._build_volume(bpy)
        self._build_lights(bpy)
        self.shadow_mesh = self._build_shadow_mesh(bpy) if o['shadow_floor'] is not None else None

    # ---------------------------------------------------------------------------------------------
    # scene objects
    # ---------------------------------------------------------------------------------------------
    def _build_volume(self, bpy):
        o = self.params
        name = self.name
        vol = bpy.data.volumes.new(name)
        obj = bpy.data.objects.new(name, vol)
        self.scene.collection.objects.link(obj)
        obj.location = tuple(self.origin)
        self.volume_object = obj
        self.material = self._build_material(bpy)
        vol.materials.append(self.material)

    def _key_light_pos_blender(self):
        o = self.params
        if o['key_light'] is not None:
            return np.array(o['key_light'].matrix_world.translation, dtype=np.float64)
        if o['key_light_pos'] is not None:
            return np.array(o['key_light_pos'], dtype=np.float64)
        WX, WY, WZ = self.W3
        p3 = np.array([-3 * (WX / 8), 6 * (WY / 8) + WY / 2 + 0.4, 3 * (WZ / 8)])
        return from_three(p3) + self.origin

    def _build_material(self, bpy):
        from . import _nodes
        o = self.params
        mat = bpy.data.materials.new(self.name + '_volume')
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (900, 0)
        pv = nt.nodes.new('ShaderNodeVolumePrincipled')
        pv.location = (600, 0)
        nt.links.new(pv.outputs['Volume'], out.inputs['Volume'])
        b = _nodes.Builder(nt)

        def attr(nm):
            n = b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY')
            return b.s(n.outputs['Fac'])

        density = attr('density')
        temperature = attr('temperature')
        age = attr('age')
        # domain-local position in three's frame: object (x, y, z) -> (x, z, -y)
        tc = b.node('ShaderNodeTexCoord')
        px, py, pz = b.vec(tc.outputs['Object']).xyz()
        p3 = (px, pz, -py)
        if o['detail_noise']:
            _nodes.snoise_group()
            q = b.combine(p3[0] * 5.5, p3[1] * 5.5 - age * 0.8, p3[2] * 5.5)
            g = b.group('eido.snoise', Vector=q)
            detail = b.s(g.outputs['Value'])
            density = density * (detail * 0.35 + 0.85)
        # fire emission (scatteringEmissiveNode): fireRamp(T) * T^(6-spread) * intensity, hue, (rho + .15) * 400/d^2
        power = 6.0 - o['fire_glow_spread']
        tpow = b.pow(b.max(temperature, 0.0), power) if power != 1.0 else temperature
        kpos = self._key_light_pos_blender() - self.origin           # in the volume object's local frame
        self.key_value_nodes = []
        kx, ky, kz = (b.value(float(v), label=f'key_light_{a}') for v, a in zip(kpos, 'xyz'))
        dxk, dyk, dzk = px - kx, py - ky, pz - kz
        d2 = dxk * dxk + dyk * dyk + dzk * dzk
        atten = 400.0 / b.max(d2, 1e-4)
        scale = (density + 0.15) * atten * (0.01 * o['emission_scale'])
        match = self._display_table('fire', o['display_path'])
        if match is not None:
            # the colour is fireRamp(clamp(T)) with the hue turn, the strength everything else: the table holds
            # the emission that displays like the engine's ACES at that colour and strength
            emis = _look.lookup(b, match[0], b.clamp(temperature, 0.0, 1.0), tpow * o['fire_intensity'] * scale,
                                *match[1:])
        else:
            start, mid, end = color(o['fire_start_color']), color(o['fire_mid_color']), color(o['fire_end_color'])
            ramp = _nodes.fire_ramp(b, b.clamp(temperature, 0.0, 1.0), start, mid, end)
            fire = _nodes.hue_rotate(b, b.vscale(ramp, tpow * o['fire_intensity']), math.radians(o['fire_hue']))
            emis = b.vscale(fire, scale)
        b.link(emis, pv.inputs['Emission Color'])
        pv.inputs['Emission Strength'].default_value = 1.0
        # extinction: the engine's raymarch barely attenuated the camera ray (its falloff scaled with the
        # light it had gathered), so the hot core always showed through the smoke it emits. EEVEE's
        # extinction is physical; burning gas is far clearer than the cooled soot above it, so hot cells
        # lose `flame_clarity` of their extinction
        clear = 1.0 - b.smoothstep(0.15, 0.9, temperature) * o['flame_clarity']
        b.link(density * clear * o['smoke_density'], pv.inputs['Density'])
        pv.inputs['Color'].default_value = (*o['smoke_color'], 1.0)
        pv.inputs['Anisotropy'].default_value = o['asymmetry']
        pv.inputs['Absorption Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        pv.inputs['Density Attribute'].default_value = ''
        pv.inputs['Temperature Attribute'].default_value = ''
        pv.inputs['Blackbody Intensity'].default_value = 0.0
        return mat

    def _ramp_colors(self, n, sat=None):
        """fireRamp(t) at t = i/(n-1) (numpy), saturated (the lava's) and hue-turned like the shaders."""
        o = self.params
        start, mid, end = (np.array(color(o[k])) for k in ('fire_start_color', 'fire_mid_color', 'fire_end_color'))
        t = np.linspace(0.0, 1.0, n)[:, None]
        c = (end[None] * smoothstep(0.05, 0.35, t))
        c = c + (mid - c) * smoothstep(0.35, 0.65, t)
        c = c + (start - c) * smoothstep(0.65, 1.0, t)
        if sat is not None:
            c = saturation(c, sat)
        return hue(c, math.radians(o['fire_hue']))

    def _display_table(self, kind, path, n_t=64, n_s=128, s_range=(-14.0, 10.0)):
        """(image, s_range, n_t, n_s) of the display match for the fire ('fire'), the burning mesh's glow ('glow':
        the fire's colours on a surface) or lava ('lava') colours, or None when display_match is off or the
        scene's colour pipeline cannot be read. One table per colour family and path, shared by its users."""
        o = self.params
        if not o['display_match']:
            return None
        if o['display_match'] not in ('aces', 'aces_compose'):
            raise ValueError(f"[fx.fire] display_match must be 'aces', 'aces_compose' or None, "
                             f"not {o['display_match']!r}")
        if o['display_match'] == 'aces_compose' and kind == 'fire':
            return None                  # the volume emits the raw ramp; create_fire_compose matches its pass
        family = 'lava' if kind == 'lava' else 'fire'
        tables = self.__dict__.setdefault('_tables', {})
        if (family, float(path)) in tables:
            return tables[(family, float(path))]
        try:
            view = getattr(self, '_view', None) or _look.SceneView(self.scene)
            self._view = view
            cols = self._ramp_colors(n_t, sat=o['saturation_amount'] if family == 'lava' else None)
            table, emax, emean = _look.match_table(cols, view, path=path, s_range=s_range, n_s=n_s)
        except Exception as e:  # noqa: BLE001
            print(f'[fx.fire] display match unavailable ({e!r}): emitting the raw ramp')
            return None
        img = _look.table_image(f'{self.name}_look_{family}', table, self.cache_dir)
        print(f'[fx.fire] {family} display match ({view.name}, exposure {view.exposure:+.2f}, path {path} m):'
              f' max display error {emax * 255:.1f}/255, mean {emean * 255:.2f}/255')
        tables[(family, float(path))] = (img, s_range, n_t, n_s)
        return tables[(family, float(path))]

    def _build_lights(self, bpy):
        o = self.params
        # surface light: at the burning mesh's origin (the example: teapot.add(pointLight)), no shadows
        ld = bpy.data.lights.new(self.name + '_light', 'POINT')
        ld.use_shadow = False
        ld.shadow_soft_size = 0.3
        ld.volume_factor = 0.0
        ld.use_custom_distance = True
        lo = bpy.data.objects.new(self.name + '_light', ld)
        self.scene.collection.objects.link(lo)
        self.point_light = lo
        # volume light: the flame column's centre (sway + half height), soft radius 1.2 m (the example's r)
        vd = bpy.data.lights.new(self.name + '_volume_light', 'POINT')
        vd.use_shadow = False
        vd.shadow_soft_size = 1.2
        vd.diffuse_factor = 0.0
        vd.specular_factor = 0.0
        vd.transmission_factor = 0.0
        vd.volume_factor = 1.0
        vd.use_custom_distance = True
        vo = bpy.data.objects.new(self.name + '_volume_light', vd)
        self.scene.collection.objects.link(vo)
        self.volume_light = vo

    # ---------------------------------------------------------------------------------------------
    # the smoke's shadow on the ground (the engine's shadowMesh)
    # ---------------------------------------------------------------------------------------------
    def _domain_box(self):
        """the domain's box in Blender world coordinates: (lo, hi)"""
        WX, WY, WZ = self.W3
        return self.origin + np.array([-WX / 2, -WZ / 2, 0.0]), self.origin + np.array([WX / 2, WZ / 2, WY])

    def _toward_key(self, P):
        """(unit directions toward the key light, distances) from the points P (Blender world); a sun is a direction"""
        kl = self.params['key_light']
        if kl is not None and kl.type == 'LIGHT' and kl.data.type == 'SUN':
            d = np.array(kl.matrix_world.to_3x3().col[2], dtype=np.float64)
            return np.broadcast_to(d / np.linalg.norm(d), P.shape), np.full(len(P), np.inf)
        D = self._key_light_pos_blender()[None, :] - P
        dist = np.maximum(np.linalg.norm(D, axis=1), 1e-9)
        return D / dist[:, None], dist

    def _build_shadow_mesh(self, bpy):
        """The engine's shadowMesh as EEVEE can have it: a plane shadow_lift over the ground (shadow_floor), seen by
        shadow rays only, its opacity per texel the smoke's transmittance toward the key light (_write_shadow, per
        baked frame), so the key light casts the smoke's soft shadow on the ground. It covers the ground the domain's
        box can shadow from where the key light is when the fire is built (at most 2 x the domain round it)."""
        z = float(self.params['shadow_floor'])
        lo, hi = self._domain_box()
        corners = np.array([(x, y, zz) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for zz in (lo[2], hi[2])])
        d, _dist = self._toward_key(corners)
        up = d[:, 2] > 1e-3
        cast = corners[up] - d[up] * ((corners[up, 2] - z) / d[up, 2])[:, None]       # down the ray onto the ground
        pts = np.vstack([corners[:, :2], cast[:, :2]])
        span = max(hi[0] - lo[0], hi[1] - lo[1]) * 2.0
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        x0, x1 = max(pts[:, 0].min(), cx - span), min(pts[:, 0].max(), cx + span)
        y0, y1 = max(pts[:, 1].min(), cy - span), min(pts[:, 1].max(), cy + span)
        zz = z + float(self.params['shadow_lift'])
        self.shadow_extent = (x0, y0, x1, y1, zz)
        me = bpy.data.meshes.new(self.name + '_shadow')
        me.from_pydata([(x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name='UVMap')
        for i, c in enumerate(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
            uv.data[i].uv = c
        ob = bpy.data.objects.new(self.name + '_shadow', me)
        self.scene.collection.objects.link(ob)
        ob.visible_camera = False
        for a in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter'):
            setattr(ob, a, False)
        ob.visible_shadow = True
        ob.hide_probe_volume = ob.hide_probe_sphere = ob.hide_probe_plane = True
        ob.hide_render = True                    # until a bake gives it the smoke's transmittance
        m = bpy.data.materials.new(self.name + '_shadow')
        m.use_nodes = True
        m.surface_render_method = 'DITHERED'
        m.use_transparent_shadow = True
        nt = m.node_tree
        nt.nodes.clear()
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.name = tex.label = 'smoke_transmittance'
        tex.interpolation, tex.extension = 'Linear', 'EXTEND'
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        mix = nt.nodes.new('ShaderNodeMixShader')
        dark = nt.nodes.new('ShaderNodeBsdfDiffuse')
        dark.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        for i, n in enumerate((tex, sep, dark, clear, mix, out)):
            n.location = (-900 + 220 * i, 0)
        nt.links.new(tex.outputs['Color'], sep.inputs[0])
        nt.links.new(sep.outputs[0], mix.inputs['Fac'])                 # transmittance 1: clear, 0: opaque
        nt.links.new(dark.outputs[0], mix.inputs[1])
        nt.links.new(clear.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        me.materials.append(m)
        return ob

    def _shadow_march(self):
        """The shadow plane's march toward the key light, which only moves with the key light: for each texel's 64
        steps across the domain, the eight voxels of its trilinear sample in the grids (flat indices into arr[..., c],
        8 x texels x 64) and their weights (zero outside the grid), and each texel's step length"""
        kl = self.params['key_light']
        if kl is not None and kl.type == 'LIGHT' and kl.data.type == 'SUN':
            key = ('sun',) + tuple(np.round(np.array(kl.matrix_world.to_3x3().col[2]), 6))
        else:
            key = tuple(np.round(self._key_light_pos_blender(), 6))
        cached = getattr(self, '_march_cache', None)
        if cached is not None and cached[0] == key:
            return cached[1]
        res = int(self.params['shadow_resolution'])
        x0, y0, x1, y1, z = self.shadow_extent
        X, Y = np.meshgrid(np.linspace(x0, x1, res), np.linspace(y0, y1, res))     # row 0 = y0 = the image's bottom
        P = np.stack([X.ravel(), Y.ravel(), np.full(X.size, z)], -1)
        d, dist = self._toward_key(P)
        lo, hi = self._domain_box()
        inv = 1.0 / np.where(np.abs(d) < 1e-9, 1e-9, d)
        ta, tb = (lo[None] - P) * inv, (hi[None] - P) * inv
        t_in = np.clip(np.minimum(ta, tb).max(axis=1), 0.0, None)
        t_out = np.minimum(np.maximum(ta, tb).min(axis=1), dist)
        ds = np.clip(t_out - t_in, 0.0, None) / 64
        Q = P[:, None, :] + d[:, None, :] * (t_in[:, None] + (np.arange(64) + 0.5)[None, :] * ds[:, None])[..., None]
        GX, GY, GZ = self.G3
        WX, WY, WZ = self.W3
        cell = WX / GX
        rel = Q - self.origin
        fz, fy, fx = ((-rel[..., 1] + WZ / 2) / cell - 0.5, rel[..., 2] / cell - 0.5, (rel[..., 0] + WX / 2) / cell - 0.5)
        z0, y0_, x0_ = (np.floor(f).astype(np.int64) for f in (fz, fy, fx))
        tz, ty, tx = fz - z0, fy - y0_, fx - x0_
        flat, wts = [], []
        for dz in (0, 1):
            for dy in (0, 1):
                for dx in (0, 1):
                    zi, yi, xi = z0 + dz, y0_ + dy, x0_ + dx
                    ok = (zi >= 0) & (zi < GZ) & (yi >= 0) & (yi < GY) & (xi >= 0) & (xi < GX)
                    w = (tz if dz else 1 - tz) * (ty if dy else 1 - ty) * (tx if dx else 1 - tx) * ok
                    flat.append(((np.clip(zi, 0, GZ - 1) * GY + np.clip(yi, 0, GY - 1)) * GX
                                 + np.clip(xi, 0, GX - 1)).astype(np.int32))
                    wts.append(w.astype(np.float32))
        self._march_cache = (key, (flat, wts, ds))
        return self._march_cache[1]

    def _write_shadow(self, frame, arr):
        """The smoke's transmittance toward the key light from each texel of the shadow plane, through this frame's
        grids (arr [z3, y3, x3, c], as written to the .vdb) with the volume material's extinction (density x
        smoke_density, burning gas clearer by flame_clarity, x 0.85 for the detail noise's mean factor when
        detail_noise is on), 64 steps across the domain: <cache>/<stem>_shadow_####.exr"""
        o = self.params
        res = int(o['shadow_resolution'])
        flat, wts, ds = self._shadow_march()
        dens_f = np.ascontiguousarray(arr[..., 0], np.float32).ravel()
        temp_f = np.ascontiguousarray(arr[..., 1], np.float32).ravel()
        dens = sum(wts[k] * dens_f[flat[k]] for k in range(8))
        temp = sum(wts[k] * temp_f[flat[k]] for k in range(8))
        clear = 1.0 - smoothstep(0.15, 0.9, temp) * o['flame_clarity']
        detail = 0.85 if o['detail_noise'] else 1.0          # the material's density x (0.35 snoise + 0.85), on average
        tau = (np.maximum(dens, 0.0) * clear).sum(axis=1) * ds * o['smoke_density'] * detail
        T = np.exp(-tau).reshape(res, res)
        from ._util import write_exr
        write_exr(frame_file(self.cache_dir, self.stem + '_shadow', frame, 'exr'), np.repeat(T[..., None], 3, 2))

    def _attach_shadow_sequence(self, fs, fe):
        import bpy
        img = bpy.data.images.load(frame_file(self.cache_dir, self.stem + '_shadow', fs, 'exr'), check_existing=False)
        img.source = 'SEQUENCE'
        img.colorspace_settings.name = 'Non-Color'
        tex = self.shadow_mesh.active_material.node_tree.nodes['smoke_transmittance']
        tex.image = img
        iu = tex.image_user
        iu.frame_duration = fe - fs + 1
        iu.frame_start = fs
        iu.frame_offset = fs - 1
        iu.use_auto_refresh = True
        iu.use_cyclic = False
        self.shadow_mesh.hide_render = False

    # ---------------------------------------------------------------------------------------------
    # emitter
    # ---------------------------------------------------------------------------------------------
    def _emitter_local_points(self, depsgraph):
        """Emitter points in the mesh object's local frame, converted to three's axes (the engine applies the
        noise to three-local vertex positions)."""
        o = self.params
        ob = self.mesh.evaluated_get(depsgraph)
        me = ob.to_mesh()
        try:
            n = len(me.vertices)
            co = np.empty(n * 3, dtype=np.float64)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            if o['emitter_points'] is None:
                pts = co
            else:
                me.calc_loop_triangles()
                nt = len(me.loop_triangles)
                tri = np.empty(nt * 3, dtype=np.int64)
                me.loop_triangles.foreach_get('vertices', tri)
                tri = tri.reshape(-1, 3)
                p0, p1, p2 = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
                area = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) * 0.5
                cum = np.cumsum(area)
                total = cum[-1]
                rnd = LCG(o['seed'])
                count = int(o['emitter_points'])
                pts = np.empty((count, 3))
                for k in range(count):
                    r = rnd() * total
                    t = int(np.searchsorted(cum, r, side='left'))
                    t = min(t, nt - 1)
                    u, v = rnd(), rnd()
                    if u + v > 1:
                        u, v = 1 - u, 1 - v
                    pts[k] = p0[t] + (p1[t] - p0[t]) * u + (p2[t] - p0[t]) * v
        finally:
            ob.to_mesh_clear()
        return np.stack([pts[:, 0], pts[:, 2], -pts[:, 1]], axis=-1)    # Blender local -> three local

    def _emitter_matrix(self):
        """three-local vertex -> three domain-world: B2T * T(-origin) * M_world * T2B."""
        M = np.array(self.mesh.matrix_world, dtype=np.float64)
        Tm = np.eye(4)
        Tm[:3, 3] = -self.origin
        return B2T @ Tm @ M @ T2B

    def _emitter_pos3(self):
        p = np.array(self.mesh.matrix_world.translation, dtype=np.float64) - self.origin
        return np.array([p[0], p[2], -p[1]])

    # ---------------------------------------------------------------------------------------------
    # the bake
    # ---------------------------------------------------------------------------------------------
    def bake(self, frame_start=None, frame_end=None, controls=None, log=print):
        """Warm up, then step once per frame over [frame_start, frame_end] and write <cache>/<name>_####.vdb.
        controls(frame, t) -> dict may override any solver option per frame (wind, densities, colours ...)."""
        glow = self.mesh.modifiers.get(GLOW_MODIFIER)
        shown = glow.show_viewport if glow is not None else None
        if glow is not None:
            glow.show_viewport = False            # the solver reads the bare mesh; the glow samples what it writes
        try:
            return self._bake(frame_start, frame_end, controls, log)
        finally:
            if glow is not None:
                glow.show_viewport = shown

    def _bake(self, frame_start, frame_end, controls, log):
        import bpy
        from ._gpu import ComputeContext, GLSL_SNOISE, GLSL_MX_NOISE
        import openvdb as vdb
        o = self.params
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = scene_fps(sc)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.stem = self._fresh_stem()
        if self.stem != self.name:
            log(f'[fx.fire] {self.name}_####.vdb may have been read in this Blender session, which keeps the grids '
                f'of every .vdb it reads: this bake writes {self.stem}_####.vdb')
        GX, GY, GZ = self.G3
        WX, WY, WZ = self.W3
        ctx = ComputeContext()
        defs = {'GX': GX, 'GY': GY, 'GZ': GZ, 'WX': f'{WX:.6f}', 'WY': f'{WY:.6f}', 'WZ': f'{WZ:.6f}'}
        pre = _HEAD + GLSL_SNOISE + GLSL_MX_NOISE
        size = (GX, GY, GZ)
        tex = lambda: ctx.texture3d(size)                                     # noqa: E731
        velA, velB, dyeA, dyeB, divT, prA, prB, rnd = (tex() for _ in range(8))
        curl = ctx.texture3d(size, extend='REPEAT')
        F = 'FLOAT'
        k_curl = ctx.kernel(_K_CURL, images=['outTex'], push=[(F, 'uTurbFreq')], defines=defs, preamble=pre)
        k_vel = ctx.kernel(_K_ADVECT_VEL, samplers=['velIn', 'dyeIn', 'curlTex'], images=['velOut'],
                           push=[(F, 'uDt'), (F, 'uTime'), (F, 'uBuoyancy'), (F, 'uWeight'), (F, 'uTurbulence'),
                                 (F, 'uTurbDecay'), (F, 'uTurbFreq'), (F, 'uVelDamping'), (F, 'uEmitterRadius'),
                                 (F, 'uEmitterSpeed'), (F, 'uWindStrength'), ('VEC3', 'uEmitterPos'),
                                 ('VEC3', 'uEmitterVel')], defines=defs, preamble=pre)
        k_div = ctx.kernel(_K_DIVERGENCE, samplers=['velIn'], images=['outTex'], defines=defs, preamble=pre)
        k_jac = ctx.kernel(_K_JACOBI, samplers=['pressIn', 'divIn'], images=['outTex'], defines=defs, preamble=pre)
        k_proj = ctx.kernel(_K_PROJECT, samplers=['pressIn', 'velIn'], images=['velOut'], defines=defs, preamble=pre)
        k_dye = ctx.kernel(_K_ADVECT_DYE, samplers=['velIn', 'dyeIn'], images=['dyeOut'],
                           push=[(F, 'uDt'), (F, 'uDissipation'), (F, 'uCooling')], defines=defs, preamble=pre)
        claim = ('R32UI', 'UINT_3D_ATOMIC', ('READ', 'WRITE'))          # a voxel's claim: its points' highest
        k_emit = ctx.kernel(_K_CLAIM + _K_EMIT, samplers=['dyeIn', 'points'], images=['claims', 'stores'],
                            sampler_types={'points': 'FLOAT_2D'},
                            image_specs={'claims': claim, 'stores': ('RGBA32UI', 'UINT_2D', ('WRITE',))},
                            local=(64, 1, 1),
                            push=[('MAT4', 'uEmitterMatrix'), (F, 'uTime'), (F, 'uEmitTemperature'),
                                  (F, 'uEmitDensity'), (F, 'uEmitterSpeed'), (F, 'uMotionBoost'), ('INT', 'uCount'),
                                  ('INT', 'uSubstep')],
                            defines=defs, preamble=pre)
        k_store = ctx.kernel(_K_CLAIM + _K_EMIT_STORE, samplers=['stores'], images=['claims', 'dyeOut'],
                             sampler_types={'stores': 'UINT_2D'}, image_specs={'claims': claim}, local=(64, 1, 1),
                             push=[('INT', 'uCount'), ('INT', 'uSubstep')], defines=defs, preamble=pre)
        k_render = ctx.kernel(_K_RENDER, samplers=['velIn', 'dyeIn'], images=['outTex'], defines=defs, preamble=pre)
        grid_groups = k_vel.groups_for(size)
        k_curl.run(grid_groups, images={'outTex': curl}, uTurbFreq=o['turb_frequency'])
        claims = ctx.texture(size, 'R32UI', filt=False)

        # emitter points (three-local), fixed over the bake like the engine's buffer
        sc.frame_set(fs)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = self._emitter_local_points(dg)
        npts = len(pts)
        rows = int(math.ceil(npts / 256))
        parr = np.zeros((rows, 256, 4), dtype=np.float32)
        parr.reshape(-1, 4)[:npts, :3] = pts
        ptex = ctx.texture2d_from(parr)
        stores = ctx.texture((256, rows), 'RGBA32UI', filt=False)          # each point's store, for the second pass
        emit_groups = (int(math.ceil(npts / 64)), 1, 1)
        log(f'[fx.fire] grid {GX}x{GY}x{GZ} (three axes) over {WX}x{WY}x{WZ} m, emitter {npts} points '
            + ('(raw vertices)' if o['emitter_points'] is None else '(area-weighted samples)'))

        cpu_noise = _noise.ImprovedNoise()
        st = dict(sim_time=0.0, acc=0.0, dye_in_a=True, substep=0)
        state = {'prev_pos': self._emitter_pos3(), 'pos': self._emitter_pos3(), 'vel': np.zeros(3), 'speed': 0.0}
        temporal = {}

        def temporal_update(t):
            temporal['time'] = t % 1000.0
            temporal['flame_height'] = o['flame_height'] + cpu_noise.noise(0, t * 2.5, 0) * 0.8
            temporal['sway'] = (cpu_noise.noise(t * 3.5, 0, 0) * 0.4, 0.0, cpu_noise.noise(0, 0, t * 3.5) * 0.4)
            temporal['flicker'] = (cpu_noise.noise(0, t * 0.8, 0) * 0.12 + cpu_noise.noise(0, t * 15.0, 0) * 0.06
                                   + 0.82)
            temporal['color_noise'] = cpu_noise.noise(t * 5.0, t * 5.0, 0) * 0.08

        def substep(p, M):
            sim_step = (1 / 120) * p['sim_speed']
            turb = p['turbulence'] / math.sqrt(p['sim_speed']) if p['sim_speed'] > 0 else 0.0
            diss = 0.0 if p['smoke_lifespan'] >= 100 else 1.0 / p['smoke_lifespan']
            cool = 1.0 / p['fire_lifespan']
            dye_cur, dye_nxt = (dyeA, dyeB) if st['dye_in_a'] else (dyeB, dyeA)
            k_vel.run(grid_groups, samplers={'velIn': velA, 'dyeIn': dye_cur, 'curlTex': curl},
                      images={'velOut': velB}, uDt=sim_step, uTime=temporal['time'], uBuoyancy=p['buoyancy'],
                      uWeight=p['weight'], uTurbulence=turb, uTurbDecay=p['turbulence_decay'],
                      uTurbFreq=p['turb_frequency'], uVelDamping=p['vel_damping'],
                      uEmitterRadius=p['emitter_radius'], uEmitterSpeed=state['speed'],
                      uWindStrength=p['wind_strength'], uEmitterPos=state['pos'], uEmitterVel=state['vel'])
            k_div.run(grid_groups, samplers={'velIn': velB}, images={'outTex': divT})
            for i in range(int(p['pressure_iterations'])):
                src, dst = (prA, prB) if i % 2 == 0 else (prB, prA)
                k_jac.run(grid_groups, samplers={'pressIn': src, 'divIn': divT}, images={'outTex': dst})
            k_proj.run(grid_groups, samplers={'pressIn': prA, 'velIn': velB}, images={'velOut': velA})
            k_dye.run(grid_groups, samplers={'velIn': velA, 'dyeIn': dye_cur}, images={'dyeOut': dye_nxt},
                      uDt=sim_step, uDissipation=diss, uCooling=cool)
            k_emit.run(emit_groups, samplers={'dyeIn': dye_cur, 'points': ptex},
                       images={'claims': claims, 'stores': stores},
                       uEmitterMatrix=M, uTime=temporal['time'], uEmitTemperature=p['emit_temperature'],
                       uEmitDensity=p['emit_density'], uEmitterSpeed=state['speed'],
                       uMotionBoost=p['motion_boost'], uCount=npts, uSubstep=st['substep'])
            k_store.run(emit_groups, samplers={'stores': stores}, images={'claims': claims, 'dyeOut': dye_nxt},
                        uCount=npts, uSubstep=st['substep'])
            st['dye_in_a'] = not st['dye_in_a']
            st['substep'] += 1

        # ---- warmup (the engine's warmup): simulation time runs up to warmup_seconds before the shot. The
        # engine's onTemporal kept moving the mesh through it (the example's teapot spins on sim time), so an
        # animated mesh is evaluated at the pre-roll scene time of every substep: the warmup ends at frame
        # frame_start - 1, where the first frame's substeps take over, and runs sim_speed x faster than the
        # scene clock like every frame does (keys need an extrapolation, or a driver on `frame`, to move
        # there). The wind stays still, as in the engine. ----
        t0 = time.time()
        p = dict(o)
        if controls:
            p.update(controls(fs, 0.0) or {})
        sim_step = (1 / 120) * p['sim_speed']
        moving = _is_animated(self.mesh)
        M = self._emitter_matrix()
        while st['sim_time'] < p['warmup_seconds']:
            st['sim_time'] += sim_step
            if moving:
                fr = fs - 1 + (st['sim_time'] - p['warmup_seconds']) / p['sim_speed'] * fps
                sc.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
                M = self._emitter_matrix()
            temporal_update(st['sim_time'])
            substep(p, M)
        sc.frame_set(fs)
        log(f'[fx.fire] warmup {p["warmup_seconds"]} s of sim ({int(round(p["warmup_seconds"] / sim_step))} substeps'
            f'{", following the mesh animation" if moving else ""}) in {time.time() - t0:.1f} s')

        light_keys = []
        for f in range(fs, fe + 1):
            t_scene = (f - fs) / fps
            p = dict(o)
            if controls:
                p.update(controls(f, t_scene) or {})
            delta = 1.0 / fps
            # emitter speed / velocity from the mesh's position change over the frame (the engine's step())
            sc.frame_set(f)
            cur = self._emitter_pos3()
            if f == fs:
                state['prev_pos'] = cur.copy()
            state['vel'] = (cur - state['prev_pos']) / delta
            state['speed'] = float(np.linalg.norm(state['vel']))
            state['pos'] = cur
            state['prev_pos'] = cur.copy()
            # no real-time clamps here: the engine's step() caps delta at 1/30 s and the accumulator at 8 substeps
            # so a browser that drops frames cannot spiral; a bake drops none, and the clamp would run a 24 fps
            # film at 0.8x (0.04 s of simulation per frame instead of 1/24 * 1.2 = 0.05 s). Every frame advances
            # 1/fps * sim_speed, as the engine's own 120 fps films did (their delta was never clamped)
            dt = delta * p['sim_speed']
            sim_step = (1 / 120) * p['sim_speed']
            st['acc'] = min(st['acc'] + dt, max(sim_step * 8, dt + sim_step))
            n_sub = int(st['acc'] / sim_step + 1e-9)
            for j in range(n_sub):
                # the mesh moves through the frame: sample its matrix at the substep's subframe
                sub = (j + 1) / n_sub
                if sub < 1.0:
                    sc.frame_set(f - 1, subframe=sub)
                else:
                    sc.frame_set(f)
                M = self._emitter_matrix()
                st['sim_time'] += sim_step
                temporal_update(st['sim_time'])
                substep(p, M)
                st['acc'] -= sim_step
            sc.frame_set(f)
            # render grids: warp + edge fade on the GPU, then out to OpenVDB in Blender's axes
            dye_cur = dyeA if st['dye_in_a'] else dyeB
            k_render.run(grid_groups, samplers={'velIn': velA, 'dyeIn': dye_cur}, images={'outTex': rnd})
            arr = ctx.read(rnd)                                   # (GZ, GY, GX, 4): [z3, y3, x3]
            self._write_vdb(vdb, f, arr)
            if self.shadow_mesh is not None:
                self._write_shadow(f, arr)
            self._grow_bounds(arr)
            light_keys.append((f, self._light_state(p, temporal, st['sim_time'])))
            if (f - fs) % 12 == 0:
                log(f'[fx.fire] frame {f} sim {st["sim_time"]:.2f} s  max density {arr[..., 0].max():.2f}'
                    f'  max T {arr[..., 1].max():.2f}')
        self.sim_time = st['sim_time']
        self._key_lights(light_keys)
        self._attach_sequence(fs, fe)
        if self.shadow_mesh is not None:
            self._attach_shadow_sequence(fs, fe)
        log(f'[fx.fire] baked frames {fs}..{fe} in {time.time() - t0:.1f} s -> '
            f'{os.path.join(self.cache_dir, self.stem)}_####.vdb')
        return self

    def _grow_bounds(self, arr):
        """Union over the bake of where there is anything to see (density or temperature), in Blender world
        coordinates; stored on the volume object as fx_bounds_min / fx_bounds_max for configure_eevee_for_fire."""
        m = (arr[..., 0] > 2e-3) | (arr[..., 1] > 2e-3)
        if not m.any():
            return
        z3, y3, x3 = (np.nonzero(m.any(axis=a))[0] for a in ((1, 2), (0, 2), (0, 1)))
        GX, GY, GZ = self.G3
        WX, WY, WZ = self.W3
        dx = WX / GX
        lo3 = np.array([x3.min(), y3.min(), z3.min()]) * dx - np.array([WX / 2, 0, WZ / 2])
        hi3 = (np.array([x3.max(), y3.max(), z3.max()]) + 1) * dx - np.array([WX / 2, 0, WZ / 2])
        corners = np.array([[a, b, c] for a in (lo3[0], hi3[0]) for b in (lo3[1], hi3[1]) for c in (lo3[2], hi3[2])])
        cb = from_three(corners) + self.origin
        lo, hi = cb.min(axis=0), cb.max(axis=0)
        if getattr(self, 'bounds', None) is None:
            self.bounds = (lo, hi)
        else:
            self.bounds = (np.minimum(self.bounds[0], lo), np.maximum(self.bounds[1], hi))
        self.volume_object['fx_bounds_min'] = [float(x) for x in self.bounds[0]]
        self.volume_object['fx_bounds_max'] = [float(x) for x in self.bounds[1]]

    def _fresh_stem(self):
        """The stem a bake writes its frames under: the fire's name, unless this session may have read frames under
        it (a fire's Volume was pointed at them in this session, or a Volume in the open file plays them, the
        fire's own included); then <name>_bake2, _bake3 ..., the first that is neither."""
        import bpy
        taken = set(_SESSION_SEQUENCES)
        for v in bpy.data.volumes:
            if v.filepath:
                taken.add(_sequence_key(bpy.path.abspath(v.filepath, library=v.library)))
        k = 1
        while _sequence_key(frame_file(self.cache_dir, self._stem_of_bake(k), 1, 'vdb')) in taken:
            k += 1
        return self._stem_of_bake(k)

    def _stem_of_bake(self, k):
        return self.name if k == 1 else f'{self.name}_bake{k}'

    def _write_vdb(self, vdb, frame, arr):
        """arr[z3, y3, x3, c] -> Blender grid [x, y, z] with x = x3, y = (GZ-1 - z3), z = y3."""
        GX, GY, GZ = self.G3
        WX, WY, WZ = self.W3
        dx = WX / GX
        grids = []
        for ch, nm in ((0, 'density'), (1, 'temperature'), (2, 'age')):
            a = arr[..., ch]                                   # [z3, y3, x3]
            b = np.ascontiguousarray(a.transpose(2, 0, 1)[:, ::-1, :])   # [x3, z3 flipped, y3] = Blender [x, y, z]
            g = vdb.FloatGrid()
            g.copyFromArray(b.astype(np.float32), tolerance=1e-4 if nm != 'age' else 0.0)
            g.name = nm
            # voxel (i, j, k) centre at local (-WX/2 + (i+.5)dx, -WZ/2 + (j+.5)dx, (k+.5)dx)
            m = [[dx, 0, 0, 0], [0, dx, 0, 0], [0, 0, dx, 0],
                 [-WX / 2 + 0.5 * dx, -WZ / 2 + 0.5 * dx, 0.5 * dx, 1]]
            g.transform = vdb.createLinearTransform(m)
            grids.append(g)
        path = frame_file(self.cache_dir, self.stem, frame, 'vdb')
        tmp = path + '.tmp'
        vdb.write(tmp, grids=grids)
        os.replace(tmp, path)

    def _attach_sequence(self, fs, fe):
        """The Volume plays the baked files, as Blender plays any .vdb sequence: each depsgraph that evaluates it (the
        viewport's, a render's, in this session or from the saved .blend) reads the frame's file, scene frame f the file
        numbered f, and outside fs..fe none. Nothing is loaded into the datablock itself: a load there runs at the frame
        the datablock last held (0 until it plays a sequence), and Blender keeps a failed load's error on the
        datablock, where every render's copy inherits it, reports no bounds and draws no volume. The sequence joins
        _SESSION_SEQUENCES: a later bake in this session writes its frames under another stem."""
        vol = self.volume_object.data
        _SESSION_SEQUENCES.add(_sequence_key(frame_file(self.cache_dir, self.stem, fs, 'vdb')))
        vol.filepath = frame_file(self.cache_dir, self.stem, fs, 'vdb')
        vol.is_sequence = True
        vol.frame_start = fs                     # scene frame fs plays file fs ...
        vol.frame_offset = fs - 1
        vol.frame_duration = fe - fs + 1         # ... and fe file fe; before and after, CLIP asks for no file
        vol.sequence_mode = 'CLIP'

    # ---------------------------------------------------------------------------------------------
    # the fire's light (pointLightColor), per frame
    # ---------------------------------------------------------------------------------------------
    def _light_state(self, p, temporal, sim_time):
        start, mid, end = (np.array(color(p[k])) for k in ('fire_start_color', 'fire_mid_color', 'fire_end_color'))

        def ramp(t):
            c = np.zeros(3)
            c = c + (end - c) * smoothstep(0.05, 0.35, t)
            c = c + (mid - c) * smoothstep(0.35, 0.65, t)
            return c + (start - c) * smoothstep(0.65, 1.0, t)

        hue_rad = math.radians(p['fire_hue'])
        colorT = float(np.clip(p['emit_temperature'] / 8.34 * 0.5 + 0.20 + temporal['color_noise'], 0, 1))
        col = hue(saturation(ramp(colorT), p['saturation_amount']), hue_rad)
        temp_factor = max(p['emit_temperature'] / 8.34, 0.0) ** 4.0
        density_scale = max(p['emit_density'] / 11.02, 0.0)
        fade_in = float(smoothstep(0.0, 3.0, sim_time))
        base = temp_factor * density_scale * p['fire_intensity'] * temporal['flicker'] * fade_in
        size_factor = math.sqrt(max(p['emit_temperature'] / 8.34 * p['emit_density'] / 11.02
                                    * p['fire_intensity'] / 5.63, 0.0))
        dist = max(0.01, 40.0 * max(0.2, size_factor) * fade_in)
        return dict(color=np.maximum(col, 0.0), surface=base * p['point_light_surface_intensity'],
                    volume=base * p['point_light_volume_intensity'] * 0.5 * (p['light_near_intensity']
                                                                             + p['light_far_intensity']),
                    sway=temporal['sway'], height=temporal['flame_height'], distance=dist,
                    flicker=temporal['flicker'], fade_in=fade_in, time=temporal['time'],
                    lava=temp_factor * density_scale * p['fire_intensity'] * temporal['flicker'] * fade_in
                    * p['mesh_emissive_intensity'])

    def _key_lights(self, keys):
        o = self.params
        lo, vo = self.point_light, self.volume_light
        lo.parent = None
        for f, s in keys:
            c = s['color']
            m = float(c.max()) if c.max() > 0 else 1.0
            # three candela -> Blender watts: P = 4*pi*I (point light, inverse square, same BRDF convention)
            lo.data.color = tuple(c / m)
            lo.data.energy = 4 * math.pi * s['surface'] * m * o['light_scale']
            lo.data.cutoff_distance = s['distance']
            lo.data.keyframe_insert('color', frame=f)
            lo.data.keyframe_insert('energy', frame=f)
            vo.data.color = tuple(c / m)
            vo.data.energy = 4 * math.pi * s['volume'] * m * o['light_scale']
            vo.data.cutoff_distance = s['distance']
            vo.data.keyframe_insert('color', frame=f)
            vo.data.keyframe_insert('energy', frame=f)
            self.scene.frame_set(f)
            base = np.array(self.mesh.matrix_world.translation, dtype=np.float64)
            lo.location = tuple(base)
            lo.keyframe_insert('location', frame=f)
            sw = from_three(np.array(s['sway']))
            vo.location = tuple(base + sw + np.array([0.0, 0.0, s['height'] * 0.5]))
            vo.keyframe_insert('location', frame=f)
            for node, key in self._lava_values:
                node.outputs[0].default_value = s[key]
                node.outputs[0].keyframe_insert('default_value', frame=f)

    # ---------------------------------------------------------------------------------------------
    def make_lava_emissive(self, material):
        """Add the engine's lava-crack emission (teapot emissiveNode) to `material` (a Principled BSDF material).
        Its time and flicker values are keyed by bake(); call this before bake()."""
        from . import _nodes
        o = self.params
        nt = material.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        b = _nodes.Builder(nt, x0=-1600, y0=-400)
        tnode = b.value(0.0, label='fire_time')
        gain = b.value(0.0, label='fire_lava_gain')
        self._lava_values += [(tnode.v.node, 'time'), (gain.v.node, 'lava')]
        tc = b.node('ShaderNodeTexCoord')
        lx, ly, lz = b.vec(tc.outputs['Object']).xyz()
        p = (lx * 0.5, lz * 0.5, -ly * 0.5)                      # three positionLocal * 0.5
        t = tnode

        def mxn(x, y, z):                                         # mx_noise_float(p) * .5 + .5 == Noise Texture
            n = b.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
            if hasattr(n, 'noise_type'):
                n.noise_type = 'FBM'
            n.inputs['Scale'].default_value = 1.0
            n.inputs['Detail'].default_value = 0.0
            n.inputs['Distortion'].default_value = 0.0
            b.link(b.combine(x, y, z), n.inputs['Vector'])
            return b.s(n.outputs['Fac'])

        # flow = (0, -t, 0)
        n1 = mxn(p[0], p[1] - t, p[2])
        p2 = (p[0] * 2.0, p[1] * 2.0 + t * 1.5, p[2] * 2.0)       # p*2 - flow*1.5
        n2 = mxn(p2[0] + n1 * 0.4, p2[1] + n1 * 0.4, p2[2] + n1 * 0.4)
        n3 = mxn(p[0] * 4.0, p[1] * 4.0 - t * 2.5, p[2] * 4.0)    # p*4 + flow*2.5
        nv = n1 * 0.5 + n2 * 0.35 + n3 * 0.15
        lava_t = b.clamp(b.pow(b.max(nv, 0.0), 2.5), 0.0, 1.0)
        match = self._display_table('lava', 1.0)
        if match is not None:
            lava = _look.lookup(b, match[0], lava_t + 0.1, gain, *match[1:])
        else:
            start, mid, end = color(o['fire_start_color']), color(o['fire_mid_color']), color(o['fire_end_color'])
            fc = _nodes.fire_ramp(b, lava_t + 0.1, start, mid, end)
            fc = _nodes.saturate_color(b, fc, o['saturation_amount'])
            lava = b.vscale(_nodes.hue_rotate(b, fc, math.radians(o['fire_hue'])), gain)
        b.link(lava, bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = 1.0
        return material

    def make_fire_glow(self, material, strength=1.0):
        """The burning mesh glows with the fire around it: its surface emits what the gas touching it emits, the
        flame's colour for that temperature over display_path metres of it (the light the volume would gather over
        the same path, through the same display match), x strength. The engine composited its volume pass with no
        depth test, so its fire showed through the burning mesh; in EEVEE the mesh hides the gas behind it, and this
        puts the fire's glow on the mesh itself.

        A Geometry Nodes modifier on the burning mesh (GLOW_MODIFIER) samples the baked grids at every vertex, live
        from the volume object at each frame, into the point attributes 'fire_temperature' and 'fire_density'; the
        material adds the emission it makes from them to whatever already feeds its Emission Color, scaled by the
        Emission Strength it had (then sets the strength to 1). The strength is the material's Value node
        'fire_glow_strength' (keyable); calling this again on a glowing material sets it. bake() mutes the modifier
        while the solver reads the mesh. Call it after make_lava_emissive when the material has both (the lava, as
        the engine's emissiveNode, replaces what feeds Emission Color). Returns the material."""
        from . import _nodes
        o = self.params
        nt = material.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None) if nt else None
        if bsdf is None:
            raise ValueError(f'[fx.fire] make_fire_glow: material {material.name!r} has no Principled BSDF')
        md = self.mesh.modifiers.get(GLOW_MODIFIER) or self.mesh.modifiers.new(GLOW_MODIFIER, 'NODES')
        md.node_group = self._glow_tree()
        gain = nt.nodes.get('fire_glow_strength')
        if gain is not None:                     # already glowing: set its strength
            gain.outputs[0].default_value = float(strength)
            return material
        b = _nodes.Builder(nt, x0=-1600, y0=-1600)
        gain = b.value(float(strength), label='fire_glow_strength')

        def attr(nm):
            return b.s(b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY').outputs['Fac'])

        temperature, density = b.max(attr('fire_temperature'), 0.0), b.max(attr('fire_density'), 0.0)
        # the volume material's emission per metre (_build_material), at the surface point
        power = 6.0 - o['fire_glow_spread']
        tpow = b.pow(temperature, power) if power != 1.0 else temperature
        px, py, pz = b.vec(b.node('ShaderNodeNewGeometry').outputs['Position']).xyz()
        kx, ky, kz = (b.value(float(v), label=f'glow_key_light_{a}') for v, a in zip(self._key_light_pos_blender(), 'xyz'))
        d2 = (px - kx) * (px - kx) + (py - ky) * (py - ky) + (pz - kz) * (pz - kz)
        scale = (density + 0.15) * (400.0 / b.max(d2, 1e-4)) * (0.01 * o['emission_scale'])
        match = self._display_table('glow', o['display_path'])
        if match is not None:
            emis = _look.lookup(b, match[0], b.clamp(temperature, 0.0, 1.0), tpow * o['fire_intensity'] * scale,
                                *match[1:])
        else:
            start, mid, end = color(o['fire_start_color']), color(o['fire_mid_color']), color(o['fire_end_color'])
            ramp = _nodes.fire_ramp(b, b.clamp(temperature, 0.0, 1.0), start, mid, end)
            fire = _nodes.hue_rotate(b, b.vscale(ramp, tpow * o['fire_intensity']), math.radians(o['fire_hue']))
            emis = b.vscale(fire, scale)
        glow = b.vscale(emis, gain * float(o['display_path']))
        sock, k = bsdf.inputs['Emission Color'], float(bsdf.inputs['Emission Strength'].default_value)
        if sock.is_linked:
            glow = b.vscale(b.vec(sock.links[0].from_socket), k) + glow
        elif k > 0.0:
            glow = b.combine(*(c * k for c in tuple(sock.default_value)[:3])) + glow
        b.link(glow, sock)
        bsdf.inputs['Emission Strength'].default_value = 1.0
        return material

    def _glow_tree(self):
        """make_fire_glow's Geometry Nodes: the volume object's density and temperature grids (in the burning mesh's
        frame) sampled at each vertex into 'fire_density' and 'fire_temperature'"""
        import bpy
        name = f'{self.name}_glow'
        tree = bpy.data.node_groups.get(name)
        if tree is not None:
            return tree
        tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        N, L = tree.nodes, tree.links
        gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
        oi = N.new('GeometryNodeObjectInfo')
        oi.transform_space = 'RELATIVE'
        oi.inputs['Object'].default_value = self.volume_object
        pos = N.new('GeometryNodeInputPosition')
        geo = gi.outputs[0]
        for i, grid in enumerate(('density', 'temperature')):
            g = N.new('GeometryNodeGetNamedGrid')
            g.data_type = 'FLOAT'
            g.inputs['Name'].default_value = grid
            L.new(oi.outputs['Geometry'], g.inputs['Volume'])
            s = N.new('GeometryNodeSampleGrid')
            s.data_type = 'FLOAT'
            L.new(g.outputs['Grid'], s.inputs['Grid'])
            L.new(pos.outputs[0], s.inputs['Position'])
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type, st.domain = 'FLOAT', 'POINT'
            st.inputs['Name'].default_value = 'fire_' + grid
            L.new(geo, st.inputs['Geometry'])
            L.new(s.outputs[0], st.inputs['Value'])
            geo = st.outputs['Geometry']
            for j, n in enumerate((g, s, st)):
                n.location = (200 + 220 * j, -260 * i)
        oi.location, pos.location, gi.location = (-40, 120), (-40, -300), (-40, 300)
        go.location = (900, 0)
        L.new(geo, go.inputs[0])
        return tree


def create_volume_fire(mesh, scene=None, look='engine', **options):
    """Build the fire around `mesh` (the object that burns). Returns a VolumeFire; call .bake() before rendering.

    Options are fluid_grid.js's, snake_case (see DEFAULTS); sizes and positions are Blender axes.
    look='engine' (default) lays ENGINE_LOOK over the engine's numbers so the fire reads under AgX the way the
    engine's read under ACES; look=None keeps the engine's numbers as they are. Explicit options win."""
    import bpy
    if mesh is None:
        raise ValueError('[fx.fire] mesh is required: the thing that burns')
    o = dict(DEFAULTS)
    unknown = set(options) - set(o)
    snake = {k: ''.join('_' + c.lower() if c.isupper() else c for c in k) for k in unknown}
    engine_only = sorted(k for k in unknown if snake[k] in ENGINE_ONLY)
    if engine_only:
        raise TypeError('[fx.fire] ' + '; '.join(f'{k}: {ENGINE_ONLY[snake[k]]}' for k in engine_only))
    if unknown:
        raise TypeError('[fx.fire] unknown options: ' + ', '.join(sorted(unknown)))
    if look == 'engine':
        o.update(ENGINE_LOOK)
    elif look is not None:
        raise ValueError(f"[fx.fire] look must be 'engine' or None, not {look!r}")
    o.update(options)
    sc = scene or bpy.context.scene
    return VolumeFire(sc, mesh, o)


def configure_eevee_for_fire(scene, fire=None, camera=None, tile='1', samples=128, start=None, end=None,
                             frames=None):
    """EEVEE settings the fire needs: fine froxels, enough volume samples, volumetric shadows, and the
    froxel depth range tight around the fire.

    EEVEE resolves volumes on a camera-aligned grid of froxels: `tile` pixels across ('1' or '2'), `samples`
    slices in depth between start and end. With a baked fire, start/end come from the bake's bounds
    (fx_bounds_*) seen from the camera at every frame of `frames` (default: the scene range), so the slices land
    on the fire instead of the empty domain around it.

    The range is one scene setting, and Blender 5.2 cannot key or drive it, so it belongs to one camera at a
    time. A shot that cuts between cameras with timeline markers (marker.camera, Blender's own camera
    switching) gets the union of the cuts' ranges, which never clips the fire from any of them but spreads the
    slices thinner; `camera` fits one camera. A render script that switches scene.camera any other way must
    call this again for the new camera before rendering: a range fitted to another camera can leave the fire
    outside the slices, and then no volume renders at all. Returns [(camera name, start, end)] per cut."""
    ee = scene.eevee
    ee.volumetric_tile_size = str(tile)
    ee.volumetric_samples = int(samples)
    ee.volumetric_sample_distribution = 0.8
    ee.use_volumetric_shadows = True
    ee.volumetric_shadow_samples = 32
    ee.volumetric_ray_depth = 16
    if start is not None:
        ee.use_volume_custom_range = True
        ee.volumetric_start, ee.volumetric_end = float(start), float(end)
        return [(None, float(start), float(end))]
    if fire is None or 'fx_bounds_min' not in fire.volume_object:
        return []
    lo = np.array(fire.volume_object['fx_bounds_min'])
    hi = np.array(fire.volume_object['fx_bounds_max'])
    corners = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])
    fr = list(frames or range(scene.frame_start, scene.frame_end + 1))
    cuts = sorted((m.frame, m.camera) for m in scene.timeline_markers if m.camera is not None) if camera is None else []
    if cuts:
        segs = []
        for i, (f0, cam_i) in enumerate(cuts):
            f1 = cuts[i + 1][0] if i + 1 < len(cuts) else max(fr) + 1
            sf = [f for f in fr if f0 <= f < f1]
            if sf:
                segs.append((min(sf), cam_i, sf))
        before = [f for f in fr if f < cuts[0][0]]
        if before and scene.camera is not None:
            segs.insert(0, (min(before), scene.camera, before))
    else:
        cam = camera or scene.camera
        segs = [(min(fr), cam, fr)] if cam is not None else []
    keep = scene.frame_current
    ranges = []
    for f0, cam, sf in segs:
        dmin, dmax = 1e9, 0.0
        for f in sf:
            scene.frame_set(f)
            M = np.array(cam.matrix_world)
            d = (corners - M[:3, 3]) @ -M[:3, 2]
            dmin, dmax = min(dmin, d.min()), max(dmax, d.max())
        ranges.append((f0, cam, float(max(0.05, dmin - 0.5)), float(max(dmax + 0.5, 0.1))))
    scene.frame_set(keep)
    if not ranges:
        return []
    ee.use_volume_custom_range = True
    ee.volumetric_start = min(r[2] for r in ranges)
    ee.volumetric_end = max(r[3] for r in ranges)
    if len(ranges) > 1:
        print(f'[fx.fire] froxel range {ee.volumetric_start:.2f} .. {ee.volumetric_end:.2f} m covers '
              + ', '.join(f'{c.name} {s:.1f}..{e:.1f}' for f0, c, s, e in ranges))
    return [(cam.name if cam else None, s, e) for f0, cam, s, e in ranges]


def create_fire_compose(scene, fire=None, saturation_amount=None, bloom_threshold=0.5, bloom_strength=0.1,
                        bloom_size=6, match=None):
    """The engine's fire compose (createFireCompose) in Blender's compositor: saturation 1.1 on the fire's
    light, then bloom.

    EEVEE renders the volume in the frame itself, with real occlusion, so the engine's separate half-resolution
    volume pass, its gaussian denoise and the max/add composite have no counterpart. With display_match
    'aces_compose' (or match='aces_compose') the volume's light is still taken apart: EEVEE's Volume Direct
    pass (the volume's emission and in-scatter, as composited into the frame) is saturated like the engine's
    volume pass and then matched per pixel to what three's ACES showed for it (fire_display_match_group), and
    the rest of the frame stays the film's own. Otherwise the saturation runs on the whole frame."""
    import bpy
    sat = saturation_amount
    if sat is None:
        sat = fire.params['saturation_amount'] if fire is not None else 1.1
    mode = match if match is not None else (fire.params['display_match'] if fire is not None else None)
    tree = bpy.data.node_groups.new('fire_compose', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    nodes, links = tree.nodes, tree.links
    rl = nodes.new('CompositorNodeRLayers')
    rl.location = (-600, 0)
    if mode == 'aces_compose':
        for vl in scene.view_layers:
            vl.eevee.use_pass_volume_direct = True
        grp = nodes.new('CompositorNodeGroup')
        grp.node_tree = fire_display_match_group(scene, sat)
        grp.location = (-300, 0)
        links.new(rl.outputs['Image'], grp.inputs['Image'])
        links.new(rl.outputs['Volume Direct'], grp.inputs['Volume'])
        img = grp.outputs['Image']
    else:
        hsv = nodes.new('CompositorNodeHueSat')
        hsv.location = (-300, 0)
        _set_input(hsv, ('Saturation',), sat)
        links.new(rl.outputs['Image'], hsv.inputs['Image'])
        img = hsv.outputs['Image']
    glare = nodes.new('CompositorNodeGlare')
    glare.location = (0, 0)
    _configure_bloom(glare, bloom_threshold, bloom_strength, bloom_size)
    out = nodes.new('NodeGroupOutput')
    out.location = (300, 0)
    if not tree.interface.items_tree:
        tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    links.new(img, glare.inputs['Image'])
    links.new(glare.outputs['Image'], out.inputs[0])
    return tree


# the colour space that inverts each view on an sRGB display (Blender 5.2's config: the "View Inverse" family)
_VIEW_INVERSE = {'AgX': 'AgX Base sRGB', 'Standard': 'sRGB', 'Filmic': 'Filmic sRGB', 'ACES 1.3': 'ACES 1.3 sRGB',
                 'ACES 2.0': 'ACES 2.0 sRGB', 'Khronos PBR Neutral': 'Khronos PBR Neutral sRGB'}


def fire_display_match_group(scene, saturation_amount=1.1, name='eido.fire_display_match'):
    """A compositor node group (Image, Volume) -> Image: the frame with its volume light shown the engine's way.

    Volume is EEVEE's Volume Direct pass. Image - Volume is the rest of the frame (surfaces behind the smoke
    already dimmed by it), left as it is. The volume light gets the engine's compose saturation, then three's
    ACESFilmic at the scene's exposure (exposure / 0.6 = 2^ev) and the sRGB transfer, which is what the
    engine's canvas showed, and then the scene view's own inverse (OCIO, e.g. 'AgX Base sRGB' -> linear), so
    the film's view turns it back into exactly that. Colours the view cannot reach clamp at 0. Every volume in
    the view layer passes through it: a shot with other volumes (fog, clouds) wants the fire on a view layer
    of its own, or display_match='aces' (the per-sample table in the material) instead."""
    import bpy
    from ._nodes import Builder
    from ._look import _IN, _OUT
    vs, ds = scene.view_settings, scene.display_settings
    inv_space = _VIEW_INVERSE.get(vs.view_transform) if ds.display_device == 'sRGB' else None
    if inv_space is None:
        raise ValueError(f'[fx.fire] no inverse colour space for view {vs.view_transform!r} on {ds.display_device!r}')
    if vs.look not in ('None', ''):
        print(f'[fx.fire] warning: the compose match ignores the scene look {vs.look!r}')
    if name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[name])
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    for nm in ('Image', 'Volume'):
        g.interface.new_socket(nm, in_out='INPUT', socket_type='NodeSocketColor')
    g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi, go = g.nodes.new('NodeGroupInput'), g.nodes.new('NodeGroupOutput')
    gi.location, go.location = (-2200, 0), (1600, 0)
    b = Builder(g, x0=-2000, y0=600)

    def split(sock):
        n = b.node('CompositorNodeSeparateColor')
        g.links.new(sock, n.inputs['Image'])
        return [b.s(n.outputs[c]) for c in ('Red', 'Green', 'Blue')]

    def join(rgb):
        n = b.node('CompositorNodeCombineColor')
        for c, v in zip(('Red', 'Green', 'Blue'), rgb):
            b.link(v, n.inputs[c])
        n.inputs['Alpha'].default_value = 1.0
        return n.outputs['Image']

    C, V = split(gi.outputs['Image']), split(gi.outputs['Volume'])
    rest = [c - v for c, v in zip(C, V)]
    lum = V[0] * 0.2126 + V[1] * 0.7152 + V[2] * 0.0722               # three's saturation(): mix(lum, rgb, k)
    k = 2.0 ** float(vs.exposure)
    v = [(lum + (x - lum) * saturation_amount) * k for x in V]
    a = [v[0] * _IN[i, 0] + v[1] * _IN[i, 1] + v[2] * _IN[i, 2] for i in range(3)]
    f = [(x * (x + 0.0245786) - 0.000090537) / (x * (x * 0.983729 + 0.4329510) + 0.238081) for x in a]
    o = [b.clamp(f[0] * _OUT[i, 0] + f[1] * _OUT[i, 1] + f[2] * _OUT[i, 2]) for i in range(3)]
    enc = []
    for x in o:                                                            # the sRGB transfer, piecewise
        hi = b.pow(b.max(x, 1e-8), 1 / 2.4) * 1.055 - 0.055
        lo = x * 12.92
        enc.append(lo + (hi - lo) * b.math('GREATER_THAN', x, 0.0031308))
    cc = b.node('CompositorNodeConvertColorSpace')
    cc.from_color_space = inv_space
    cc.to_color_space = 'Linear Rec.709'
    g.links.new(join(enc), cc.inputs['Image'])
    lin = split(cc.outputs['Image'])
    out = [r + b.max(x, 0.0) * (1.0 / k) for r, x in zip(rest, lin)]
    g.links.new(join(out), go.inputs['Image'])
    return g


def _set_input(node, names, value):
    for nm in names:
        if nm in node.inputs:
            node.inputs[nm].default_value = value
            return True
    for nm in names:
        attr = nm.lower()
        if hasattr(node, attr):
            setattr(node, attr, value)
            return True
    return False


def _configure_bloom(glare, threshold, strength, size):
    if hasattr(glare, 'glare_type'):
        glare.glare_type = 'BLOOM'
    elif 'Type' in glare.inputs:
        glare.inputs['Type'].default_value = 'Bloom'
    _set_input(glare, ('Threshold',), threshold)
    _set_input(glare, ('Strength', 'Mix'), strength)
    if 'Size' in glare.inputs:
        try:
            glare.inputs['Size'].default_value = size / 9.0 if glare.inputs['Size'].type == 'VALUE' else size
        except Exception:
            pass
    elif hasattr(glare, 'size'):
        glare.size = size
