"""look/post/display.py: display space inside the compositor, the scene's own view transform and its inverse.

The WebGPU print and paint passes (era looks' halftone / toon / watercolor, all of aeropittura) paint in DISPLAY
space: toDisp = the renderer's own ACES at its exposure, fromDisp = its exact inverse, so a paper or ink colour lands
on screen as authored. Here the renderer's tone map is the scene's view transform (AgX and its look), so:

    to_disp(g, c, ev)   = sRGB -> linear ( Convert To Display ( c * 2^ev ) )         display-LINEAR, as toDisp gave
    from_disp(g, d, ev) = Convert To Display (Invert) ( linear -> sRGB ( clamp(d) ) ) / 2^ev

ev is the scene's exposure, carried as a group input that a driver keeps equal to scene.view_settings.exposure
(Convert To Display's own exposure is read-only, stack-notes.md). The nodes copy the scene's view transform, look
and display when built; sync(scene) copies them again (the era and aeropittura passes call it when applied, and
FX.update() does). A view set later would land paper and ink through the wrong curve (measured: the poster's bare
newsprint 16 levels off after the look goes from AgX Base Contrast to Punchy, 0.08 once synced), so
keep_synced() (turned on by those passes) syncs each scene before every render and save in this session, and
stale(scene) lists the nodes that differ. Measured on the meadow frame: through Convert To Display and its
inverse, the worst pixel came back within 0.016 (linear); the 'AgX Base sRGB' colour-space pair was 3x worse
(0.053), so the view node pair it is.
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


def trees_of(scene):
    """The scene's compositor tree and every group it uses, nested groups included: the trees its render composites
    with. (The function groups are shared between scenes that use the same pass.)"""
    out, todo = [], [scene.compositing_node_group] if scene.compositing_node_group else []
    while todo:
        t = todo.pop()
        if t is None or t in out:
            continue
        out.append(t)
        todo += [n.node_tree for n in t.nodes if n.bl_idname == 'CompositorNodeGroup' and n.node_tree is not None]
    return out


def _display_nodes(trees):
    for t in trees:
        for n in t.nodes:
            if n.bl_idname == 'CompositorNodeConvertToDisplay' and n.get(TAG):
                yield n


def stale(scene, trees=None):
    """The display nodes of the scene's own trees whose view transform, look or display differ from the scene's: the
    view settings changed after the pass was applied (a config's render block setting the look, a set_view call), so
    paper and ink would land through the wrong curve. [] when every one matches; sync() fixes the rest."""
    vs, ds = scene.view_settings, scene.display_settings
    return [n for n in _display_nodes(trees if trees is not None else trees_of(scene))
            if (n.display_settings.display_device, n.view_settings.view_transform, n.view_settings.look)
            != (ds.display_device, vs.view_transform, vs.look)]


def sync(scene, trees=None):
    """Copy the scene's view transform, look and display into the display nodes of the given trees (default: the
    trees the scene composites with, trees_of(scene): another scene's view never leaks into this one's). Only nodes
    that differ are touched. Warns about view settings the pair does not carry (gamma, curves). Returns how many
    display nodes the trees hold."""
    vs, ds = scene.view_settings, scene.display_settings
    if abs(vs.gamma - 1.0) > 1e-6:
        print(f'[look.post.display] warning: view gamma {vs.gamma} is not carried into display-space looks', flush=True)
    if vs.use_curve_mapping:
        print('[look.post.display] warning: view curves are not carried into display-space looks', flush=True)
    nodes = list(_display_nodes(trees if trees is not None else trees_of(scene)))
    for n in nodes:
        if n.display_settings.display_device != ds.display_device:
            n.display_settings.display_device = ds.display_device
        if n.view_settings.view_transform != vs.view_transform:
            n.view_settings.view_transform = vs.view_transform
        if n.view_settings.look != vs.look:
            n.view_settings.look = vs.look
    return len(nodes)


@bpy.app.handlers.persistent
def _sync_before_render(scene, *_a):
    """render_pre: a scene about to render gets its display nodes onto its current view (only when they differ)."""
    try:
        if scene is not None and stale(scene):
            n = len(stale(scene))
            sync(scene)
            print(f'[look.post.display] {scene.name}: {n} display node(s) copied onto the view '
                  f'{scene.view_settings.view_transform} / {scene.view_settings.look} before rendering', flush=True)
    except Exception as e:                                     # noqa: BLE001 - never stop a render over this
        print(f'[look.post.display] warning: could not sync the display nodes before rendering: {e}', flush=True)


@bpy.app.handlers.persistent
def _sync_before_save(*_a):
    """save_pre: every scene's display nodes onto its view, so a saved .blend renders as authored on its own."""
    for sc in bpy.data.scenes:
        try:
            if stale(sc):
                sync(sc)
        except Exception as e:                                 # noqa: BLE001
            print(f'[look.post.display] warning: could not sync {sc.name} before saving: {e}', flush=True)


def keep_synced(enable=True):
    """While this Python session renders or saves, copy each scene's view transform, look and display into its
    display nodes first (render_pre, save_pre), so a view set after a pass was applied (the harness's config render
    block, a later set_view) still lands paper and ink as authored. The era and aeropittura passes turn it on when
    applied. A .blend rendered from the command line has no handler: it renders with the nodes as saved, and the
    save synced them."""
    for hs, fn_ in ((bpy.app.handlers.render_pre, _sync_before_render), (bpy.app.handlers.save_pre, _sync_before_save)):
        for h in [h for h in hs if getattr(h, '__name__', '') == fn_.__name__]:
            hs.remove(h)
        if enable:
            hs.append(fn_)


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
