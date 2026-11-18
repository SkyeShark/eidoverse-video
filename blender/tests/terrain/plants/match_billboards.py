"""Each billboard beside the level it takes over from (surfacing design 4.4 and 5.4, package 4, item 2): every
SeedThree individual an ecotope grows, alone on one spot, rendered as its full level (LOD0), its card level (LOD2) and
its billboard through the still grove (plant_instances: one points mesh, the near and the billboard object) at the
distance where a stand hands one over to the other, under make_sky with the sun 70 degrees left of the view (the
review's light), from the eye height, with a lens that frames the plant, the film transparent, at four turns of the
plant. Measured within each silhouette: the mean colour (CIELAB of the display image) and the area. The billboard is
matched to the level that stands before it in a stand: the card level, or the full level for a species whose card
level is set aside (its lod billboard_m no farther than hero_m). Its gain is that level's mean scene-linear colour
over the billboard's, per channel, and its cut-out threshold the one that keeps the share of its baked alpha that
scales its silhouette to that level's (plant_instances.BILLBOARD_GAIN holds both); the billboard is rendered again
with them. The bar: the mean colour within 3 ΔE and the silhouette area within 10 %.

    bash run_blender.sh blender/tests/terrain/plants/match_billboards.py [--only douglasFir,redMaple] [--no-grow]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Writes out/plants/billboards/<species>_<seed>_<key>.png (per turn: the full level | the card level | the billboard |
the billboard matched), out/plants/billboards/match.json (per individual the colours, areas, gain, cut-out, ΔE and
area before and after, and how much of its full level's area its card level covers) and prints the BILLBOARD_GAIN
entries.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'plants', 'billboards')
sys.path.insert(0, HERE)
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import render_references as RR  # noqa: E402
from surfacing_judge import measures as M  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain.build import ecotopes as E  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import plant_instances as PI  # noqa: E402

W, H = 960, 540
EXPOSURE = -0.5                         # the review's textured exposure
EYE = 1.7
SWITCH_M = {'tree': 60.0, 'shrub': 120.0}   # where a stand hands its card level over to its billboards (the card
                                           # distance of a 300-500 stems/ha forest, of a 900/ha shrubland)
YAWS = (0.0, 25.0, 50.0, 75.0)
FILL = 0.6                              # the plant's height over the frame's
HEADING = (1.0, 0.0)                    # the camera looks along +x


def individuals(only=None):
    """{(species, seed, dials json): (kind, size_m[1], [ecotope/species, ...], level)} over every recipe's ecotope;
    level is what stands before the billboard: 'card' (LOD2) where the species keeps its card level beyond its full
    level (lod billboard_m over hero_m), else 'full' (LOD0: a species whose card level is set aside)."""
    out = {}
    for r in sorted(P.RECIPE_PALETTES):
        eco = E.get('auto', recipe=r)
        for s in eco['species']:
            kind, ident, opts, seeds = s['source']
            if kind != 'seedthree' or (only and ident not in only):
                continue
            level = 'card' if float(s['lod']['billboard_m']) > float(s['lod']['hero_m']) else 'full'
            for sd in seeds:
                key = (ident, int(sd), json.dumps(opts, sort_keys=True))
                k, size, users, lv = out.get(key, (s['kind'], float(s['size_m'][1]), [], level))
                users.append(f"{eco['name']}/{s['name']}")
                out[key] = (k, max(size, float(s['size_m'][1])), users, lv)
    return out


def scene():
    sc = RR.new_scene((W, H), 16, EXPOSURE)
    bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
    sc.render.film_transparent = True
    cam = bpy.data.objects.new('match_cam', bpy.data.cameras.new('match_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def aim(cam, dist, height):
    """The camera at the eye height, dist metres from the plant along -HEADING, framing its height."""
    eye = (-HEADING[0] * dist, -HEADING[1] * dist, EYE)
    target = (0.0, 0.0, 0.5 * height)
    RR.place_camera(cam, eye, target)
    vfov = 2.0 * math.atan(0.5 * height / FILL / dist)
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    cam.data.lens = 36.0 * H / W / (2.0 * math.tan(0.5 * vfov))
    cam.data.clip_start, cam.data.clip_end = 0.5, 4.0 * dist + 100.0


def light(sc, cam, cache):
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    return sky


def plant(species, seed, dials, kind, size, yaw):
    """The individual on one spot at the origin through the still grove: [near object, billboard object]. Its
    level is chosen with levels(): the full level (LOD0), the card level (LOD2) or the billboard."""
    rec = np.zeros((1, 12), np.float32)
    rec[0, 3] = math.radians(yaw)
    rec[0, 4] = 1.0
    rec[0, 6] = 0.5                                      # a neutral tone (the instancer's tint: 1 + k (tint - 0.5))
    rec[0, 9] = 1.0
    entry = dict(name=f'{species} {seed}', kind=kind, size_m=[0.5 * size, size], sink=0.0, foot_m=0.0,
                 source=dict(seedthree=species, dials=json.loads(dials), seeds=[seed]),
                 lod=dict(hero_m=0.0, billboard_m=SWITCH_M[kind], near_m=0.0))
    coll = bpy.data.collections.get('match_plants') or bpy.data.collections.new('match_plants')
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    entry['lod']['hero_m'] = 1.0e9
    obs = PI._instance_seedthree_still(entry, rec, np.zeros((1, 2)), coll, entry['lod'], 'match', True, None, 1)
    PI.bind_sun()                                        # the plant's backlight and the billboards' cast-only light
    return obs


def show(obs, level):
    """Show the plant at one level: 'full', 'card' or 'billboard' (the grove's values: hero count, card distance)."""
    for o in obs:
        nodes = o.modifiers['Eido Plants'].node_group.nodes
        nodes['Card Distance'].outputs[0].default_value = 0.0 if level == 'billboard' else 1.0e9
        if 'Hero Count' in nodes:
            nodes['Hero Count'].outputs[0].default_value = 1.0 if level == 'full' else 0.0
        o.update_tag()


def clear():
    coll = bpy.data.collections.get('match_plants')
    if coll is not None:
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_recursive=True)


def render(sc, path):
    """One frame: (scene-linear RGBA straight, display sRGB RGBA straight), both (H, W, 4), row 0 the top."""
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images['Render Result']
    exr = path[:-4] + '.exr'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    img.save_render(exr, scene=sc)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    out = []
    for p in (exr, path):
        im = bpy.data.images.load(p, check_existing=False)
        if p.endswith('.exr'):
            im.colorspace_settings.name = 'Non-Color'
        a = np.array(im.pixels[:], np.float64).reshape(im.size[1], im.size[0], 4)[::-1]
        bpy.data.images.remove(im)
        out.append(a)
    os.remove(exr)
    lin = out[0]
    alpha = lin[..., 3:4]
    lin = np.concatenate([np.where(alpha > 1e-6, lin[..., :3] / np.maximum(alpha, 1e-6), 0.0), alpha], -1)
    return lin, out[1]


def stats(lin, disp):
    m = disp[..., 3] > 0.5
    if not m.any():
        return dict(area=0, lab=[0.0, 0.0, 0.0], linear=[0.0, 0.0, 0.0])
    return dict(area=int(m.sum()), lab=[round(float(v), 2) for v in M.mean_lab(disp[..., :3], m)],
                linear=[float(v) for v in lin[..., :3][m].mean(0)])


def alpha_texels(species, seed, dials):
    """The baked alpha of an individual's two billboard cards, every texel of both (from the plant library)."""
    p = PI.grow_seedthree(species, seed, json.loads(dials), log=None)
    out = []
    for card in p['cards']:
        mat = card.data.materials[0]
        for n in mat.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeTexImage' and n.image is not None \
                    and any(lk.to_node.bl_idname == 'ShaderNodeMath' for lk in n.outputs['Alpha'].links):
                im = n.image
                out.append(np.array(im.pixels[:], np.float32).reshape(-1, 4)[:, 3])
                break
    for o in p['objects']:
        bpy.data.objects.remove(o, do_unlink=True)
    return np.concatenate(out) if out else None


def matching_cut(alpha, area_ratio, cut=PI.ALPHA_CUT):
    """The cut-out threshold that keeps 1 / area_ratio of the texels the default one keeps (the billboard's
    silhouette scaled to its card level's): the default when the areas already agree within 10 %."""
    if alpha is None or abs(area_ratio - 1.0) <= 0.10:
        return cut
    want = float((alpha > cut).mean()) / area_ratio
    lo, hi = (cut, 0.97) if area_ratio > 1.0 else (0.02, cut)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if float((alpha > mid).mean()) > want:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 3)


def board(path, rows):
    """Per turn a row: full level | card level | billboard | billboard with its gain and cut (display images on
    grey)."""
    from PIL import Image
    tiles = []
    for row in rows:
        ims = []
        for d in row:
            rgb = d[..., :3] * d[..., 3:4] + 0.5 * (1.0 - d[..., 3:4])
            ims.append(Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)))
        tiles.append(ims)
    w, h = W // 2, H // 2
    out = Image.new('RGB', (w * max(len(t) for t in tiles), h * len(tiles)), (40, 40, 40))
    for j, ims in enumerate(tiles):
        for i, im in enumerate(ims):
            out.paste(im.resize((w, h), Image.LANCZOS), (i * w, j * h))
    out.save(path)


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    grow = '--no-grow' not in a
    os.makedirs(OUT, exist_ok=True)
    rec_path = os.path.join(OUT, 'match.json')
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    inds = individuals(only)
    sc, cam = scene()
    sky = None
    for (species, seed, dials), (kind, size, users, level) in inds.items():
        t0 = time.time()
        key = PI.seedthree_key(species, seed, json.loads(dials))
        tag = f'{species}_{seed}_{key[:8]}'
        if not grow and not (PI.library_root() / f'seedthree_{species}_{seed}_{key}.blend').is_file():
            print(f'[match] {tag}: not in the plant library (run without --no-grow)', flush=True)
            continue
        dist = SWITCH_M[kind]
        aim(cam, dist, size)
        if sky is None:
            sky = light(sc, cam, os.path.join(OUT, '_sky'))
        PI.BILLBOARD_GAIN.pop((species, seed, dials), None)
        per, rows = [], []
        for yaw in YAWS:
            obs = plant(species, seed, dials, kind, size, yaw)
            got = {}
            for lv in ('full', 'card', 'billboard'):
                show(obs, lv)
                got[lv] = render(sc, os.path.join(OUT, f'_{tag}_{lv}.png'))
            clear()
            per.append({lv: stats(*got[lv]) for lv in got} | dict(yaw=yaw))
            rows.append([got['full'][1], got['card'][1], got['billboard'][1]])
        # the billboard against the level that stands before it (level: the card level, or the full level for a
        # species whose card level is set aside)
        ref_lin = np.mean([p[level]['linear'] for p in per], 0)
        bb_lin = np.mean([p['billboard']['linear'] for p in per], 0)
        gain = tuple(round(float(v), 3) for v in np.clip(ref_lin / np.maximum(bb_lin, 1e-6), 0.2, 2.0))
        ratio0 = float(np.mean([p['billboard']['area'] / max(p[level]['area'], 1) for p in per]))
        cut = matching_cut(alpha_texels(species, seed, dials), ratio0)
        PI.BILLBOARD_GAIN[(species, seed, dials)] = dict(gain=gain, alpha=cut)
        for p, row in zip(per, rows):
            obs = plant(species, seed, dials, kind, size, p['yaw'])
            show(obs, 'billboard')
            lg, dg = render(sc, os.path.join(OUT, f'_{tag}_gain.png'))
            clear()
            p['gained'] = stats(lg, dg)
            row.append(dg)
        for p in per:
            p['de_before'] = round(M.delta_e(p[level]['lab'], p['billboard']['lab']), 2)
            p['de_after'] = round(M.delta_e(p[level]['lab'], p['gained']['lab']), 2)
            p['area_ratio'] = round(p['billboard']['area'] / max(p[level]['area'], 1), 3)
            p['area_ratio_after'] = round(p['gained']['area'] / max(p[level]['area'], 1), 3)
            p['card_over_full'] = round(p['card']['area'] / max(p['full']['area'], 1), 3)
        for f in os.listdir(OUT):
            if f.startswith(f'_{tag}_'):
                os.remove(os.path.join(OUT, f))
        board(os.path.join(OUT, f'{tag}.png'), rows)
        r = dict(species=species, seed=seed, dials=json.loads(dials), kind=kind, size_m=size, users=users,
                 switch_m=dist, matched_to=level, gain=list(gain), alpha=cut, turns=per,
                 card_over_full=round(float(np.mean([p['card_over_full'] for p in per])), 3),
                 de_before=round(float(np.mean([p['de_before'] for p in per])), 2),
                 de_after=round(float(np.mean([p['de_after'] for p in per])), 2),
                 area_ratio=round(float(np.mean([p['area_ratio'] for p in per])), 3),
                 area_ratio_after=round(float(np.mean([p['area_ratio_after'] for p in per])), 3),
                 seconds=round(time.time() - t0, 1))
        r['passed'] = r['de_after'] <= 3.0 and abs(r['area_ratio_after'] - 1.0) <= 0.10
        rec[tag] = r
        with open(rec_path, 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, indent=1)
        print(f"[match] {tag} ({', '.join(sorted(set(users)))}): against its {level} level: gain {gain}, alpha {cut}, "
              f"ΔE {r['de_before']} -> {r['de_after']}, area ratio {r['area_ratio']} -> {r['area_ratio_after']}; "
              f"its card level covers {r['card_over_full']} of its full level's area ({r['seconds']} s)", flush=True)
        print(f"[match]     ({species!r}, {seed}, {dials!r}): dict(gain={gain}, alpha={cut}),", flush=True)
    os._exit(0)


main()
