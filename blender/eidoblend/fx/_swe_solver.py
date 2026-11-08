"""The shallow-water solver of eidoverse/fluid_swe.js in numpy, kernel for kernel (no bpy here).

Everything runs in three.js's frame (x, y-up, z) on (NZ, NX) arrays, the engine's depth-1 3D textures:
texel (i, k) is array [k, i]. Reads at a cell centre +- one texel are exact neighbour reads with clamp to edge;
semi-Lagrangian back-traces and particle lookups are bilinear with clamp to edge, as the GPU's linear
samplers. Stored fields are rounded to half float after every kernel (precision='half', the default), as the
engine's rgba16float textures are: the presets, rain rates and thresholds were all tuned on that storage
(rain increments under half an fp16 ulp vanish on deep cells there, and here). precision='single' keeps
float32 everywhere.

The ping-pong A/B texture pairs are plain arrays; the phase uniform is gone (the "current" arrays are the
phase). The spray exchange's fixed-point int32 atomics become np.add.at on int64 accumulators with the same
1e6 scale and round-half-even rounding.
"""

from __future__ import annotations

import math

import numpy as np

from ._noise import tsl_hash, tsl_hash_int, swe_fbm2, swe_ripple_field
from ._util import smoothstep

FXP = 1e6
NEMI = 4
NSPH = 12

LIQUID_PRESETS = {
    'water': {},
    'gel': dict(
        yieldSlope=0.22, waveScale=0.32, bedFriction=0.4, drag=0.12, maxSpeed=2.5,
        rippleAmp=0.005, rippleSpeed=0.35, flowT=2.4, surfaceOpacity=0.97, absorption=4.5,
        specPow=260, specGain=1.7, foamDecay=0.8, shoreFade=0.05, sprayStretch=0.3, spraySize=0.06,
        streamAeration=0.12, dropletVisibility=0.4, foamGain=0.22, promoTaMin=0.9, promoCrestMin=5.0),
    'goo': dict(
        yieldSlope=0.09, waveScale=0.45, bedFriction=0.25, drag=0.08, maxSpeed=3.0,
        rippleAmp=0.007, rippleSpeed=0.45, flowT=2.0, surfaceOpacity=0.95, absorption=3.6,
        specPow=180, specGain=1.4, foamDecay=1.0, shoreFade=0.04, sprayStretch=0.45, spraySize=0.065,
        streamAeration=0.2, dropletVisibility=0.5, foamGain=0.35),
    'lava': dict(
        yieldSlope=0.3, waveScale=0.18, bedFriction=0.55, drag=0.16, maxSpeed=1.6,
        rippleAmp=0.004, rippleSpeed=0.2, flowT=3.2, surfaceOpacity=1.0, absorption=6.0,
        specPow=40, specGain=0.35, emissiveStrength=1.4, emissiveFalloff=2.2,
        foamDecay=0.5, shoreFade=0.06, sprayStretch=0.5, promoRate=1.2,
        streamAeration=0.1, dropletVisibility=0.35, foamGain=0.3),
    'mud': dict(
        yieldSlope=0.14, waveScale=0.4, bedFriction=0.35, drag=0.1, maxSpeed=2.2,
        rippleAmp=0.006, rippleSpeed=0.3, flowT=2.6, surfaceOpacity=1.0, absorption=7.0,
        specPow=18, specGain=0.25, foamDecay=1.2, shoreFade=0.05, sprayStretch=0.5,
        streamAeration=0.15, dropletVisibility=0.4, foamGain=0.5),
}

# fluid_swe.js DEFAULTS (camelCase kept inside the solver: it is the engine's own vocabulary)
SOLVER_DEFAULTS = dict(
    preset='water', worldSize=(10.8, 10.8), gridSize=(256, 256), domainCenter=(0.0, 0.0, 0.0),
    bedYMin=-2.6, gravity=9.8, yieldSlope=0.0, waveScale=1.0, specPow=90, specGain=0.9, sprayStretch=1.0,
    momentumTransfer=0.25, streamAeration=1.0, dropletVisibility=1.0, foamGain=1.0, maxSpeed=6.0, maxDepth=4.0,
    substeps=3, maxSubSteps=12, fixedStep=1 / 60, drag=0.015, bedFriction=0.06, chop=0.0,
    rippleAmp=0.014, rippleScale=9.0, rippleSpeed=0.9, erosion=None, rainRate=0.0, rainPatchiness=0.6,
    sprayMax=0, spraySize=0.055, sprayJetSpread=0.06, pourVol=3.0e-4, promoVol=1.5e-4,
    promoTaMin=0.5, promoTaMax=2.5, promoCrestMin=3.0, promoCrestMax=14.0, promoEnMin=0.10, promoEnMax=1.5,
    promoKta=0.7, promoKwc=0.6, promoRate=2.5, promoVy=0.45, flowT=1.4, chopScale=55.0, chopSpeed=2.6,
    dryEps=0.004, initLevel=None, foamDecay=1.5, foamChurn=0.55, foamCrest=0.7, foamWake=1.5,
    deepColor='#06283d', shallowColor='#2f8f9d', skyColor='#9db8c9', absorption=2.2, surfaceOpacity=0.9,
    keyLightDir=(0.4, 0.8, 0.45), emissiveColor='#2ffbe0', emissiveStrength=0.0, emissiveFalloff=3.8,
    foamColor='#eefaf6', foamStrength=1.0, foamTexScale=5.5, shoreFade=0.03,
)

EROSION_DEFAULTS = dict(
    capacity=0.5, erode=0.55, deposit=0.35, bank=1.0, minDepth=0.004, talusSlope=0.55, talusRate=2.2,
    maxDelta=0.9, maxFill=0.15, edgeFeather=0.8, siltColor='#96754e', cutColor='#6b4f33',
    siltWaterColor='#8a6b42', wetDarken=0.4, terrain=True, terrainMaps=None, terrainRepeat=7,
    terrainTexPeriod=None,
)

SSEG, SRAD, STMAX = 28, 8, 1.35


def _q16(a):
    return a.astype(np.float16).astype(np.float32)


class SWESolver:
    """fluid_swe.js's createWaterSWE state and kernels. `bed` is an (NZ, NX) array of three-y bed heights at the
    cell centres (the engine's bedFn baked at build time)."""

    def __init__(self, o, bed, precision='half'):
        self.o = o
        self.NX, self.NZ = int(o['gridSize'][0]), int(o['gridSize'][1])
        self.WX, self.WZ = float(o['worldSize'][0]), float(o['worldSize'][1])
        self.DX, self.DZ = self.WX / self.NX, self.WZ / self.NZ
        self.center = np.array(o['domainCenter'], dtype=np.float64)
        self.q = _q16 if precision == 'half' else (lambda a: a.astype(np.float32))
        NX, NZ = self.NX, self.NZ
        self.bed = self.q(np.asarray(bed, dtype=np.float32).reshape(NZ, NX))
        self.ERO = bool(o['erosion'] is not None and o['erosion'] is not False)
        self.EK = dict(EROSION_DEFAULTS, **(o['erosion'] or {})) if self.ERO else None
        z = lambda: np.zeros((NZ, NX), dtype=np.float32)            # noqa: E731
        h0 = z() if o['initLevel'] is None else np.maximum(np.float32(o['initLevel']) - self.bed, 0)
        self.h = self.q(h0)
        self.h_prev = self.h.copy()
        self.u, self.w = z(), z()
        self.foam = z()
        self.flux = np.zeros((4, NZ, NX), dtype=np.float32)
        self.dbed, self.silt, self.age = z(), z(), z()
        self.ripple, self.foam_nz = z(), z()
        self.dep_vol = np.zeros(NZ * NX, dtype=np.int64)
        self.dep_mx = np.zeros(NZ * NX, dtype=np.int64)
        self.dep_mz = np.zeros(NZ * NX, dtype=np.int64)
        self.dep_foam = np.zeros(NZ * NX, dtype=np.int64)
        self.dt = o['fixedStep'] / o['substeps']
        self.time = 0.0
        self.sim_time = 0.0
        self.acc = 0.0
        self.consume = False
        self.rain = float(o['rainRate'])
        # uniforms: emitters (x, z, rate | vx, vz, foam), spheres (x, y, z | r, vx, vz | vy)
        self.emi_pos = np.zeros((NEMI, 3))
        self.emi_vel = np.zeros((NEMI, 3))
        self.sph_pos = np.tile(np.array([0.0, -99.0, 0.0]), (NSPH, 1))
        self.sph_aux = np.zeros((NSPH, 3))
        self.sph_aux2 = np.zeros((NSPH, 3))
        # cell-centre uvw and world xz
        ii = (np.arange(NX, dtype=np.float32) + 0.5) / NX
        kk = (np.arange(NZ, dtype=np.float32) + 0.5) / NZ
        self.pu, self.pw = np.meshgrid(ii, kk)                          # uvw.x, uvw.z per cell
        self.wx = (self.pu - 0.5) * self.WX + self.center[0]
        self.wz = (self.pw - 0.5) * self.WZ + self.center[2]
        dwall = np.minimum(np.minimum(self.pu, 1 - self.pu), np.minimum(self.pw, 1 - self.pw)) * min(self.WX, self.WZ)
        self.dwall = dwall.astype(np.float32)
        # spray
        self.spray = None
        if o['sprayMax'] > 0:
            M = int(o['sprayMax'])
            ids = np.arange(M)
            self.spray = dict(
                M=M, ids=ids, PROMO0=M - int(math.floor(M * 0.3)),
                P=np.stack([np.zeros(M), np.full(M, -99.0), np.zeros(M), tsl_hash_int(ids) * -0.8], axis=1),
                V=np.zeros((M, 4)),
                pour_pos=np.tile(np.array([0.0, -99.0, 0.0]), (NEMI, 1)), pour_vel=np.zeros((NEMI, 3)),
                pour_meta=np.zeros((NEMI, 3)), pour_aux=np.tile(np.array([0.0, 0.5, 0.0]), (NEMI, 1)),
                is_mist=tsl_hash_int(ids + 991) < 0.18, size_rand=tsl_hash_int(ids),
                stream_pos=np.zeros((NEMI * SSEG * SRAD, 4)), stream_nor=np.zeros((NEMI * SSEG * SRAD, 4)),
            )

    # ------------------------------------------------------------------------------------------------
    # sampling
    # ------------------------------------------------------------------------------------------------
    @staticmethod
    def nb(a, di, dk):
        """a at (i + di, k + dk), clamp to edge (a texel-centre read one texel away)."""
        NZ, NX = a.shape[-2:]
        ix = np.clip(np.arange(NX) + di, 0, NX - 1)
        kx = np.clip(np.arange(NZ) + dk, 0, NZ - 1)
        return a[..., kx, :][..., :, ix]

    def bilin(self, a, u, w):
        """Bilinear sample of (NZ, NX) array(s) at uvw (u, w), clamp to edge."""
        NX, NZ = self.NX, self.NZ
        x = np.asarray(u, dtype=np.float64) * NX - 0.5
        z = np.asarray(w, dtype=np.float64) * NZ - 0.5
        x0 = np.floor(x)
        z0 = np.floor(z)
        fx = x - x0
        fz = z - z0
        i0 = np.clip(x0.astype(np.int64), 0, NX - 1)
        i1 = np.clip(x0.astype(np.int64) + 1, 0, NX - 1)
        k0 = np.clip(z0.astype(np.int64), 0, NZ - 1)
        k1 = np.clip(z0.astype(np.int64) + 1, 0, NZ - 1)
        if isinstance(a, (list, tuple)):
            return [self._bl(c, i0, i1, k0, k1, fx, fz) for c in a]
        return self._bl(a, i0, i1, k0, k1, fx, fz)

    @staticmethod
    def _bl(a, i0, i1, k0, k1, fx, fz):
        a00, a10 = a[k0, i0], a[k0, i1]
        a01, a11 = a[k1, i0], a[k1, i1]
        top = a00 + (a10 - a00) * fx
        bot = a01 + (a11 - a01) * fx
        return (top + (bot - top) * fz).astype(np.float32)

    def uvw_of_world(self, x, z):
        return ((np.asarray(x) - self.center[0]) / self.WX + 0.5, (np.asarray(z) - self.center[2]) / self.WZ + 0.5)

    def cell_idx(self, x, z):
        ci = np.clip(((np.asarray(x) - self.center[0]) / self.WX + 0.5) * self.NX, 0.5, self.NX - 0.5).astype(np.int64)
        ck = np.clip(((np.asarray(z) - self.center[2]) / self.WZ + 0.5) * self.NZ, 0.5, self.NZ - 0.5).astype(np.int64)
        return ck * self.NX + ci

    def live_bed(self, dbed=None):
        return self.bed + (self.dbed if dbed is None else dbed) if self.ERO else self.bed

    # ------------------------------------------------------------------------------------------------
    # kernels (one substep)
    # ------------------------------------------------------------------------------------------------
    def _k_vel(self):
        o, dt = self.o, np.float32(self.dt)
        h, u0, w0 = self.h, self.u, self.w
        bedL = self.live_bed()
        bu = self.pu - u0 * dt / self.WX
        bw = self.pw - w0 * dt / self.WZ
        vx, vz = self.bilin([u0, w0], bu, bw)
        eta = bedL + h
        gx5 = (self.nb(eta, 1, 0) - self.nb(eta, -1, 0)) / np.float32(2 * self.DX)
        gz5 = (self.nb(eta, 0, 1) - self.nb(eta, 0, -1)) / np.float32(2 * self.DZ)
        gEff = np.float32(o['gravity'] * o['waveScale'])
        if o['yieldSlope'] > 0:
            gEff = gEff * smoothstep(o['yieldSlope'] * 0.7, o['yieldSlope'] * 1.3, np.hypot(gx5, gz5))
        vx = vx - gx5 * gEff * dt
        vz = vz - gz5 * gEff * dt
        if self.consume:
            m = h > o['dryEps']
            mx = (self.dep_mx / FXP).reshape(h.shape)
            mz = (self.dep_mz / FXP).reshape(h.shape)
            den = h * np.float32(self.DX * self.DZ) + np.float32(1e-4)
            vx = np.where(m, vx + np.clip(mx / den, -1.2, 1.2), vx)
            vz = np.where(m, vz + np.clip(mz / den, -1.2, 1.2), vz)
        for s in range(NSPH):
            sp, sa = self.sph_pos[s], self.sph_aux[s]
            if sa[0] <= 0 or sp[1] < -90:
                continue
            dx2, dz2 = self.wx - sp[0], self.wz - sp[2]
            dist = np.maximum(np.hypot(dx2, dz2), 1e-4)
            surfY = bedL + h
            dy = np.abs(sp[1] - surfY)
            inside = (dist < sa[0]) & (dy < sa[0] * 1.4) & (h > o['dryEps'])
            if not inside.any():
                continue
            plunge = min(max(-self.sph_aux2[s][0], 0.0), 6.0)
            k = (sa[0] - dist) / sa[0] * (plunge * 0.35 + 1.0) * 2.2
            px, pz = dx2 / dist * k, dz2 / dist * k
            vx = np.where(inside, vx + (px + sa[1] * 0.7) * dt * 8, vx)
            vz = np.where(inside, vz + (pz + sa[2] * 0.7) * dt * 8, vz)
        for e in range(NEMI):
            ep, ev = self.emi_pos[e], self.emi_vel[e]
            if ep[2] <= 0:
                continue
            dx3, dz3 = self.wx - ep[0], self.wz - ep[1]
            dist3 = np.maximum(np.hypot(dx3, dz3), 1e-4)
            m = (dist3 < 0.55) & (h > o['dryEps'])
            prox3 = (0.55 - dist3) / 0.55
            vx = np.where(m, vx + (dx3 / dist3 * 3.4 + ev[0]) * prox3 * dt * 10, vx)
            vz = np.where(m, vz + (dz3 / dist3 * 3.4 + ev[1]) * prox3 * dt * 10, vz)
        sp0 = np.hypot(vx, vz)
        fric = 1.0 / (1.0 + sp0 * np.float32(o['bedFriction']) * dt / np.maximum(h, 0.008))
        vx, vz = vx * fric, vz * fric
        damp = np.float32(1 - min(o['drag'] * self.dt, 0.5))
        vx, vz = vx * damp, vz * damp
        dry = h < 0.0006
        vx = np.where(dry, 0, vx)
        vz = np.where(dry, 0, vz)
        sp2 = np.maximum(np.hypot(vx, vz), 1e-5)
        k = np.minimum(np.float32(o['maxSpeed']), sp2) / sp2
        return self.q(vx * k), self.q(vz * k)

    def _k_flux(self, u, w):
        h, dt = self.h, np.float32(self.dt)
        fPx = np.maximum((u + self.nb(u, 1, 0)) * 0.5, 0) * h
        fMx = np.maximum(-(u + self.nb(u, -1, 0)) * 0.5, 0) * h
        fPz = np.maximum((w + self.nb(w, 0, 1)) * 0.5, 0) * h
        fMz = np.maximum(-(w + self.nb(w, 0, -1)) * 0.5, 0) * h
        total = fPx + fMx + fPz + fMz
        k = np.minimum(1.0, h * np.float32(self.DX) / dt / (total + np.float32(1e-6)))
        return self.q(np.stack([fPx * k, fMx * k, fPz * k, fMz * k]))

    def _k_height(self, flux):
        o, dt = self.o, np.float32(self.dt)
        h = self.h.copy()
        inXm = self.nb(flux[0], -1, 0)
        inXp = self.nb(flux[1], 1, 0)
        inZm = self.nb(flux[2], 0, -1)
        inZp = self.nb(flux[3], 0, 1)
        net = inXm + inXp + inZm + inZp - (flux[0] + flux[1] + flux[2] + flux[3])
        h = h + net / np.float32(self.DX) * dt
        rad = 0.30
        for e in range(NEMI):
            ep = self.emi_pos[e]
            if ep[2] <= 0:
                continue
            d = np.hypot(self.wx - ep[0], self.wz - ep[1])
            area = math.pi * rad * rad
            h = np.where(d < rad, h + np.float32(ep[2] / area * self.dt) * (1 - d / rad) * 3, h)
        if self.consume:
            h = h + (self.dep_vol / FXP / (self.DX * self.DZ)).reshape(h.shape).astype(np.float32)
        if o['rainRate'] > 0:
            t = np.float32(self.time)
            squall = swe_fbm2(self.wx * np.float32(0.16) + t * np.float32(0.11),
                              self.wz * np.float32(0.16) + t * np.float32(0.045))
            bands = np.clip(squall * 1.5 - 0.25, 0.0, 1.6)
            rain_mul = 1.0 + (bands - 1.0) * o['rainPatchiness']
            edgeR = smoothstep(0.0, self.EK['edgeFeather'] * 1.6, self.dwall) if self.ERO else 1.0
            h = h + (np.float32(self.rain) * rain_mul * edgeR * dt).astype(np.float32)
        return self.q(np.clip(h, 0.0, o['maxDepth']))

    def _k_foam(self, u, w):
        o, dt = self.o, np.float32(self.dt)
        h = self.h                                         # hSrc: the OLD depth (as the engine's mkFoam)
        bu = self.pu - u * dt / self.WX
        bw = self.pw - w * dt / self.WZ
        f = self.bilin(self.foam, bu, bw)
        dux = (self.nb(u, 1, 0) - self.nb(u, -1, 0)) / np.float32(2 * self.DX)
        dwz = (self.nb(w, 0, 1) - self.nb(w, 0, -1)) / np.float32(2 * self.DZ)
        churn = np.abs(dux + dwz)
        e = self.live_bed() + h
        steep = np.hypot((self.nb(e, 1, 0) - self.nb(e, -1, 0)) / np.float32(2 * self.DX),
                         (self.nb(e, 0, 1) - self.nb(e, 0, -1)) / np.float32(2 * self.DZ))
        wet = smoothstep(0.0, o['dryEps'] * 2, h)
        churnN = smoothstep(6.0, 30.0, churn)
        f = f + churnN * (o['foamChurn'] * o['foamGain']) * dt * wet
        f = f + smoothstep(0.55, 1.6, steep) * (o['foamCrest'] * o['foamGain']) * dt * wet
        for k in range(NEMI):
            ep, ev = self.emi_pos[k], self.emi_vel[k]
            if ep[2] <= 0:
                continue
            d = np.hypot(self.wx - ep[0], self.wz - ep[1])
            f = np.where(d < 0.45, f + ev[2] * dt * 2.0 * wet, f)
        bedL = self.live_bed()
        for s in range(NSPH):
            sp, sa = self.sph_pos[s], self.sph_aux[s]
            if sa[0] <= 0 or sp[1] < -90:
                continue
            d = np.hypot(self.wx - sp[0], self.wz - sp[2])
            plungeF = min(max(-self.sph_aux2[s][0], 0.0), 6.0)
            spd = math.hypot(sa[1], sa[2]) + plungeF * 0.6
            dyF = np.abs(sp[1] - (bedL + h))
            if spd > 0.15:
                m = (d < sa[0]) & (dyF < sa[0] * 1.4)
                f = np.where(m, f + spd * o['foamWake'] * dt * wet, f)
        if self.consume:
            f = f + (self.dep_foam / FXP).reshape(h.shape) * wet
        f = f * np.float32(1 - min(o['foamDecay'] * self.dt, 0.9))
        return self.q(np.clip(f, 0.0, 1.5))

    def _k_erode(self, hN, u, w):
        EK, dt = self.EK, np.float32(self.dt)
        edgeM = smoothstep(0.0, EK['edgeFeather'], self.dwall)
        delta = self.dbed.copy()
        age = self.age.copy()
        bu = self.pu - u * dt / self.WX
        bw = self.pw - w * dt / self.WZ
        s = self.bilin(self.silt, bu, bw)
        wet = smoothstep(EK['minDepth'], EK['minDepth'] * 3, hN)
        spd = np.hypot(u, w)
        bT = self.bed + self.dbed
        bC = bT
        slope = np.hypot((self.nb(bT, 1, 0) - self.nb(bT, -1, 0)) / np.float32(2 * self.DX),
                         (self.nb(bT, 0, 1) - self.nb(bT, 0, -1)) / np.float32(2 * self.DZ))
        C = EK['capacity'] * np.power(spd, 1.7) * (np.minimum(hN, 0.08) * 12.0) * wet
        diff = C - s
        cutRoom = smoothstep(-EK['maxDelta'], -EK['maxDelta'] * 0.6, delta)
        ero = np.maximum(diff, 0.0) * EK['erode'] * dt * wet * cutRoom * (1 + np.minimum(slope, 1.2) * 1.6) * edgeM
        if EK['bank'] > 0:
            bank = np.zeros_like(hN)
            for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                hN_n = self.nb(hN, di, dk)
                spN = np.hypot(self.nb(u, di, dk), self.nb(w, di, dk))
                face = np.clip(bC - self.nb(bT, di, dk), 0.0, 0.6)
                powN = np.power(spN, 1.7) * (np.minimum(hN_n, 0.08) * 12.0) * smoothstep(EK['minDepth'], EK['minDepth'] * 3, hN_n)
                bank = bank + powN * face
            ero = ero + bank * EK['bank'] * EK['erode'] * 0.35 * dt * cutRoom
        fillRoom = smoothstep(EK['maxFill'], EK['maxFill'] * 0.4, delta)
        dep = np.minimum(np.maximum(-diff, 0.0) * EK['deposit'] * dt * fillRoom * edgeM, s)
        delta = delta - ero + dep
        s = s + ero - dep
        age = (age + dep * 26.0) * np.float32(1 - min(0.08 * self.dt, 0.5))
        reposeH = EK['talusSlope'] * self.DX
        slump = np.zeros_like(hN)
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            dEl = self.nb(bT, di, dk) - bC
            ex2 = np.abs(dEl) - reposeH
            touched = smoothstep(0.003, 0.012, np.maximum(np.abs(self.nb(self.dbed, di, dk)), np.abs(self.dbed)))
            slump = slump + np.maximum(ex2, 0.0) * (0.25 * EK['talusRate']) * dt * np.sign(dEl) * touched
        delta = np.clip(delta + slump * edgeM, -EK['maxDelta'], EK['maxFill'])
        return self.q(delta), self.q(np.clip(s, 0.0, 0.6)), self.q(np.clip(age, 0.0, 1.0))

    def substep(self):
        u, w = self._k_vel()
        flux = self._k_flux(u, w)
        hN = self._k_height(flux)
        foam = self._k_foam(u, w)
        if self.ERO:
            dbed, silt, age = self._k_erode(hN, u, w)
            self.dbed, self.silt, self.age = dbed, silt, age
        self.h_prev, self.h = self.h, hN
        self.u, self.w, self.foam, self.flux = u, w, foam, flux

    # ------------------------------------------------------------------------------------------------
    # per frame
    # ------------------------------------------------------------------------------------------------
    def step(self, delta):
        o = self.o
        dtSub = o['fixedStep'] / o['substeps']
        self.acc = min(self.acc + min(delta, 0.1), dtSub * o['maxSubSteps'])
        self.dt = dtSub
        if self.spray is not None:
            self._k_spray(min(delta, 0.1), self.sim_time)
            self._k_stream(self.time)
        first = True
        while self.acc >= dtSub:
            self.acc -= dtSub
            self.sim_time += dtSub
            self.time = self.sim_time
            self.consume = first
            self.substep()
            if first:
                self.dep_vol[:] = 0
                self.dep_mx[:] = 0
                self.dep_mz[:] = 0
                self.dep_foam[:] = 0
                first = False
        self.consume = False
        self._k_ripple()

    def _k_ripple(self):
        o = self.o
        h, u, w = self.h, self.u, self.w
        actR = smoothstep(0.04, 0.45, np.hypot(u, w)) * smoothstep(0.0, o['dryEps'] * 6, h)
        tt = self.time
        flowT = o['flowT']
        ph1 = (tt / flowT) % 1.0
        ph2 = (tt / flowT + 0.5) % 1.0
        r1 = swe_ripple_field(self.wx - u * (ph1 * flowT), self.wz - w * (ph1 * flowT), tt * o['rippleSpeed'], o['rippleScale'])
        r2 = swe_ripple_field(self.wx - u * (ph2 * flowT), self.wz - w * (ph2 * flowT), tt * o['rippleSpeed'] + 31.7, o['rippleScale'])
        blend = abs(ph1 * 2 - 1)
        self.ripple = self.q((r1 + (r2 - r1) * blend) * o['rippleAmp'] * actR)
        fsc = o['foamTexScale']

        def nzF(ox, oz):
            qx, qz = (self.wx - ox), (self.wz - oz)
            return (swe_fbm2(qx * fsc + 3.1, qz * fsc + 3.1) * 0.55
                    + swe_fbm2(qx * (fsc * 3.7) + 17.3, qz * (fsc * 3.7) + 17.3) * 0.45)

        n1 = nzF(u * (ph1 * flowT), w * (ph1 * flowT))
        n2 = nzF(u * (ph2 * flowT), w * (ph2 * flowT))
        self.foam_nz = self.q(n1 + (n2 - n1) * blend)

    # ------------------------------------------------------------------------------------------------
    # spray (one integrate per FRAME) and pour streams
    # ------------------------------------------------------------------------------------------------
    def _bed_at(self, u, w):
        return self.bilin(self.live_bed(), u, w)

    def _h_at(self, u, w):
        return self.bilin(self.h, u, w)

    def _surf_at(self, x, z):
        u, w = self.uvw_of_world(x, z)
        return self._bed_at(u, w) + self._h_at(u, w)

    def _k_spray(self, dtF, time):
        o, S = self.o, self.spray
        ids, P, V = S['ids'], S['P'], S['V']
        life = P[:, 3].copy()
        is_promo = ids >= S['PROMO0']
        bkt = int(time * 60)
        alive = life > 0
        foam_st = alive & (V[:, 3] < -0.5)
        fly = alive & ~foam_st
        dead = ~alive
        # ---- foam state: ride the field's velocity on the surface, feed the foam field --------------
        if foam_st.any():
            idx = np.nonzero(foam_st)[0]
            uF, wF = self.uvw_of_world(P[idx, 0], P[idx, 2])
            vFx, vFz = self.bilin([self.u, self.w], uF, wF)
            P[idx, 0] += vFx * dtF
            P[idx, 2] += vFz * dtF
            P[idx, 1] = self._surf_at(P[idx, 0], P[idx, 2]) + 0.012
            V[idx, 0], V[idx, 1], V[idx, 2] = vFx, 0.0, vFz
            np.add.at(self.dep_foam, self.cell_idx(P[idx, 0], P[idx, 2]),
                      np.rint(0.55 * o['foamGain'] * dtF * FXP).astype(np.int64))
            life[idx] -= dtF
            gone = (self._h_at(uF, wF) < o['dryEps']) | (life[idx] < 0)
            g = idx[gone]
            life[g] = tsl_hash_int(g + 77) * -0.22
            V[g, 3] = 0.0
        # ---- ballistic flight, demotion on landing -------------------------------------------------
        if fly.any():
            idx = np.nonzero(fly)[0]
            V[idx, 1] -= 9.8 * dtF
            P[idx, :3] += V[idx, :3] * dtF
            life[idx] -= dtF
            surf = self._surf_at(P[idx, 0], P[idx, 2])
            hit = P[idx, 1] < surf
            land = hit | (life[idx] < 0)
            li = idx[land]
            if len(li):
                vol = V[li, 3]
                impact = np.linalg.norm(V[li, :3], axis=1)
                carry = vol > 0
                ci = self.cell_idx(P[li, 0], P[li, 2])
                hv9 = np.maximum(np.hypot(V[li, 0], V[li, 2]), 0.15)
                spreadK = np.minimum(1 + np.abs(V[li, 1]) * 0.35 / hv9, 1.2) * o['momentumTransfer']
                c = carry
                np.add.at(self.dep_vol, ci[c], np.rint(vol[c] * FXP).astype(np.int64))
                np.add.at(self.dep_mx, ci[c], np.rint(vol[c] * V[li[c], 0] * spreadK[c] * FXP).astype(np.int64))
                np.add.at(self.dep_mz, ci[c], np.rint(vol[c] * V[li[c], 2] * spreadK[c] * FXP).astype(np.int64))
                np.add.at(self.dep_foam, ci[c], np.rint(vol[c] * (45.0 * o['foamGain']) * FXP).astype(np.int64))
                to_foam = is_promo[li] & hit[land] & (impact > 0.8)
                tf = li[to_foam]
                V[tf, 3] = -1.0
                P[tf, 1] = surf[land][to_foam] + 0.012
                life[tf] = tsl_hash_int(tf + 83) * 0.9 + 0.4
                rs = li[~to_foam]
                life[rs] = tsl_hash_int(rs + 77) * -0.22
                V[rs, 3] = 0.0
        # ---- respawn ---------------------------------------------------------------------------------
        if dead.any():
            idx = np.nonzero(dead)[0]
            life[idx] += dtF
            ready = idx[life[idx] > 0]
            pour = ready[~is_promo[ready]]
            promo = ready[is_promo[ready]]
            if len(pour):
                self._spawn_pour(pour, life, bkt)
            if len(promo):
                self._spawn_promo(promo, life, bkt, dtF)
        P[:, 3] = life

    def _spawn_pour(self, idx, life, bkt):
        o, S = self.o, self.spray
        P, V = S['P'], S['V']
        src = idx % NEMI
        meta = S['pour_meta'][src]
        roll = tsl_hash_int(idx + 3 + bkt)
        ok = (meta[:, 1] > 0.5) & (roll < meta[:, 0])
        life[idx[~ok]] = -0.03
        idx, src = idx[ok], src[ok]
        if not len(idx):
            return
        jp, jv, aux = S['pour_pos'][src], S['pour_vel'][src], S['pour_aux'][src]
        j1, j2, j3 = tsl_hash_int(idx + 5 + bkt), tsl_hash_int(idx + 7 + bkt), tsl_hash_int(idx + 11 + bkt)
        j4, j6 = tsl_hash_int(idx + 23 + bkt), tsl_hash_int(idx + 29 + bkt)

        def solveTL(ys):
            disc = np.maximum(jv[:, 1] ** 2 + (jp[:, 1] - ys) * 19.6, 0.01)
            return (jv[:, 1] + np.sqrt(disc)) / 9.8

        uM, wM = self.uvw_of_world(jp[:, 0], jp[:, 2])
        t1 = solveTL(self._bed_at(uM, wM) + self._h_at(uM, wM))
        lx, lz = jp[:, 0] + jv[:, 0] * t1, jp[:, 2] + jv[:, 2] * t1
        uL, wL = self.uvw_of_world(lx, lz)
        tL = np.clip(solveTL(self._bed_at(uL, wL) + self._h_at(uL, wL)), 0.08, 1.35)
        seep = aux[:, 0] > 0.5
        jvS = jv * np.where(seep, 0.3, 1.0)[:, None]
        ts = np.where(seep, j6 * 0.2, tL * (0.72 + j6 * 0.27))
        perp = np.stack([-jv[:, 2] + 0.001, np.zeros(len(idx)), jv[:, 0]], axis=1)
        perp /= np.linalg.norm(perp, axis=1, keepdims=True)
        lat = np.where(seep, (j1 - 0.5) * aux[:, 1], 0.0)
        sp = o['sprayJetSpread']
        P[idx, :3] = (jp + perp * lat[:, None] + jvS * ts[:, None] + np.array([0, -4.9, 0]) * (ts * ts)[:, None]
                      + np.stack([(j1 - 0.5) * sp * 2, (j2 - 0.5) * sp, (j3 - 0.5) * sp * 2], axis=1))
        jit = np.stack([(j2 - 0.5) * 0.55, (j3 - 0.5) * 0.3, (j1 - 0.5) * 0.55], axis=1) * np.where(seep, 0.45, 1.0)[:, None]
        V[idx, :3] = (jvS + np.array([0, -9.8, 0]) * ts[:, None]) * (j4 * 0.24 + 0.9)[:, None] + jit
        V[idx, 3] = o['pourVol']
        life[idx] = 1.6

    def _spawn_promo(self, idx, life, bkt, dtF):
        o, S = self.o, self.spray
        P, V = S['P'], S['V']
        rc1 = tsl_hash_int(idx + 31 + bkt)
        rc2 = tsl_hash_int(idx + 37 + bkt)
        pick = tsl_hash_int(idx + 53 + bkt)
        biased = pick < 0.7
        si2 = (pick * NSPH * 10).astype(np.int64) % NSPH
        spC, srC = self.sph_pos[si2], self.sph_aux[si2, 0]
        use = biased & (srC > 0.01)
        aa = tsl_hash_int(idx + 59 + bkt) * 6.2832
        rr2 = srC * (tsl_hash_int(idx + 61 + bkt) * 1.6 + 0.7)
        rc1 = np.where(use, (spC[:, 0] + np.cos(aa) * rr2 - self.center[0]) / self.WX + 0.5, rc1)
        rc2 = np.where(use, (spC[:, 2] + np.sin(aa) * rr2 - self.center[2]) / self.WZ + 0.5, rc2)
        u, w = np.clip(rc1, 0.01, 0.99), np.clip(rc2, 0.01, 0.99)
        hC = self._h_at(u, w)
        vCx, vCz = self.bilin([self.u, self.w], u, w)
        spdC = np.hypot(vCx, vCz)
        du, dw = 1.0 / self.NX, 1.0 / self.NZ

        def ta(oU, oW, dx, dz):
            nx, nz = self.bilin([self.u, self.w], u + oU, w + oW)
            dvx, dvz = vCx - nx, vCz - nz
            return (np.hypot(dvx, dvz) + dvx * dx + dvz * dz) * 0.5

        taRaw = ta(du, 0, 1, 0) + ta(-du, 0, -1, 0) + ta(0, dw, 0, 1) + ta(0, -dw, 0, -1)
        PHI = lambda I, mn, mx: np.clip((I - mn) / (mx - mn), 0, 1)        # noqa: E731
        Ita = PHI(taRaw, o['promoTaMin'], o['promoTaMax'])
        eta = lambda a, b: self._bed_at(a, b) + self._h_at(a, b)          # noqa: E731
        etaC = eta(u, w)
        lap = (eta(u + du, w) + eta(u - du, w) + eta(u, w + dw) + eta(u, w - dw) - etaC * 4) / (self.DX * self.DX)
        dhdt = (hC - self.bilin(self.h_prev, u, w)) / self.dt
        rising = smoothstep(0.02, 0.25, dhdt)
        Iwc = PHI(-lap, o['promoCrestMin'], o['promoCrestMax']) * rising
        Ik = PHI(spdC * spdC + dhdt * dhdt * 0.5, o['promoEnMin'], o['promoEnMax'])
        pot = Ik * np.clip(Ita * o['promoKta'] + Iwc * o['promoKwc'], 0, 1)
        roll2 = tsl_hash_int(idx + 43 + bkt)
        go = (hC > 0.03) & (roll2 < pot * o['promoRate'])
        life[idx[~go]] = -0.05
        if not go.any():
            return
        g = idx[go]
        u, w, pot, vCx, vCz, spdC, dhdt, etaC = u[go], w[go], pot[go], vCx[go], vCz[go], spdC[go], dhdt[go], etaC[go]
        wx2 = (u - 0.5) * self.WX + self.center[0]
        wz2 = (w - 0.5) * self.WZ + self.center[2]
        ci = self.cell_idx(wx2, wz2)
        vol = o['promoVol'] * (pot * 0.9 + 0.5)
        np.add.at(self.dep_vol, ci, -np.rint(vol * FXP).astype(np.int64))
        a6 = tsl_hash_int(g + 41 + bkt) * 6.2832
        r6 = np.sqrt(tsl_hash_int(g + 47 + bkt)) * (self.DX * 2.5)
        along = tsl_hash_int(g + 59 + bkt) * dtF
        j5 = tsl_hash_int(g + 61 + bkt)
        P[g, 0] = wx2 + np.cos(a6) * r6 + vCx * along
        P[g, 1] = etaC + 0.02 + j5 * 0.03
        P[g, 2] = wz2 + np.sin(a6) * r6 + vCz * along
        radV = pot * 0.9 + 0.35
        V[g, 0] = vCx + np.cos(a6) * radV
        V[g, 1] = (np.clip(dhdt, 0.0, 3.0) * 1.1 + spdC * o['promoVy']) * (j5 * 0.6 + 0.7)
        V[g, 2] = vCz + np.sin(a6) * radV
        V[g, 3] = vol
        life[g] = (tsl_hash_int(g + 67) * 0.5 + 0.35) * (pot * 0.8 + 0.6)

    def _k_stream(self, time):
        """The pour tubes: 28 rings x 8 spokes per pour along the ballistic arc, cut at the surface crossing."""
        from ._noise import swe_vnoise
        S = self.spray
        n = NEMI * SSEG * SRAD
        vid = np.arange(n)
        pi = vid // (SSEG * SRAD)
        rem = vid % (SSEG * SRAD)
        ring, spoke = rem // SRAD, rem % SRAD
        s = ring / (SSEG - 1)
        th = spoke / SRAD * 6.2832
        jp, jv, meta = S['pour_pos'][pi], S['pour_vel'][pi], S['pour_meta'][pi]

        def solveTL(ys):
            disc = np.maximum(jv[:, 1] ** 2 + (jp[:, 1] - ys) * 19.6, 0.01)
            return (jv[:, 1] + np.sqrt(disc)) / 9.8

        uM, wM = self.uvw_of_world(jp[:, 0], jp[:, 2])
        ysM = self._bed_at(uM, wM) + self._h_at(uM, wM)
        t1g = solveTL(ysM)
        uL, wL = self.uvw_of_world(jp[:, 0] + jv[:, 0] * t1g, jp[:, 2] + jv[:, 2] * t1g)
        tL = np.clip(np.maximum(solveTL(self._bed_at(uL, wL) + self._h_at(uL, wL)), t1g * 0.6), 0.08, STMAX)
        tF = s * tL * 1.03
        g = np.array([0.0, -4.9, 0.0])
        pos = jp + jv * tF[:, None] + g * (tF * tF)[:, None]
        vNow = jv + np.array([0.0, -9.8, 0.0]) * tF[:, None]
        spd = np.maximum(np.linalg.norm(vNow, axis=1), 0.4)
        Q = np.maximum(meta[:, 2], 0.001)
        spd0 = np.maximum(np.linalg.norm(jv, axis=1), 0.4)
        rMouth = np.minimum(np.sqrt(Q / (spd0 * math.pi)), 0.08)
        wob = swe_vnoise((s - time / tL) * 9.0, pi * 9.7) * 0.55 + 0.75
        r0 = rMouth * np.sqrt(spd0 / spd) * wob
        Tn = vNow / np.maximum(np.linalg.norm(vNow, axis=1, keepdims=True), 1e-9)   # unused pours: zero arcs
        Nn = np.stack([-jv[:, 2] + 0.001, np.zeros(n), jv[:, 0]], axis=1)
        Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
        Bn = np.cross(Tn, Nn)
        Bn /= np.maximum(np.linalg.norm(Bn, axis=1, keepdims=True), 1e-9)
        rad = Nn * np.cos(th)[:, None] + Bn * np.sin(th)[:, None]
        pos = pos + rad * r0[:, None]
        sCut = 1 - smoothstep(0.94, 1.0, s)
        brkA = 1 - smoothstep(0.85, 1.0, s) * 0.7
        dryMouth = smoothstep(0.02, 0.12, jp[:, 1] - ysM)
        alpha = meta[:, 1] * dryMouth * (1 - S['pour_aux'][pi, 0]) * sCut * (brkA * 0.85)
        S['stream_pos'] = np.concatenate([pos, alpha[:, None]], axis=1)
        S['stream_nor'] = np.concatenate([rad, tL[:, None]], axis=1)

    # ------------------------------------------------------------------------------------------------
    # the API's setters (world coordinates in three's frame)
    # ------------------------------------------------------------------------------------------------
    def set_pours(self, lst):
        S = self.spray
        if S is None:
            return
        slots = math.floor(self.o['sprayMax'] * 0.7 / NEMI)
        cycle = 1.05
        for i in range(NEMI):
            j = lst[i] if i < len(lst) else None
            S['pour_pos'][i] = (j['x'], j['y'], j['z']) if j else (0, -99, 0)
            S['pour_vel'][i] = (j.get('vx', 0), j.get('vy', 0), j.get('vz', 0)) if j else (0, 0, 0)
            rate = j.get('rate', 0) if j else 0
            needed = rate / self.o['pourVol']
            S['pour_meta'][i] = (min(1.0, needed / (slots / cycle)), 1.0 if rate > 0 else 0.0, rate)
            S['pour_aux'][i] = (1.0 if j and j.get('style') == 'seep' else 0.0, j.get('seepWidth', 0.5) if j else 0.5, 0)

    def set_emitters(self, lst):
        for i in range(NEMI):
            e = lst[i] if i < len(lst) else None
            self.emi_pos[i] = (e['x'], e['z'], e.get('rate', 0)) if e else (0, 0, 0)
            self.emi_vel[i] = (e.get('vx', 0), e.get('vz', 0), e.get('foam', 0.8)) if e else (0, 0, 0)

    def set_spheres(self, lst):
        for i in range(NSPH):
            s = lst[i] if i < len(lst) else None
            self.sph_pos[i] = (s['x'], s['y'], s['z']) if s else (0, -99, 0)
            self.sph_aux[i] = (s['r'], s.get('vx', 0), s.get('vz', 0)) if s else (0, 0, 0)
            self.sph_aux2[i] = (s.get('vy', 0), 0, 0) if s else (0, 0, 0)

    def volume(self):
        """Water held by the field (m^3), for conservation checks."""
        return float(self.h.astype(np.float64).sum() * self.DX * self.DZ)
