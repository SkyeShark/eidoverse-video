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
stock frame; its finish (fabrication.cutting.finish_stock with axes='rotary') reads the stock point as (z, y, x) in
three's axes, the WebGPU stock's swizzle, and fades its fine patterns by their exact screen footprint, the WebGPU
fwidth(phase).

PLAYBACK. Nothing runs at render time. write_frame(frame) stores the field as an OpenVDB grid ('density' = minus the
distance, positive inside, pruned to tiles) in <cache_dir>/<name>_<frame:04d>.vdb; the stock's Volume datablock plays
that file sequence (EXTEND: the first and last held outside it) and the stock mesh object's Volume to Mesh modifier
meshes the current file at the zero level. Blender shows a file sequence at floor(time); a driver on the sequence's
frame offset makes every time within half a frame of a written frame show that frame's file, so the motion-blur
samples of a frame (and its sub-frame keys, carve.RotaryJob.key) all see the same carved surface. Write every frame
the film shows; a saved .blend then plays and renders any frame on its own, with the cache folder beside it.
show_frames(first, last) plays a written stretch alone instead, its ends held around it (a job keyed at its own speed
writes the stretch it plays: carve.RotaryJob.write_stock).
"""

from __future__ import annotations

import bisect
import math
import os

import numpy as np

from .removal import blank_distance_np
from .sweeps import cutter_frame, index_rotary_sweeps, stroke_bounds, sweep_core

GRID_NAME = 'density'


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
        self.run = None                                 # (first, last): the frames the file sequence plays
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
        if material is None:
            from ..cutting import stock_material, stock_profile
            material, self.finish = stock_material(name + ' finish', stock_profile(settings.get('material', 'wood')),
                                                   color, axes='rotary')
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
        """Store the current field for this frame and extend the stock's file sequence over it: the sequence plays
        every frame from the first written to the last (a frame between them without its file shows no stock, so a
        film keyed at chosen frames renders those frames)."""
        import openvdb as vdb
        os.makedirs(self.cache_dir, exist_ok=True)
        f = int(frame)
        p = self.frame_path(f)
        tmp = p + '.tmp'
        vdb.write(tmp, grids=[self.grid()])
        os.replace(tmp, p)
        if f not in self.frames_written:
            self.frames_written.append(f)
            self.frames_written.sort()
        self.run = (self.frames_written[0], self.frames_written[-1])
        self._sequence()
        self._last_file = p
        return p

    def show_frames(self, first, last):
        """Play only the written frames first .. last (each must have its file), holding the stretch's ends before and
        after it: a stretch of a job keyed at its own speed (RotaryJob.write_stock) shows its stock at every frame,
        and every frame around it the nearer end, never an empty stock."""
        first, last = int(first), int(last)
        have = set(self.frames_written)
        missing = [f for f in range(first, last + 1) if f not in have]
        if last < first or missing:
            raise ValueError(f'show_frames: frames {first} .. {last} need their files ({len(missing)} not written: '
                             f'{missing[:5]})')
        self.run = (first, last)
        self._sequence()

    def _sequence(self):
        first, last = self.run
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
        self.run = None
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
