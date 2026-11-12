"""eidoblend.harness.assets: textures, PBR sets, models, kits and lookdev HDRIs in Blender. The WebGPU edition's
loadImageTexture / fetchPBR / loadPBR / fetchModelFile / playModelAnimations / cloneModel / loadKit, in snake_case.

    from eidoblend.harness import assets

    img = assets.load_image_texture(ctx.assets['poster'], srgb=True)          # a bpy Image (colour or data)
    mat = assets.load_pbr('Concrete031', res='1k', maps=('diff', 'normal', 'rough'), repeat=(4, 4))
    path = assets.fetch_model_file('wooden_stool_01', res='1k')               # the shared library, fetched once
    stool = assets.import_model(path)                                         # an Empty that owns the import
    crow = assets.import_model(ctx.assets['crow'])
    assets.play_model_animations(crow, clip='Peck', start=1, end=ctx.frame_end)
    crow2 = assets.clone_model(crow)                                          # its own rig, shared mesh data
    kit = assets.load_kit(ctx.assets['pipe_kit']); kit.list(); kit.get('pipe_elbow_01')

The shared library: fetch_pbr / fetch_model_file read eidoverse/assets/cache/ (or EIDO_ASSET_CACHE) and run
fetch_texture.py / fetch_model.py --cache once for an ID that is not there yet. Offline, or with EIDO_NO_FETCH=1, a
missing ID raises with the one-line fetch command. A downloaded model is CC0 (Poly Haven); read its .license.json.

Models keep their authored UVs and materials (the importer's Principled BSDF materials are the look). Real-world
scale is the default: a fetched stool is 0.44 m tall.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector

from .. import common

PBR_MAPS = {'diff': True, 'rough': False, 'normal': False, 'normal_dx': False, 'ao': False, 'metal': False,
            'displacement': False, 'arm': False, 'opacity': False, 'emissive': True}


# ------------------------------------------------------------------------------------------------- images ---

def load_image_texture(path: str, srgb: bool = True, name: str = None):
    """A bpy Image from a file, reused if already loaded. srgb=False marks data (normal, roughness, masks)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f'load_image_texture: {path} not found')
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    if name:
        img.name = name
    return img


# --------------------------------------------------------------------------------------------- the library ---

def _python():
    return os.environ.get('PYTHON') or ('python' if os.name == 'nt' else 'python3')


def _fetch(cmd_args, what):
    if os.environ.get('EIDO_NO_FETCH') == '1':
        raise FileNotFoundError(f'{what} is not in the library; fetch it with: python {" ".join(cmd_args)}')
    common.log('assets', f'{what}: not in the library yet; fetching once (CC0) ...')
    r = subprocess.run([_python(), os.path.join(common.REPO, cmd_args[0])] + cmd_args[1:], cwd=common.REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        common.log('assets', f'{what}: fetch exited {r.returncode}: {r.stderr.strip()[-300:]}')


def fetch_pbr(id: str, res: str = '1k') -> dict:
    """{'id', 'res', 'dir', 'files': {map: path}} for a texture set in the shared library (fetched once)."""
    res = str(res).lower()
    d = common.cache_dir('textures', f"{id.replace(':', '_')}_{res}")
    js = os.path.join(d, 'tex_urls.json')
    if not os.path.isfile(js):
        _fetch(['fetch_texture.py', id, res, '--cache'], f'fetch_pbr {id} ({res})')
    if not os.path.isfile(js):
        raise FileNotFoundError(f'fetch_pbr: {id} ({res}) could not be fetched; run: python fetch_texture.py {id} {res} --cache')
    with open(js, encoding='utf-8') as f:
        urls = json.load(f)
    # tex_urls.json holds the paths where it was fetched; the files sit beside it wherever the library is now
    files = {k: os.path.join(d, os.path.basename(str(v).replace('\\', '/'))) for k, v in urls.items()}
    return {'id': id, 'res': res, 'dir': d, 'files': files}


def fetch_model_file(id: str, res: str = '1k') -> str:
    """The path of a Poly Haven model in the shared library (<id>_<res>/<id>_embedded.gltf), fetched once."""
    res = str(res).lower()
    d = common.cache_dir('models', f'{id}_{res}')

    def find():
        if os.path.isdir(d):
            for n in sorted(os.listdir(d)):
                if n.endswith('_embedded.gltf') or n.endswith('.glb'):
                    return os.path.join(d, n)
        return None
    p = find()
    if not p:
        _fetch(['fetch_model.py', id, '--cache', '--res', res], f'fetch_model_file {id} ({res})')
        p = find()
    if not p:
        raise FileNotFoundError(f'fetch_model_file: {id} ({res}) could not be fetched; run: python fetch_model.py {id} --cache --res {res}')
    return p


# -------------------------------------------------------------------------------------------- PBR material ---

def load_pbr(id: str, res: str = '1k', maps=('diff', 'normal', 'rough'), repeat=None, name: str = None,
             displacement: str = None, displacement_scale: float = 0.02, normal_strength: float = 1.0):
    """A Principled BSDF material from a library set. Only the maps named are wired (a set that later gains a map
    must not change a look tuned without it).

      diff -> Base Color (sRGB)        rough -> Roughness           metal -> Metallic
      normal -> a Normal Map node (OpenGL convention, as fetched)   normal_dx -> green flipped first
      arm -> Separate Color: G roughness, B metallic (R is AO, which the Principled BSDF has no input for)
      opacity -> Alpha (the material renders DITHERED)   emissive -> Emission Color (strength 1)
      displacement -> 'bump' (a Bump node into Normal) or 'true' (material displacement, needs dense geometry)
      ao -> not wired: EEVEE's ray-traced GI and fast GI make the occlusion; a baked AO map would double it
    repeat: (u, v) tiles across the object's UVs (a Mapping node)."""
    s = fetch_pbr(id, res)
    files = s['files']
    mat = bpy.data.materials.new(name or f'{id}_{s["res"]}')
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    out = next(n for n in nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
    tc = nodes.new('ShaderNodeTexCoord')
    mp = nodes.new('ShaderNodeMapping')
    links.new(tc.outputs['UV'], mp.inputs['Vector'])
    if repeat is not None:
        r = repeat if isinstance(repeat, (tuple, list)) else (repeat, repeat)
        mp.inputs['Scale'].default_value = (float(r[0]), float(r[1]), 1.0)
    tc.location, mp.location = (-1200, 0), (-1000, 0)
    y = [300]

    def tex(key):
        path = files.get(key)
        if not path or not os.path.isfile(path):
            return None
        n = nodes.new('ShaderNodeTexImage')
        n.image = load_image_texture(path, srgb=PBR_MAPS.get(key, False))
        n.interpolation = 'Linear'
        n.location = (-700, y[0])
        y[0] -= 280
        links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n

    wired = []
    for key in maps:
        if key not in files:
            continue
        if key == 'diff':
            n = tex(key)
            links.new(n.outputs['Color'], bsdf.inputs['Base Color'])
        elif key == 'rough':
            n = tex(key)
            links.new(n.outputs['Color'], bsdf.inputs['Roughness'])
        elif key == 'metal':
            n = tex(key)
            links.new(n.outputs['Color'], bsdf.inputs['Metallic'])
        elif key in ('normal', 'normal_dx'):
            n = tex(key)
            nm = nodes.new('ShaderNodeNormalMap')
            nm.location = (-350, -300)
            nm.inputs['Strength'].default_value = normal_strength
            src = n.outputs['Color']
            if key == 'normal_dx':                                   # DirectX green -> OpenGL green
                sep = nodes.new('ShaderNodeSeparateColor')
                inv = nodes.new('ShaderNodeMath')
                inv.operation = 'SUBTRACT'
                inv.inputs[0].default_value = 1.0
                comb = nodes.new('ShaderNodeCombineColor')
                links.new(src, sep.inputs['Color'])
                links.new(sep.outputs['Green'], inv.inputs[1])
                links.new(sep.outputs['Red'], comb.inputs['Red'])
                links.new(inv.outputs[0], comb.inputs['Green'])
                links.new(sep.outputs['Blue'], comb.inputs['Blue'])
                src = comb.outputs['Color']
            links.new(src, nm.inputs['Color'])
            links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        elif key == 'arm':
            n = tex(key)
            sep = nodes.new('ShaderNodeSeparateColor')
            links.new(n.outputs['Color'], sep.inputs['Color'])
            links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
            links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
        elif key == 'opacity':
            n = tex(key)
            links.new(n.outputs['Color'], bsdf.inputs['Alpha'])
            mat.surface_render_method = 'DITHERED'
        elif key == 'emissive':
            n = tex(key)
            links.new(n.outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0
        elif key == 'displacement':
            n = tex(key)
            if displacement == 'true':
                d = nodes.new('ShaderNodeDisplacement')
                d.inputs['Scale'].default_value = displacement_scale
                links.new(n.outputs['Color'], d.inputs['Height'])
                links.new(d.outputs['Displacement'], out.inputs['Displacement'])
                mat.displacement_method = 'DISPLACEMENT'
            else:
                b = nodes.new('ShaderNodeBump')
                b.inputs['Distance'].default_value = displacement_scale
                links.new(n.outputs['Color'], b.inputs['Height'])
                nrm = bsdf.inputs['Normal'].links[0].from_socket if bsdf.inputs['Normal'].is_linked else None
                if nrm is not None:
                    links.new(nrm, b.inputs['Normal'])
                links.new(b.outputs['Normal'], bsdf.inputs['Normal'])
        elif key == 'ao':
            continue
        else:
            continue
        wired.append(key)
    mat['eido_pbr'] = f'{id}_{s["res"]}:' + ','.join(wired)
    return mat


# -------------------------------------------------------------------------------------------------- models ---

def _new_objects(before):
    return [o for o in bpy.data.objects if o not in before]


def import_model(path: str, name: str = None, collection=None, location=(0, 0, 0), fix_glass: bool = True):
    """Import a .glb / .gltf / .vrm-less glTF into its own collection, under one Empty (returned) placed at
    `location`. The Empty carries 'eido_src_asset' (the audits' provenance) and the import keeps its authored UVs,
    materials, rig and clips. glTF's +Y up becomes Blender's +Z up (the importer's own conversion): a model's
    nose along glTF +Z faces Blender -Y.

    The Empty, every object the import made and their mesh data carry 'eido_loaded_asset' (the engine's
    userData._loadedAsset): the tools that rewrite UVs and materials (the terrain family's layer_surface,
    normalize_texel_density) skip what carries it, so a whole scene root can be handed to them. clone_model's copies
    and load_kit's parts keep the mark (copied ID properties).

    Two material repairs, each logged: alpha and transmission materials get shadows and refraction that respect
    them (fix_see_through_materials); and with fix_glass, a material NAMED glass that is alpha-blended through a
    texture with no alpha (a JPEG: Poly Haven's glTF exports ship their glass this way, opaque) becomes clear thin
    glass (make_glass). fix_glass=False keeps the materials exactly as shipped."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f'import_model: {path} not found')
    name = name or os.path.splitext(os.path.basename(path))[0].replace('_embedded', '')
    scene = bpy.context.scene
    coll = collection or bpy.data.collections.new(name)
    if coll.name not in scene.collection.children and collection is None:
        scene.collection.children.link(coll)
    before = set(bpy.data.objects)
    acts_before = {a.name for a in bpy.data.actions}
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.glb', '.gltf'):
        bpy.ops.import_scene.gltf(filepath=path)
        _stamp_clip_names(acts_before)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == '.obj':
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f'import_model: {ext} files are not handled here (VRM: the characters family)')
    # only what the importer put in the scene for the model (it selects those). It also makes helper objects that
    # must stay where it put them: the glTF importer's 'Icosphere' bone-display shape (2 m across) lives in a
    # 'glTF_not_exported' collection excluded from the view layer; relinked, it renders over the model
    created = _new_objects(before)
    new = [o for o in created if o.select_get()] or [
        o for o in created if o.users_collection and not any(c.name.startswith('glTF_not_exported')
                                                              for c in o.users_collection)]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    mats = {s.material for o in new for s in o.material_slots if s.material}
    if fix_glass:
        for m in sorted(mats, key=lambda m: m.name):
            if 'glass' in m.name.lower() and _opaque_blend(m):
                make_glass(m)
                common.log('assets', f"{os.path.basename(path)}: material '{m.name}' is alpha-blended through a "
                           'texture with no alpha (it would render opaque): made clear glass (fix_glass=False keeps it)')
    fix_see_through_materials(mats)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.2
    coll.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
    root.location = location
    root['eido_src_asset'] = os.path.abspath(path)
    coll['eido_src_asset'] = os.path.abspath(path)
    for o in [root] + new:
        o['eido_loaded_asset'] = True
        if o.data is not None and o.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
            o.data['eido_loaded_asset'] = True
    order = _importer_clip_order(root)
    if order:
        root['eido_clip_order'] = order                          # clip=<index> keeps the file's order after plays
    return root


def fix_see_through_materials(materials) -> list:
    """Imported glass and alpha-cut materials, made to read in EEVEE as they read in a glTF viewer:

      alpha (a linked or < 1 Alpha)  -> shadows that respect the alpha (EEVEE's default is an OPAQUE shadow, which
                                        puts whatever is behind a clock glass or a leaf card in full shade)
      transmission (> 0 or linked)   -> ray-traced refraction (else only light probes show through: black in a dark
                                        room), thickness SLAB (glTF without KHR_materials_volume is thin-walled),
                                        transparent shadows
    Returns the names of the materials changed."""
    changed = []
    for m in materials:
        if not m or not m.use_nodes or not m.node_tree:
            continue
        b = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
        if b is None:
            continue
        a, tw = b.inputs.get('Alpha'), b.inputs.get('Transmission Weight')
        see_alpha = a is not None and (a.is_linked or a.default_value < 0.999)
        see_trans = tw is not None and (tw.is_linked or tw.default_value > 0.001)
        if not (see_alpha or see_trans):
            continue
        if hasattr(m, 'use_transparent_shadow'):
            m.use_transparent_shadow = True
        if see_trans:
            if hasattr(m, 'use_raytrace_refraction'):
                m.use_raytrace_refraction = True
            if hasattr(m, 'thickness_mode'):
                m.thickness_mode = 'SLAB'
        changed.append(m.name)
    return changed


def _opaque_blend(m) -> bool:
    """Alpha-blended, its Alpha fed by an image whose alpha is 1 everywhere."""
    if getattr(m, 'surface_render_method', '') != 'BLENDED' or not m.use_nodes:
        return False
    b = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if b is None or not b.inputs['Alpha'].is_linked:
        return False
    src = b.inputs['Alpha'].links[0].from_node
    if src.bl_idname != 'ShaderNodeTexImage' or src.image is None:
        return False
    import numpy as np
    im = src.image
    px = np.empty(im.size[0] * im.size[1] * im.channels, np.float32)
    im.pixels.foreach_get(px)
    return im.channels < 4 or float(px.reshape(-1, im.channels)[:, 3].min()) > 0.999


def make_glass(m, tint=(1.0, 1.0, 1.0), roughness: float = 0.02, alpha: float = 0.12, refract: bool = False,
               ior: float = 1.5):
    """Make a Principled material read as clear glass in EEVEE.

    thin (default): an alpha-blended sheet with a glass sheen, so what sits just behind a pane stays sharp: a clock
        dial, a gauge, a picture under glass. EEVEE's screen-space refraction loses things a few millimetres behind
        a pane (on Poly Haven's alarm clock refractive glass shows a dark disc, thin glass the dial).
    refract=True: transmission 1, ray-traced refraction, SLAB thickness; for glass whose subject is well behind it
        (a window onto a room, a bottle on a table) where bending the view is the point.
    Both cast shadows that let light through."""
    b = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    for name in ('Base Color', 'Alpha', 'Roughness', 'Metallic'):
        for l in list(b.inputs[name].links):
            m.node_tree.links.remove(l)
    b.inputs['Base Color'].default_value = (*tint, 1.0)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = roughness
    b.inputs['IOR'].default_value = ior
    if refract:
        b.inputs['Alpha'].default_value = 1.0
        b.inputs['Transmission Weight'].default_value = 1.0
        m.surface_render_method = 'DITHERED'
        m.use_raytrace_refraction = True
        m.thickness_mode = 'SLAB'
    else:
        b.inputs['Alpha'].default_value = alpha
        b.inputs['Transmission Weight'].default_value = 0.0
        m.surface_render_method = 'BLENDED'
    m.use_transparent_shadow = True
    return m


def subtree(root):
    return [root] + list(root.children_recursive)


def bounds(root, evaluated=True):
    """World-space (min, max) Vectors of every mesh under root (root included)."""
    bpy.context.view_layer.update()
    lo, hi = Vector((math.inf,) * 3), Vector((-math.inf,) * 3)
    for o in subtree(root):
        if o.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META') or o.hide_render:
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    if lo.x == math.inf:
        raise ValueError(f"bounds: '{root.name}' has no geometry")
    return lo, hi


def rest_on(root, z: float = 0.0, xy=None):
    """Move root so the bottom of its geometry sits at height z (and its footprint centre at xy, if given)."""
    lo, hi = bounds(root)
    root.location.z += z - lo.z
    if xy is not None:
        root.location.x += xy[0] - (lo.x + hi.x) / 2
        root.location.y += xy[1] - (lo.y + hi.y) / 2
    bpy.context.view_layer.update()
    return root


def _stamp_clip_names(acts_before):
    """Each action a glTF import made carries its clip's own name as 'eido_clip': Blender makes action names unique
    across the file, so a second model with a 'Walk' clip gets 'Walk.001', where three kept every glTF's own names."""
    import re
    for a in bpy.data.actions:
        if a.name in acts_before or 'eido_clip' in a:
            continue
        m = re.match(r'^(.*)\.\d{3}$', a.name)
        a['eido_clip'] = m.group(1) if m and m.group(1) in acts_before else a.name


def _clip_key(act):
    """An action's clip name (its glTF name), or None for the action a clip='all' mix baked."""
    if act is None or act.get('eido_mix'):
        return None
    return act.get('eido_clip') or act.name


def _importer_clip_order(root):
    """The clips in the glTF importer's order (three's gltf.animations order): each rig's active action first, then
    its NLA tracks bottom-up; the tracks play_model_animations adds (eido_*) are not the importer's."""
    order = []
    for o in subtree(root):
        ad = o.animation_data
        if not ad:
            continue
        acts = ([ad.action] if ad.action else []) + [s.action for t in reversed(list(ad.nla_tracks))
                                                      if not t.name.startswith('eido_') for s in t.strips if s.action]
        for a in acts:
            k = _clip_key(a)
            if k is not None and k not in order:
                order.append(k)
    return order


def model_clips(root) -> dict:
    """{clip name: action} for the actions the glTF importer left on the rigs under root (active + NLA tracks),
    by each clip's own glTF name (a clone's own copies included); a clip='all' mix is not a clip."""
    clips = {}
    for o in subtree(root):
        ad = o.animation_data
        if not ad:
            continue
        acts = ([ad.action] if ad.action else []) + [s.action for t in ad.nla_tracks for s in t.strips if s.action]
        for a in acts:
            k = _clip_key(a)
            if k is not None:
                clips.setdefault(k, a)
    return clips


def _clip_slot(act, o):
    """The slot of a clip's action that animates o: by o's own name, or the name of the object a clone copied."""
    names = {f'OB{o.name}', f"OB{o.get('eido_clone_of', o.name)}"}
    return next((s for s in act.slots if s.target_id_type == 'OBJECT' and
                 (s.identifier in names or len(act.slots) == 1)), None)


def _clip_curves(act, slot):
    """{(data_path, index): fcurve} of one action slot (Blender 5.x layered actions)."""
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, slot)
    return {} if cb is None else {(fc.data_path, fc.array_index): fc for fc in cb.fcurves}


def _qslerp(a, b, t):
    """three's Quaternion.slerpFlat on (w, x, y, z) tuples: the shortest arc, normalised lerp when nearly parallel."""
    from mathutils import Quaternion
    qa, qb = Quaternion(a), Quaternion(b)
    if qa.dot(qb) < 0:
        qb = -qb
    return tuple(qa.slerp(qb, t))


def _original(o, path, idx):
    """The value a property has before any clip moves it (three's PropertyMixer 'original'): a pose bone's rest pose
    (identity in pose space), else the object's own current value."""
    base = path.rsplit('.', 1)[-1]
    if path.startswith('pose.bones['):
        return {'location': 0.0, 'rotation_quaternion': (1.0, 0.0, 0.0, 0.0)[idx] if idx < 4 else 0.0,
                'rotation_euler': 0.0, 'rotation_axis_angle': (0.0, 0.0, 1.0, 0.0)[idx] if idx < 4 else 0.0,
                'scale': 1.0}.get(base, 0.0)
    try:
        v = o.path_resolve(path)
        return float(v[idx]) if hasattr(v, '__len__') else float(v)
    except (ValueError, TypeError, IndexError):
        return 0.0


def clip_span(act):
    """(first frame, length in frames) of an imported clip as three's AnimationMixer plays it. A glTF clip's clock
    starts at time 0 even when its first key is later (a Blender export's first key sits at frame 1 = 1/24 s): the
    value before the first key holds, and the clip loops on its LAST key's time (AnimationClip.duration). The importer
    puts glTF time t at frame t x fps, so the clip runs from frame 0 (or its first key, if that is earlier) to its
    last key."""
    a0, a1 = act.frame_range
    c0 = min(0.0, float(a0))
    return c0, max(1e-6, float(a1) - c0)


def _mix_clips(root, chosen, clips, weights, start, end, speed, offset, repeat, fps):
    """three's AnimationMixer with every chosen clip playing at its weight, baked into one LINEAR action per animated
    object (keyed data: every frame renders the same, jumped to or played up to).

    Per animated property the mixer blends only the clips that animate it, in order, each by weight / (the summed
    weight so far): the weighted mean of their values (quaternions by slerp along that chain, as three's
    PropertyMixer does). When the weights on a property sum to less than 1, the rest pose fills the remainder (the
    mixer's 'original'), so a lone clip at weight 0.5 plays half way out of the rest pose. Each clip loops on its
    own length."""
    import numpy as np
    from mathutils import Quaternion
    frames = list(range(int(start), int(end) + 1))
    made = []
    for o in subtree(root):
        ad = o.animation_data
        if not ad:
            continue
        per = []                                                  # (weight, curves, a0, length) per clip
        for cname, w in zip(chosen, weights):
            if w <= 0:
                continue
            act = clips[cname]
            slot = _clip_slot(act, o)
            if slot is None:
                continue
            curves = _clip_curves(act, slot)
            if not curves:
                continue
            c0, length = clip_span(act)
            per.append((float(w), curves, c0, length))
        if not per:
            continue
        props = {}
        for _w, curves, _a0, _len in per:
            for (path, idx) in curves:
                props.setdefault(path, set()).add(idx)
        out = {}                                                  # (path, idx) -> [values per frame]
        for f in frames:
            local = (f - start) * speed + offset * fps            # clip frames since the clip's own start
            for path, idxs in props.items():
                quat = path.endswith('rotation_quaternion')
                acc, cum = None, 0.0
                for w, curves, a0, length in per:
                    if not any((path, i) in curves for i in idxs):
                        continue
                    lt = (local % length) if repeat else min(max(local, 0.0), length)
                    t = a0 + lt
                    if quat:
                        v = tuple(curves[(path, i)].evaluate(t) if (path, i) in curves else (1.0, 0, 0, 0)[i]
                                  for i in range(4))
                        v = tuple(Quaternion(v).normalized())
                    else:
                        v = {i: curves[(path, i)].evaluate(t) for i in idxs if (path, i) in curves}
                    cum += w
                    if acc is None:
                        acc = v
                    elif quat:
                        acc = _qslerp(acc, v, w / cum)
                    else:
                        k = w / cum
                        acc = {i: (acc[i] + (v[i] - acc[i]) * k) if (i in acc and i in v) else v.get(i, acc.get(i))
                               for i in set(acc) | set(v)}
                if acc is None:
                    continue
                if cum < 1.0:                                     # the mixer fills the rest from the original
                    k = 1.0 - cum
                    if quat:
                        acc = _qslerp(acc, tuple(_original(o, path, i) for i in range(4)), k)
                    else:
                        acc = {i: acc[i] + (_original(o, path, i) - acc[i]) * k for i in acc}
                items = enumerate(acc) if quat else acc.items()
                for i, val in items:
                    out.setdefault((path, i), []).append((f, float(val)))
        act = bpy.data.actions.new(f'eido_mix_{root.name}_{o.name}')
        act['eido_mix'] = True                                    # a bake of clips, not a clip (model_clips skips it)
        ad.action = act
        slot = ad.action_slot
        if slot is None:
            slot = act.slots.new('OBJECT', o.name)
            ad.action_slot = slot
        from bpy_extras import anim_utils
        cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
        for (path, idx), kv in sorted(out.items()):
            fc = cb.fcurves.new(path, index=idx)
            fc.keyframe_points.add(len(kv))
            co = np.array(kv, dtype=np.float32).ravel()
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [1] * len(kv))      # LINEAR
            fc.update()
        made.append(o.name)
    return made


def play_model_animations(root, clip=0, start: int = None, end: int = None, speed: float = 1.0, offset: float = 0.0,
                          repeat: bool = True, weights=None):
    """Play an imported model's own clip on its rigs: one NLA strip per animated object, from frame `start` to `end`
    (default: the scene's range), repeated to fill it. clip: an index, a name, or 'all'. offset: seconds into the
    clip at `start` (de-sync a flock). The importer's other clips stay as muted NLA tracks. Returns the clip names
    played.

    clip='all' plays every clip at once the way three's AnimationMixer did: per property, the weighted mean of the
    clips that animate it, in the file's clip order (all weights 1 unless `weights` gives {clip name: weight} or a
    list in name order; weight 0 leaves a clip out), baked into one LINEAR action per animated object. Clips that
    animate different bones layer in full; clips on the same bones average, which is the engine's warning: 'all' is
    for clips meant to layer. Returns the clips played, in name order."""
    scene = bpy.context.scene
    start = scene.frame_start if start is None else int(start)
    end = scene.frame_end if end is None else int(end)
    clips = model_clips(root)
    if not clips:
        common.log('assets', f"play_model_animations: '{root.name}' has no embedded animations (animate it by hand)")
        return []
    names = sorted(clips)
    if clip == 'all':
        chosen = names
        if weights is None:
            ws = [1.0] * len(chosen)
        elif isinstance(weights, dict):
            unknown = sorted(set(weights) - set(chosen))
            if unknown:
                raise KeyError(f"play_model_animations: weights for clips '{root.name}' does not have: {unknown}")
            ws = [float(weights.get(c, 1.0)) for c in chosen]
        else:
            ws = [float(w) for w in weights]
            if len(ws) != len(chosen):
                raise ValueError(f'play_model_animations: {len(ws)} weights for {len(chosen)} clips ({chosen})')
        fps = scene.render.fps / scene.render.fps_base
        for o in subtree(root):
            if o.animation_data:
                for t in o.animation_data.nla_tracks:
                    t.mute = True
        # mixed in the file's order, as three's mixer activated gltf.animations (rotations slerp along that chain:
        # with three or more clips on one bone the order shows); the weights stay by name
        wmap = dict(zip(chosen, ws))
        mix = [k for k in (root.get('eido_clip_order') or _importer_clip_order(root)) if k in clips]
        mix += [k for k in chosen if k not in mix]
        made = _mix_clips(root, mix, clips, [wmap[c] for c in mix], start, end, speed, offset, repeat, fps)
        common.log('assets', f"play_model_animations: '{root.name}' plays all {len(chosen)} clip(s) mixed by weight "
                   f"({', '.join(f'{c} {wmap[c]:g}' for c in mix)}), baked on {len(made)} object(s)")
        return [c for c, w in zip(chosen, ws) if w > 0]
    if isinstance(clip, int):
        order = [k for k in (root.get('eido_clip_order') or _importer_clip_order(root)) if k in clips]
        chosen = [order[clip]]
    else:
        if clip not in clips:
            raise KeyError(f"play_model_animations: no clip {clip!r} on '{root.name}'; clips: {', '.join(names)}")
        chosen = [clip]
    fps = scene.render.fps / scene.render.fps_base
    for o in subtree(root):
        ad = o.animation_data
        if not ad:
            continue
        ad.action = None
        for t in ad.nla_tracks:
            t.mute = True
        for cname in chosen:
            act = clips[cname]
            slot = _clip_slot(act, o)
            if slot is None:
                continue
            c0, span = clip_span(act)                          # three's clip clock: from time 0 to the last key
            length = max(1.0, span / max(1e-6, speed))
            off = offset * fps / max(1e-6, speed)
            first = start - off
            reps = math.ceil((end - first + 1) / length) if repeat else 1
            tr = ad.nla_tracks.new()
            tr.name = f'eido_{cname}'
            st = tr.strips.new(cname, int(math.floor(first)), act)
            if hasattr(st, 'action_slot'):
                st.action_slot = slot
            # the strip took its length from the slot strips.new picked by the object's name (none on a clone: a
            # one-frame strip); the clip's own range, set after the slot: from time 0 (hold the first key) to its end
            st.action_frame_end = c0 + span
            st.action_frame_start = c0
            st.scale = 1.0 / max(1e-6, speed)
            st.repeat = max(1, reps)
            st.extrapolation = 'HOLD' if not repeat else 'NOTHING'
            st.blend_type = 'REPLACE' if cname == chosen[0] else 'COMBINE'
    return chosen


def _same_slot(action, slot):
    """The slot of `action` with `slot`'s identifier (a copied action keeps its slots' identifiers)."""
    if action is None or slot is None:
        return None
    return next((s for s in action.slots if s.identifier == slot.identifier), None)


def clone_model(root, name: str = None, location=None, independent_actions: bool = False):
    """A copy of an imported model with its OWN rig (posed and animated independently), the mesh data shared: the
    engine's cloneModel (SkeletonUtils.clone). Armature modifiers and parenting are re-pointed to the copies.

    The clips' actions are shared by default (an NLA strip per copy already plays them independently: play a
    different clip or offset on the copy with play_model_animations). independent_actions=True gives the copy its
    OWN copy of every action it carries (NLA strips and the active action), named '<action>.<clone name>', so keys
    edited on one copy never move the other."""
    mapping = {}
    coll = root.users_collection[0] if root.users_collection else bpy.context.scene.collection
    new_name = name or root.name + '.copy'
    copies = {}

    def act_for(a):
        if a is None or not independent_actions:
            return a
        if a.name not in copies:
            c = a.copy()
            c.name = f'{a.name}.{new_name}'
            if not a.get('eido_mix'):
                c['eido_clip'] = _clip_key(a)                     # still played by its own name on the copy
            copies[a.name] = c
        return copies[a.name]
    for o in subtree(root):
        c = o.copy()                                                  # shares mesh data; copies modifiers, anim data
        c['eido_clone_of'] = o.get('eido_clone_of', o.name)           # the clips' slots name the original
        if o.animation_data:
            src_ad = o.animation_data
            c.animation_data_clear()
            ad = c.animation_data_create()
            for t in src_ad.nla_tracks:
                nt = ad.nla_tracks.new()
                nt.name, nt.mute = t.name, t.mute
                for s in t.strips:
                    ns = nt.strips.new(s.name, int(s.frame_start), act_for(s.action))
                    sl = _same_slot(ns.action, getattr(s, 'action_slot', None))
                    if sl is not None:
                        ns.action_slot = sl
                    # the copy's strip was sized to the slot strips.new found by the copy's name (none: one frame)
                    ns.action_frame_end = s.action_frame_end
                    ns.action_frame_start = s.action_frame_start
                    ns.scale, ns.repeat, ns.blend_type = s.scale, s.repeat, s.blend_type
                    if abs(ns.frame_start - s.frame_start) > 1e-6:
                        ns.frame_start_ui = s.frame_start             # a fractional start (an offset flock)
                    ns.extrapolation = s.extrapolation
                    ns.influence = s.influence
            if src_ad.action is not None:
                ad.action = act_for(src_ad.action)
                sl = _same_slot(ad.action, src_ad.action_slot)
                if sl is not None:
                    ad.action_slot = sl
        coll.objects.link(c)
        mapping[o] = c
    for o, c in mapping.items():
        if o.parent in mapping:
            c.parent = mapping[o.parent]
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        for m in c.modifiers:
            if getattr(m, 'object', None) in mapping:
                m.object = mapping[m.object]
    new_root = mapping[root]
    new_root.name = new_name
    if location is not None:
        new_root.location = location
    if independent_actions:
        new_root['eido_own_actions'] = sorted(a.name for a in copies.values())
    return new_root


# ------------------------------------------------------------------------------------------------------ kits ---

def _parts_host(root):
    """model_kit.js's _partsRoot: descend single-child wrapper nodes (Scene > RootNode > [parts]) to the level that
    actually holds the kit's parts."""
    n = root
    while len(n.children) == 1 and len(n.children[0].children) > 1:
        n = n.children[0]
    return n


def _has_geometry(o):
    return any(d.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META') for d in subtree(o))


class Kit:
    """A model that is a catalogue of parts (the engine's loadKit). Each part (an object of the import's parts level,
    with its children) moves into a collection of its own that is not in the scene (so the catalogue row never
    renders), with its instance offset at the bottom centre of its geometry: get() places a collection instance
    standing on its base. The parts keep their authored geometry, UVs and materials; get() the same name again for
    another copy. The placement family seats and audits these instances by their real geometry."""

    def __init__(self, root):
        self.root = root
        self.parts = {}
        self.boxes = {}
        self._islands = None
        bpy.context.view_layer.update()
        host = _parts_host(root)
        for o in [c for c in host.children if _has_geometry(c)]:
            lo, hi = bounds(o)
            mw = o.matrix_world.copy()
            c = bpy.data.collections.new(f'kit_{o.name}')
            for d in [o] + list(o.children_recursive):
                for uc in list(d.users_collection):
                    uc.objects.unlink(d)
                c.objects.link(d)
            o.parent = None
            o.matrix_world = mw
            c.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
            c['eido_src_asset'] = root.get('eido_src_asset', '')
            self.parts[o.name] = c
            self.boxes[o.name] = (lo.copy(), hi.copy())
        self.names = list(self.parts)                        # the catalogue's own order
        self.count = len(self.names)

    def list(self):
        """The part names in the catalogue's own order, as the engine's list() (a copy of names)."""
        return list(self.names)

    def family(self, prefix: str, location=(0, 0, 0)):
        """One instance of each part whose name starts with prefix (case-insensitive, as the engine's), in the
        catalogue's order."""
        pf = str(prefix).lower()
        return [self.get(n, location) for n in self.list() if n.lower().startswith(pf)]

    def _instance(self, name, coll, location, rotation_z):
        e = bpy.data.objects.new(name, None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = coll
        e.location = location
        e.rotation_euler = (0, 0, rotation_z)
        e['eido_src_asset'] = self.root.get('eido_src_asset', '')
        e['eido_loaded_asset'] = True
        bpy.context.scene.collection.objects.link(e)
        return e

    def get(self, name: str, location=(0, 0, 0), rotation_z: float = 0.0):
        """A collection instance of one part (an Empty), standing on its base at `location`."""
        if name not in self.parts:
            raise KeyError(f"kit: no part {name!r}; parts: {', '.join(self.list()[:20])}")
        return self._instance(name, self.parts[name], location, rotation_z)

    def part(self, i: int, location=(0, 0, 0), rotation_z: float = 0.0):
        """The i-th part in the catalogue's own order (None past the end), as get()."""
        return self.get(self.names[i], location, rotation_z) if 0 <= i < self.count else None

    def island_groups(self):
        """[[part names]] per spatially separate piece: parts whose boxes, grown by 0.15 x the median part diagonal,
        touch are one island (union-find, model_kit.js's islands())."""
        names = self.names
        boxes = [self.boxes[n] for n in names]
        diags = sorted((b[1] - b[0]).length for b in boxes)
        eps = (diags[len(diags) >> 1] if diags else 1.0) * 0.15
        par = list(range(len(boxes)))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if all(a[0][k] - eps <= b[1][k] and b[0][k] <= a[1][k] + eps for k in range(3)):
                    par[find(i)] = find(j)
        groups = {}
        for i, n in enumerate(names):
            groups.setdefault(find(i), []).append(n)
        return list(groups.values())

    def islands(self, location=(0, 0, 0), rotation_z: float = 0.0):
        """One instance per spatially separate piece (a multi-part plant is ONE island, a row of three plants is
        three), each standing on its base at `location`: an island's collection holds its parts' collections."""
        if self._islands is None:
            self._islands = []
            for k, group in enumerate(self.island_groups()):
                c = bpy.data.collections.new(f'kit_island_{k}')
                lo = Vector(map(min, *[self.boxes[n][0] for n in group])) if len(group) > 1 else self.boxes[group[0]][0]
                hi = Vector(map(max, *[self.boxes[n][1] for n in group])) if len(group) > 1 else self.boxes[group[0]][1]
                for n in group:
                    c.children.link(self.parts[n])
                c.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
                c['eido_src_asset'] = self.root.get('eido_src_asset', '')
                c['eido_kit_parts'] = list(group)
                self._islands.append(c)
        return [self._instance(f'kit_island_{k}', c, location, rotation_z) for k, c in enumerate(self._islands)]


def load_kit(path_or_root) -> Kit:
    """A kit from a model file (imported here) or a model already imported with import_model."""
    root = import_model(path_or_root) if isinstance(path_or_root, str) else path_or_root
    return Kit(root)


# ---------------------------------------------------------------------------------------------------- HDRIs ---

def load_hdri(path: str, strength: float = 1.0, rotation_deg: float = 0.0, visible: bool = True, name: str = 'hdri'):
    """A World lit by an equirectangular HDRI (.hdr / .exr, read natively). For lookdev and studio light only:
    a set that needs a sky uses the sky family's make_sky, never a photo of one. visible=False lights the scene
    while the camera sees a dark background."""
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)
    tc = nodes.new('ShaderNodeTexCoord')
    mp = nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(rotation_deg))
    env = nodes.new('ShaderNodeTexEnvironment')
    env.image = load_image_texture(path, srgb=False)
    env.image.colorspace_settings.name = 'Linear Rec.709'
    bg = nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    out = nodes.new('ShaderNodeOutputWorld')
    links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    links.new(mp.outputs['Vector'], env.inputs['Vector'])
    links.new(env.outputs['Color'], bg.inputs['Color'])
    if visible:
        links.new(bg.outputs['Background'], out.inputs['Surface'])
    else:
        lp = nodes.new('ShaderNodeLightPath')
        dark = nodes.new('ShaderNodeBackground')
        dark.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        mix = nodes.new('ShaderNodeMixShader')
        links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        links.new(bg.outputs['Background'], mix.inputs[1])
        links.new(dark.outputs['Background'], mix.inputs[2])
        links.new(mix.outputs['Shader'], out.inputs['Surface'])
    bpy.context.scene.world = w
    return w
