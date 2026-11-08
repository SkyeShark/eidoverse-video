"""look/post/display.py: display space inside the compositor, the scene's own view transform and its inverse.

The WebGPU print and paint passes (era looks' halftone / toon / watercolor, all of aeropittura) paint in DISPLAY
space: toDisp = the renderer's own ACES at its exposure, fromDisp = its exact inverse, so a paper or ink colour lands
on screen as authored. Here the renderer's tone map is the scene's view transform (AgX and its look), so:

    to_disp(g, c, ev)   = sRGB -> linear ( Convert To Display ( c * 2^ev ) )         display-LINEAR, as toDisp gave
    from_disp(g, d, ev) = Convert To Display (Invert) ( linear -> sRGB ( clamp(d) ) ) / 2^ev

ev is the scene's exposure, carried as a group input that a driver keeps equal to scene.view_settings.exposure
(Convert To Display's own exposure is read-only, stack-notes.md). The nodes copy the scene's view transform, look
and display when built; sync(scene) copies them again (apply_to and FX.update call it). Measured 11-07 on the meadow
frame: through Convert To Display and its inverse, the worst pixel came back within 0.016 (linear); the
'AgX Base sRGB' colour-space pair was 3x worse (0.053), so the view node pair it is.
"""
from __future__ import annotations

import bpy

from ._graph import V

TAG = 'eido_display'


def _ctd(g, invert):
    n = g.node('CompositorNodeConvertToDisplay')
    n[TAG] = 'inv' if invert else 'fwd'
    n.inputs['Invert'].default_value = bool(invert)
    return n


def _ccs(g, src, dst):
    n = g.node('CompositorNodeConvertColorSpace')
    n.from_color_space = src
    n.to_color_space = dst
    return n


def _exposure(g, img, ev, sign=1.0):
    n = g.node('CompositorNodeExposure')
    g.link(img, n.inputs['Image'])
    if sign == 1.0:
        g.link(ev, n.inputs['Exposure'])
    else:
        g.link(-g.s(ev), n.inputs['Exposure'])
    return n.outputs['Image']


def to_disp(g, c, ev):
    """Scene-linear colour field -> display-linear (the view's output, sRGB transfer undone)."""
    a = _exposure(g, g.image(c) if not isinstance(c, bpy.types.NodeSocket) else c, ev)
    n = _ctd(g, False)
    g.link(a, n.inputs['Image'])
    lin = _ccs(g, 'sRGB', 'Linear Rec.709')
    g.link(n.outputs['Image'], lin.inputs['Image'])
    return V(g, lin.outputs['Image'])


def from_disp(g, d, ev):
    """Display-linear colour field (clamped to 0..1) -> the scene-linear colour the view shows as it."""
    d = g.clamp(g.v(d), 0.0, 1.0)
    enc = _ccs(g, 'Linear Rec.709', 'sRGB')
    g.link(d, enc.inputs['Image'])
    n = _ctd(g, True)
    g.link(enc.outputs['Image'], n.inputs['Image'])
    return V(g, _exposure(g, n.outputs['Image'], ev, -1.0))


def sync(scene, trees=None):
    """Copy the scene's view transform, look and display into every display node of the given trees (default: every
    compositor group). Warns about view settings the pair does not carry (gamma, curves)."""
    vs, ds = scene.view_settings, scene.display_settings
    if abs(vs.gamma - 1.0) > 1e-6:
        print(f'[look.post.display] warning: view gamma {vs.gamma} is not carried into display-space looks', flush=True)
    if vs.use_curve_mapping:
        print('[look.post.display] warning: view curves are not carried into display-space looks', flush=True)
    n_set = 0
    for t in (trees or [t for t in bpy.data.node_groups if t.bl_idname == 'CompositorNodeTree']):
        for n in t.nodes:
            if n.bl_idname == 'CompositorNodeConvertToDisplay' and n.get(TAG):
                n.display_settings.display_device = ds.display_device
                n.view_settings.view_transform = vs.view_transform
                n.view_settings.look = vs.look
                n_set += 1
    return n_set


def drive_exposure(scene, socket):
    """A driver keeping a group node's exposure input equal to the scene's view exposure (keyed exposure follows)."""
    try:
        socket.driver_remove('default_value')
    except (TypeError, RuntimeError):
        pass
    fc = socket.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    var = d.variables.new()
    var.name = 'ev'
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = scene
    var.targets[0].data_path = 'view_settings.exposure'
    d.expression = 'ev'
    socket.default_value = scene.view_settings.exposure
    return fc
