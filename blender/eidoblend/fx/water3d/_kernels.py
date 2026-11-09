"""fluid_water.js's compute kernels as GLSL for Blender's `gpu` module, line for line.

Every kernel reads rgba16float 3D textures through linear, clamp-to-edge samplers (the engine's
`texture3D(tex, p, 0)`), writes one image (the engine's single textureStore per pass) and runs one thread per
cell. The defines a kernel is compiled with:

    NX NY NZ      the grid this kernel runs over (a multigrid level's own size for the level kernels)
    WX WY WZ      the domain's interior size in metres, three.js axes (y up)
    DX            the fine grid's cell size (the engine's DX = world.x / NX, used isotropically)
    WALLM         the analytic wall margin in uvw (1.5/NX at the fine level, max(1.5/NX, 1/nx) on a coarse one)
    WALLS SOLIDTEX NSPH   which solid layers exist (the engine's three OR'd layers)
    NEMI          emitter slots
    FNX FNY FNZ   the fine grid (the CFL trace cap and the B-spline need it)

The solid predicate, the face test and the ghost-fluid stencil are written once here and shared, as the engine
shares isSolid / faceBlocked / mgStencil: changing them changes every kernel at once.
"""

HEAD = r"""
const vec3 GRID = vec3(float(NX), float(NY), float(NZ));
const vec3 WSIZE = vec3(WX, WY, WZ);
const vec3 DXV = vec3(1.0 / float(NX), 0.0, 0.0);
const vec3 DYV = vec3(0.0, 1.0 / float(NY), 0.0);
const vec3 DZV = vec3(0.0, 0.0, 1.0 / float(NZ));
#define INSIDE(c) all(lessThan(c, ivec3(NX, NY, NZ)))
vec3 uvw_of(ivec3 c) { return (vec3(c) + 0.5) / GRID; }
"""

# the engine's isSolid: analytic walls OR the baked field (> 0.5) OR the dynamic spheres (world-space test,
# domain-local metres). No layer at all -> never solid (p.y < -1).
SOLID = r"""
bool isSolidWalls(vec3 p) {
  float m = WALLM;
  return p.x < m || p.x > 1.0 - m || p.z < m || p.z > 1.0 - m || p.y < m;   // top stays OPEN
}
bool isSolid(vec3 p) {
  bool s = false;
#if WALLS
  s = s || isSolidWalls(p);
#endif
#if SOLIDTEX
  s = s || (textureLod(solidTex, p, 0.0).r > 0.5);
#endif
#if NSPH > 0
  vec3 pw = (p - vec3(0.5)) * WSIZE;
  for (int i = 0; i < NSPH; i++) {
    vec4 sp = texelFetch(sphTex, ivec2(i, 0), 0);
    if (sp.w > 0.0 && length(pw - sp.xyz) < sp.w) s = true;
  }
#endif
#if !WALLS && !SOLIDTEX && NSPH == 0
  s = p.y < -1.0;
#endif
  return s;
}
bool faceBlocked(vec3 p, vec3 cellOff) { return isSolid(p) || isSolid(p + cellOff); }
// the static layers only (analytic walls and the baked field), for the edition's phi extension into solids
bool isSolidStatic(vec3 p) {
  bool s = false;
#if WALLS
  s = s || isSolidWalls(p);
#endif
#if SOLIDTEX
  s = s || (textureLod(solidTex, p, 0.0).r > 0.5);
#endif
  return s;
}
"""

# the shared semi-Lagrangian trace (needs sampler velA): cell-centred velocity = the mean of the cell's two
# opposing faces (the MAC layout), a CFL cap of MAXTRACE cells, clamped into [0.001, 0.999]
TRACE = r"""
vec3 cellVel(vec3 p) {
  return vec3((textureLod(velA, p, 0.0).x + textureLod(velA, p - DXV, 0.0).x) * 0.5,
              (textureLod(velA, p, 0.0).y + textureLod(velA, p - DYV, 0.0).y) * 0.5,
              (textureLod(velA, p, 0.0).z + textureLod(velA, p - DZV, 0.0).z) * 0.5);
}
vec3 traceRaw(vec3 p, float sgn) {
  vec3 trace = cellVel(p) / WSIZE * uDt * sgn;
  vec3 maxTrace = MAXTRACE * vec3(1.0 / float(NX), 1.0 / float(NY), 1.0 / float(NZ));
  return p - clamp(trace, -maxTrace, maxTrace);
}
vec3 traceBack(vec3 p, float sgn) { return clamp(traceRaw(p, sgn), 0.001, 0.999); }
// a trace that left the domain reads AIR, never the clamped edge slice (the "looped rain" fix)
bool tracedOut(vec3 p, float sgn) {
  vec3 r = traceRaw(p, sgn);
  return r.x < 0.0 || r.x > 1.0 || r.y < 0.0 || r.y > 1.0 || r.z < 0.0 || r.z > 1.0;
}
"""

INIT_PHI = r"""
float columnPhi(vec3 p) {
  float m = WALLM;
  // the column OVERLAPS the solid walls: phi = 0 exactly on the floor's boundary read as neither fluid nor air
  vec3 lo = vec3(m - 0.05, m - 0.05, 0.5 - COLD * 0.5);
  vec3 hi = vec3(m + COLW, m + COLH, 0.5 + COLD * 0.5);
  vec3 ctr = (lo + hi) * 0.5;
  vec3 hlf = (hi - lo) * 0.5;
  vec3 q = (abs(p - ctr) - hlf) * WSIZE;
  float outside = length(max(q, vec3(0.0)));
  float inside = min(max(max(q.x, q.y), q.z), 0.0);
  return outside + inside;
}
float levelPhi(vec3 p) { return p.y * WSIZE.y - INITLEVEL; }
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
#if USELEVEL
  imageStore(dst, c, vec4(levelPhi(uvw_of(c)), 0.0, 0.0, 1.0));
#else
  imageStore(dst, c, vec4(columnPhi(uvw_of(c)), 0.0, 0.0, 1.0));
#endif
}
"""

# 1) velocity extrapolation into air: air cells take the phi-weighted mean of deeper neighbours
EXTRAP = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiC = textureLod(phiTex, p, 0.0).x;
  vec3 v = textureLod(src, p, 0.0).xyz;
  if (phiC > 0.0) {
    vec3 sum = vec3(0.0);
    float wsum = 0.0;
    vec3 offs[6] = vec3[6](DXV, -DXV, DYV, -DYV, DZV, -DZV);
    for (int k = 0; k < 6; k++) {
      vec3 pn = p + offs[k];
      float phiN = textureLod(phiTex, pn, 0.0).x;
      float w = max(phiC - phiN, 0.0);
      sum += textureLod(src, pn, 0.0).xyz * w;
      wsum += w;
    }
    if (wsum > 1e-5) v = sum / wsum;
  }
  imageStore(dst, c, vec4(v, 1.0));
}
"""

# 1b) the Blender edition's breadth-first extrapolation (extrapolation='bfs'): an air cell takes the mean velocity of
# its neighbours nearest the water in steps (.w carries that step count, 0 in the water), so a cell between two
# bodies takes the nearer one's velocity whatever phi holds there. EXTRAP_BFS_INIT seeds .w from phi.
EXTRAP_BFS_INIT = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiC = textureLod(phiTex, p, 0.0).x;
  imageStore(dst, c, vec4(textureLod(src, p, 0.0).xyz, phiC <= 0.0 ? 0.0 : 1e4));
}
"""

EXTRAP_BFS = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec4 here = textureLod(src, p, 0.0);
  if (here.w > 0.5) {
    vec3 offs[6] = vec3[6](DXV, -DXV, DYV, -DYV, DZV, -DZV);
    float m = 1e4;
    for (int k = 0; k < 6; k++) m = min(m, textureLod(src, p + offs[k], 0.0).w);
    if (m + 1.0 < here.w) {
      vec3 sum = vec3(0.0);
      float n = 0.0;
      for (int k = 0; k < 6; k++) {
        vec4 q = textureLod(src, p + offs[k], 0.0);
        if (q.w < m + 0.5) { sum += q.xyz; n += 1.0; }
      }
      here = vec4(sum / max(n, 1.0), m + 1.0);
    }
  }
  imageStore(dst, c, here);
}
"""

# 2a) velocity advection + gravity (fluid + a 2-cell air band only), zero beyond 4 cells, damping, emitters
ADVECT_VEL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec3 bc = traceBack(p, 1.0);
  vec3 v = textureLod(velA, bc, 0.0).xyz;
  float phiC = textureLod(phiTex, p, 0.0).x;
  if (phiC < DX * 2.0) v -= vec3(0.0, uGravity * uDt, 0.0);
  if (phiC > DX * 4.0) v = vec3(0.0);
  v *= max(1.0 - uVelDamping * uDt, 0.0);
#if NEMI > 0
  vec3 pw = (p - vec3(0.5)) * WSIZE;
  for (int i = 0; i < NEMI; i++) {
    vec4 e = texelFetch(emitTex, ivec2(i, 0), 0);
    if (e.w > 0.0 && length(pw - e.xyz) < e.w) v = texelFetch(emitTex, ivec2(i, 1), 0).xyz;
  }
#endif
  if (isSolid(p)) v = vec3(0.0);
  imageStore(dst, c, vec4(v, 1.0));
}
"""

# 2b) phi step 1: forward SL  phiHat = SL(phi, +dt)
PHI_FWD = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiF = tracedOut(p, 1.0) ? AIRV : textureLod(src, traceBack(p, 1.0), 0.0).x;
  imageStore(dst, c, vec4(phiF, 0.0, 0.0, 1.0));
}
"""

# 2c) phi step 2: MacCormack correction, extrema limiter over the departure point's 6 neighbours, the paper's
# section 3.4 clamps, emitters unioned into the level set. phi is NEVER forced to air inside solids (the mass sink).
PHI_CORR = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec3 bc = traceBack(p, 1.0);
  float phiHatC = textureLod(phiHat, p, 0.0).x;
  float phiBack = textureLod(phiHat, traceBack(p, -1.0), 0.0).x;
  float phiOld = textureLod(src, p, 0.0).x;
  float corrected = phiHatC + (phiOld - phiBack) * 0.5;
  float sl = tracedOut(p, 1.0) ? AIRV : textureLod(src, bc, 0.0).x;
  float n0 = textureLod(src, bc + DXV, 0.0).x, n1 = textureLod(src, bc - DXV, 0.0).x;
  float n2 = textureLod(src, bc + DYV, 0.0).x, n3 = textureLod(src, bc - DYV, 0.0).x;
  float n4 = textureLod(src, bc + DZV, 0.0).x, n5 = textureLod(src, bc - DZV, 0.0).x;
  float lo = min(min(min(n0, n1), min(n2, n3)), min(min(n4, n5), sl));
  float hi = max(max(max(n0, n1), max(n2, n3)), max(max(n4, n5), sl));
  float phi = (corrected < lo || corrected > hi) ? sl : corrected;
#if !NOCLAMP
  if (abs(phi) < DX * 1.5) phi = clamp(phi, -DX, DX);
  phi = clamp(phi, -5.0 * DX, 5.0 * DX);
#endif
#if NEMI > 0
  vec3 pw = (p - vec3(0.5)) * WSIZE;
  for (int i = 0; i < NEMI; i++) {
    vec4 e = texelFetch(emitTex, ivec2(i, 0), 0);
    float d = length(pw - e.xyz) - e.w;
    phi = e.w > 0.0 ? min(phi, d) : phi;
  }
#endif
  imageStore(dst, c, vec4(phi, 0.0, 0.0, 1.0));
}
"""

# 2d) the Blender edition's level-set extension INTO solids (two passes after PHI_CORR). The engine never writes phi
# in solid cells, so they keep whatever they held, usually air; a back-trace that dips into a wall (the
# extrapolation pass writes velocity into solid texels, which hold the -x/-y/-z faces of the fluid beside them)
# then reads air and erodes the water touching the wall. A basin with a few centimetres of water in it is all
# wall contact and could not fill. Here a solid cell takes the mean phi of its non-solid neighbours (a zero-
# gradient contact: the waterline meets the wall square), so a trace into a wall reads the water or air that is
# actually beside it. .y marks a defined value; pass 2 reaches the second solid layer from the first.
# Static solids only (walls and the baked field): a moving sphere's cells keep the engine's phi. Extended into the
# spheretest's ball, the pool lost 5.5 % more water than the engine's by 10 s (volume control off), where without
# it the two traces agree within 0.6 % (test_water3d_spheretest_parity.py).
PHI_SOLID_EXTEND = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec4 here = textureLod(src, p, 0.0);
  if (!isSolidStatic(p)) { imageStore(dst, c, vec4(here.x, 1.0, 0.0, 1.0)); return; }
#if PASS1
  float defined = 0.0;     // pass 1: the stored phi of solid cells is stale, of non-solid cells exact
#else
  float defined = here.y;
#endif
  if (defined > 0.5) { imageStore(dst, c, vec4(here.x, 1.0, 0.0, 1.0)); return; }
  vec3 offs[6] = vec3[6](DXV, -DXV, DYV, -DYV, DZV, -DZV);
  float sum = 0.0, n = 0.0;
  for (int k = 0; k < 6; k++) {
    vec3 pn = p + offs[k];
    if (any(lessThan(pn, vec3(0.0))) || any(greaterThan(pn, vec3(1.0)))) continue;
    vec4 q = textureLod(src, pn, 0.0);
#if PASS1
    bool ok = !isSolidStatic(pn);
#else
    bool ok = q.y > 0.5;
#endif
    if (ok) { sum += q.x; n += 1.0; }
  }
  if (n > 0.0) imageStore(dst, c, vec4(sum / n, 1.0, 0.0, 1.0));
  else imageStore(dst, c, vec4(here.x, 0.0, 0.0, 1.0));
}
"""

# 3b) the Blender edition's redistancing (reinit_scheme='godunov'): the same equation, phi_tau = sign(phi)(1 - |grad
# phi|), with the same near-surface freeze and 5 DX clamp, but |grad phi| from Godunov's upwind one-sided differences
# (Sussman, Smereka & Osher 1994; Osher & Fedkiw ch. 7): the stable scheme the engine's notes name as the condition for
# turning redistancing on. Pseudo-time step 0.4 DX (under the 3D CFL bound DX / sqrt 3). (Re-estimating the frozen
# cells from their zero crossings every sweep was tried and dropped: it drifted, a 0.12 m ball melted at 64^3 and
# the dam break's sensor read 22 % high.)
REINIT_GODUNOV = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phi = textureLod(src, p, 0.0).x;
  float xp = textureLod(src, p + DXV, 0.0).x, xm = textureLod(src, p - DXV, 0.0).x;
  float yp = textureLod(src, p + DYV, 0.0).x, ym = textureLod(src, p - DYV, 0.0).x;
  float zp = textureLod(src, p + DZV, 0.0).x, zm = textureLod(src, p - DZV, 0.0).x;
  float minN = min(min(min(xp, xm), min(yp, ym)), min(zp, zm));
  float maxN = max(max(max(xp, xm), max(yp, ym)), max(zp, zm));
  bool nearSurface = phi * minN < 0.0 || phi * maxN < 0.0 || phi == 0.0;
  if (!nearSurface) {
    vec3 a = vec3(phi - xm, phi - ym, phi - zm);       // backward differences (x DX)
    vec3 b = vec3(xp - phi, yp - phi, zp - phi);       // forward differences (x DX)
    vec3 ap = max(a, vec3(0.0)), am = min(a, vec3(0.0)), bp = max(b, vec3(0.0)), bm = min(b, vec3(0.0));
    vec3 g2 = phi > 0.0 ? max(ap * ap, bm * bm) : max(am * am, bp * bp);
    float g = sqrt(g2.x + g2.y + g2.z) / DX;
    phi -= sign(phi) * (g - 1.0) * (0.4 * DX);
  }
  phi = clamp(phi, -5.0 * DX, 5.0 * DX);
  imageStore(dst, c, vec4(phi, 0.0, 0.0, 1.0));
}
"""

# 3) redistancing (off by default in the engine: central differences, near-surface freeze)
REINIT = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phi = textureLod(src, p, 0.0).x;
  float xp = textureLod(src, p + DXV, 0.0).x, xm = textureLod(src, p - DXV, 0.0).x;
  float yp = textureLod(src, p + DYV, 0.0).x, ym = textureLod(src, p - DYV, 0.0).x;
  float zp = textureLod(src, p + DZV, 0.0).x, zm = textureLod(src, p - DZV, 0.0).x;
  float minN = min(min(min(xp, xm), min(yp, ym)), min(zp, zm));
  float maxN = max(max(max(xp, xm), max(yp, ym)), max(zp, zm));
  bool nearSurface = phi * minN < 0.0 || phi * maxN < 0.0;
  if (!nearSurface) {
    float g = length(vec3((xp - xm) / (2.0 * DX), (yp - ym) / (2.0 * DX), (zp - zm) / (2.0 * DX)));
    phi += sign(phi) * (1.0 - g) * (0.5 * DX);
  }
  phi = clamp(phi, -5.0 * DX, 5.0 * DX);
  imageStore(dst, c, vec4(phi, 0.0, 0.0, 1.0));
}
"""

# 4) divergence of the staggered field: raw face differences, solid faces carry zero flux; the Kim 2007 source
DIV = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float uP = faceBlocked(p, DXV) ? 0.0 : textureLod(velB, p, 0.0).x;
  float uM = faceBlocked(p - DXV, DXV) ? 0.0 : textureLod(velB, p - DXV, 0.0).x;
  float vP = faceBlocked(p, DYV) ? 0.0 : textureLod(velB, p, 0.0).y;
  float vM = faceBlocked(p - DYV, DYV) ? 0.0 : textureLod(velB, p - DYV, 0.0).y;
  float wP = faceBlocked(p, DZV) ? 0.0 : textureLod(velB, p, 0.0).z;
  float wM = faceBlocked(p - DZV, DZV) ? 0.0 : textureLod(velB, p - DZV, 0.0).z;
  float div = ((uP - uM) + (vP - vM)) + (wP - wM);
#if VC
  float s = textureLod(volCtrl, vec3(0.5), 0.0).y;
  float phiC = textureLod(phiTex, p, 0.0).x;
  if (phiC <= 0.0 && !isSolid(p)) div -= s * DX;
#endif
  imageStore(dst, c, vec4(div, 0.0, 0.0, 1.0));
}
"""

# the Eq. 16 stencil at any level: ghost fluid (1/theta on the DIAGONAL) toward air, a dropped neighbour for a
# solid. Samplers: phiL (this level's phi), srcP (the pressure being smoothed), rhsTex. Split in three blocks
# because GLSL compiles every function, used or not: the prolongation has no rhsTex.
MG_FLUID = r"""
bool mgIsFluid(vec3 p, float phiC) { return phiC <= 0.0 && !isSolid(p); }
"""

STENCIL = r"""
void mgStencil(vec3 p, out float phiC, out float sum, out float diag) {
  phiC = textureLod(phiL, p, 0.0).x;
  sum = 0.0;
  diag = 0.0;
  vec3 offs[6] = vec3[6](DXV, -DXV, DYV, -DYV, DZV, -DZV);
  for (int k = 0; k < 6; k++) {
    vec3 pn = p + offs[k];
    float phiN = textureLod(phiL, pn, 0.0).x;
    bool solidN = isSolid(pn);
    bool isAir = phiN > 0.0;
    float theta = clamp(phiC / min(phiC - phiN, -1e-5), 0.02, 1.0);
    float pv = textureLod(srcP, pn, 0.0).x;
    sum += solidN ? 0.0 : (isAir ? 0.0 : pv);
    diag += solidN ? 0.0 : (isAir ? 1.0 / theta : 1.0);
  }
}
float rhsAt(vec3 p) {
#if RHSNEG
  return -textureLod(rhsTex, p, 0.0).x;
#else
  return textureLod(rhsTex, p, 0.0).x;
#endif
}
"""

# 5) plain Jacobi (the mgLevels < 2 fallback): out = (sum - div) / diag
JACOBI = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiC, sum, diag;
  mgStencil(p, phiC, sum, diag);
  float outv = 0.0;
  if (phiC <= 0.0 && !isSolid(p)) {
    float div = textureLod(rhsTex, p, 0.0).x;
    outv = (sum - div) / max(diag, 1e-4);
  }
  imageStore(dst, c, vec4(outv, 0.0, 0.0, 1.0));
}
"""

MG_SMOOTH = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiC, sum, diag;
  mgStencil(p, phiC, sum, diag);
  float outv = 0.0;
  if (mgIsFluid(p, phiC)) {
    float jac = (sum + rhsAt(p)) / max(diag, 1e-4);
    outv = mix(textureLod(srcP, p, 0.0).x, jac, uOmega);
  }
  imageStore(dst, c, vec4(outv, 0.0, 0.0, 1.0));
}
"""

MG_RESIDUAL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phiC, sum, diag;
  mgStencil(p, phiC, sum, diag);
  float outv = 0.0;
  if (mgIsFluid(p, phiC)) outv = rhsAt(p) + sum - diag * textureLod(srcP, p, 0.0).x;
  imageStore(dst, c, vec4(outv, 0.0, 0.0, 1.0));
}
"""

# one linear tap at a coarse centre = the mean of its 8 fine cells (full weighting); x4 for the unit stencil
MG_RESTRICT = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  imageStore(dst, c, vec4(textureLod(src, uvw_of(c), 0.0).x * 4.0, 0.0, 0.0, 1.0));
}
"""

COPY_TAP = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  imageStore(dst, c, vec4(textureLod(src, uvw_of(c), 0.0).x, 0.0, 0.0, 1.0));
}
"""

# p_fine += P(e_coarse) (one trilinear tap), into the fine level's p2. Samplers phiL (fine phi), srcP (fine p),
# coarseP
MG_PROLONG = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float outv = 0.0;
  if (mgIsFluid(p, textureLod(phiL, p, 0.0).x))
    outv = textureLod(srcP, p, 0.0).x + textureLod(coarseP, p, 0.0).x;
  imageStore(dst, c, vec4(outv, 0.0, 0.0, 1.0));
}
"""

# 6) projection with the SAME ghost the solve assumed (fluid->air face gradient -p_C/theta), no-flux solid faces,
# the physical speed cap
PROJECT = r"""
float gradAt(vec3 p, vec3 off, float phiC, float qC) {
  vec3 pn = p + off;
  float phiN = textureLod(phiTex, pn, 0.0).x;
  float qN = textureLod(prs, pn, 0.0).x;
  bool cW = phiC <= 0.0, nW = phiN <= 0.0;
  float thC = clamp(phiC / min(phiC - phiN, -1e-5), 0.02, 1.0);
  float thN = clamp(phiN / min(phiN - phiC, -1e-5), 0.02, 1.0);
  if (isSolid(p) || isSolid(pn)) return 0.0;
  return (cW && nW) ? (qN - qC) : (cW ? -qC / thC : (nW ? qN / thN : 0.0));
}
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float qC = textureLod(prs, p, 0.0).x;
  float phiC = textureLod(phiTex, p, 0.0).x;
  vec3 v = textureLod(velB, p, 0.0).xyz;
  v.x = v.x - gradAt(p, DXV, phiC, qC);
  v.y = v.y - gradAt(p, DYV, phiC, qC);
  v.z = v.z - gradAt(p, DZV, phiC, qC);
  if (faceBlocked(p, DXV)) v.x = 0.0;
  if (faceBlocked(p, DYV)) v.y = 0.0;
  if (faceBlocked(p, DZV)) v.z = 0.0;
  float spd = length(v);
  if (spd > uMaxSpeed) v = v / spd * uMaxSpeed;
  imageStore(dst, c, vec4(v, 1.0));
}
"""

# viscosity: a neighbour blend (velSmooth), zero in solids
SMOOTH_VEL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec3 v0 = textureLod(src, p, 0.0).xyz;
  vec3 avg = (textureLod(src, p + DXV, 0.0).xyz + textureLod(src, p - DXV, 0.0).xyz
            + textureLod(src, p + DYV, 0.0).xyz + textureLod(src, p - DYV, 0.0).xyz
            + textureLod(src, p + DZV, 0.0).xyz + textureLod(src, p - DZV, 0.0).xyz) * (1.0 / 6.0);
  vec3 v = mix(v0, avg, uVelSmooth);
  if (isSolid(p)) v = vec3(0.0);
  imageStore(dst, c, vec4(v, 1.0));
}
"""

# the engine's BISECT-only path (__noPressure): velB -> velA with wall clamps, no projection
COPY_VEL = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  vec3 v = textureLod(src, p, 0.0).xyz;
  float m = WALLM;
  float TX = 1.0 / float(NX), TY = 1.0 / float(NY), TZ = 1.0 / float(NZ);
  if (p.x < m + TX) v.x = max(v.x, 0.0);
  if (p.x > 1.0 - m - TX) v.x = min(v.x, 0.0);
  if (p.z < m + TZ) v.z = max(v.z, 0.0);
  if (p.z > 1.0 - m - TZ) v.z = min(v.z, 0.0);
  if (p.y < m + TY) v.y = max(v.y, 0.0);
  if (isSolid(p)) v = vec3(0.0);
  imageStore(dst, c, vec4(v, 1.0));
}
"""

# the GPU volume sensor: a smoothed Heaviside per cell (0 in solids) ...
VOL_FRAC = r"""
void main() {
  ivec3 c = ivec3(gl_GlobalInvocationID);
  if (!INSIDE(c)) return;
  vec3 p = uvw_of(c);
  float phi = textureLod(phiTex, p, 0.0).x;
  float frac = clamp(0.5 - phi / (DX * 3.0), 0.0, 1.0);
  imageStore(dst, c, vec4(isSolid(p) ? 0.0 : frac, 0.0, 0.0, 1.0));
}
"""

# ... the tail of the mip chain summed into ONE texel (the global mean), the only value anything reads
VOL_FINAL = r"""
void main() {
  float acc = 0.0;
  for (int k = 0; k < FZ; k++)
    for (int j = 0; j < FY; j++)
      for (int i = 0; i < FX; i++)
        acc += textureLod(src, vec3((float(i) + 0.5) / float(FX), (float(j) + 0.5) / float(FY),
                                    (float(k) + 0.5) / float(FZ)), 0.0).x;
  imageStore(dst, ivec3(0), vec4(acc / float(FX * FY * FZ), 0.0, 0.0, 1.0));
}
"""

# the PI controller, one texel: .x integral (anti-windup clamp), .y source s (1/s), .z the measured volume
VOL_CTRL = r"""
void main() {
  float mean = textureLod(volFinal, vec3(0.5), 0.0).x;
  float V = mean * CELLSVOL;
  float e = (uTarget - V) / uTarget;
  vec4 prev = textureLod(src, vec3(0.5), 0.0);
  float I = clamp(prev.x + e * (uDt * VCEVERY), -0.5, 0.5);
  float s = clamp(e * uKp + I * uKi, -uMaxRate, uMaxRate);
  imageStore(dst, ivec3(0), vec4(I, s, V, 1.0));
}
"""
