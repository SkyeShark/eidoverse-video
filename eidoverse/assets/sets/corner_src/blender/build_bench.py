"""Split-log bench, 1.4 m: a half log (flat, worn-smooth seat face up, bark underneath, weathered
end grain) cradled in saddle notches cut into two short stumps (root flare, bark, moss at the
foot, end-grain rims around the notch). Seat top at z = 0.42. Origin: ground centre.
-> glb/camp_bench.glb ('Bench')
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from clib import *
from camp_lib import *
from camp_logs import *

reset()
SEAT_Z, SEAT_R, SEAT_L = 0.42, 0.16, 1.40
ST_R, ST_TOP, ST_X = 0.18, 0.34, 0.48


def moss(nb, col, vec):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    low = ramp_s(nb, z, 0.16, 0.02)
    m = nb.math('MULTIPLY', low, ramp_s(nb, nb.noise(oc, 7.0, 4.0, 0.6), 0.45, 0.62))
    col = nb.mix(nb.math('MULTIPLY', m, 0.85), col, (0.10, 0.15, 0.04))
    lich = nb.math('MULTIPLY', ramp_s(nb, nb.noise(oc, 30.0, 2.0, 0.5), 0.70, 0.74), 0.7)
    return nb.mix(lich, col, (0.45, 0.50, 0.38))


def seat_extra(nb, col, vec):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    top = ramp_s(nb, z, SEAT_Z - 0.01, SEAT_Z - 0.002)
    # where people sit: body-oil darkened, polished middle
    sit = nb.math('MULTIPLY', ramp_s(nb, nb.math('ABSOLUTE', x), 0.62, 0.35), top)
    sit = nb.math('MULTIPLY', sit, ramp_s(nb, nb.math('ABSOLUTE', y), 0.14, 0.05))
    col = nb.mix(nb.math('MULTIPLY', sit, 0.45), col, (0.16, 0.12, 0.085))
    # long drying checks along the grain
    cv = nb.n('ShaderNodeMapping'); cv.inputs['Scale'].default_value = (0.8, 22.0, 22.0); nb.l(oc, cv.inputs['Vector'])
    ck = nb.math('MULTIPLY', voronoi_cracks(nb, cv.outputs[0], 1.0, 0.045),
                 ramp_s(nb, nb.noise(oc, 2.0, 2.0, 0.5), 0.42, 0.58))
    return nb.mix(nb.math('MULTIPLY', ck, 0.9), col, (0.04, 0.035, 0.03))


def weather_end(nb, col, vec):
    oc = obj_coord(nb)
    g = ramp_s(nb, nb.noise(oc, 12.0, 4.0, 0.6), 0.3, 0.7)
    return nb.mix(nb.math('ADD', nb.math('MULTIPLY', g, 0.18), 0.10), col, (0.36, 0.33, 0.30))


bark = layered_mat('bark', 'Bark012', scale=2.4, tint=(0.80, 0.66, 0.52), sat=0.75, val=0.72, rough_add=0.18,
                   nstr=1.6, extra_color=moss,
                   grime=dict(color=(0.035, 0.03, 0.025), dist=0.03, amount=0.8, gain=1.9))
endg = endgrain_clamp(layered_mat('endgrain', 'TreeEnd003', scale=1.0, tint=(0.86, 0.78, 0.70), sat=0.6, val=0.62,
                                  rough_add=0.25, nstr=1.2, extra_color=weather_end,
                                  grime=dict(color=(0.05, 0.045, 0.04), dist=0.02, amount=0.6)))
seatw = layered_mat('seatwood', 'Wood049', scale=1.4, tint=(1.0, 0.90, 0.80), sat=0.7, val=0.64, rough_mul=0.75,
                    rough_add=0.05, nstr=1.0, extra_color=seat_extra,
                    wear=dict(color=(0.62, 0.56, 0.48), radius=0.008, amount=0.8, rough=0.35, gain=10, noise=6),
                    grime=dict(color=(0.05, 0.04, 0.03), dist=0.025, amount=0.7, gain=1.8))

# ---- seat: half log, flat face up at SEAT_Z
seat = log_mesh('seat', SEAT_L, SEAT_R, seed=3, bend=0.008, split={'z': 0.0}, na=40, nl=36,
                mats=[bark, endg, seatw], bark_amp=0.035)
seat.location.z = SEAT_Z
select_only(seat); bpy.ops.object.transform_apply(location=True)
m = bevel_mod(seat, 0.012, segments=3, angle=55)      # worn, rounded seat edges
m.miter_outer = 'MITER_ARC'
apply_mods(seat)
smooth(seat, 45)

# ---- stumps with the saddle notch (boolean with the seat's underside cylinder)
parts = [seat]
for k, sx in enumerate((-ST_X, ST_X)):
    st = log_mesh('stump', ST_TOP + 0.03, ST_R, seed=21 + k, bend=0.004, na=40, nl=12, cut_tilt=0.03,
                  mats=[bark, endg, seatw], root_flare=0.22, bark_amp=0.06)
    place_log(st, (sx, 0.0, -0.03), (sx, 0.0, ST_TOP))
    # cutter: the seat's lower half-cylinder (+1.5 mm clearance), carrying split-wood UV/material
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=SEAT_R + 0.0015, radius2=SEAT_R + 0.0015, depth=0.6)
    for v in bm.verts:
        v.co = Vector((v.co.z + sx, v.co.x, v.co.y + SEAT_Z))
    cut = obj_from_bm('cut', bm, seatw)
    cut.data.uv_layers.new(name='TexUV')
    for p in cut.data.polygons:
        for li in p.loop_indices:
            co = cut.data.vertices[cut.data.loops[li].vertex_index].co
            cut.data.uv_layers['TexUV'].data[li].uv = (co.x, math.atan2(co.z - SEAT_Z, co.y) * SEAT_R)
    boolean(st, cut)
    # the buried bottom cap goes
    bm = bmesh.new(); bm.from_mesh(st.data)
    bot = [f for f in bm.faces if f.normal.z < -0.9 and f.calc_center_median().z < 0.0]
    bmesh.ops.delete(bm, geom=bot, context='FACES')
    bm.to_mesh(st.data); bm.free()
    smooth(st, 45)
    parts.append(st)

B = join(parts, 'Bench')
uv_bake(B, margin=0.004, angle=60)
bake_and_swap(B, 'bench', size=2048, samples=40, ao_dist=0.08)
finalize_export_material(B.data.materials[0])
export_glb([B], 'camp_bench.glb')

g = ground_plane(4.0)
preview([B], 'bench', height=0.45)
lit_shot('bench_close', (0.95, -0.95, 0.75), (0.35, 0.0, 0.33), lens=45, size=768)
lit_shot('bench_end', (-1.15, -0.45, 0.55), (-0.6, 0.0, 0.35), lens=50, size=768)
