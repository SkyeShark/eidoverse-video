"""GPU eyes (Warp ray casting, for my review only): orthographic views of large meshes (millions of triangles) with
smooth (interpolated vertex normal) or flat shading, a key + fill light, optional per-face tint (a gate's folds) and
a soft ambient occlusion term. One ray per pixel (x ss^2 supersampled) against the mesh's BVH.

    from eidoverse.bestiary.forge import render
    render.views(V, F, out_png, views=('side', 'front', 'top', 'threeq'), size=1024, box=None, tint=None)
"""
import numpy as np
import warp as wp
from PIL import Image, ImageDraw


@wp.kernel
def k_cast(mesh: wp.uint64, vn: wp.array(dtype=wp.vec3), tri: wp.array(dtype=wp.int32),
           tint: wp.array(dtype=wp.vec3), use_tint: int, smooth: int,
           origin0: wp.vec3, du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, ss: int, ao_n: int, ao_r: float,
           light: wp.vec3, out: wp.array(dtype=wp.vec3)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    acc = wp.vec3(0.0)
    hits = int(0)
    state = wp.rand_init(17, tid)
    for i in range(ss):
        for j in range(ss):
            fx = float(px) + (float(i) + 0.5) / float(ss)
            fy = float(py) + (float(j) + 0.5) / float(ss)
            o = origin0 + du * fx + dv * fy
            q = wp.mesh_query_ray(mesh, o, dirv, 1.0e3)
            if not q.result:
                acc = acc + wp.vec3(0.105, 0.105, 0.12)
                continue
            f = q.face
            w = 1.0 - q.u - q.v
            n = wp.mesh_eval_face_normal(mesh, f)
            if smooth == 1:
                n = wp.normalize(vn[tri[3 * f]] * q.u + vn[tri[3 * f + 1]] * q.v + vn[tri[3 * f + 2]] * w)
            if wp.dot(n, dirv) > 0.0:
                n = -n                                # two-sided
            p = o + dirv * q.t
            # soft AO: cosine rays over ao_r
            occl = float(0.0)
            for a in range(ao_n):
                d2 = wp.sample_unit_disk(state)
                z = wp.sqrt(wp.max(0.0, 1.0 - d2[0] * d2[0] - d2[1] * d2[1]))
                t1 = wp.normalize(wp.cross(n, wp.vec3(0.31, 0.83, 0.47)))
                t2 = wp.cross(n, t1)
                r = wp.mesh_query_ray(mesh, p + n * 1.0e-5, wp.normalize(t1 * d2[0] + t2 * d2[1] + n * z), ao_r)
                if r.result:
                    occl = occl + 1.0
            ao = 1.0 - occl / float(wp.max(ao_n, 1)) * 0.85
            key = wp.max(wp.dot(n, light), 0.0)
            fill = wp.max(wp.dot(n, -dirv), 0.0)
            shade = (0.15 + 0.62 * key + 0.30 * fill) * ao
            base = wp.vec3(0.86, 0.84, 0.80)
            if use_tint == 1:
                tc = tint[f]
                if tc[0] + tc[1] + tc[2] > 0.0:
                    base = tc
            acc = acc + base * shade
            hits = hits + 1
    out[tid] = acc / float(ss * ss)


def basis(view, fwd=np.array([0.0, 0.0, 1.0])):
    up = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fwd)
    cams = {'side': side, 'front': fwd, 'back': -fwd, 'top': up, 'bottom': -up,
            'threeq': fwd * 0.6 + side * 0.8 + up * 0.35, 'threeq_r': fwd * 0.6 - side * 0.8 + up * 0.35,
            'under': fwd * 0.5 + side * 0.5 - up * 0.7, 'threeq_back': -fwd * 0.6 + side * 0.8 + up * 0.35}
    cam = cams[view] / np.linalg.norm(cams[view])
    u = fwd if view in ('top', 'bottom') else up
    right = np.cross(u, cam)
    right /= np.linalg.norm(right)
    upv = np.cross(cam, right)
    return right, upv, cam


def views(V, F, out_png, views=('side', 'front', 'top', 'threeq'), size=1024, box=None, tint=None, smooth=True,
          ss=2, ao_n=12, ao_r=0.01, label=''):
    V = np.asarray(V, np.float32)
    F = np.asarray(F, np.int32)
    if box is not None:
        b = np.asarray(box, np.float32)
        c = V[F].mean(1)
        keep = np.all((c >= b[:3]) & (c <= b[3:]), axis=1)
        F = F[keep]
        if tint is not None:
            tint = tint[keep]
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
    mesh = wp.Mesh(points=wp.array(V, dtype=wp.vec3), indices=wp.array(F.ravel(), dtype=wp.int32))
    vn_d = wp.array(vn, dtype=wp.vec3)
    tri_d = wp.array(F.ravel(), dtype=wp.int32)
    tint_d = wp.array(np.asarray(tint, np.float32) / 255.0 if tint is not None else np.zeros((1, 3), np.float32),
                      dtype=wp.vec3)
    used = np.unique(F)
    P = V[used]
    tiles = []
    for vname in views:
        right, upv, cam = basis(vname)
        X, Y, Z = P @ right, P @ upv, P @ cam
        span = max(X.max() - X.min(), Y.max() - Y.min()) * 1.06
        cx, cy = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2
        pix = span / size
        far = Z.max() + 1.0
        origin0 = right * (cx - span / 2) + upv * (cy + span / 2) + cam * far
        light = (cam * 0.55 + upv * 0.65 + right * 0.35)
        light /= np.linalg.norm(light)
        out = wp.zeros(size * size, dtype=wp.vec3)
        wp.launch(k_cast, dim=size * size, inputs=[
            mesh.id, vn_d, tri_d, tint_d, int(tint is not None), int(smooth), wp.vec3(*origin0),
            wp.vec3(*(right * pix)), wp.vec3(*(-upv * pix)), wp.vec3(*(-cam)), size, ss, ao_n, float(ao_r),
            wp.vec3(*light), out])
        img = (np.clip(out.numpy().reshape(size, size, 3), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
        im = Image.fromarray(img)
        ImageDraw.Draw(im).text((6, 6), f'{label} {vname}  frame {span:.3f} m', fill=(240, 240, 240))
        tiles.append(im)
    sheet = Image.new('RGB', (size * len(tiles), size))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * size, 0))
    sheet.save(out_png)
    return out_png
