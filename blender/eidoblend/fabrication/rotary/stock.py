"""Solid subtraction in stock-local coordinates, with seekable history: the port of eidoverse/robotics/rotary_stock.js
(createRotaryStock; indexRotarySweeps lives in sweeps.py).

    from eidoblend.fabrication.rotary.stock import create_rotary_stock
    stock = create_rotary_stock(program.path, program.settings, parent=frame, resolution=(256, 96, 96),
                                cache_dir='//rotary_cache')
    stock.update(program.path.sample(t))     # the carved field at that moment (rewinding rebuilds it)
    stock.write_frame(frame)                 # this frame's field -> <cache>/<name>_<frame>.vdb, played by the mesh
    stock.mesh                               # the carved block: a mesh object meshed from the frame's field
    stock.to_mesh('carved')                  # a static mesh of the current field (to keep, edit or export)

THE FIELD. As in the WebGPU edition: a clamped signed distance (negative inside the stock) on a vertex-centred grid
over the blank plus a two-cell pad: resolution (nx, ny, nz) counts samples along the stock's X (length), Y (width)
and Z (height), Blender's axis order; eps = max(L / (nx - 4), W / (ny - 4), H / (nz - 4)), pad 2 eps, values clamped
to +-3 eps. The WebGPU [nx, ny, nz] counted three's axes (length, height, width): a non-square resolution ported
from a scene file swaps its last two numbers (WebGPU [256, 80, 96] is (256, 96, 80) here). It starts
as the prepared blank (box, centre seat and pilot) and takes, for every cutting stroke up to the sampled one (that
one only to its fraction), the maximum with minus the swept cutter's distance. Strokes only ever remove, so an
update applies the strokes since the last one; going back in time rebuilds from the blank. The WebGPU edition did
this per frame in a fragment pass over a 3D field tiled into 2D half-float targets and drew the result by ray
marching a proxy box; here numpy evaluates the same distances in float64 (each stroke over only the voxels its sweep
can reach), and the surface is a real mesh: Blender's OpenVDB volume-to-mesh of the field, so it casts and takes
shadows, has real depth, blurs as it turns with the chuck, and renders under every light. Its object space is the
stock frame; its finish (fabrication.cutting.finish_stock) reads the stock point as (z, y, x) in three's axes, the
WebGPU stock's swizzle, through swizzle_finish, and fades its fine patterns by their true screen footprint, the
WebGPU fwidth(phase), through filter_finish.

PLAYBACK. Nothing runs at render time. write_frame(frame) stores the field as an OpenVDB grid ('density' = minus the
distance, positive inside, pruned to tiles) in <cache_dir>/<name>_<frame:04d>.vdb; the stock's Volume datablock plays
that file sequence (EXTEND: the first and last held outside it) and the stock mesh object's Volume to Mesh modifier
meshes the current file at the zero level. Blender shows a file sequence at floor(time); a driver on the sequence's
frame offset makes every time within half a frame of a written frame show that frame's file, so the motion-blur
samples of a frame (and its sub-frame keys, carve.RotaryJob.key) all see the same carved surface. Write every frame
the film shows; a saved .blend then plays and renders any frame on its own, with the cache folder beside it.
"""

from __future__ import annotations

import bisect
import math
import os

import numpy as np

from .removal import blank_distance_np
from .sweeps import cutter_frame, index_rotary_sweeps, stroke_bounds, sweep_core

GRID_NAME = 'density'
GRAIN_NODE = 'rotary grain (z, y, x)'
FOOTPRINT_NODE = 'exact footprint'


def swizzle_finish(material):
    """Give the stock's finish the point the WebGPU rotary stock gave finishStock: its stock-local hit point as
    (z, y, x) in three's axes, so the long grain and the growth rings run along the rotary axis.

    finish_stock (eidoblend.fabrication.cutting) reads three's (x, y, z) from the Texture Coordinate node's Object
    output o as (ox, oz, -oy). With the stock surface's object space equal to stock space s, feeding it
    (-sy, -sx, sz) makes it read (-sy, sz, sx): three's (z, y, x), exactly. That swizzle is a reflection, so it lives
    in the material (Separate XYZ, two negations, Combine XYZ), not in the object's transform. Returns the number of
    links rerouted (0 when the material has no Object coordinates, or already has the swizzle)."""
    nt = material.node_tree
    if nt is None or GRAIN_NODE in nt.nodes:
        return 0
    n = 0
    for tc in [nd for nd in nt.nodes if nd.type == 'TEX_COORD']:
        links = [lk for lk in nt.links if lk.from_node == tc and lk.from_socket.identifier == 'Object']
        if not links:
            continue
        x0, y0 = tc.location.x + 180, tc.location.y - 220
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        sep.location = (x0, y0)
        neg = []
        for k, axis in enumerate(('X', 'Y')):
            m = nt.nodes.new('ShaderNodeMath')
            m.operation = 'MULTIPLY'
            m.inputs[1].default_value = -1.0
            m.location = (x0 + 170, y0 - 90 * k)
            nt.links.new(sep.outputs[axis], m.inputs[0])
            neg.append(m)
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        comb.name = comb.label = GRAIN_NODE
        comb.location = (x0 + 340, y0)
        nt.links.new(tc.outputs['Object'], sep.inputs[0])
        nt.links.new(neg[1].outputs[0], comb.inputs['X'])          # -sy
        nt.links.new(neg[0].outputs[0], comb.inputs['Y'])          # -sx
        nt.links.new(sep.outputs['Z'], comb.inputs['Z'])           # sz
        for lk in links:
            to = lk.to_socket
            nt.links.remove(lk)
            nt.links.new(comb.outputs[0], to)
            n += 1
    return n


# finish_stock's fine patterns, by the frequency it multiplies its footprint estimate with
PATTERNS = {4200.0: 'growth rings', 18000.0: 'wood fibre', 83000.0: 'metal brushing'}


def _footprint_uses(nt):
    """[(node, input index, frequency)] for each of finish_stock's fades: MULTIPLY(footprint, k), where footprint =
    (View Distance * pixel_angle) * 1.4 is its estimate of a pattern's screen footprint per unit of phase."""
    pix = nt.nodes.get('pixel_angle')
    if pix is None:
        return []

    def outs(node):
        return [lk for lk in nt.links if lk.from_node == node]

    def mult(node):
        return node.type == 'MATH' and node.operation == 'MULTIPLY'

    uses = []
    for l1 in outs(pix):
        if not mult(l1.to_node):
            continue
        for l2 in outs(l1.to_node):
            if not mult(l2.to_node):
                continue
            for l3 in outs(l2.to_node):
                c = l3.to_node
                if not mult(c):
                    continue
                i = list(c.inputs).index(l3.to_socket)
                other = c.inputs[1 - i]
                if not other.is_linked:
                    uses.append((c, i, float(other.default_value)))
    return uses


def filter_finish(material):
    """Fade the finish's fine patterns by their true screen footprint: the WebGPU finishStock's fwidth(phase).

    finish_stock estimates fwidth(phase) as (view distance * pixel angle * 1.4) times the pattern's frequency. That is
    right only where the pattern's gradient lies in the surface, across the screen. On a turned part the growth
    rings' gradient runs nearly along the surface normal on the sides that face the camera, so there the rings and the
    fibre stay wide on screen while the estimate faded the rings to a quarter and the fibre to nothing. This reroutes
    each fade to the exact derivative: the pattern's 3D gradient g (the rings, fibre and brushing as finish_stock
    defines them; the broad noise's gradient by finite differences) taken through the pixel's footprint on the
    surface, dP/dx = t a (e_x - (e_x . N) / (I . N) I) for the screen axes e_x, e_y (t the view distance, a the pixel
    angle, N the normal, I the direction to the eye), and fwidth = |g . dP/dx| + |g . dP/dy|. Needs swizzle_finish
    first (it reads the stock point there). Returns the number of fades rerouted: 2 for wood (rings, fibre), 1 for
    metal (brushing), 0 when there is nothing to do (no swizzle, no footprint fades, or already filtered: a node
    named FOOTPRINT_NODE, which finish_stock may one day make itself)."""
    from .._nodes import V, Builder
    nt = material.node_tree
    if nt is None or FOOTPRINT_NODE in nt.nodes:
        return 0
    comb = nt.nodes.get(GRAIN_NODE)
    uses = _footprint_uses(nt)
    if comb is None or not uses:
        return 0
    unknown = sorted({k for _c, _i, k in uses} - set(PATTERNS))
    if unknown:
        raise RuntimeError(f'finish_stock fades a pattern of frequency {unknown} this filter does not know: '
                           'teach stock.filter_finish its gradient')
    marker = nt.nodes.new('NodeFrame')
    marker.name = marker.label = FOOTPRINT_NODE
    marker.location = (comb.location.x + 400, comb.location.y - 300)
    b = Builder(nt, x0=comb.location.x + 400, y0=comb.location.y - 360)
    bx, by, bz = b.sep(comb.outputs[0])
    px, py, pz = bx, bz, -by                                  # three's (x, y, z), as finish_stock reads them
    geo = b.node('ShaderNodeNewGeometry')
    normal, eye = V(b, geo.outputs['Normal']), V(b, geo.outputs['Incoming'])
    cam = b.node('ShaderNodeCameraData')
    metres_per_pixel = b.s(cam.outputs['View Distance']) * b.s(nt.nodes['pixel_angle'].outputs[0])

    def screen_axis(v):
        n = b.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='CAMERA', convert_to='WORLD')
        n.inputs[0].default_value = v
        return V(b, n.outputs[0])

    ex, ey = screen_axis((1.0, 0.0, 0.0)), screen_axis((0.0, 1.0, 0.0))
    i_n = b.dot(eye, normal)
    inv_i_n = i_n / b.max(i_n * i_n, 1e-6)                    # 1 / (I . N), bounded at the silhouette
    rx, ry = b.dot(ex, normal) * inv_i_n, b.dot(ey, normal) * inv_i_n

    def fwidth(g_three):
        gx, gy, gz = b.sep(g_three)
        g_object = b.vec(gz, -gx, gy)                          # through the swizzle: p = (-oy, oz, ox)
        tw = b.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
        b.link(g_object, tw.inputs[0])
        g = V(b, tw.outputs[0])
        gi = b.dot(g, eye)
        return (b.abs(b.dot(g, ex) - gi * rx) + b.abs(b.dot(g, ey) - gi * ry)) * metres_per_pixel

    grads = {}
    if {4200.0, 18000.0} & {k for _c, _i, k in uses}:
        def broad_at(d=(0.0, 0.0, 0.0)):
            """finish_stock's broad noise, mx_noise(p * (38, 27, 19)), at p + d"""
            n = b.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
            n.inputs['Scale'].default_value = 1.0
            n.inputs['Detail'].default_value = 0.0
            n.inputs['Roughness'].default_value = 0.5
            n.inputs['Distortion'].default_value = 0.0
            q = [c * k + k * dc if dc else c * k for c, k, dc in zip((px, py, pz), (38.0, 27.0, 19.0), d)]
            b.link(b.vec(*q), n.inputs['Vector'])
            return (b.s(n.outputs['Fac']) - 0.5) * 2.0

        h = 5e-5
        broad = broad_at()
        gb = b.vec(*[(broad_at(tuple(h if j == k else 0.0 for j in range(3))) - broad) * (1.0 / h) for k in range(3)])
        warp = b.sin(pz * 38.0) * .004 + broad * .002
        u = px + .049 + warp
        w = (py + .024) * 1.18
        r = b.max(b.sqrt(u * u + w * w), 1e-6)
        gu = b.vec(1.0, 0.0, b.cos(pz * 38.0) * .152) + b.vscale(gb, .002)      # d(px + .049 + warp) / dp
        grads[4200.0] = b.vscale(b.vscale(gu, u) + b.vec(0.0, w * 1.18, 0.0), 4200.0 / r) + b.vscale(gb, 2.8)
        grads[18000.0] = b.vscale(gu, 18000.0)
    if 83000.0 in {k for _c, _i, k in uses}:
        grads[83000.0] = b.vec(b.cos(px * 270.0) * 189.0, 0.0, 83000.0)
    for c, i, k in uses:
        for lk in [lk for lk in nt.links if lk.to_socket == c.inputs[i]]:
            nt.links.remove(lk)
        b.link(fwidth(grads[k]) * (1.0 / k), c.inputs[i])     # footprint * k becomes the exact fwidth(phase)
    return len(uses)


def check_resolution(resolution):
    """createRotaryStock's rule: three whole numbers of samples, 24 to 512 each."""
    if len(resolution) != 3 or any(not isinstance(n, int) or isinstance(n, bool) or n < 24 or n > 512
                                   for n in resolution):
        raise ValueError('Invalid stock resolution')
    return tuple(resolution)


class StockField:
    """The carved field alone (no Blender objects): what RotaryStock updates and writes."""

    def __init__(self, path, settings, resolution=(256, 96, 96)):
        check_resolution(resolution)
        self.path, self.settings = path, settings
        L, W, H = settings['stock_length'], settings['stock_width'], settings['stock_height']
        nx, ny, nz = resolution
        self.resolution = tuple(resolution)
        self.eps = max(L / (nx - 4), W / (ny - 4), H / (nz - 4))
        self.pad, self.band = self.eps * 2, self.eps * 3
        self.bounds = {'min': (-L / 2 - self.pad, -W / 2 - self.pad, -H / 2 - self.pad),
                       'max': (L / 2 + self.pad, W / 2 + self.pad, H / 2 + self.pad)}
        extent = [self.bounds['max'][k] - self.bounds['min'][k] for k in range(3)]
        self.cell = tuple(extent[k] / (resolution[k] - 1) for k in range(3))
        self.axes = [self.bounds['min'][k] + np.arange(resolution[k]) * self.cell[k] for k in range(3)]
        X, Y, Z = np.meshgrid(*self.axes, indexing='ij')
        self.blank = np.clip(blank_distance_np(np.stack([X, Y, Z], -1), settings), -self.band,
                             self.band).astype(np.float32)
        self._YZ = (Y[0], Z[0])
        self.field = self.blank.copy()
        self.index = index_rotary_sweeps(path, settings, self.bounds, (40, 16, 16), self.band)
        self._cuts = [s['index'] for s in path.segments if s['type'] == 'cut']
        self._frames = {}
        self._previous, self._time = None, -1.0
        self.applied = 0

    # ------------------------------------------------------------------------------------------- the update ---
    def _cutter_yz(self, a0):
        key = round(math.fmod(a0, 2 * math.pi), 12)
        f = self._frames.get(key)
        if f is None:
            f = self._frames[key] = cutter_frame(np.stack([np.zeros_like(self._YZ[0]), *self._YZ], -1), a0)
        return f

    def _apply(self, s, fraction):
        st = self.settings
        R, flute, tool, band = st['radius'], st['flute_length'], st.get('tool') or 'ball', self.band
        lo, hi = stroke_bounds(s, st, band)
        bmin, cell, res = self.bounds['min'], self.cell, self.resolution
        r = [(max(0, math.ceil((lo[k] - bmin[k]) / cell[k])), min(res[k] - 1, math.floor((hi[k] - bmin[k]) / cell[k])))
             for k in range(3)]
        if any(a > b for a, b in r):
            return
        (i0, i1), (j0, j1), (k0, k1) = r
        Hc, Lc = self._cutter_yz(s['a0'])
        a, b = s['a'], s['b']
        sub_h = Hc[j0:j1 + 1, k0:k1 + 1]
        sub_l = Lc[j0:j1 + 1, k0:k1 + 1] + a[1]
        tip, top = min(a[2], b[2]), max(a[2], b[2]) + flute
        # the ball's distance is Euclidean, so nothing beyond the band changes; the flat end's vertical distance is
        # divided by the stroke's slope normaliser and reaches further below a sloped stroke, so it gets the whole
        # stroke box below the tip, as the WebGPU bins gave it
        below = band + (R if tool == 'flat' else 0.0)
        m = (np.abs(sub_l) <= R + band) & (sub_h >= tip - below) & (sub_h <= top + band)
        if not m.any():
            return
        jj, kk = np.nonzero(m)
        jj += j0
        kk += k0
        F = self.field
        block = F[i0:i1 + 1][:, jj, kk]
        act = block < band
        if not act.any():
            return
        ii, cols = np.nonzero(act)
        d = sweep_core(self.axes[0][i0 + ii], Hc[jj[cols], kk[cols]], Lc[jj[cols], kk[cols]] + a[1], s, R, flute,
                       fraction, tool)
        block[ii, cols] = np.maximum(block[ii, cols], np.clip(-d, -band, band))
        F[i0:i1 + 1, jj, kk] = block
        self.applied += 1

    def update(self, state):
        """The field at a sampled moment (path.sample(t)): strokes before state['index'] whole, that one to its
        fraction. Forward updates apply only the strokes since the last; going back rebuilds from the blank."""
        if state['time'] == self._time:
            return False
        rebuild = self._previous is None or state['time'] < self._time
        if rebuild:
            self.field = self.blank.copy()
        begin = 0 if rebuild else self._previous['index']
        cursor = state['index']
        lo = bisect.bisect_left(self._cuts, begin)
        hi = bisect.bisect_right(self._cuts, cursor)
        segs = self.path.segments
        for sid in self._cuts[lo:hi]:
            self._apply(segs[sid], state['fraction'] if sid == cursor else 1.0)
        self._previous = dict(state)
        self._time = state['time']
        return True

    # -------------------------------------------------------------------------------------------- the output ---
    def tiled(self):
        """The field in the WebGPU edition's layout: z slices tiled cols x rows into a (rows * ny, cols * nx) image,
        three's axes (its y = our z, its z = our -y)."""
        nx, ny, nz = self.resolution
        three = self.field[:, ::-1, :].transpose(0, 2, 1)                 # [x][y3 = our z][z3 = -our y]
        n3y, n3z = nz, ny
        cols = math.ceil(math.sqrt(n3z))
        rows = math.ceil(n3z / cols)
        img = np.zeros((rows * n3y, cols * nx), dtype=np.float32)
        for z3 in range(n3z):
            r, c = divmod(z3, cols)
            img[r * n3y:(r + 1) * n3y, c * nx:(c + 1) * nx] = three[:, :, z3].T
        return img

    @property
    def cell_size(self):
        """the WebGPU cellSize: the grid spacing along X, Y, Z (metres)"""
        return self.cell

    @property
    def layout(self):
        """The WebGPU api.layout of the tiled target (tiled()), key for key in its own terms, three's axes: nx the
        length, ny the height and nz the width count (this resolution is Blender's (length, width, height)), cols x
        rows tiles of the nz width slices, each nx wide and ny high."""
        nx, ny, nz = self.resolution                    # Blender: length, width, height
        cols = math.ceil(math.sqrt(ny))
        rows = math.ceil(ny / cols)
        return {'width': nx * cols, 'height': nz * rows, 'cols': cols, 'nx': nx, 'ny': nz, 'nz': ny}

    def grid(self):
        """The current field as an OpenVDB FloatGrid named 'density': minus the distance (positive inside), the
        background minus the band, constant blocks pruned to tiles, voxel (i, j, k) at bounds.min + ijk * cell."""
        import openvdb as vdb
        g = vdb.FloatGrid(float(-self.band))
        g.copyFromArray(np.ascontiguousarray(-self.field, dtype=np.float32))
        g.prune(0.0)
        cx, cy, cz = self.cell
        mx, my, mz = self.bounds['min']
        g.transform = vdb.createLinearTransform([[cx, 0, 0, 0], [0, cy, 0, 0], [0, 0, cz, 0], [mx, my, mz, 1]])
        g.name = GRID_NAME
        g.saveFloatAsHalf = True
        return g

    def polygons(self):
        """(vertices (N, 3), faces) of the field's zero level in stock coordinates, outward facing."""
        import openvdb as vdb
        g = vdb.FloatGrid(float(self.band))
        g.copyFromArray(np.ascontiguousarray(self.field, dtype=np.float32))
        cx, cy, cz = self.cell
        mx, my, mz = self.bounds['min']
        g.transform = vdb.createLinearTransform([[cx, 0, 0, 0], [0, cy, 0, 0], [0, 0, cz, 0], [mx, my, mz, 1]])
        pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=0.0)
        faces = [tuple(t) for t in np.asarray(tris).tolist()] + [tuple(q) for q in np.asarray(quads).tolist()]
        return np.asarray(pts, dtype=np.float64), faces

    def volume(self):
        """m3 of stock left (cells with the distance below zero, trilinear-free count: a check, not a mesh volume)."""
        return float((self.field < 0).sum()) * self.cell[0] * self.cell[1] * self.cell[2]


class RotaryStock(StockField):
    """create_rotary_stock's result: the field plus its Blender objects (stock mesh, field volume, material)."""

    def __init__(self, path, settings, parent=None, resolution=(256, 96, 96), color=None, name='Rotary volumetric stock',
                 cache_dir=None, collection=None, material=None):
        super().__init__(path, settings, resolution)
        import bpy
        self.name = name
        self.cache_dir = _abspath(cache_dir or ('//' + _safe(name) + '_cache'))
        self.frames_written = []
        col = collection or (parent.users_collection[0] if parent is not None else bpy.context.scene.collection)
        self.volume_data = bpy.data.volumes.new(name + ' field')
        self.volume_object = bpy.data.objects.new(name + ' field', self.volume_data)
        col.objects.link(self.volume_object)
        self.volume_object.hide_render = True
        self.volume_object.hide_set(True)
        self.volume_object.display_type = 'BOUNDS'
        me = bpy.data.meshes.new(name)
        self.mesh = bpy.data.objects.new(name, me)
        col.objects.link(self.mesh)
        for ob in (self.volume_object, self.mesh):     # both at the stock frame: object space = stock space
            if parent is not None:
                ob.parent = parent
                ob.matrix_parent_inverse.identity()
            ob.matrix_basis.identity()
        mod = self.mesh.modifiers.new('stock surface', 'VOLUME_TO_MESH')
        mod.object = self.volume_object
        mod.grid_name = GRID_NAME
        mod.threshold = 0.0
        mod.resolution_mode = 'GRID'
        mod.adaptivity = 0.0
        mod.use_smooth_shade = True
        self.finish = None
        self.footprint_fades = 0
        if material is None:
            from ..cutting import stock_material, stock_profile
            material, self.finish = stock_material(name + ' finish', stock_profile(settings.get('material', 'wood')),
                                                   color)
            if not swizzle_finish(material):
                raise RuntimeError('finish_stock no longer reads Object texture coordinates: the rotary grain '
                                   'swizzle (stock.swizzle_finish) needs updating')
            self.footprint_fades = filter_finish(material)
            if not self.footprint_fades and FOOTPRINT_NODE not in material.node_tree.nodes:
                raise RuntimeError("finish_stock's footprint fades changed: the rotary stock's exact filter "
                                   '(stock.filter_finish) needs updating')
        self.material = material
        me.materials.append(material)
        self.mesh['eidoverse_rotary_stock'] = True
        self._last_file = None
        self.hold()                                     # the prepared blank shows until frames are written

    @property
    def texture(self):
        """The WebGPU edition's render-target texture: here the VDB file written last (by write_frame or hold), the
        field as it was then (None before any). An update() without a write leaves it describing the earlier field."""
        return self._last_file

    @property
    def hold_path(self):
        return os.path.join(self.cache_dir, '%s_hold.vdb' % _safe(self.name))

    def frame_path(self, frame):
        return os.path.join(self.cache_dir, '%s_%04d.vdb' % (_safe(self.name), int(frame)))

    def write_frame(self, frame):
        """Store the current field for this frame and extend the stock's file sequence over it."""
        import openvdb as vdb
        os.makedirs(self.cache_dir, exist_ok=True)
        p = self.frame_path(frame)
        tmp = p + '.tmp'
        vdb.write(tmp, grids=[self.grid()])
        os.replace(tmp, p)
        if frame not in self.frames_written:
            self.frames_written.append(int(frame))
            self.frames_written.sort()
        self._sequence()
        self._last_file = p
        return p

    def _sequence(self):
        first, last = self.frames_written[0], self.frames_written[-1]
        v = self.volume_data
        v.filepath = _blend_path(self.frame_path(first))
        v.is_sequence = True
        v.frame_start = first
        v.frame_duration = last - first + 1
        v.frame_offset = first - 1                      # whole frames; the driver adds the half-frame rounding
        v.sequence_mode = 'EXTEND'
        _nearest_frame_driver(v, first, last)
        v.grids.load()

    def hold(self):
        """Show the current field on every frame (the job stopped): one file, no sequence."""
        import openvdb as vdb
        os.makedirs(self.cache_dir, exist_ok=True)
        p = self.hold_path
        vdb.write(p + '.tmp', grids=[self.grid()])
        os.replace(p + '.tmp', p)
        v = self.volume_data
        if v.animation_data is not None and v.animation_data.drivers.find('frame_offset') is not None:
            v.driver_remove('frame_offset')
        v.is_sequence = False
        v.filepath = _blend_path(p)
        v.grids.load()
        self._last_file = p
        return p

    def readback(self):
        """A copy of the current field (nx, ny, nz) float32; the WebGPU edition read its tiled target back."""
        return self.field.copy()

    def to_mesh(self, name='carved stock', link=True):
        """A static mesh object of the current field in stock coordinates, placed where the stock surface is (so its
        finish reads the same), with the stock's material."""
        import bpy
        pts, faces = self.polygons()
        me = bpy.data.meshes.new(name)
        me.from_pydata(pts.tolist(), [], faces)
        me.update()
        me.shade_smooth()
        me.materials.append(self.material)
        ob = bpy.data.objects.new(name, me)
        if link:
            for c in self.mesh.users_collection:
                c.objects.link(ob)
            ob.matrix_world = self.mesh.matrix_world.copy()
        return ob

    def dispose(self, files=False):
        """Remove the stock's objects and datablocks; with files=True also every file it wrote (each frame's, the
        hold file) and the cache folder when nothing else is left in it."""
        import bpy
        for ob in (self.mesh, self.volume_object):
            if ob is not None and ob.name in bpy.data.objects:
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data is not None and data.users == 0:
                    (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.volumes).remove(data)
        if self.material is not None and self.material.users == 0:
            bpy.data.materials.remove(self.material)
        self.mesh = self.volume_object = None
        if files:
            for p in [self.frame_path(f) for f in self.frames_written] + [self.hold_path]:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.rmdir(self.cache_dir)                # only when empty: never another job's files
            except OSError:
                pass
            self._last_file = None


def create_rotary_stock(path, settings, parent=None, resolution=(256, 96, 96), color=None,
                        name='Rotary volumetric stock', cache_dir=None, collection=None, material=None):
    """createRotaryStock (see the module docstring). parent: the object the stock rides on (the job's stock frame, which
    turns with the chuck); color overrides the material preset's colour."""
    return RotaryStock(path, settings, parent, tuple(resolution), color, name, cache_dir, collection, material)


def _nearest_frame_driver(volume, first, last):
    """Blender plays a volume file sequence at floor(time), so a motion-blur sample a quarter frame before frame F
    shows file F - 1. Drive the sequence's frame offset (first - 1 at whole frames) one further from half a frame
    before each written frame, inside the sequence, so every time within half a frame of F shows file F and the
    ends still hold (EXTEND). A simple expression: it evaluates without Python, in any saved file."""
    fc = volume.animation_data.drivers.find('frame_offset') if volume.animation_data is not None else None
    if fc is None:
        fc = volume.driver_add('frame_offset')
    d = fc.driver
    d.type = 'SCRIPTED'
    for var in list(d.variables):
        d.variables.remove(var)
    d.expression = ('%d + (floor(frame + 0.5) - floor(frame)) * min(1, max(0, floor(frame) - %d)) '
                    '* min(1, max(0, %d - floor(frame)))') % (first - 1, first - 1, last)
    return fc


def _blend_path(p):
    """p relative to the saved .blend ('//...'), so the build moves with its cache folder; absolute otherwise"""
    import bpy
    if bpy.data.filepath:
        try:
            return bpy.path.relpath(p)
        except ValueError:                              # another drive
            pass
    return p


def _safe(name):
    return ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in name)


def _abspath(p):
    if p.startswith('//'):
        import bpy
        if not bpy.data.filepath:
            raise ValueError('cache_dir ' + p + ' is relative to the .blend, which is not saved yet: save it first or '
                             'pass an absolute cache_dir (the stock writes one VDB file per keyed frame)')
        return os.path.normpath(os.path.join(os.path.dirname(bpy.data.filepath), p[2:]))
    return os.path.abspath(p)
