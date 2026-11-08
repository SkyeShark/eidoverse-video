"""eidoblend.fx.stable_fluids: eidoverse/fluid_sim.js for Blender 5.2: 2D screen-space stable fluids.

fluid_sim.js wraps the npm package three-fluid-fx 0.1.0 (its TSL edition: WGSLFluidSimulation plus its TSL
overlay and distortion nodes). This module ports that package's solver and effects and the wrapper's API:

    from eidoblend.fx.stable_fluids import create_fluid_sim
    fluid = create_fluid_sim(profile='balanced', curl_strength=0.55)     # fluid_sim.js createFluidSim(renderer, opts)
    fluid.resize(1920, 1080)                                             # the panel's aspect (splats stay round)

    def controls(frame, t, fluid):                                       # the engine's per-frame calls
        fluid.splat(0.5 + 0.3 * math.cos(t), 0.5, -40 * math.sin(t), 25, [0.9, 0.3, 0.6])
    fluid.bake(1, 240, controls=controls, cache_dir='//fluid_cache')    # step(1/fps) per frame -> EXR sequences
    panel = fluid.panel(size=(3.2, 1.8))                                 # densityNode as the panel's colour
    mat = fluid.overlay_node(scene_image, style='smoke')                 # an overlay composited over an image
    fluid.overlay_node('render', style='oil', target='compositor')       # ... or over the render itself
    fluid.distortion('render', 1.0, target='compositor')                 # simpleDistortion(scene, density)

The solver is the package's WGSL, kernel for kernel, in numpy on the WGSL's own texel layout (row 0 = top, uv
y up through sampleYUp): splat, curl, vorticity, divergence (reflective walls), pressure decay and Jacobi sweeps,
gradient subtract, semi-Lagrangian advection with the package's BFECC variant, dissipation scaled by dt /
baseDelta. Every kernel's output is rounded to half float, as its rgba16float storage was (precision='half').
Baked frames are OpenEXR half images (the textures as they were), played by Blender as image sequences, so a
saved .blend renders any frame with no Python.

The effects (overlays and distortions) are written once as node expressions and built either as a shader graph
(a panel material: the engine's material.colorNode use) or as a compositor graph over the render (its
post-processing outputNode use); see EFFECTS.

Licence. three-fluid-fx is MIT licensed and its kernels follow PavelDoGreat/WebGL-Fluid-Simulation (MIT); this
module is a translation of substantial portions of both, so their notices travel with it:

    MIT License. Copyright (c) 2026 Artem Korenevych (three-fluid-fx).
    MIT License. Copyright (c) 2017 Pavel Dobryakov (WebGL-Fluid-Simulation).

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without
    limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
    Software, and to permit persons to whom the Software is furnished to do so, subject to the following
    conditions: The above copyright notice and this permission notice shall be included in all copies or
    substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
    AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
    OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
    WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import math
import os
import random
import time as _time

import numpy as np

from ._util import abspath, frame_file, scene_fps

# ------------------------------------------------------------------------------------------------------------
# the solver: three-fluid-fx's WGSLFluidSimulation
# ------------------------------------------------------------------------------------------------------------

FLUID_PROFILES = {
    'performance': dict(sim_resolution=128, dye_resolution=256, pressure_iterations=6),
    'balanced': dict(sim_resolution=256, dye_resolution=512, pressure_iterations=12),
    'quality': dict(sim_resolution=384, dye_resolution=1024, pressure_iterations=20),
}


def _half(a):
    return a.astype(np.float16).astype(np.float32)


def _nbrs(c):
    """The four clamped neighbours of a (H, W) channel, as loadClamped reads them (WGSL layout, row 0 = top):
    L = (x-1, y), R = (x+1, y), T = (x, y-1) (the row above), B = (x, y+1)."""
    p = np.pad(c, 1, mode='edge')
    return p[1:-1, :-2], p[1:-1, 2:], p[:-2, 1:-1], p[2:, 1:-1]


def _sample_yup(t, u, v, channels):
    """sampleYUp: a linear, clamp-to-edge sample at uv (y up) of a row-0-top texture; returns the listed
    channels as a list of (H, W) arrays."""
    h, w = t.shape[:2]
    tx = u * np.float32(w) - np.float32(0.5)
    ty = (np.float32(1.0) - v) * np.float32(h) - np.float32(0.5)
    x0 = np.floor(tx)
    y0 = np.floor(ty)
    fx = tx - x0
    fy = ty - y0
    x0 = x0.astype(np.int32)
    y0 = y0.astype(np.int32)
    x0c, x1c = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    y0c, y1c = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    i00, i01, i10, i11 = y0c * w + x0c, y0c * w + x1c, y1c * w + x0c, y1c * w + x1c
    # all the listed channels gathered at once (one row gather per corner), the same float32 arithmetic per channel
    ch = list(channels)
    flat = t.reshape(-1, t.shape[2])
    sel = flat[:, ch] if ch != list(range(t.shape[2])) else flat
    gx, gy = (1 - fx)[..., None], fx[..., None]
    a = sel[i00] * gx + sel[i01] * gy
    b = sel[i10] * gx + sel[i11] * gy
    r = a * (1 - fy)[..., None] + b * fy[..., None]
    return [r[..., k] for k in range(len(ch))]


class FluidSimulation:
    """three-fluid-fx's (WGSL)FluidSimulation in numpy. Textures are (H, W, 4) float32 in the WGSL's layout
    (row 0 = the top row); uv has y up. Options and defaults are the package's, snake_case."""

    def __init__(self, profile='balanced', sim_resolution=None, dye_resolution=None, pressure_iterations=None,
                 density_dissipation=0.91, velocity_dissipation=0.985, pressure_dissipation=0.8, curl_strength=0.55,
                 splat_radius=42e-5, splat_force=6.0, base_delta=1 / 60, enable_vorticity=False, bfecc=True,
                 reflect_walls=True, dye_dissipation=None, enable_dye=False, precision='half'):
        if profile not in FLUID_PROFILES:
            raise ValueError(f'unknown profile {profile!r}: {", ".join(FLUID_PROFILES)}')
        p = FLUID_PROFILES[profile]
        self.sim_resolution = int(sim_resolution if sim_resolution is not None else p['sim_resolution'])
        self.dye_resolution = int(dye_resolution if dye_resolution is not None else p['dye_resolution'])
        self.pressure_iterations = int(pressure_iterations if pressure_iterations is not None
                                       else p['pressure_iterations'])
        self.density_dissipation = float(density_dissipation)
        self.velocity_dissipation = float(velocity_dissipation)
        self.pressure_dissipation = float(pressure_dissipation)
        self.curl_strength = float(curl_strength)
        self.splat_radius = float(splat_radius)
        self.splat_force = float(splat_force)
        self.base_delta = float(base_delta)
        self.enable_vorticity = bool(enable_vorticity)
        self.bfecc = bool(bfecc)
        self.reflect_walls = bool(reflect_walls)
        self.enable_dye = bool(enable_dye)
        self.dye_dissipation = float(dye_dissipation if dye_dissipation is not None else self.density_dissipation)
        self.half = precision == 'half'
        self.viewport_width = 1
        self.viewport_height = 1
        self.sim_width = self.sim_height = self.sim_resolution
        self.dye_width = self.dye_height = self.dye_resolution
        self.splats = []
        self._alloc()

    def _alloc(self):
        sw, sh, dw, dh = self.sim_width, self.sim_height, self.dye_width, self.dye_height
        z = lambda w, h: np.zeros((h, w, 4), dtype=np.float32)          # noqa: E731
        self.velocity, self.velocity_write = z(sw, sh), z(sw, sh)
        self.pressure = z(sw, sh)
        self.divergence = z(sw, sh)
        self.curl = z(sw, sh)
        self.density, self.density_write = z(dw, dh), z(dw, dh)
        self.dye = z(dw, dh)

    def _q(self, a):
        return _half(a) if self.half else a.astype(np.float32)

    # the package's public getters -------------------------------------------------------------------------
    @property
    def velocity_texture(self):
        return self.velocity

    @property
    def velocity_projected_texture(self):
        """The projected velocity before this step's advection (the package's velocity.write after step)."""
        return self.velocity_write

    @property
    def density_texture(self):
        return self.density

    @property
    def dye_texture(self):
        return self.dye

    def resize(self, width, height):
        """The panel or viewport size in pixels: the grids take its aspect (the long side keeps the resolution)
        and splats stay round. Reallocates (clears) when a grid size changes, as the package does."""
        self.viewport_width = max(1, int(width))
        self.viewport_height = max(1, int(height))
        aspect = self.viewport_width / self.viewport_height
        if aspect >= 1:
            sw, sh = self.sim_resolution, max(1, round(self.sim_resolution / aspect))
            dw, dh = self.dye_resolution, max(1, round(self.dye_resolution / aspect))
        else:
            sw, sh = max(1, round(self.sim_resolution * aspect)), self.sim_resolution
            dw, dh = max(1, round(self.dye_resolution * aspect)), self.dye_resolution
        if (sw, sh, dw, dh) != (self.sim_width, self.sim_height, self.dye_width, self.dye_height):
            self.sim_width, self.sim_height, self.dye_width, self.dye_height = sw, sh, dw, dh
            self._alloc()

    def add_splat(self, x, y, dx, dy, radius=None, color=None, dye_color=None):
        """Queue a splat at (x, y) in [0, 1] (y up) with velocity impulse (dx, dy). color tints DENSITY and, as
        the package does, is ALSO what the velocity receives (color defaults to (dx, dy, 1))."""
        self.splats.append(dict(x=min(1.0, max(0.0, float(x))), y=min(1.0, max(0.0, float(y))), dx=float(dx),
                                dy=float(dy), radius=self.splat_radius if radius is None else float(radius),
                                color=None if color is None else tuple(float(c) for c in color),
                                dye_color=None if dye_color is None else tuple(float(c) for c in dye_color)))

    # kernels ----------------------------------------------------------------------------------------------
    def _uv(self, w, h):
        """normalizedUvYUp of every texel of a (h, w) target (cached)."""
        key = (w, h)
        if getattr(self, '_uv_cache', None) is None:
            self._uv_cache = {}
        if key not in self._uv_cache:
            u = ((np.arange(w, dtype=np.float32) + 0.5) / w)[None, :].repeat(h, 0)
            v = (1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h)[:, None].repeat(w, 1)
            self._uv_cache[key] = (u, v)
        return self._uv_cache[key]

    def _splat(self, t, s, color):
        h, w = t.shape[:2]
        u, v = self._uv(w, h)
        half_size = max(1e-6, 3.0 * math.sqrt(s['radius']))
        aspect = self.viewport_width / self.viewport_height
        lx = (u - np.float32(s['x'])) * np.float32(2.0 * aspect / half_size)
        ly = (v - np.float32(s['y'])) * np.float32(2.0 / half_size)
        amount = np.clip(1.0 - np.sqrt(lx * lx + ly * ly), 0.0, 1.0) ** 2
        out = t.copy()
        for c in range(3):
            out[..., c] += np.float32(color[c]) * amount
        out[..., 3] += amount
        return self._q(out)

    def _curl(self):
        V = self.velocity
        L, R, _, _ = _nbrs(V[..., 1])
        _, _, T, B = _nbrs(V[..., 0])
        out = np.zeros_like(V)
        out[..., 0] = (R - L - T + B) * 0.5
        out[..., 3] = 1.0
        self.curl = self._q(out)

    def _vorticity(self, dt):
        C = self.curl[..., 0]
        L, R, T, B = _nbrs(C)
        fx = (np.abs(T) - np.abs(B)) * 0.5
        fy = (np.abs(R) - np.abs(L)) * 0.5
        ln = np.sqrt(fx * fx + fy * fy) + np.float32(0.0001)
        k = np.float32(self.curl_strength) * C / ln
        out = np.zeros_like(self.velocity)
        out[..., 0] = self.velocity[..., 0] + fx * k * np.float32(dt)
        out[..., 1] = self.velocity[..., 1] - fy * k * np.float32(dt)
        out[..., 3] = 1.0
        self.velocity_write = self._q(out)
        self.velocity, self.velocity_write = self.velocity_write, self.velocity

    def _divergence(self):
        V = self.velocity
        cx, cy = V[..., 0], V[..., 1]
        L, R, _, _ = (a.copy() for a in _nbrs(cx))
        _, _, T, B = (a.copy() for a in _nbrs(cy))
        if self.reflect_walls:
            L[:, 0] = -cx[:, 0]
            R[:, -1] = -cx[:, -1]
            T[0, :] = -cy[0, :]
            B[-1, :] = -cy[-1, :]
        out = np.zeros_like(V)
        out[..., 0] = (R - L + T - B) * 0.5
        out[..., 3] = 1.0
        self.divergence = self._q(out)

    def _pressure_sweep(self):
        L, R, T, B = _nbrs(self.pressure[..., 0])
        out = np.zeros_like(self.pressure)
        out[..., 0] = (L + R + B + T - self.divergence[..., 0]) * 0.25
        out[..., 3] = 1.0
        self.pressure = self._q(out)

    def _gradient_subtract(self):
        L, R, T, B = _nbrs(self.pressure[..., 0])
        out = np.zeros_like(self.velocity)
        out[..., 0] = self.velocity[..., 0] - (R - L)
        out[..., 1] = self.velocity[..., 1] - (T - B)
        out[..., 3] = 1.0
        self.velocity_write = self._q(out)
        self.velocity, self.velocity_write = self.velocity_write, self.velocity

    def _advect(self, src, dissipation, dt):
        h, w = src.shape[:2]
        u, v = self._uv(w, h)
        kx, ky = np.float32(dt / w), np.float32(dt / h)          # velocity * dt * texelSize (the TARGET's)
        V = self.velocity
        vx, vy = _sample_yup(V, u, v, (0, 1))
        cu, cv = u - vx * kx, v - vy * ky
        if self.bfecc:
            bx, by = _sample_yup(V, cu, cv, (0, 1))
            fu, fv = cu + bx * kx, cv + by * ky
            mu, mv = u - (fu - u) * 0.5, v - (fv - v) * 0.5
            mx, my = _sample_yup(V, mu, mv, (0, 1))
            cu, cv = mu - mx * kx, mv - my * ky
        out = np.empty_like(src)
        for c, a in enumerate(_sample_yup(src, cu, cv, (0, 1, 2))):
            out[..., c] = a * np.float32(dissipation)
        out[..., 3] = 1.0
        return self._q(out)

    # the step ---------------------------------------------------------------------------------------------
    def step(self, delta_seconds):
        """One frame: splats, vorticity, divergence, pressure (decay + Jacobi), projection, advection. dt is
        clamped to [1e-6, 1/60] as the package does (a 30 fps film advances 1/60 s a frame)."""
        dt = min(max(float(delta_seconds), 1e-6), 1 / 60)
        dts = dt / self.base_delta if self.base_delta > 0 else 1.0
        for s in self.splats:
            color = s['color'] if s['color'] is not None else (s['dx'], s['dy'], 1.0)
            self.velocity = self._splat(self.velocity, s, color)
            self.density = self._splat(self.density, s, color)
            if self.enable_dye and s['dye_color'] is not None:
                self.dye = self._splat(self.dye, s, s['dye_color'])
        self.splats = []
        if self.enable_vorticity:
            self._curl()
            self._vorticity(dt)
        self._divergence()
        self.pressure = self._q(self.pressure * (self.pressure_dissipation ** dts))
        for _ in range(self.pressure_iterations):
            self._pressure_sweep()
        self._gradient_subtract()
        new_vel = self._advect(self.velocity, self.velocity_dissipation ** dts, dt)
        self.velocity, self.velocity_write = new_vel, self.velocity
        self.density = self._advect(self.density, self.density_dissipation ** dts, dt)
        if self.enable_dye:
            self.dye = self._advect(self.dye, self.dye_dissipation ** dts, dt)

    def dispose(self):
        self.velocity = self.velocity_write = self.pressure = self.divergence = self.curl = None
        self.density = self.density_write = self.dye = None


# ------------------------------------------------------------------------------------------------------------
# attachPointerSplats: a pointer, driven by a path instead of DOM events
# ------------------------------------------------------------------------------------------------------------

def _hsv2rgb(h, s, v):
    i = math.floor(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]


class PointerSplats:
    """The package's attachPointerSplats(element, fluid, options), driven by a pointer PATH (a film has no mouse):
    pointer(t) -> (x, y) in [0, 1] (y up) or None (no pointer), sampled at `events_per_second` move events over
    the panel's pixel size. Each event runs the package's handler: the gap reset (> 200 ms), the < 0.25 px skip,
    the fire guard (a jump over 200 px faster than 6.5 px/ms starts a new stroke), dx, dy in pixels (y up) times
    fluid.splat_force, and the dye colour from colorize(dx, dy, t_ms) or the HSV stroke colour (x 0.3) cycling at
    color_update_speed when colored_strokes. Call it once per frame with the frame's time (create_fluid_sim's bake
    does, through attach_pointer_splats)."""

    def __init__(self, fluid, pointer, size=(1920, 1080), colored_strokes=False, color_update_speed=10.0,
                 colorize=None, events_per_second=60.0, seed=1):
        self.fluid = fluid
        self.pointer = pointer
        self.w, self.h = max(1, int(size[0])), max(1, int(size[1]))
        self.colored = bool(colored_strokes)
        self.speed = float(color_update_speed)
        self.colorize = colorize
        self.eps = float(events_per_second)
        self.rng = random.Random(seed)
        self.stroke = _hsv2rgb(self.rng.random(), 1, 1)
        self.color_timer = 0.0
        self.last = None            # (px, py) of the last event
        self.last_time = -1e9
        self.has = False
        self.last_fire = (0.0, 0.0)
        self.t_done = None

    def _event(self, t_ms, x01, y01):
        px, py = x01 * self.w, (1.0 - y01) * self.h          # client pixels (y down, as DOM events)
        gap = t_ms - self.last_time
        if gap > 200:
            self.has = False
        self.last_time = t_ms
        start = not self.has
        if self.colored:
            self.color_timer += min(max(gap, 0), 100) / 1e3 * self.speed
            if start or self.color_timer >= 1:
                if self.color_timer >= 1:
                    self.color_timer %= 1
                self.stroke = _hsv2rgb(self.rng.random(), 1, 1)
        dx = (px - self.last[0]) if (self.has and self.last) else 0.0
        dy = -(py - self.last[1]) if (self.has and self.last) else 0.0
        self.last = (px, py)
        self.has = True
        if abs(dx) + abs(dy) < 0.25:
            return
        lf = self.last_fire
        fire = math.hypot(px - lf[0], py - lf[1]) if (lf[0] or lf[1]) else 0.0
        if gap > 0 and fire / gap > 6.5 and fire > 200:
            self.has = False
            self.last_fire = (px, py)
            return
        self.last_fire = (px, py)
        force = self.fluid.splat_force
        dye = self.colorize(dx, dy, t_ms) if self.colorize else None
        if dye is None and self.colored:
            dye = [c * 0.3 for c in self.stroke]
        self.fluid.add_splat(x01, y01, dx * force, dy * force, dye_color=dye)

    def __call__(self, t):
        """Fire the move events of (t_prev, t] (seconds)."""
        t0 = self.t_done if self.t_done is not None else t - 1.0 / self.eps
        n = max(1, int(round((t - t0) * self.eps)))
        for k in range(1, n + 1):
            tk = t0 + (t - t0) * k / n
            p = self.pointer(tk)
            if p is None:
                self.has = False
                continue
            self._event(tk * 1000.0, float(p[0]), float(p[1]))
        self.t_done = t


def attach_pointer_splats(fluid, pointer, size=(1920, 1080), colored_strokes=False, color_update_speed=10.0,
                          colorize=None, events_per_second=60.0, seed=1):
    """fluid: a FluidSimulation (the engine passes fluid._raw). pointer: a callable t -> (x, y) | None, or a
    Blender object (its position projected through the scene camera onto the frame). Returns the PointerSplats;
    a FluidSim's bake calls it every frame when attached with fluid_sim.attach(...)."""
    if not callable(pointer):
        pointer = _object_pointer(pointer)
    return PointerSplats(fluid, pointer, size, colored_strokes, color_update_speed, colorize, events_per_second,
                         seed)


def _object_pointer(obj):
    """A pointer path from an object's world position through the scene camera (frame coordinates, y up)."""
    def at(t):
        import bpy
        from bpy_extras.object_utils import world_to_camera_view
        sc = bpy.context.scene
        fps = scene_fps(sc)
        f = sc.frame_start + t * fps
        fi = int(math.floor(f))
        sc.frame_set(fi, subframe=f - fi)
        co = world_to_camera_view(sc, sc.camera, obj.matrix_world.translation)
        if co.z <= 0:
            return None
        return (co.x, co.y)
    return at


# ------------------------------------------------------------------------------------------------------------
# effects: the package's overlay and distortion nodes, as shader or compositor graphs
# ------------------------------------------------------------------------------------------------------------

TAU = 6.28318530718


class _V3:
    """Three scalar node expressions (r, g, b) with component-wise arithmetic."""

    __slots__ = ('b', 'c')

    def __init__(self, b, x, y, z):
        self.b = b
        self.c = (b.s(x), b.s(y), b.s(z))

    @staticmethod
    def of(b, v):
        if isinstance(v, _V3):
            return v
        if isinstance(v, (tuple, list)):
            return _V3(b, *v)
        return _V3(b, v, v, v)

    def _zip(self, o, f):
        o = _V3.of(self.b, o)
        return _V3(self.b, *(f(a, c) for a, c in zip(self.c, o.c)))

    def __add__(self, o): return self._zip(o, lambda a, c: a + c)
    __radd__ = __add__
    def __sub__(self, o): return self._zip(o, lambda a, c: a - c)
    def __rsub__(self, o): return _V3.of(self.b, o) - self
    def __mul__(self, o): return self._zip(o, lambda a, c: a * c)
    __rmul__ = __mul__
    def __truediv__(self, o): return self._zip(o, lambda a, c: a / c)

    @property
    def x(self): return self.c[0]

    @property
    def y(self): return self.c[1]

    @property
    def z(self): return self.c[2]

    def dot(self, o):
        o = _V3.of(self.b, o)
        return self.c[0] * o.c[0] + self.c[1] * o.c[1] + self.c[2] * o.c[2]

    def length(self):
        return self.b.sqrt(self.dot(self))

    def clamp(self, lo, hi):
        return _V3(self.b, *(self.b.clamp(a, lo, hi) for a in self.c))

    def mix(self, o, t):
        return self + (_V3.of(self.b, o) - self) * t


class _Graph:
    """Where an effect is built: a shader graph (taps are Image Texture nodes at a UV) or a compositor graph (taps
    are Map UV nodes over Image nodes, the UV from Image Coordinates of the render)."""

    def __init__(self, tree, kind, sources, fps, frame_start, uv_source='UV'):
        from ._nodes import Builder
        self.tree = tree
        self.kind = kind
        self.b = Builder(tree, x0=-2400, y0=900)
        self.src = sources                    # name -> bpy image | 'render' | (r, g, b)
        self._img_nodes = {}
        b = self.b
        if kind == 'shader':
            tc = b.node('ShaderNodeTexCoord')
            u, v, _ = b.vec(tc.outputs[uv_source]).xyz()
        else:
            ic = b.node('CompositorNodeImageCoordinates')
            tree.links.new(self._render_socket(), ic.inputs['Image'])
            u, v, _ = b.vec(ic.outputs['Normalized']).xyz()
        self.uv = (u, v)
        if kind == 'shader':
            tnode = b.node('ShaderNodeValue')
            tnode.name = tnode.label = 'fluid.time'
            tnode.hide = False
            d = tnode.outputs[0].driver_add('default_value').driver
            d.type = 'SCRIPTED'
            d.expression = f'(frame - {int(frame_start)}) / {float(fps):.6g}'
            self.time = b.s(tnode.outputs[0])
        else:
            # the compositor's own clock (scene seconds = frame / fps), from the bake's first frame
            st = b.node('CompositorNodeSceneTime')
            self.time = b.s(st.outputs['Seconds']) - float(frame_start) / float(fps)

    def _render_socket(self):
        if 'render' not in self._img_nodes:
            rl = self.b.node('CompositorNodeRLayers')
            self._img_nodes['render'] = rl.outputs['Image']
        return self._img_nodes['render']

    def _image_socket(self, img):
        key = ('img', img.name)
        if key not in self._img_nodes:
            n = self.b.node('CompositorNodeImage')
            n.image = img
            _setup_sequence_user(n, img)
            self._img_nodes[key] = n.outputs['Image']
        return self._img_nodes[key]

    def split(self, sock):
        """(r, g, b) scalars of a colour socket."""
        b = self.b
        if self.kind == 'shader':
            r, g, bb = b.vec(sock).xyz()
            return r, g, bb
        n = b.node('CompositorNodeSeparateColor')
        self.tree.links.new(sock, n.inputs['Image'])
        return b.s(n.outputs['Red']), b.s(n.outputs['Green']), b.s(n.outputs['Blue'])

    def join(self, v3):
        b = self.b
        if self.kind == 'shader':
            return b.combine(*v3.c).v
        n = b.node('CompositorNodeCombineColor')
        for nm, c in zip(('Red', 'Green', 'Blue'), v3.c):
            b.link(c, n.inputs[nm])
        n.inputs['Alpha'].default_value = 1.0
        return n.outputs['Image']

    def tap(self, name, u, v):
        """The rgb of source `name` at uv."""
        s = self.src[name]
        b = self.b
        if isinstance(s, (tuple, list)):
            return _V3(b, *s[:3])
        # Map UV reads its UV in the UV pass's layout: (u, v, mask), a zero third component masks the pixel out
        uvv = b.combine(u, v, 0.0 if self.kind == 'shader' else 1.0)
        if self.kind == 'shader':
            n = b.node('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
            n.image = s
            _setup_sequence_user(n, s)
            b.link(uvv, n.inputs['Vector'])
            return _V3(b, *self.split(n.outputs['Color']))
        img = self._render_socket() if s == 'render' else self._image_socket(s)
        m = b.node('CompositorNodeMapUV')
        self.tree.links.new(img, m.inputs['Image'])
        b.link(uvv, m.inputs['UV'])
        for nm, val in (('Interpolation', 'Bilinear'), ('Extension X', 'Extend'), ('Extension Y', 'Extend')):
            try:
                m.inputs[nm].default_value = val
            except Exception:
                pass
        return _V3(b, *self.split(m.outputs['Image']))


def _setup_sequence_user(node, img):
    """An image sequence plays with the scene frame (frame f shows file f): Image Texture and compositor Image
    nodes alike."""
    if img.source != 'SEQUENCE':
        return
    iu = node.image_user if hasattr(node, 'image_user') else node
    iu.frame_start = int(img.get('fluid_frame_start', 1))
    iu.frame_duration = int(img.get('fluid_frame_count', 1))
    iu.frame_offset = int(img.get('fluid_frame_start', 1)) - 1
    iu.use_auto_refresh = True
    iu.use_cyclic = False


def _hsv2rgb_nodes(b, h, s, v):
    """The TSL hsv2rgb: p = |fract(h + K) * 6 - 3|, rgb = v * mix(1, clamp(p - 1), s), K = (1, 2/3, 1/3)."""
    out = []
    for k in (1.0, 2.0 / 3.0, 1.0 / 3.0):
        p = b.abs(b.fract(h + k) * 6.0 - 3.0)
        out.append(v * (1.0 + (b.clamp(p - 1.0) - 1.0) * s))
    return _V3(b, *out)


def _vibrant(b, col, amount):
    lum = col.dot((0.299, 0.587, 0.114))
    return _V3(b, lum, lum, lum).mix(col, 1.0 + amount).clamp(0.0, 1.0)


def _palette(b, phase):
    p = b.fract(phase)
    return _V3(b, b.sin(p * TAU) * 0.5 + 0.5, b.sin((p + 0.333) * TAU) * 0.5 + 0.5,
               b.sin((p + 0.666) * TAU) * 0.5 + 0.5)


def _oil_palette(b, phase):
    ember, mint, cream = (1.0, 0.33, 0.2), (0.08, 0.78, 0.68), (1.0, 0.84, 0.55)
    return _V3.of(b, ember).mix(cream, b.smoothstep(0.15, 0.85, phase)).mix(mint, b.smoothstep(0.55, 1.0, phase)
                                                                            * 0.42)


OVERLAY_STYLES = ('default', 'volumeCursor', 'trail', 'oil', 'velocity', 'colorful', 'rainbowFish', 'glaze',
                  'burn', 'smoke', 'artInk', 'rainbowInk', 'colorWater', 'liquidLens')
OVERLAY_DEFAULTS = dict(intensity=1.0, time=None, texel=(1 / 512, 1 / 512), cursor_color=(0.85, 0.95, 1.0),
                        vibrance=0.0, velocity_scale=1.0, opacity=1.0)


def _overlay(g, style, o):
    """FluidOverlayNode.setup(): every style, as written in the package (sources: scene, density, dye, velocity)."""
    b = g.b
    u, v = g.uv
    I = o['intensity']
    T = g.time if o['time'] is None else o['time']
    tx, ty = o['texel']
    cursor = _V3.of(b, o['cursor_color'])
    vib = o['vibrance']
    dens = g.tap('density', u, v)
    density = b.clamp(dens.z, 0.0, 1.0)
    velx, vely = dens.x, dens.y                        # the density texture's rg (the splat's colour or impulse)
    scene = g.tap('scene', u, v)
    speed = b.sqrt(velx * velx + vely * vely)
    cache = {}

    def dye5():
        if 'dye' not in cache:
            d = g.tap('dye', u, v) * 0.5
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                d = d + g.tap('dye', u + tx * sx, v + ty * sy) * 0.125
            amp = d.length()
            cache['dye'] = (d, amp, (d / (amp + 1e-5)).clamp(0.0, 1.0))
        return cache['dye']

    def composite(over):
        return scene.mix(over, b.clamp(o['opacity'], 0.0, 1.0))

    if style == 'default':
        far = None
        for ox, oy in ((tx * 8, 0.0), (-tx * 8, 0.0), (0.0, ty * 8), (0.0, -ty * 8)):
            ln = g.tap('dye', u + ox, v + oy).length()
            far = ln if far is None else far + ln
        far = far * 0.25
        _, amp, _ = dye5()
        core = b.smoothstep(0.02, 0.55, far * I * 4.0)
        kinetic = b.clamp(speed * 0.02, 0.0, 1.0)
        tint = _vibrant(b, cursor * (0.48 + core * 0.52) + kinetic * 0.12, vib)
        alpha = b.clamp(amp * I * 3.0, 0.0, 0.95)
        return composite(scene.mix(tint, alpha))
    if style == 'volumeCursor':
        gx = g.tap('dye', u + tx * 1.5, v).length() - g.tap('dye', u - tx * 1.5, v).length()
        gy = g.tap('dye', u, v + ty * 1.5).length() - g.tap('dye', u, v - ty * 1.5).length()
        gl = b.sqrt(gx * gx + gy * gy) + 1e-4
        lit = b.clamp((gx / gl * -0.6 + gy / gl * 0.8) * 0.5 + 0.5, 0.2, 1.0)
        _, amp, _ = dye5()
        shade = b.pow(amp, 0.42) * lit
        tint = _vibrant(b, (cursor * (0.3 + shade * 1.1)).clamp(0.0, 1.0), vib)
        alpha = b.clamp(amp * I * 2.2, 0.0, 0.88)
        return composite(scene.mix(tint, alpha))
    if style == 'trail':
        tail, ws = None, 0.0
        for i in range(1, 8):
            w = 1 - i / 8
            d = g.tap('density', u - velx * (i * 0.04), v - vely * (i * 0.04)).z * w
            tail = d if tail is None else tail + d
            ws += w
        tail = tail / ws
        head = b.pow(density, 4.0)
        glow = (tail * 0.7 + head * 1.4) * I
        return composite(scene + _vibrant(b, cursor, vib) * glow)
    if style == 'oil':
        trail = density
        for i in range(1, 6):
            trail = trail + g.tap('density', u - velx * (i * 0.035), v - vely * (i * 0.035)).z * (1 - i / 7)
        glow = b.clamp(trail * I, 0.0, 1.0)
        col = _vibrant(b, _oil_palette(b, b.fract(glow * 0.62 + speed * 0.015 + T * 0.025)), vib)
        alpha = b.clamp(glow * 0.58 + speed * 0.012, 0.0, 0.86)
        additive = scene + col * alpha * 0.86
        return composite(additive.mix(col, alpha * 0.14))
    if style == 'velocity':
        vs = g.tap('velocity', u, v)
        sx, sy = vs.x * o['velocity_scale'] * 0.04 * I, vs.y * o['velocity_scale'] * 0.04 * I
        ln = b.clamp(b.sqrt(sx * sx + sy * sy), 0.0, 1.0)
        return composite(scene + _V3(b, sx * 1.5 + 0.1, sy * 1.5 + 0.1, 1.0) * ln)
    if style == 'colorful':
        glow, col = None, None
        for i in range(6):
            ou, ov = u - velx * (i * 0.035), v - vely * (i * 0.035)
            w = g.tap('density', ou, ov).z * (1 - i / 7)
            glow = w if glow is None else glow + w
            ha = ou * 1.6 + ov * 0.9 + T * 0.05
            hb = ov * 1.2 - ou * 0.4 - T * 0.03
            ca = _hsv2rgb_nodes(b, b.fract(ha), 0.9, 1.0)
            cb = _hsv2rgb_nodes(b, b.fract(hb), 0.85, 0.95)
            c = ca.mix(cb, 0.5) * w
            col = c if col is None else col + c
        col = col / b.max(glow, 1e-4)
        amount = b.clamp(glow * I * 0.55, 0.0, 1.4)
        return composite(scene + _vibrant(b, col, vib) * amount)
    if style == 'rainbowFish':
        vs = g.tap('velocity', u, v)
        fx, fy = vs.x * o['velocity_scale'] * 0.04, vs.y * o['velocity_scale'] * 0.04
        fs = b.sqrt(fx * fx + fy * fy)
        ang = b.math('ARCTAN2', fy, fx)
        ca = _hsv2rgb_nodes(b, b.fract(ang / TAU + 0.5 + T * 0.05), 0.92, 1.0)
        cb = _hsv2rgb_nodes(b, b.fract(u * 1.2 + v * 0.8 + T * 0.04), 0.7, 0.95)
        col = _vibrant(b, ca.mix(cb, 0.35), vib)
        s = b.clamp(fs * 8.0, 0.0, 1.0)
        return composite(scene + col * (b.pow(s, 2.5) * 1.6 * I))
    if style == 'glaze':
        return composite(scene + _vibrant(b, _V3(b, 1.0, 0.45, 0.22), vib) * (density * I))
    if style == 'burn':
        fingers = None
        for i in range(5):
            d = g.tap('density', u - velx * ((i + 1) * 0.05), v - vely * ((i + 1) * 0.05)).z * (1 - i / 5)
            fingers = d if fingers is None else fingers + d
        fingers = fingers * I
        fc = b.clamp(fingers, 0.0, 1.0)
        burn, ember = (1.0, 0.3, 0.0), (0.8, 0.15, 0.0)
        fire = _V3.of(b, ember).mix(burn, fc) + _V3.of(b, burn) * (fc * fc * 2.0)
        smoke = fingers * 0.3
        fire = fire + _V3(b, 0.1, 0.1, 0.15) * smoke
        flicker = b.sin(T * 15.0 + fingers * 20.0) * 0.2 + 0.8
        fire = fire * flicker
        alpha = b.clamp(fingers * 0.5 * flicker + smoke * 0.2, 0.0, 0.85)
        return composite(scene.mix(_vibrant(b, fire, vib), alpha))
    if style == 'smoke':
        _, amp, _ = dye5()
        alpha = b.clamp(amp * I * 2.6, 0.0, 0.78)
        smoke = _V3(b, 0.9, 0.92, 0.94) * (0.22 + alpha * 0.9)
        return composite(scene.mix(smoke, alpha))
    if style == 'artInk':
        _, amp, hue = dye5()
        alpha = b.clamp(amp * I * 2.2, 0.0, 1.0)
        return composite(scene + _vibrant(b, hue, vib) * (alpha * 1.55))
    if style == 'rainbowInk':
        _, amp, hue = dye5()
        phase = u * 0.45 + v * 0.35 + amp * 0.2 + T * 0.03
        tint = _vibrant(b, hue.mix(_palette(b, phase), 0.45), vib)
        alpha = b.clamp(amp * I * 2.35, 0.0, 1.0)
        return composite(scene + tint * (alpha * 1.35))
    if style == 'colorWater':
        _, amp, hue = dye5()
        alpha = b.clamp(amp * I * 2.1, 0.0, 0.72)
        wash = scene.mix(_vibrant(b, hue, vib), alpha)
        return composite(wash + scene * hue * (alpha * 0.35))
    # liquidLens: the package's fallthrough (any other style name lands here too)
    _, amp, hue = dye5()
    gate = b.clamp(amp * 4.0, 0.0, 1.0)
    refr = g.tap('scene', u + velx * gate * 0.012, v + vely * gate * 0.012)
    tint = (_vibrant(b, hue, vib) * (amp * I * 1.4)).clamp(0.0, 1.6)
    return composite(refr + refr * tint)


def _density_tint(g, o):
    """DensityTintOverlayNode: scene + tint * density.b * intensity (defaults 0.14 and teal)."""
    b = g.b
    u, v = g.uv
    scene = g.tap('scene', u, v)
    d = b.clamp(g.tap('density', u, v).z, 0.0, 1.0)
    return scene + _V3.of(b, o.get('tint', (0.1, 0.42, 0.36))) * (d * o.get('intensity', 0.14))


def _caustic_web(b, ru, rv, t):
    INTEN = 5e-3
    pu, pv = b.mod(ru * TAU, TAU) - 250.0, b.mod(rv * TAU, TAU) - 250.0
    iu, iv = pu, pv
    c = b.s(1.0)
    for n in range(5):
        tt = t * (1 - 3.5 / (n + 1))
        iu, iv = (pu + (b.cos(tt - iu) + b.sin(tt + iv)), pv + (b.sin(tt - iv) + b.cos(tt + iu)))
        dx = b.sin(iu + tt) / INTEN
        dy = b.cos(iv + tt) / INTEN
        lu, lv = pu / dx, pv / dy
        c = c + 1.0 / b.sqrt(lu * lu + lv * lv)
    c = c / 5.0
    c = 1.17 - b.pow(c, 1.4)
    return b.clamp(b.pow(b.abs(c), 8.0), 0.0, 1.0)


DISTORTIONS = ('simple', 'chromatic', 'rgbShift', 'water', 'waterCaustics')


def _distortion(g, kind, intensity, inv_size, time=None):
    """The package's distortion nodes (sources: scene, fluid = the density texture: rg velocity-ish, b density)."""
    b = g.b
    u, v = g.uv
    I = intensity
    if kind == 'simple':
        f = g.tap('fluid', u, v)
        du = b.clamp(u - f.x * I * 3e-4, 0.0, 1.0)
        dv = b.clamp(v - f.y * I * 3e-4, 0.0, 1.0)
        return g.tap('scene', du, dv)
    if kind == 'rgbShift':
        f = g.tap('fluid', u, v)
        d = b.clamp(f.z, 0.0, 1.0)
        sp = b.max(b.sqrt(f.x * f.x + f.y * f.y), 1e-4)
        st = b.pow(d, 1.4) * I * 0.012
        sx, sy = f.x / sp * st, f.y / sp * st
        return _V3(b, g.tap('scene', u + sx, v + sy).x, g.tap('scene', u, v).y, g.tap('scene', u - sx, v - sy).z)
    ix, iy = inv_size
    if kind == 'chromatic':
        c = g.tap('fluid', u, v) * 0.36
        for ox, oy in ((2 * ix, 0), (-2 * ix, 0), (0, 2 * iy), (0, -2 * iy)):
            c = c + g.tap('fluid', u + ox, v + oy) * 0.16
        d = b.clamp(c.z, 0.0, 1.0)
        fall = b.pow(d, 1.2)
        chx, chy = c.x * 3e-3 * I * fall, c.y * 3e-3 * I * fall
        du, dv = u - c.x * 2e-4 * I * fall, v - c.y * 2e-4 * I * fall
        return _V3(b, g.tap('scene', du + chx, dv + chy).x, g.tap('scene', du - chx, dv + chy).y,
                   g.tap('scene', du - chx, dv - chy).z)
    hL = g.tap('fluid', u - 2 * ix, v).z
    hR = g.tap('fluid', u + 2 * ix, v).z
    hD = g.tap('fluid', u, v - 2 * iy).z
    hU = g.tap('fluid', u, v + 2 * iy).z
    nx, ny = hR - hL, hU - hD
    ou, ov = nx * I * 0.6, ny * I * 0.6
    col = _V3(b, g.tap('scene', u + ou * 0.95, v + ov * 0.95).x, g.tap('scene', u + ou, v + ov).y,
              g.tap('scene', u + ou * 1.05, v + ov * 1.05).z)
    if kind == 'water':
        return col
    if kind != 'waterCaustics':
        raise ValueError(f'unknown distortion {kind!r}: {", ".join(DISTORTIONS)}')
    T = g.time if time is None else time
    fc = g.tap('fluid', u, v)
    surface = b.smoothstep(0.015, 0.16, fc.z)
    slope = b.smoothstep(15e-4, 0.04, b.sqrt(nx * nx + ny * ny))
    web = _caustic_web(b, u * 4.0 + fc.x * 12e-4, v * 4.0 + fc.y * 12e-4, T * 0.5 + 23.0)
    caustic = _V3(b, web, web + 0.35, web + 0.5).clamp(0.0, 1.0)
    energy = b.pow(web, 1.25) * surface * (slope * 0.6 + 0.4)
    return col + caustic * (energy * I * 0.38)


EFFECTS = {('overlay', s): s for s in OVERLAY_STYLES}
EFFECTS.update({('overlay', 'densityTint'): 'densityTint'})
EFFECTS.update({('distortion', d): d for d in DISTORTIONS})


# ------------------------------------------------------------------------------------------------------------
# fluid_sim.js: createFluidSim and its API
# ------------------------------------------------------------------------------------------------------------

class FluidSim:
    """What create_fluid_sim returns (fluid_sim.js's object). step, splat, resize; density / velocity / dye (the
    live numpy textures, the engine's *Node getters); after bake(): images (the EXR sequences as Blender images),
    panel(), overlay_node(), distortion(); overlays (EFFECTS); raw (the FluidSimulation, the engine's _raw)."""

    def __init__(self, sim, name):
        self.raw = sim
        self._raw = sim
        self.name = name
        self.images = {}
        self.pointers = []
        self.frame_start = 1
        self.frame_count = 0
        self.fps = 24.0
        self.overlays = EFFECTS

    # the engine's methods ---------------------------------------------------------------------------------
    def step(self, dt=None):
        self.raw.step(1 / 60 if dt is None else dt)

    def splat(self, x, y, dx, dy, color=None):
        """fluid_sim.js splat(): the colour tints DENSITY and the dye (color AND dyeColor = color)."""
        self.raw.add_splat(x, y, dx, dy, color=color, dye_color=color)

    def resize(self, w, h):
        self.raw.resize(w, h)

    @property
    def density(self):
        return self.raw.density

    @property
    def velocity(self):
        return self.raw.velocity

    @property
    def dye(self):
        return self.raw.dye

    # the engine's sampleable TextureNodes: here the baked image sequences (None before bake() or load_bake())
    @property
    def density_node(self):
        """densityNode: the coloured ink, the main display (a Blender image sequence, rgba as stored)."""
        return self.images.get('density')

    @property
    def velocity_node(self):
        """velocityNode: the 2D velocity field (rg)."""
        return self.images.get('velocity')

    @property
    def dye_node(self):
        """dyeNode: the dye field (fluid_sim.js turns dye on, so it carries the splat colours too)."""
        return self.images.get('dye')

    def load_bake(self, cache_dir, frame_start, frame_end, fields=('density', 'dye', 'velocity'), scene=None):
        """Attach a bake made earlier (its EXR sequences in cache_dir) without re-simulating: the images, panel(),
        material(), overlay_node() and distortion() then play it."""
        import bpy
        d = abspath(cache_dir)
        fs, fe = int(frame_start), int(frame_end)
        self.frame_start, self.frame_count = fs, fe - fs + 1
        self.fps = scene_fps(scene or bpy.context.scene)
        for fld in fields:
            p = frame_file(d, f'{self.name}_{fld}', fs, 'exr')
            if not os.path.exists(p):
                raise FileNotFoundError(p)
            self.images[fld] = _load_sequence(p, f'{self.name}_{fld}', fs, fe - fs + 1)
        return self

    # the bake (the Blender edition's frame loop) ----------------------------------------------------------
    def attach(self, pointer, **options):
        """attachPointerSplats on this fluid's raw simulation, fired by every baked frame."""
        p = attach_pointer_splats(self.raw, pointer, **options)
        self.pointers.append(p)
        return p

    def bake(self, frame_start=None, frame_end=None, controls=None, cache_dir='//fluid_cache', scene=None,
             fields=('density', 'dye', 'velocity'), log=print):
        """Per frame: pointers, controls(frame, t, fluid), step(1/fps), then write each field as an OpenEXR half
        image <cache>/<name>_<field>_####.exr (rgba, the texture as stored). A hold copy as frame start - 1 keeps
        sub-frames and frame start - 1 off magenta. Loads the sequences as Blender images (fluid.images)."""
        import bpy
        from ._util import write_exr
        sc = scene or bpy.context.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = scene_fps(sc)
        self.fps, self.frame_start, self.frame_count = fps, fs, fe - fs + 1
        d = abspath(cache_dir)
        os.makedirs(d, exist_ok=True)
        t0 = _time.time()
        for f in range(fs, fe + 1):
            t = (f - fs) / fps
            for p in self.pointers:
                p(t)
            if controls:
                controls(f, t, self)
            self.raw.step(1.0 / fps)
            for fld in fields:
                a = getattr(self.raw, fld)
                write_exr(frame_file(d, f'{self.name}_{fld}', f, 'exr'), a[::-1], half=True)
                if f == fs:
                    write_exr(frame_file(d, f'{self.name}_{fld}', f - 1, 'exr'), a[::-1], half=True)
            if (f - fs) % 48 == 0:
                log(f'[fluid] frame {f}  density max {float(self.raw.density[..., 2].max()):.3f}  '
                    f'{_time.time() - t0:.1f} s')
        for fld in fields:
            self.images[fld] = _load_sequence(frame_file(d, f'{self.name}_{fld}', fs, 'exr'), f'{self.name}_{fld}',
                                              fs, fe - fs + 1)
        log(f'[fluid] baked frames {fs}..{fe} in {_time.time() - t0:.1f} s -> {d}')
        return self

    # display ----------------------------------------------------------------------------------------------
    def panel(self, size=(3.2, 1.8), location=(0, 0, 1), rotation=(math.radians(90), 0, 0), name=None,
              strength=1.0, scene=None):
        """The engine's display example: a plane whose material's colour IS densityNode (unlit)."""
        import bpy
        sc = scene or bpy.context.scene
        mat = self.material(lambda g: g.tap('density', *g.uv), name=(name or self.name) + '_panel',
                            strength=strength)
        return _plane(sc, name or (self.name + '_panel'), size, location, rotation, mat)

    def material(self, build, name, strength=1.0, scene_src=None):
        """A panel material from an effect builder build(graph) -> _V3: emission (unlit, as MeshBasic was)."""
        import bpy
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (1600, 0)
        srcs = dict(self.images)
        srcs['scene'] = scene_src if scene_src is not None else (0.0, 0.0, 0.0)
        srcs['fluid'] = self.images.get('density')
        g = _Graph(nt, 'shader', srcs, self.fps, self.frame_start)
        col = build(g)
        em = nt.nodes.new('ShaderNodeEmission')
        em.location = (1300, 0)
        g.b.link(g.join(col), em.inputs['Color'])
        em.inputs['Strength'].default_value = strength
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        return mat

    def compositor(self, build, scene=None, name=None, scene_src='render'):
        """Install an effect over the render: scene.compositing_node_group = RLayers -> effect -> Group Output."""
        import bpy
        sc = scene or bpy.context.scene
        tree = bpy.data.node_groups.new(name or (self.name + '_compose'), 'CompositorNodeTree')
        sc.compositing_node_group = tree
        sc.render.use_compositing = True
        tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        srcs = dict(self.images)
        srcs['scene'] = scene_src
        srcs['fluid'] = self.images.get('density')
        g = _Graph(tree, 'compositor', srcs, self.fps, self.frame_start)
        col = build(g)
        go = tree.nodes.new('NodeGroupOutput')
        go.location = (1600, 0)
        tree.links.new(g.join(col), go.inputs[0])
        return tree

    def overlay_node(self, scene_node=(0.0, 0.0, 0.0), style='colorful', target='material', **opts):
        """fluid_sim.js overlayNode(sceneNode, {style, ...}): the package's <style>Overlay composited over
        scene_node (a colour, a Blender image, or 'render' with target='compositor'). Unknown styles fall back to
        colorful, as the wrapper does; 'densityTint' runs DensityTintOverlay with its defaults (the wrapper passes
        the dye node where that function takes its options)."""
        o = dict(OVERLAY_DEFAULTS)
        o.update({k: v for k, v in opts.items() if k in OVERLAY_DEFAULTS})
        if style == 'densityTint':
            build = lambda g: _density_tint(g, {})                       # noqa: E731
        else:
            st = style if style in OVERLAY_STYLES else 'colorful'
            build = lambda g: _overlay(g, st, o)                         # noqa: E731
        return self._target(build, scene_node, target, f'{self.name}_overlay_{style}')

    def fluid_overlay(self, style, scene_node=(0.0, 0.0, 0.0), target='material', **opts):
        """The package's fluidOverlay(style, ...): the overlay chain of any style, including the liquidLens
        fallthrough (styles the package does not name land there too)."""
        o = dict(OVERLAY_DEFAULTS)
        o.update({k: v for k, v in opts.items() if k in OVERLAY_DEFAULTS})
        return self._target(lambda g: _overlay(g, style, o), scene_node, target, f'{self.name}_fluid_{style}')

    def density_tint_overlay(self, scene_node=(0.0, 0.0, 0.0), target='material', intensity=0.14,
                             tint=(0.1, 0.42, 0.36)):
        """The package's densityTintOverlay(scene, fluid, {intensity, tint})."""
        return self._target(lambda g: _density_tint(g, dict(intensity=intensity, tint=tint)), scene_node, target,
                            f'{self.name}_densityTint')

    def distortion(self, scene_node=(0.0, 0.0, 0.0), strength=1.0, kind='simple', target='material', time=None):
        """fluid_sim.js distortion(sceneNode, strength) = simpleDistortion(scene, densityNode, strength); kind
        picks the package's other distortions (chromatic, rgbShift, water, waterCaustics) on the same fluid."""
        dens = self.raw.density
        inv = (1.0 / dens.shape[1], 1.0 / dens.shape[0])
        return self._target(lambda g: _distortion(g, kind, strength, inv, time), scene_node, target,
                            f'{self.name}_distortion_{kind}')

    def _target(self, build, scene_node, target, name):
        if target == 'compositor':
            return self.compositor(build, name=name, scene_src=scene_node)
        if scene_node == 'render':
            raise ValueError("scene_node='render' needs target='compositor'")
        return self.material(build, name, scene_src=scene_node)

    def dispose(self):
        self.raw.dispose()


def _load_sequence(first_path, name, frame_start, count):
    import bpy
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.load(first_path)
    img.name = name
    img.source = 'SEQUENCE'
    img.colorspace_settings.is_data = True
    img['fluid_frame_start'] = int(frame_start)
    img['fluid_frame_count'] = int(count)
    return img


def _plane(sc, name, size, location, rotation, mat):
    import bpy
    w, h = size
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [],
                   [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, (a, c) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = (a, c)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = location
    ob.rotation_euler = rotation
    return ob


def create_fluid_sim(profile='balanced', enable_dye=True, enable_vorticity=True, curl_strength=None,
                     density_dissipation=None, velocity_dissipation=None, dye_dissipation=None, splat_radius=None,
                     splat_force=None, bfecc=None, reflect_walls=None, name='fluid', **advanced):
    """fluid_sim.js createFluidSim(renderer, opts): profile 'balanced', dye and vorticity ON (the wrapper's
    choice), the other options passed only when given (the package's defaults otherwise). advanced: the
    package's remaining options (sim_resolution, dye_resolution, pressure_iterations, pressure_dissipation,
    base_delta, precision)."""
    kw = dict(profile=profile, enable_dye=enable_dye, enable_vorticity=enable_vorticity)
    for k, v in (('curl_strength', curl_strength), ('density_dissipation', density_dissipation),
                 ('velocity_dissipation', velocity_dissipation), ('dye_dissipation', dye_dissipation),
                 ('splat_radius', splat_radius), ('splat_force', splat_force), ('bfecc', bfecc),
                 ('reflect_walls', reflect_walls)):
        if v is not None:
            kw[k] = v
    kw.update(advanced)
    return FluidSim(FluidSimulation(**kw), name)


__all__ = ['FLUID_PROFILES', 'FluidSimulation', 'FluidSim', 'create_fluid_sim', 'attach_pointer_splats',
           'PointerSplats', 'OVERLAY_STYLES', 'OVERLAY_DEFAULTS', 'DISTORTIONS', 'EFFECTS']
