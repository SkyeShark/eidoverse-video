"""The 2D moisture history (Eanpa Engine engine/rain_accumulation_field.js), in numpy. No bpy.

A world-aligned history of thin wetness and pooled water around the camera. Both integrate the same local cloud
supply as the drops (cell_at x rain), then dry on their own: thin wetness arrives first (tau 7 s) and dries in ~70 s,
pooled water fills later (tau 32 s) and outlasts the rain (tau 150 s). A dry cloud gap stays dry under a rainy global
target; overcast humidity with no rain damps surfaces without making puddles.

Same stepping as the GPU field: the history refreshes every `refresh_seconds` (0.25 s) on a grid snapped to whole
texels, recentres (keeping the overlapping history) when the camera moves more than radius / 4, clears when time runs
backwards, and between refreshes every displayed frame advances the last published state analytically, so wetness
never steps at 4 Hz. Coordinates are Blender world metres: the grid lies on (x, y), and cell_at(x, y) is sampled at
reference height zero, as the GPU field samples its columns.
"""
import math

import numpy as np


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class RainAccumulationField:
    """makeRainAccumulationField: prepare(camera_xy, time, rain, wet_target), sample(x, y), image(), reset()."""

    def __init__(self, cell_at, radius=1024.0, resolution=256, refresh_seconds=0.25):
        self.cell_at = cell_at
        self.size = max(64, int(round(resolution)))
        self.radius = float(radius)
        self.span = self.radius * 2
        self.texel = self.span / self.size
        self.refresh_seconds = float(refresh_seconds)
        self.state = np.zeros((self.size, self.size, 4), np.float64)     # [row = y, col = x]: wet, water, desired x2
        self.center = np.zeros(2)
        self.previous_center = np.zeros(2)
        self.ready = False
        self.blend = np.zeros(4)
        self.last_time = -math.inf
        self.disposed = False
        self.stats = dict(captures=0, resolution=self.size, radiusMeters=self.radius,
                          refreshSeconds=self.refresh_seconds, historyBytes=self.size * self.size * 8 * 2,
                          ready=False, lastUpdateSeconds=None)

    # ---- the blend factors of the time since the last refresh ----
    def _set_elapsed(self, time):
        dt = max(0.0, time - self.last_time) if math.isfinite(self.last_time) else 0.0
        self.blend = np.array([-math.expm1(-dt / 7), -math.expm1(-dt / 70),
                               -math.expm1(-dt / 32), -math.expm1(-dt / 150)])

    @staticmethod
    def _advance(state, blend):
        r, g, b, a = state[..., 0], state[..., 1], state[..., 2], state[..., 3]
        wet = r + (b - r) * np.where(b > r, blend[0], blend[1])
        water = g + (a - g) * np.where(a > g, blend[2], blend[3])
        return np.stack([wet, water], axis=-1)

    def _world_grid(self, center):
        i = (np.arange(self.size) + 0.5) / self.size
        u, v = np.meshgrid(i, i)                              # u along x (columns), v along y (rows)
        return (u - 0.5) * self.span + center[0], (v - 0.5) * self.span + center[1]

    def prepare(self, camera_xy, time, rain, wet_target, force=False, active=True):
        """One refresh opportunity (call every frame, before sampling). Returns True when the history was updated."""
        if self.disposed or camera_xy is None:
            return False
        self._set_elapsed(time)
        if not force and not active:
            return False
        rewound = time < self.last_time
        cx, cy = float(camera_xy[0]), float(camera_xy[1])
        next_center = np.array([math.floor(cx / self.texel) * self.texel, math.floor(cy / self.texel) * self.texel])
        moved = max(abs(cx - self.center[0]), abs(cy - self.center[1])) > self.radius * 0.25
        if not force and self.ready and not rewound and not moved and time - self.last_time < self.refresh_seconds:
            return False
        self.previous_center = self.center.copy()
        if not self.ready or moved or rewound:
            self.center = next_center
        if rewound:
            self.ready = False
        x, y = self._world_grid(self.center)
        moisture = np.zeros((self.size, self.size, 2))
        if self.ready:
            ou = (x - self.previous_center[0]) / self.span + 0.5
            ov = (y - self.previous_center[1]) / self.span + 0.5
            inside = (ou >= 0) & (ov >= 0) & (ou < 1) & (ov < 1)
            ci = np.clip(np.floor(ou * self.size).astype(int), 0, self.size - 1)
            ri = np.clip(np.floor(ov * self.size).astype(int), 0, self.size - 1)
            old = self.state[ri, ci]                     # integer texel copy: no refiltering while recentring
            moisture = np.where(inside[..., None], self._advance(old, self.blend), 0.0)
        supply = _smoothstep(0.0, 0.10, np.asarray(self.cell_at(x, y), np.float64) * rain)
        damp = wet_target if rain <= 0.001 else 0.0
        desired_wet = np.clip(np.maximum(wet_target * supply, damp), 0.0, 1.0)
        desired_water = np.clip(math.pow(max(wet_target, 0.0), 1.8) * supply, 0.0, 1.0)
        self.state = np.concatenate([moisture, desired_wet[..., None], desired_water[..., None]], axis=-1)
        self.last_time = time
        self.blend = np.zeros(4)
        self.ready = True
        self.stats.update(ready=True, captures=self.stats['captures'] + 1, lastUpdateSeconds=time)
        return True

    def displayed(self):
        """(wet, water) of every texel as a receiver sees it this frame: the published state advanced by the time
        since the refresh, faded to zero over the outer fifth of the field. Shape (size, size, 2), row = y."""
        if not self.ready:
            return np.zeros((self.size, self.size, 2))
        val = self._advance(self.state, self.blend)
        i = (np.arange(self.size) + 0.5) / self.size
        u, v = np.meshgrid(i, i)
        edge = np.maximum(np.abs(u - 0.5), np.abs(v - 0.5))
        return val * (1.0 - _smoothstep(0.4, 0.5, edge))[..., None]

    def sample(self, x, y):
        """accumulation.sample(world): (wet, water) at Blender world (x, y), with the GPU field's sampler-free
        bilinear reconstruction of the published state, advanced, and the edge fade."""
        x = np.atleast_1d(np.asarray(x, np.float64))
        y = np.atleast_1d(np.asarray(y, np.float64))
        out = np.zeros(x.shape + (2,))
        if not self.ready:
            return out
        u = (x - self.center[0]) / self.span + 0.5
        v = (y - self.center[1]) / self.span + 0.5
        inside = (u >= 0) & (v >= 0) & (u < 1) & (v < 1)
        pu, pv = u * self.size - 0.5, v * self.size - 0.5
        iu, iv = np.floor(pu), np.floor(pv)
        fu, fv = (pu - iu)[..., None], (pv - iv)[..., None]

        def load(du, dv):
            c = np.clip(iu + du, 0, self.size - 1).astype(int)
            r = np.clip(iv + dv, 0, self.size - 1).astype(int)
            return self.state[r, c]

        st = (load(0, 0) * (1 - fu) + load(1, 0) * fu) * (1 - fv) + (load(0, 1) * (1 - fu) + load(1, 1) * fu) * fv
        edge = np.maximum(np.abs(u - 0.5), np.abs(v - 0.5))
        val = self._advance(st, self.blend) * (1.0 - _smoothstep(0.4, 0.5, edge))[..., None]
        return np.where(inside[..., None], val, 0.0)

    def bounds(self):
        """(x0, y0, x1, y1) world rectangle the field covers now."""
        return (self.center[0] - self.radius, self.center[1] - self.radius,
                self.center[0] + self.radius, self.center[1] + self.radius)

    def reset(self):
        self.last_time = -math.inf
        self.ready = False
        self.blend = np.zeros(4)
        self.stats.update(ready=False, lastUpdateSeconds=None)

    def dispose(self):
        self.disposed = True
        self.ready = False
        self.stats['ready'] = False
