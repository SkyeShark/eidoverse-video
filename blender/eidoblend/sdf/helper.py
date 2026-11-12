"""register_sdf_helper and help(): the engine's renderer integration, and its agent-discoverable API reference.

The engine kept SDF meshes in a helper-owned shadow scene and patched renderer.render to composite them over the
main scene: the proxy boxes wrote marched depth, a pass-type uniform answered the GTAO normal pre-pass, the scene's
HDRI was copied into each SDF's uEnvMap every frame, and transparent volumes were re-sorted back to front.

In Blender an SDF solid is a mesh and an SDF volume a Volume object: EEVEE draws them into every pass (depth,
normals, AO, shadows, reflections, motion vectors) like any other geometry, lights them with the world, and
integrates overlapping volumes physically. What registering still does here: it links the SDF collection into the
scene, and binds the world's environment image to every SDF program, so an example's sampleEnvMap() (in its shade()
or surface()) sees the same HDRI EEVEE lights with (the engine's uEnvMap / uEnvMapStrength).
"""

from __future__ import annotations

import weakref

_LIVE = weakref.WeakSet()


def track(sdf):
    """Remember an SdfObject / SdfVolume so register_sdf_helper can bind the environment to it."""
    try:
        _LIVE.add(sdf)
    except TypeError:
        pass
    return sdf


def world_environment_image(scene):
    """The image of the world's Environment Texture node, or None (a colour or sky world has none)."""
    w = scene.world
    if w is None or not w.use_nodes or w.node_tree is None:
        return None
    for n in w.node_tree.nodes:
        if n.type == 'TEX_ENVIRONMENT' and n.image is not None:
            return n.image
    return None


def register_sdf_helper(scene=None, main_scene=None, strength=None):
    """The engine's registerSdfHelper(renderer, mainScene). Pass the scene (as either argument). Links the SDF
    collection into it and binds the world's HDRI as sampleEnvMap's image for every tracked SDF (strength: the world
    background strength unless given; no HDRI: strength 0, sampleEnvMap returns the engine's mid grey). Returns
    {'sdf': count, 'env': image name or None}."""
    import bpy
    from .spec import sdf_collection
    sc = main_scene or scene or bpy.context.scene
    if not hasattr(sc, 'collection'):
        sc = bpy.context.scene
    sdf_collection(sc)
    img = world_environment_image(sc)
    if strength is None and img is not None:
        bg = next((n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND'), None)
        strength = float(bg.inputs['Strength'].default_value) if bg is not None else 1.0
    n = 0
    for sdf in list(_LIVE):
        prog = getattr(sdf, 'program', None)
        if prog is None:
            continue
        if img is not None:
            prog.set_env_map(img, strength)
        else:
            prog.values['uEnvMapStrength'] = 0.0
        n += 1
    return {'sdf': n, 'env': img.name if img is not None else None}


HELP = r"""
---------- eidoblend.sdf: the SDF engine, Blender 5.2 EEVEE edition ----------

Build any SDF (characters, vehicles, buildings, abstract geometry) as REAL geometry: the GLSL map() is evaluated
on the GPU, dual-contoured into a quad mesh at film resolution, and its surface() baked to textures. EEVEE then
lights, shadows, reflects and depth-tests it like any mesh. EXAMPLES are templates; the power is your own map().

== Roll your own ==
    from eidoblend.sdf import create_sdf_object
    sdf = create_sdf_object(
        bounds={'min': [-1.5, -1, -1.5], 'max': [1.5, 1, 1.5]},     # the SDF's local frame, three style (y up)
        quality='balanced',
        map='''vec2 map(vec3 p) {
                 float a = sdSphere(p - vec3(-0.4, 0.0, 0.0), 0.5);
                 float b = sdSphere(p - vec3( 0.4, 0.0, 0.0), 0.5);
                 return vec2(smin(a, b, 0.3), 1.0); }''',
        surface='''SdfSurface surface(vec3 p, vec3 n, float mat) {
                 return sdfSurface(vec3(0.85, 0.45, 0.25), 0.5); }''',
        shade='''vec3 shade(vec3 p, vec3 n, float mat) {     // optional: the engine's lit look, its own contract
                 vec3 L = normalize(vec3(0.5, 0.9, 0.4));
                 return vec3(0.85, 0.45, 0.25) * (0.4 + 0.6 * max(0.0, dot(n, L))); }''',
        location=(0, 0, 1))
    sdf.object                     # the bpy object;  sdf.place_on_ground(0.0)
    sdf.bake(1, 120)               # uTime-animated: re-meshed per frame, a PLY sequence played by Geometry Nodes

== Primitives (auto-included in every GLSL stage) ==
  sdSphere(p, r) sdSphere(p, c, r)  sdBox(p, b)  sdRoundBox(p, b, r)  sdCapsule(p, a, b, r)  sdCap2(p, a, b, r1, r2)
  sdEllipsoid(p, r) sdEllipsoid(p, c, r)  sdTorus(p, vec2(R, r))  sdCone(p, vec2(sin, cos), h)
  sdRoundCone(p, a, b, r1, r2)  sdTriPrism(p, hx, hz)
  smin smax opU opSmoothU opSub opSmoothSub opInt  opRotateX/Y/Z(p, a)  opMirrorX/Z(p)  _hash vnoise fbm fbm6
  calcNormal(p) softShadow(ro, rd, mint, maxt, k) sampleEnvMap(dir) sdfReflectWorld(p, n)   uTime cameraPosition
  The same library in Python over numpy: SDF_NP (= SDF_TSL), sd_sphere ... fbm6; map / surface may be Python.

== surface(p, n, mat) -> SdfSurface (what EEVEE renders) ==
  sdfSurface(albedo, roughness), then .metallic .emission .sheen .sheenTint .subsurface .coat .specular
  .transmission. Baked per texel ('atlas', default) with an object-space normal map, or per vertex ('vertex').

== Options of create_sdf_object(spec, **overrides) ==
  map / surface / shade / extra (GLSL or Python), bounds, quality ('fast' | 'balanced' | 'high' | 'ultra'),
  max_steps / max_dist / step_scale / surf_eps (the engine's march numbers, kept as set),
  uniforms {'uName': value | (type, value)},
  textures {sampler: image}, defines, voxel / cells (mesh resolution), texels (atlas texels per quad side),
  carrier ('atlas' | 'vertex'), normals ('corner' | 'vertex'), iso (level set, for distance estimators),
  refine, qef_lambda, min_component, materials {mat id: bpy Material}, material_settings, cache_dir, time,
  shade_as ('albedo' | 'emission': a map + shade spec with no surface renders its shade() colour),
  cut_by_bounds (a shape that runs past its box on purpose), atlas_budget, pack_images,
  location / rotation / scale / name / scene / collection, build.
  Python SDFs read S.time (uTime) and S.uniform('uName') while they are evaluated; a Python shade or surface may
  take the engine's ctx as a 4th argument (ctx.ro, ctx.rd, ctx.softShadow(ro, rd, mint, maxt, k), ctx.calcNormal(p)).
  Cache files are named for the object (two objects of one example keep their own); a frame with no surface is an
  empty mesh.

== Volumes ==
  create_sdf_volume(sample=GLSL | medium=GLSL, bounds, steps, post, cells | voxel, ...) -> a Volume object
  sample: SdfSample sample(vec3 p) -> sdfSample(color, alpha, step)   (the engine's contract, converted exactly;
          sample_as='albedo' reads the colour as scattering, lit by the scene)
  medium: SdfMedium medium(vec3 p) -> sdfMedium(density, albedo, emission)  (+ .temperature)
  explosion_ring flame smoke gyroid_fireball bonfire candle_flame fire nuclear_blast (examples_volumes.py, tools-guides/sdf-explosions.md)
  EXAMPLES['bonfire'].make(cells=200, build=False).bake(1, 120); make(look='lit'): fire emits, smoke scatters the scene's light
  light_from_emission(vol) / light_from_surface(sdf): keyed lamps (EEVEE's volume emission lights no surface)
  fit_volume_range(scene, camera, [vols]): the froxel range over these and every other scene volume; build_still(vol, t)
  nuclear_explosion.apply_to(scene, camera, {origin, scale, timeOffset, loopSeconds, opacity}) -> .bake(fs, fe) .update(t) .key_opacity(f, v)

== Screens ==
  make_sdf_texture(recipe='mandelbulb' | 'sierpinski_tetra' | 'menger_sponge' | 'gyroid', width, height, ...)
  .update(t) .bake(fs, fe, controls=) .material(emission_strength=0.9) .set_uniform(name, v)
  encoding='linear' (the engine's look: its sRGB render target read the shader's values as linear light, the
  default) | 'srgb' (the values as display colours: darker); update(t) packs its frame into the .blend
  make_explosion_texture(width, height, camera_pos, camera_target, time_scale, time_offset, update_every)
  the mushroom-cloud detonation on a 15 s loop; .set_camera_pos(x, y, z) .set_camera_target(x, y, z), as above

== Voxels ==
  rhombic_dodecahedron: create_rhombic_dodecahedron(radius) fill_volume_rd fill_sphere_rd voxelize_mesh_rd .reveal()

== EXAMPLES ==
  %(examples)s
  EXAMPLES['name'].make(**overrides) builds one; register_example(name, ...) adds yours.
  Vehicles: EXAMPLES['stylized_modern_sedan' | 'stylized_cyberpunk_sedan' | 'stylized_sci_fi_sleek_car' |
  'stylized_fighter_jet'].make(paint_color=, paint_roughness=, decal_text=, metal_color=, camo=, lamps=, quality=)
  -> .set_paint() .set_camo() .set_decal_text() .key_uniform(name, frame, value) .live_uniforms .lamps
  (tools-guides/sdf-vehicles.md)

== Gotchas ==
  * bounds must hold the whole shape: the surface is closed at the bounds box (the engine never drew outside it).
  * bounds.min is the real lowest point: place_on_ground() seats the mesh's lowest vertex on the plane.
  * thin parts need voxels finer than their thickness: raise quality or pass voxel=.
  * distance estimators (fractals) mesh their DE = iso level set; give iso ~ the march's surfEps * distance.
"""


def help():  # noqa: A001 - the engine's name
    """Print (and return) the API reference, with the registered EXAMPLES."""
    from .spec import EXAMPLES
    msg = HELP % {'examples': ', '.join(sorted(EXAMPLES)) or '(none registered)'}
    from . import EXAMPLE_IMPORT_ERRORS
    if EXAMPLE_IMPORT_ERRORS:
        msg += '\n  NOT LOADED (import failed, see the log): ' + ', '.join(sorted(EXAMPLE_IMPORT_ERRORS)) + '\n'
    print(msg)
    return msg
