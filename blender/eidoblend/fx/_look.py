"""The engine's display, matched under the film's view transform.

The engine rendered its fire through three.js's ACESFilmicToneMapping (exposure 2): bright red and orange run
to orange, yellow, then white. The Blender edition renders through AgX, whose path to white for the same red
runs through salmon and pink, so the engine's fire ramp would read pink. A display match keeps the engine's
look: for an emission colour family c(t) (the fire ramp) and a strength s, it finds the scene-linear emission
whose display under the scene's own view (its view transform, display, exposure and look, through Blender's
own OCIO config) equals what three's ACES showed for c(t) * s, and stores it per unit s in a small 2D table
(t across, log2 s up). Shaders then look the table up instead of emitting c(t) * s.

Three's ACES (ACESFilmicToneMapping):
    v = c * exposure / 0.6;  v = IN * v;  v = (v (v + .0245786) - .000090537) / (v (.983729 v + .432951) + .238081)
    v = clamp(OUT * v, 0, 1), then the sRGB transfer for the canvas
Blender multiplies scene-linear values by 2^exposure before its view, so three's exposure 0.6 * 2^ev is the
same scene: the match is made at the scene's own exposure.
"""

from __future__ import annotations

import os

import numpy as np

_IN = np.array([[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]])
_OUT = np.array([[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]])


def three_aces(rgb, exposure=1.0):
    """three.js ACESFilmicToneMapping of linear Rec.709 `rgb` (..., 3), then the sRGB transfer: the display
    values the engine's canvas showed."""
    v = np.asarray(rgb, dtype=np.float64) * (exposure / 0.6)
    v = v @ _IN.T
    a = v * (v + 0.0245786) - 0.000090537
    b = v * (0.983729 * v + 0.4329510) + 0.238081
    v = np.clip((a / b) @ _OUT.T, 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)


class SceneView:
    """The scene's display pipeline as numpy functions (Blender's own OCIO config): to_display(x) is what a
    render shows for scene-linear x, from_display(d) its inverse (refined by Newton steps on to_display and
    kept non-negative)."""

    def __init__(self, scene):
        import bpy
        import PyOpenColorIO as ocio
        path = os.environ.get('OCIO') or os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles',
                                                      'colormanagement', 'config.ocio')
        cfg = ocio.Config.CreateFromFile(path)
        vs, ds = scene.view_settings, scene.display_settings
        self.exposure = float(vs.exposure)
        self.gamma = float(vs.gamma)
        src = cfg.getColorSpace(ocio.ROLE_SCENE_LINEAR).getName()
        steps = []
        self.look = vs.look if vs.look not in ('None', '') else None
        if self.look is not None:
            steps.append(ocio.LookTransform(src=src, dst=src, looks=self.look))
        steps.append(ocio.DisplayViewTransform(src=src, display=ds.display_device, view=vs.view_transform))
        fwd = ocio.GroupTransform(steps) if len(steps) > 1 else steps[0]
        self._fwd = cfg.getProcessor(fwd).getDefaultCPUProcessor()
        inv = ocio.GroupTransform(steps) if len(steps) > 1 else steps[0]
        inv.setDirection(ocio.TRANSFORM_DIR_INVERSE)
        self._inv = cfg.getProcessor(inv).getDefaultCPUProcessor()
        self.name = f'{vs.view_transform} / {ds.display_device}' + (f' / {self.look}' if self.look else '')
        if vs.use_curve_mapping:
            print('[fx.look] warning: the scene\'s curve mapping is not part of the display match')

    def _apply(self, proc, a):
        a = np.ascontiguousarray(np.asarray(a, dtype=np.float32).reshape(-1, 3)).copy()
        proc.applyRGB(a)
        return a

    def to_display(self, x):
        x = np.asarray(x, dtype=np.float64)
        d = self._apply(self._fwd, x * 2.0 ** self.exposure).astype(np.float64)
        if self.gamma != 1.0:
            d = np.power(np.maximum(d, 0.0), 1.0 / self.gamma)
        return d.reshape(x.shape)

    def from_display(self, d, iterations=40):
        """Scene-linear x >= 0 whose display is d, least squares where d is out of the view's reach (AgX cannot
        show ACES's most saturated bright oranges): OCIO's inverse as the start, then Levenberg-Marquardt steps
        on to_display, each kept only where it lowers the error."""
        d = np.asarray(d, dtype=np.float64).reshape(-1, 3)
        dg = np.power(np.maximum(d, 0.0), self.gamma) if self.gamma != 1.0 else d
        x_max = 1e4 / 2.0 ** self.exposure
        x = np.clip(self._apply(self._inv, dg).astype(np.float64) / 2.0 ** self.exposure, 0.0, x_max)
        f0 = self.to_display(x)
        cost = ((d - f0) ** 2).sum(axis=1)
        lam = np.full(len(x), 1e-3)
        eye = np.eye(3)[None]
        for _ in range(iterations):
            live = cost > 1e-9
            if not live.any():
                break
            hstep = np.maximum(x * 1e-3, 1e-6)
            J = np.empty((len(x), 3, 3))
            for k in range(3):
                xp = x.copy()
                xp[:, k] += hstep[:, k]
                J[:, :, k] = (self.to_display(xp) - f0) / hstep[:, k:k + 1]
            J = np.nan_to_num(J, nan=0.0, posinf=0.0, neginf=0.0)
            A = np.einsum('nij,nik->njk', J, J)
            g = np.einsum('nij,ni->nj', J, d - f0)
            diag = np.maximum(np.einsum('nii->ni', A), 1e-9)[..., None] * eye
            dx = np.einsum('nij,nj->ni', np.linalg.pinv(A + lam[:, None, None] * diag), g)
            xn = np.clip(x + dx, 0.0, x_max)
            fn = self.to_display(xn)
            cn = ((d - fn) ** 2).sum(axis=1)
            ok = (cn < cost) & live
            x[ok], f0[ok], cost[ok] = xn[ok], fn[ok], cn[ok]
            lam = np.where(ok, lam / 3.0, lam * 4.0)
        return x


def match_table(colors, view, path=1.0, s_range=(-14.0, 10.0), n_s=128, engine_exposure=None):
    """The display-match table for the colour family `colors` (n_t, 3) (linear Rec.709, c(t) at t = i/(n_t-1)).

    Entry [j, i] is the scene-linear emission PER UNIT s at t_i, s_j = 2^(s_lo + j (s_hi - s_lo)/(n_s - 1)),
    whose display under `view`, gathered over `path` metres (1 for a surface), equals three's ACES display of
    c(t_i) * s_j * path at the same exposure. engine_exposure overrides three's exposure (default 0.6 * 2^ev)."""
    colors = np.asarray(colors, dtype=np.float64)
    s_lo, s_hi = s_range
    s = 2.0 ** np.linspace(s_lo, s_hi, n_s)
    X = (0.6 * 2.0 ** view.exposure) if engine_exposure is None else engine_exposure
    E = colors[None, :, :] * (s[:, None, None] * path)                     # (n_s, n_t, 3) pixel radiance
    target = three_aces(E, X)
    x = view.from_display(target.reshape(-1, 3)).reshape(E.shape)
    err = np.abs(view.to_display(x.reshape(-1, 3)).reshape(E.shape) - target)
    table = x / (s[:, None, None] * path)
    return table.astype(np.float32), float(err.max()), float(err.mean())


def table_image(name, table, directory):
    """Write the table as an OpenEXR data image (row 0 = s_lo) and load it into Blender, non-colour."""
    import bpy
    from ._util import write_exr
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name + '.exr')
    write_exr(path, table)
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.load(path)
    img.name = name
    img.colorspace_settings.is_data = True
    return img


def lookup(b, img, t, s, s_range, n_t, n_s):
    """Shader nodes: the table's emission for family position t (0..1) and strength s (Expr), as a Vec."""
    s_lo, s_hi = s_range
    u = b.clamp(t) * ((n_t - 1) / n_t) + 0.5 / n_t
    ls = b.math('LOGARITHM', b.max(s, 2.0 ** s_lo), 2.0)
    v = b.clamp((ls - s_lo) / (s_hi - s_lo)) * ((n_s - 1) / n_s) + 0.5 / n_s
    tex = b.node('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
    tex.image = img
    b.link(b.combine(u, v, 0.0), tex.inputs['Vector'])
    return b.vscale(b.vec(tex.outputs['Color']), s)
