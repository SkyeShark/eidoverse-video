"""look/post/after_image.py: three's afterImage() as a compositor pass (effects_tsl/after_image.js): a frame-feedback
trail, each frame's light lingering and fading.

    e = fx.apply_to(scene, 'after_image', {'after_image': {'damp': 0.96, 'opacity': 1.0}})
    e.uniforms['damp'].default_value = 0.9            # shorter trails; keyable like any input

three's AfterImageNode keeps its own previous output on the GPU: trail = max(new, old x damp), where `old` is cleared
per channel below 0.1 (its mask: max(sign(old - 0.1), 0)), and the pass shows mix(frame, trail, opacity) with the
frame's alpha. A compositor has no previous frame, so here `old` is this pass's own trail a frame earlier, written to
disk by a File Output every frame and read back by an Image node (look/post/history.py): the per-frame compositing
pass over the saved previous output. It is exact when the frames render in order (an animation render, or stills
one after another); a frame rendered alone reads whatever trail the frame before it last wrote. On the scene's first
frame the trail starts from the frame itself, as the WebGPU node's empty buffer did. The WebGPU effect does not reset
at camera cuts, and neither does this one (e.cut() restarts it if a film wants that).
Cost, measured in tests/post_era/test_after_image.py: one half-float DWAA EXR written and one read per frame.
"""
from __future__ import annotations

from ._graph import fn

GROUP = 'eido_after_image'


def build(rebuild=False):
    def body(g, a):
        # NaN -> 0 and +Inf -> 65504 on both sides: a non-finite pixel recorded in the trail would otherwise come
        # back every frame after (the feedback keeps it)
        new = g.sanitize(g.c(a['Image']), hi=65504.0)
        old_rgba = a['Old']
        old = g.sanitize(g.c(old_rgba), hi=65504.0) * (1.0 - a['Fresh'])
        oa = g.alpha(old_rgba) * (1.0 - a['Fresh'])
        na = g.alpha(a['Image'])
        damp = a['damp']
        # m: 1 where the old value is above 0.1 (sign(old - 0.1) clamped at 0), per channel
        m = g.step(g.v((0.1, 0.1, 0.1)), old) * (1.0 - g.step(old, g.v((0.1, 0.1, 0.1))))
        trail = g.max(new, old * damp * m)
        ma = g.step(0.1, oa) * (1.0 - g.step(oa, 0.1))
        trail_a = g.max(na, oa * damp * ma)
        shown = g.mix(new, trail, a['opacity'])
        return {'Image': g.rgba(shown, na), 'Trail': g.rgba(trail, trail_a)}
    ins = [('Image', 'C', (0, 0, 0, 1)), ('Old', 'C', (0, 0, 0, 0)), ('damp', 'S', 0.96), ('opacity', 'S', 1.0),
           ('Fresh', 'S', 0.0)]
    return fn(GROUP, ins, [('Image', 'C'), ('Trail', 'C')], body, rebuild=rebuild, version=2)


def make(scene, o, stage='after_image', layer='over'):
    """Put the pass in the chain (custom_effects.apply_to calls this): its trail recorded every frame and read back a
    frame later. Returns (node, {damp, opacity}, [History])."""
    from . import chain, history as HI
    grp = build()
    t = chain.tree(scene)
    node = t.nodes.new('CompositorNodeGroup')
    node.node_tree = grp
    chain.add_stage(scene, layer, stage, node)
    h = HI.History(scene, f'{stage}_trail', tree=t)
    h.feed(node.outputs['Trail'])
    img, _present = h.tap(t, 1)
    t.links.new(img, node.inputs['Old'])
    cuts = o.get('cuts')
    h.set_cuts([] if cuts is None else cuts, t, fresh=node.inputs['Fresh'])
    U = {'damp': node.inputs['damp'], 'opacity': node.inputs['opacity']}
    U['damp'].default_value = float(o.get('damp', 0.96))
    U['opacity'].default_value = float(o.get('opacity', 1.0))
    return node, U, [h]
