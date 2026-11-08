"""cloud_spatial: the Eanpa 'balanced' tier's current-frame spatial sky downsample, in the Blender edition.

WebGPU (eidoverse/cloud_spatial.js) renders the sky domes into private offscreen targets at 1/div of the frame for the
CURRENT camera, with no temporal history, and composites them back through screen-space proxy shells at the domes' draw
slots. The Blender edition already works that way by construction: bake() renders each frame's camera layer for that
frame's camera alone, at a resolution of its own, and EEVEE composites it through the world (by direction, filtered),
so the WebGPU pass maps onto the bake's layer scale. This module keeps the WebGPU surface for scenes that use it:

    spatial = make_spatial_cloud_pass(sky, div=2)     # attach happens here: the sky's layers bake at 1/div
    spatial.set_divisor(3); spatial.get_resolution()  # {'width', 'height', 'divisor'} of the camera layer
    spatial.render()                                  # nothing per frame: sky.bake() renders the layers
    spatial.dispose()                                 # back to full resolution

The WebGPU-only parts have nothing to drive here: render targets, MRT stamps, tone-map flags, the proxy meshes and the
EANPA_SPATIAL_DIAG debug modes (the layer itself is the debug view: blender/tests/sky/inspect_exr.py).
"""
import math


class SpatialCloudPass:
    mode = 'spatial-current-frame-sky'

    def __init__(self, sky, div=2, width=None, height=None):
        self.sky = sky
        self.divisor = max(1, int(round(div)))
        self.base = (width, height)
        self.disposed = False
        self.attached = False
        self.attach(sky)

    def _size(self):
        sc = self.sky.scene
        pct = sc.render.resolution_percentage / 100.0
        w = self.base[0] or int(sc.render.resolution_x * pct)
        h = self.base[1] or int(sc.render.resolution_y * pct)
        return w, h

    def attach(self, sky=None, *_):
        if self.disposed or self.attached:
            return False
        self.sky = sky or self.sky
        self.sky.layer_scale = 1.0 / self.divisor
        self.attached = True
        return True

    def render(self):
        """Per frame in WebGPU; here sky.bake() renders every frame's layers at the pass's scale."""
        return None

    def resize(self, w=None, h=None):
        if not self.disposed:
            self.base = (w or self.base[0], h or self.base[1])

    def get_divisor(self):
        return self.divisor

    def set_divisor(self, nxt):
        if self.disposed:
            return False
        resolved = max(1, int(round(nxt)))
        if resolved == self.divisor:
            return False
        self.divisor = resolved
        self.sky.layer_scale = 1.0 / resolved
        return True

    def get_resolution(self):
        w, h = self._size()
        return dict(width=max(1, math.ceil(w / self.divisor)), height=max(1, math.ceil(h / self.divisor)),
                    divisor=self.divisor)

    def dispose(self):
        if self.disposed:
            return
        self.disposed = True
        self.sky.layer_scale = 1.0


def make_spatial_cloud_pass(sky, div=2, width=None, height=None):
    return SpatialCloudPass(sky, div, width, height)
