"""eidoblend.terrain.ekigar: Ekigar, our WorldMachine/Gaea-class terrain generator, ported from its three.js WebGPU
alpha to numpy for the Blender edition: the typed node graph and its compiler, every operator of the registry, all 39
landforms, Phacelle erosion, the masks, the display grid, the local area, the exports and the headless API. The
fields match Ekigar's own code to float tolerance (blender/tests/terrain_ekigar/test_*_parity.py run Ekigar's JS
against the port). The plan's tier-B hydrology (fill, lakes, flow accumulation and the masks on them) is added here.

    from eidoblend.terrain import ekigar
    hf = ekigar.generate('volcano', resolution=512, world_size=400)        # one operator
    hf = ekigar.generate('my_terrain.ekigar.json')                         # an ekigar-project/3 file
    obj = ekigar.build_mesh(hf, name='Volcano')                           # (Blender) true displacement
    z = hf.height_at(x, y)                                                 # metres, on that mesh

    g = ekigar.create_graph()                                              # build a graph by hand
    a = ekigar.add_node(g, 'mountainRange', params={'style': 'alpine'})
    b = ekigar.add_node(g, 'phacelle', params={'strength': 0.3})
    ekigar.connect(g, {'node': a, 'port': 'out'}, {'node': b, 'port': 'in'}, ekigar.graph_ports)
    hf = ekigar.generate(g, target=b, resolution=1024, world_size=2000)
    hf.mask('wear'), hf.mask('slope'), hf.mask('channels'), hf.masks()

Modules: noise, phacelle, field_cpu (Ekigar's CPU field), registry (+ ops_*), landform_shared / landforms_wave1..4,
model (graph + project format), compile (evaluation), masks, hydrology (tier B), display_grid (terrain_mesh.js),
local_area (local_area.js + the field side of mixed.js), export (heightmaps, map sets, PNG), terrain (Heightfield,
generate, projects), examples (the operator gallery), api (the headless agent API), mesh (bpy: mesh, preview material,
GLB; imported on first use so the generator itself runs without Blender).
Guide: tools-guides/_drafts/terrain-ekigar-core.md.
"""
from .registry import (OPERATORS, LANDFORM_IDS, BLEND_MODES, COMBINE_MODES, list_operators, get_schema,
                       default_params, structural_params, ports_of, graph_ports)
from .model import (PORT_TYPES, PROJECT_FORMAT, can_connect, create_graph, add_node, remove_node, connect,
                    disconnect, inputs_of, consumers_of, evaluation_order, to_json, from_json, migrate_project,
                    ensure_band_ids, initialise_material_bands, create_portal, remove_portal, connect_via_portal,
                    convert_to_portal, available_portals, add_group, add_note, add_tab, move_to_tab, nodes_on_tab,
                    connection_target_rank, choose_connection_target, choose_input_port, downstream_terminal,
                    target_after_add)
from .compile import (compile_graph, compile_preview_graph, evaluate_graph, derivative_depth, snap_periods,
                      is_live_param, Ctx)
from .masks import build_masks, masks_from_stencil, MASK_NAMES, ALL_MASKS, world_position, world_normal, blender_normal
from .hydrology import (hydrology, fill_depressions, route as route_flow, accumulate as accumulate_flow,
                        horizon_occlusion, box_blur, flat_average, HYDROLOGY_MASKS)
from .display_grid import (VERT_CAP, VERT_FLOOR, terrain_vertex_side, terrain_geometry_cost, build_terrain_geometry,
                           field_height_bilinear, display_heights)
from .local_area import (local_weight, wrap_delta, resolve_geometry, resolve_cut, weight_at_texel, weight_at_metres,
                         weight_field, seam_ring, area_downsample, sample_field_metres, sample_field_nearest_metres,
                         crop_local, split_field, masks_used_by, resolve_driver_field, rasterise_local_masks,
                         field_of, cut_for, to_ekigar_metres, from_ekigar_metres)
from .terrain import (Heightfield, generate, stats_of, load_project, save_project, make_project, project_graph,
                      terminal_node, single_operator_graph, chain_graph, DEFAULT_WORLD_SIZE, DEFAULT_VERTICAL_SCALE)
from .examples import EXAMPLES, GALLERY_VIEW, operator_example, gallery, gallery_ids, fixture_graph
from .export import (export_heightmap, export_maps, HEIGHTMAP_FORMATS, normalise_heights, encode_png8,
                     encode_png16_gray, decode_png, decode_png16_gray, encode_r32, encode_r16, decode_r32, decode_r16,
                     linear_to_srgb, srgb_to_linear, SRGB_TO_LINEAR)
from .field_cpu import (make_field, default_config, tiling_report as field_tiling_report, gradient_fd, snap_freq,
                        get_trees_amount, reference_trees)
from .phacelle import phacelle_noise, erosion_operator, ekigar_field
from .noise import hash2, noised, fractal_noise, wrap_cell
from . import api


def build_mesh(hf, **kw):
    """A Blender grid mesh of a Heightfield (see mesh.py: side=None | 'auto' | N, crop=cut, wrap=True for tiled
    copies). Imports bpy on first use."""
    from .mesh import build_mesh as _bm
    return _bm(hf, **kw)


def preview_material(mode='grey', name=None):
    """Ekigar's preview shading as a Blender material (see mesh.py), or 'mask:<name>' for one mask, unlit."""
    from .mesh import preview_material as _pm
    return _pm(mode, name)


def build_lake_mesh(hf, **kw):
    """The flat water surfaces of the filled depressions (see mesh.py), or None when there are none."""
    from .mesh import build_lake_mesh as _bl
    return _bl(hf, **kw)


def export_glb(hf, path, **kw):
    """The terrain mesh written as binary glTF through Blender's exporter (see mesh.py)."""
    from .mesh import export_glb as _eg
    return _eg(hf, path, **kw)
