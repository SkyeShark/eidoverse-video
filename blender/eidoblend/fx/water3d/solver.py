"""The GPU solver of fluid_water.js (createWaterSim's simulation half) on Blender's `gpu` compute.

The same storage (rgba16float 3D textures, linear clamp-to-edge samplers), the same kernels (_kernels.py) in the
same order per substep (paper Algorithm 1: extrapolate -> reinit (periodic) -> volume control (every vcEvery) ->
advect + forces -> incompressibility -> viscosity), the same multigrid, the same volume sensor and PI controller.
Everything here is in three.js axes (y up), domain-local: uvw in [0, 1]^3 over the domain, metres = (uvw - 0.5) *
world. The public API (water.py) converts Blender coordinates on the way in and out.

    S = WaterSolver(opts)          # opts: water.DEFAULTS merged with the caller's (snake_case)
    S.set_solid(occupancy)         # (NZ, NY, NX) float 0/1 from the collider voxeliser, or None
    S.init(); S.capture_volume_target()
    S.step(1 / 30)                 # the engine's step(): real-time clamp + fixed-step accumulator
    S.advance(1 / 24)              # a bake's step: the same accumulator, no 1/30 clamp
    S.phi()                        # (NZ, NY, NX) float32, the current level set (metres, negative = water)
"""

from __future__ import annotations

import numpy as np

from .._gpu import ComputeContext
from . import _kernels as K


class WaterSolver:
    def __init__(self, o, log=print):
        self.o = o
        self.log = log
        NX, NY, NZ = (int(v) for v in o['grid3'])
        self.N = (NX, NY, NZ)
        self.CELLS = NX * NY * NZ
        W = tuple(float(v) for v in o['world3'])
        self.W = np.array(W, dtype=np.float64)
        self.DXV = (W[0] / NX, W[1] / NY, W[2] / NZ)
        self.DX = self.DXV[0]
        self.CELL_VOL = self.DXV[0] * self.DXV[1] * self.DXV[2]
        self.wallM = 1.5 / NX
        self.ctx = ComputeContext()
        ctx = self.ctx
        size = (NX, NY, NZ)
        mk = lambda s=size: ctx.texture3d(s)                                  # noqa: E731
        self.velA, self.velB = mk(), mk()
        self.phiA, self.phiB = mk(), mk()
        self.phiHat, self.divT = mk(), mk()
        self.prsA, self.prsB = mk(), mk()
        self.phi_in_a = True
        self.volCtrlA, self.volCtrlB = mk((1, 1, 1)), mk((1, 1, 1))
        self.vol_ctrl_in_a = True
        self.volFinal = mk((1, 1, 1))
        self.solidTex = None
        self.solid_np = None
        self.solid_levels = {}
        self.NSPH = max(0, int(o['max_spheres']))
        self.NEMI = max(0, int(o['max_emitters']))
        self.spheres = np.zeros((max(self.NSPH, 1), 4), dtype=np.float32)
        self.spheres[:, 3] = -1.0
        self.emitters = np.zeros((2, max(self.NEMI, 1), 4), dtype=np.float32)
        self.emitters[0, :, 3] = -1.0
        self.sphTex = self.emitTex = None
        self._sph_dirty = self._emi_dirty = True
        if o['volume_control']:
            o['measure_volume'] = True
        # the uniforms the kernels read every substep (the engine's U.* the scene may change live)
        self.U = dict(dt=float(o['fixed_step']), time=0.0, gravity=float(o['gravity']),
                      vel_damping=float(o['vel_damping']), max_speed=float(o['max_speed']),
                      vel_smooth=float(o['vel_smooth']), mg_omega=float(o['mg_omega']), vol_target=1.0,
                      vc_kp=float(o['vc_kp']), vc_ki=float(o['vc_ki']), vc_max_rate=float(o['vc_max_rate']))
        self.sim_time = 0.0
        self.acc = 0.0
        self.target_valid = False                # a real target is set (an empty start leaves the placeholder 1)
        self.frame_count = 0                     # substeps run (the engine's frameCount)
        self._logged = False
        self._kernels_built = False

    # ------------------------------------------------------------------------------------------------
    # solids, spheres, emitters
    # ------------------------------------------------------------------------------------------------
    def set_solid(self, occ):
        """The baked field (the engine's solidTex): (NZ, NY, NX) occupancy 0..1, or None. Must be called before
        the kernels are built (the engine bakes colliders at setup)."""
        if occ is None:
            self.solidTex, self.solid_np = None, None
            return
        import gpu
        NX, NY, NZ = self.N
        a = np.ascontiguousarray(np.asarray(occ, dtype=np.float32).reshape(NZ, NY, NX))
        self.solid_np = a
        buf = gpu.types.Buffer('FLOAT', a.size, a.ravel())
        tex = gpu.types.GPUTexture((NX, NY, NZ), format='R16F', data=buf)
        tex.filter_mode(True)                    # LINEAR: the sim thresholds > 0.5, the render reads it soft
        tex.extend_mode('EXTEND')
        self.solidTex = tex

    def set_spheres_local(self, arr):
        """(n, 4) domain-local three-axes centres + radius; rows past max_spheres are ignored, unused slots off."""
        self.spheres[:] = 0.0
        self.spheres[:, 3] = -1.0
        n = min(len(arr), self.NSPH)
        if n:
            self.spheres[:n] = np.asarray(arr, dtype=np.float32)[:n]
        self._sph_dirty = True

    def set_emitters_local(self, pos_r, vel):
        self.emitters[:] = 0.0
        self.emitters[0, :, 3] = -1.0
        n = min(len(pos_r), self.NEMI)
        if n:
            self.emitters[0, :n] = np.asarray(pos_r, dtype=np.float32)[:n]
            self.emitters[1, :n, :3] = np.asarray(vel, dtype=np.float32)[:n, :3]
        self._emi_dirty = True

    def _upload_arrays(self):
        if self.NSPH and self._sph_dirty:
            self.sphTex = self.ctx.texture2d_from(self.spheres[None, :, :])
            self._sph_dirty = False
        if self.NEMI and self._emi_dirty:
            self.emitTex = self.ctx.texture2d_from(self.emitters)
            self._emi_dirty = False

    # ------------------------------------------------------------------------------------------------
    # kernels
    # ------------------------------------------------------------------------------------------------
    def _defs(self, dims, margin=None):
        o = self.o
        NX, NY, NZ = self.N
        W = self.W
        d = {'NX': int(dims[0]), 'NY': int(dims[1]), 'NZ': int(dims[2]),
             'WX': f'{W[0]:.9g}', 'WY': f'{W[1]:.9g}', 'WZ': f'{W[2]:.9g}',
             'DX': f'{self.DX:.9g}', 'WALLM': f'{(self.wallM if margin is None else margin):.9g}',
             'WALLS': 1 if o['walls'] else 0, 'SOLIDTEX': 1 if self.solidTex is not None else 0,
             'NSPH': self.NSPH, 'NEMI': self.NEMI, 'MAXTRACE': f'{float(o["max_trace_cells"]):.9g}',
             'AIRV': f'{self.DX * 4:.9g}', 'NOCLAMP': 1 if o.get('__no_clamp') else 0,
             'VC': 1 if o['volume_control'] else 0, 'RHSNEG': 0}
        # GLSL wants a float literal
        for k in ('WX', 'WY', 'WZ', 'DX', 'WALLM', 'MAXTRACE', 'AIRV'):
            if '.' not in d[k] and 'e' not in d[k]:
                d[k] += '.0'
        return d

    def _kernel(self, body, samplers=(), push=(), dims=None, margin=None, solid=False, trace=False,
                stencil=False, fluid=False, emit=False, extra=None, local=(8, 8, 4), solid_level=0):
        defs = self._defs(dims or self.N, margin)
        defs.update(extra or {})
        uses_solid = solid or stencil or fluid
        pre = K.HEAD + (K.SOLID if uses_solid else '') + (K.TRACE if trace else '') + \
            (K.MG_FLUID if (stencil or fluid) else '') + (K.STENCIL if stencil else '')
        smp = list(samplers)
        types = {}
        if uses_solid and self.solidTex is not None:
            smp.append('solidTex')
        if uses_solid and self.NSPH:
            smp.append('sphTex')
            types['sphTex'] = 'FLOAT_2D'
        if emit and self.NEMI:
            smp.append('emitTex')
            types['emitTex'] = 'FLOAT_2D'
        k = self.ctx.kernel(body, samplers=smp, images=['dst'], push=list(push), local=local,
                            sampler_types=types, defines=defs, preamble=pre)
        k.samplers = smp
        k.dims = tuple(int(v) for v in (dims or self.N))
        k.solid_level = int(solid_level)
        return k

    def _run(self, k, samplers, dst, **push):
        smp = dict(samplers)
        if 'solidTex' in k.samplers:
            smp['solidTex'] = self.solid_levels.get(k.solid_level, self.solidTex)
        if 'sphTex' in k.samplers:
            smp['sphTex'] = self.sphTex
        if 'emitTex' in k.samplers:
            smp['emitTex'] = self.emitTex
        k.run(k.groups_for(k.dims), samplers=smp, images={'dst': dst}, **push)

    def build(self):
        """Compile every kernel (after set_solid: the solid layers are compile-time, as the engine's TSL)."""
        o = self.o
        F = 'FLOAT'
        NX, NY, NZ = self.N
        self._upload_arrays()
        col = {'COLW': f'{float(o["column_width"]):.9g}', 'COLH': f'{float(o["column_height"]):.9g}',
               'COLD': f'{float(o["column_depth"]):.9g}',
               'INITLEVEL': f'{float(o["initial_level"] or 0.0):.9g}',
               'USELEVEL': 1 if o['initial_level'] is not None else 0}
        for k in ('COLW', 'COLH', 'COLD', 'INITLEVEL'):
            if '.' not in col[k] and 'e' not in col[k]:
                col[k] += '.0'
        self.kInitPhi = self._kernel(K.INIT_PHI, extra=col)
        self.kExtrap = self._kernel(K.EXTRAP, samplers=['phiTex', 'src'])
        ex = o.get('extrapolation', 'phi')
        if ex not in ('phi', 'bfs'):
            raise ValueError(f"water3d: extrapolation must be 'phi' or 'bfs', not {ex!r}")
        if ex == 'bfs':
            self.kExtrapInit = self._kernel(K.EXTRAP_BFS_INIT, samplers=['phiTex', 'src'])
            self.kExtrapBfs = self._kernel(K.EXTRAP_BFS, samplers=['src'])
        self.kAdvectVel = self._kernel(K.ADVECT_VEL, samplers=['velA', 'phiTex'], trace=True, solid=True,
                                       emit=True, push=[(F, 'uDt'), (F, 'uGravity'), (F, 'uVelDamping')])
        self.kPhiFwd = self._kernel(K.PHI_FWD, samplers=['velA', 'src'], trace=True, push=[(F, 'uDt')])
        self.kPhiCorr = self._kernel(K.PHI_CORR, samplers=['velA', 'src', 'phiHat'], trace=True, emit=True,
                                     push=[(F, 'uDt')])
        scheme = o.get('reinit_scheme', 'central')
        if scheme not in ('central', 'godunov'):
            raise ValueError(f"water3d: reinit_scheme must be 'central' or 'godunov', not {scheme!r}")
        self.kReinit = self._kernel(K.REINIT_GODUNOV if scheme == 'godunov' else K.REINIT, samplers=['src'])
        ext = o.get('extend_phi_into_solids')
        self.extend_phi = bool(ext) if ext is not None else (self.solidTex is not None or self.NSPH > 0)
        if self.extend_phi:
            self.kPhiExt1 = self._kernel(K.PHI_SOLID_EXTEND, samplers=['src'], solid=True, extra={'PASS1': 1})
            self.kPhiExt2 = self._kernel(K.PHI_SOLID_EXTEND, samplers=['src'], solid=True, extra={'PASS1': 0})
        div_smp = ['velB'] + (['volCtrl', 'phiTex'] if o['volume_control'] else [])
        self.kDiv = self._kernel(K.DIV, samplers=div_smp, solid=True)
        self.kJacobi = self._kernel(K.JACOBI, samplers=['phiL', 'srcP', 'rhsTex'], stencil=True)
        self.kProject = self._kernel(K.PROJECT, samplers=['prs', 'phiTex', 'velB'], solid=True,
                                     push=[(F, 'uMaxSpeed')])
        self.kSmooth = self._kernel(K.SMOOTH_VEL, samplers=['src'], solid=True, push=[(F, 'uVelSmooth')])
        self.kCopyVel = self._kernel(K.COPY_VEL, samplers=['src'], solid=True)
        self._build_multigrid()
        self._build_volume()
        self._kernels_built = True

    def _build_multigrid(self):
        """Paper section 3.7: levels while every dim halves exactly and stays >= 4. Level 0 smooths prsA/prsB
        against -divT on the live phi; coarse levels own p, p2, r, phi and b."""
        o = self.o
        NX, NY, NZ = self.N
        ctx = self.ctx
        self.MG = []
        if int(o['mg_levels']) > 1:
            for L in range(int(o['mg_levels'])):
                nx, ny, nz = NX >> L, NY >> L, NZ >> L
                if L > 0 and ((nx << L) != NX or (ny << L) != NY or (nz << L) != NZ or min(nx, ny, nz) < 4):
                    break
                lv = dict(L=L, dims=(nx, ny, nz), margin=max(1.5 / NX, 1.0 / nx))
                if L == 0:
                    lv['p'], lv['p2'] = self.prsA, self.prsB
                    lv['r'] = ctx.texture3d((nx, ny, nz))
                    lv['phi'] = None                   # the live phi
                    lv['b'] = None                     # -divT
                else:
                    for key in ('p', 'p2', 'r', 'phi', 'b'):
                        lv[key] = ctx.texture3d((nx, ny, nz))
                self.MG.append(lv)
        self._build_solid_levels()
        F = 'FLOAT'
        for i, lv in enumerate(self.MG):
            dims, m = lv['dims'], lv['margin']
            rhsneg = {'RHSNEG': 1 if i == 0 else 0}
            lv['kSmooth'] = self._kernel(K.MG_SMOOTH, samplers=['phiL', 'srcP', 'rhsTex'], dims=dims, margin=m,
                                         stencil=True, extra=rhsneg, push=[(F, 'uOmega')], solid_level=i)
            if i < len(self.MG) - 1:
                lv['kRes'] = self._kernel(K.MG_RESIDUAL, samplers=['phiL', 'srcP', 'rhsTex'], dims=dims,
                                          margin=m, stencil=True, extra=rhsneg, solid_level=i)
            if i > 0:
                lv['kRestrict'] = self._kernel(K.MG_RESTRICT, samplers=['src'], dims=dims)
                lv['kRestrictPhi'] = self._kernel(K.COPY_TAP, samplers=['src'], dims=dims)
                f = self.MG[i - 1]
                # runs over the FINER level (its fluid test, its wall margin), sampling this level's p
                lv['kProlong'] = self._kernel(K.MG_PROLONG, samplers=['phiL', 'srcP', 'coarseP'], dims=f['dims'],
                                              margin=f['margin'], fluid=True, solid_level=i - 1)

    def _build_solid_levels(self):
        """The baked collider field per multigrid level. The engine sampled the fine field at a coarse cell centre
        (one linear tap = the mean of its 8 children) and thresholded it at 0.5, so a wall under ~3 fine cells
        thick, a cup's side or a one-cell ground slab, vanished from the coarse grids: they then solved an open,
        floorless box and the correction drained the water (measured: a basin poured for 4.6 s held 4 litres of
        the ~19 poured). The engine keeps its analytic walls alive per level for exactly this reason (the scaled
        margin, 'one solid ring per level'); this is the same rule for the baked field: level L is the 2x2x2 max
        of level L-1, so whatever blocks flow on the fine grid blocks it on every grid. Without baked colliders
        nothing changes."""
        self.solid_levels = {0: self.solidTex}
        if self.solid_np is None or len(self.MG) < 2:
            return
        import gpu
        a = (np.asarray(self.solid_np, dtype=np.float32) > 0.5).astype(np.float32)
        for L in range(1, len(self.MG)):
            nz, ny, nx = a.shape
            a = a.reshape(nz // 2, 2, ny // 2, 2, nx // 2, 2).max(axis=(1, 3, 5))
            lz, ly, lx = a.shape
            buf = gpu.types.Buffer('FLOAT', a.size, np.ascontiguousarray(a).ravel())
            tex = gpu.types.GPUTexture((lx, ly, lz), format='R16F', data=buf)
            tex.filter_mode(True)                      # taps land on texel centres: exact 0 / 1
            tex.extend_mode('EXTEND')
            self.solid_levels[L] = tex

    def _build_volume(self):
        """The GPU volume sensor (a mip chain of single linear taps while every dim halves, then ONE sum into a
        1x1x1 texel) and the PI controller pair."""
        o = self.o
        NX, NY, NZ = self.N
        self.vol_levels, self.vol_reduce = [], []
        if not o['measure_volume']:
            return
        ctx = self.ctx
        self.vol_levels.append(ctx.texture3d((NX, NY, NZ)))
        self.kVolFrac = self._kernel(K.VOL_FRAC, samplers=['phiTex'], solid=True)
        lx, ly, lz = NX, NY, NZ

        def halvable(n):
            return n == 1 or n % 2 == 0

        while (lx > 1 or ly > 1 or lz > 1) and halvable(lx) and halvable(ly) and halvable(lz):
            nx, ny, nz = max(1, lx >> 1), max(1, ly >> 1), max(1, lz >> 1)
            self.vol_levels.append(ctx.texture3d((nx, ny, nz)))
            self.vol_reduce.append(self._kernel(K.COPY_TAP, samplers=['src'], dims=(nx, ny, nz)))
            lx, ly, lz = nx, ny, nz
        self.vol_tail = (lx, ly, lz)
        self.kVolFinal = self._kernel(K.VOL_FINAL, samplers=['src'], dims=(1, 1, 1), local=(1, 1, 1),
                                      extra={'FX': lx, 'FY': ly, 'FZ': lz})
        cv = f'{self.CELLS * self.CELL_VOL:.9g}'
        F = 'FLOAT'
        self.kVolCtrl = self._kernel(K.VOL_CTRL, samplers=['volFinal', 'src'], dims=(1, 1, 1), local=(1, 1, 1),
                                     extra={'CELLSVOL': cv if ('.' in cv or 'e' in cv) else cv + '.0',
                                            'VCEVERY': f'{float(o["vc_every"]):.1f}'},
                                     push=[(F, 'uTarget'), (F, 'uKp'), (F, 'uKi'), (F, 'uMaxRate'), (F, 'uDt')])

    # ------------------------------------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------------------------------------
    @property
    def phi_tex(self):
        return self.phiA if self.phi_in_a else self.phiB

    @property
    def vol_ctrl_tex(self):
        return self.volCtrlA if self.vol_ctrl_in_a else self.volCtrlB

    def init(self):
        """runInit: the dam-break column (or the still layer) into both phi textures, zero velocity and pressure."""
        if not self._kernels_built:
            self.build()
        self._run(self.kInitPhi, {}, self.phiA)
        self._run(self.kInitPhi, {}, self.phiB)
        for t in (self.velA, self.velB, self.prsA, self.prsB, self.phiHat, self.divT):
            t.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))
        self.phi_in_a = True

    def run_volume_sensor(self):
        self._run(self.kVolFrac, {'phiTex': self.phi_tex}, self.vol_levels[0])
        for i, k in enumerate(self.vol_reduce):
            self._run(k, {'src': self.vol_levels[i]}, self.vol_levels[i + 1])
        self._run(self.kVolFinal, {'src': self.vol_levels[-1]}, self.volFinal)

    def measure_volume(self):
        """Liquid volume in m^3 from the GPU sensor (None without measure_volume)."""
        if not self.o['measure_volume']:
            return None
        self.run_volume_sensor()
        mean = float(self.ctx.read(self.volFinal).reshape(-1)[0])
        return mean * self.CELLS * self.CELL_VOL

    def capture_volume_target(self):
        """The target is the initial state measured BY THE SAME SENSOR (an analytic target would bake the
        Heaviside's curvature bias in). An explicit volume_target is honoured even when the start is empty (the
        engine's code skipped it then, and the chorus scene had to set the uniform by hand)."""
        self.volCtrlA.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))
        self.volCtrlB.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))
        self.vol_ctrl_in_a = True
        if not self.o['measure_volume']:
            return
        v = self.measure_volume()
        tgt = self.o['volume_target']
        self.target_valid = False
        if tgt is not None:
            self.U['vol_target'] = float(tgt)
            self.target_valid = True
        elif v > 0:
            self.U['vol_target'] = v
            self.target_valid = True
        if self.o['volume_control']:
            msg = (f'(PI control ON: kp {self.o["vc_kp"]} ki {self.o["vc_ki"]} max {self.o["vc_max_rate"]}/s every '
                   f'{self.o["vc_every"]} substeps)')
        else:
            msg = '(control OFF: measuring only)'
        self.log(f'[water3d] volume target = {self.U["vol_target"]:.5f} m3 (measured {v:.5f}) {msg}')

    # ------------------------------------------------------------------------------------------------
    # the substep (paper Algorithm 1)
    # ------------------------------------------------------------------------------------------------
    def _mg_smooth(self, i, n, from_p2):
        lv = self.MG[i]
        in_p2 = bool(from_p2)
        sweeps = max(1, int(n))
        if (in_p2 and sweeps % 2 == 0) or (not in_p2 and sweeps % 2 == 1):
            sweeps += 1                                   # always land back in lv.p
        phiL = self.phi_tex if i == 0 else lv['phi']
        rhs = self.divT if i == 0 else lv['b']
        for _ in range(sweeps):
            src, dst = (lv['p2'], lv['p']) if in_p2 else (lv['p'], lv['p2'])
            self._run(lv['kSmooth'], {'phiL': phiL, 'srcP': src, 'rhsTex': rhs}, dst, uOmega=self.U['mg_omega'])
            in_p2 = not in_p2

    def _mg_vcycle(self, i):
        o = self.o
        if i == len(self.MG) - 1:
            self._mg_smooth(i, o['mg_coarse'], False)
            return
        lv, lc = self.MG[i], self.MG[i + 1]
        self._mg_smooth(i, o['mg_pre'], False)
        phiL = self.phi_tex if i == 0 else lv['phi']
        rhs = self.divT if i == 0 else lv['b']
        self._run(lv['kRes'], {'phiL': phiL, 'srcP': lv['p'], 'rhsTex': rhs}, lv['r'])
        self._run(lc['kRestrict'], {'src': lv['r']}, lc['b'])
        lc['p'].clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))          # e starts at 0
        self._mg_vcycle(i + 1)
        self._run(lc['kProlong'], {'phiL': phiL, 'srcP': lv['p'], 'coarseP': lc['p']}, lv['p2'])
        self._mg_smooth(i, o['mg_post'], True)

    def _mg_solve(self):
        for i in range(1, len(self.MG)):
            src = self.phi_tex if i == 1 else self.MG[i - 1]['phi']      # phi moves every substep: re-restrict
            self._run(self.MG[i]['kRestrictPhi'], {'src': src}, self.MG[i]['phi'])
        for _ in range(int(self.o['mg_cycles'])):
            self._mg_vcycle(0)

    def _log_config(self):
        o = self.o
        NX, NY, NZ = self.N
        if len(self.MG) > 1 and not o.get('__no_multigrid'):
            solver = ('multigrid ' + '->'.join(f'{lv["dims"][0]}x{lv["dims"][1]}x{lv["dims"][2]}' for lv in self.MG)
                      + f' x{o["mg_cycles"]}V (pre {o["mg_pre"]} post {o["mg_post"]} coarse {o["mg_coarse"]}'
                      f' w {o["mg_omega"]})')
        else:
            solver = f'jacobi x{o["pressure_iters"]}'
        self.log(f'[water3d] grid {NX}x{NY}x{NZ} (three axes) | pressure {solver} | fixedStep '
                 f'1/{round(1 / o["fixed_step"])} | extrap {o["extrapolation_passes"]} | gravity {self.U["gravity"]}'
                 f' | DX {self.DX:.4f}')

    def substep(self):
        o, U = self.o, self.U
        if not self._logged:
            self._logged = True
            self._log_config()
        self._upload_arrays()
        # 1) velocity extrapolation into air: pass pairs velA -> velB -> velA
        if o.get('extrapolation', 'phi') == 'bfs':
            # seed (velA -> velB), then an odd number of passes so the result lands back in velA
            self._run(self.kExtrapInit, {'phiTex': self.phi_tex, 'src': self.velA}, self.velB)
            n = int(o['extrapolation_passes'])
            n = n if n % 2 == 1 else n + 1
            src, dst = self.velB, self.velA
            for _ in range(n):
                self._run(self.kExtrapBfs, {'src': src}, dst)
                src, dst = dst, src
        else:
            for _ in range(0, int(o['extrapolation_passes']), 2):
                self._run(self.kExtrap, {'phiTex': self.phi_tex, 'src': self.velA}, self.velB)
                self._run(self.kExtrap, {'phiTex': self.phi_tex, 'src': self.velB}, self.velA)
        # 2) reinitialisation (periodic; off by default)
        if (not o.get('__no_reinit') and int(o['reinit_every']) > 0
                and self.frame_count % int(o['reinit_every']) == 0 and self.frame_count > 0):
            for _ in range(0, int(o['reinit_iters']), 2):
                for _pass in range(2):
                    src, dst = (self.phiA, self.phiB) if self.phi_in_a else (self.phiB, self.phiA)
                    self._run(self.kReinit, {'src': src}, dst)
                    self.phi_in_a = not self.phi_in_a
        # volume control: sensor + controller every vc_every substeps, the loop closed on the GPU
        if o['volume_control'] and self.frame_count % int(o['vc_every']) == 0:
            self.run_volume_sensor()
            src, dst = (self.volCtrlA, self.volCtrlB) if self.vol_ctrl_in_a else (self.volCtrlB, self.volCtrlA)
            self._run(self.kVolCtrl, {'volFinal': self.volFinal, 'src': src}, dst, uTarget=U['vol_target'],
                      uKp=U['vc_kp'], uKi=U['vc_ki'], uMaxRate=U['vc_max_rate'], uDt=U['dt'])
            self.vol_ctrl_in_a = not self.vol_ctrl_in_a
        # 3) advection + forces: velocity (velA -> velB), then phi by MacCormack
        dt = U['dt']
        self._run(self.kAdvectVel, {'velA': self.velA, 'phiTex': self.phi_tex}, self.velB, uDt=dt,
                  uGravity=U['gravity'], uVelDamping=U['vel_damping'])
        src, dst = (self.phiA, self.phiB) if self.phi_in_a else (self.phiB, self.phiA)
        self._run(self.kPhiFwd, {'velA': self.velA, 'src': src}, self.phiHat, uDt=dt)
        self._run(self.kPhiCorr, {'velA': self.velA, 'src': src, 'phiHat': self.phiHat}, dst, uDt=dt)
        self.phi_in_a = not self.phi_in_a
        if self.extend_phi:
            # phi into the first two solid layers (phiHat is free scratch now), landing back in the live texture
            self._run(self.kPhiExt1, {'src': dst}, self.phiHat)
            self._run(self.kPhiExt2, {'src': self.phiHat}, dst)
        # 4) incompressibility
        if o.get('__no_pressure'):
            self._run(self.kCopyVel, {'src': self.velB}, self.velA)
        else:
            smp = {'velB': self.velB}
            if o['volume_control']:
                smp.update(volCtrl=self.vol_ctrl_tex, phiTex=self.phi_tex)
            self._run(self.kDiv, smp, self.divT)
            if len(self.MG) > 1 and not o.get('__no_multigrid'):
                self._mg_solve()
            else:
                for _ in range(0, int(o['pressure_iters']), 2):
                    self._run(self.kJacobi, {'phiL': self.phi_tex, 'srcP': self.prsA, 'rhsTex': self.divT},
                              self.prsB)
                    self._run(self.kJacobi, {'phiL': self.phi_tex, 'srcP': self.prsB, 'rhsTex': self.divT},
                              self.prsA)
            self._run(self.kProject, {'prs': self.prsA, 'phiTex': self.phi_tex, 'velB': self.velB}, self.velA,
                      uMaxSpeed=U['max_speed'])
        # 5) viscosity, as a pair so the result lands back in velA
        if U['vel_smooth'] > 0:
            self._run(self.kSmooth, {'src': self.velA}, self.velB, uVelSmooth=U['vel_smooth'])
            self._run(self.kSmooth, {'src': self.velB}, self.velA, uVelSmooth=U['vel_smooth'])
        self.frame_count += 1

    # ------------------------------------------------------------------------------------------------
    # stepping
    # ------------------------------------------------------------------------------------------------
    def step(self, delta=1 / 60):
        """The engine's step(): delta clamped to 1/30 s, the accumulator capped at max_sub_steps substeps."""
        return self._accumulate(min(float(delta), 1 / 30), self.o['fixed_step'] * self.o['max_sub_steps'])

    def advance(self, delta):
        """A bake's step: the engine's accumulator without the real-time clamp, so a 24 fps film advances 1/24 s
        a frame (the engine's 1/30 cap would run it at 0.8x)."""
        fs = self.o['fixed_step']
        return self._accumulate(float(delta), max(fs * self.o['max_sub_steps'], float(delta) + fs))

    def _accumulate(self, delta, max_acc):
        fs = float(self.o['fixed_step'])
        self.acc = min(self.acc + delta, max_acc)
        self.U['dt'] = fs
        n = 0
        while self.acc >= fs:
            self.sim_time += fs
            self.U['time'] = self.sim_time
            self.substep()
            self.acc -= fs
            n += 1
        return n

    def warmup(self, seconds):
        self.U['dt'] = float(self.o['fixed_step'])
        while self.sim_time < seconds:
            self.sim_time += self.o['fixed_step']
            self.U['time'] = self.sim_time
            self.substep()

    def reset(self):
        self.sim_time = 0.0
        self.acc = 0.0
        self.frame_count = 0
        self.init()
        self.capture_volume_target()

    # ------------------------------------------------------------------------------------------------
    # readback (the bake's meshing, the grids for inspection)
    # ------------------------------------------------------------------------------------------------
    def phi(self):
        return self.ctx.read(self.phi_tex)[..., 0]

    def velocity(self):
        return self.ctx.read(self.velA)[..., :3]

    def pressure(self):
        return self.ctx.read(self.prsA)[..., 0]

    def divergence(self):
        return self.ctx.read(self.divT)[..., 0]

    def reset_controller(self):
        """Zero the PI controller's state (integral and source) without touching its target: a bumpless hand-over
        from filling to holding, so an integral wound up while water was added does not overshoot afterwards."""
        self.volCtrlA.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))
        self.volCtrlB.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))

    def controller(self):
        """(integral, source s in 1/s, last measured volume m^3) of the PI controller."""
        a = self.ctx.read(self.vol_ctrl_tex).reshape(-1)
        return float(a[0]), float(a[1]), float(a[2])

    def dispose(self):
        for name in ('velA', 'velB', 'phiA', 'phiB', 'phiHat', 'divT', 'prsA', 'prsB', 'volCtrlA', 'volCtrlB',
                     'volFinal', 'solidTex', 'sphTex', 'emitTex'):
            setattr(self, name, None)
        self.vol_levels = []
        self.MG = []
        self._kernels_built = False


def check_cubic(grid3, world3, log=print):
    """The engine's loud warning: this solver needs cubic cells (raw face-difference divergence and gradient,
    an isotropic DX for every level-set band, the multigrid's x4 coarse scaling)."""
    dxv = [w / n for w, n in zip(world3, grid3)]
    aniso = max(dxv) / min(dxv)
    if aniso > 1.005:
        dx = dxv[0]
        want = [int(round(w / dx)) for w in world3]
        log('[water3d] WARNING NON-CUBIC CELLS: physics will be wrong. dx/dy/dz = '
            + ' / '.join(f'{v:.5f}' for v in dxv) + f' (aspect {aniso:.3f}). For this world size use a grid of '
            + f'{want} (three axes x, y-up, z).')
    return aniso
