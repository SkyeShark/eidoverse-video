#!/usr/bin/env python3
"""run_all.py: every area's tests in one run, PASS / FAIL per test (stdlib only; run from anywhere):

    python blender/tests/run_all.py                       # the import smoke, then every test below
    python blender/tests/run_all.py --list                # the manifest: each test, how it runs, in what order
    python blender/tests/run_all.py --areas sdf,weather   # some areas (comma list; --skip-areas to leave some out)
    python blender/tests/run_all.py --kinds imports,py,bl # no renders: the import smoke, plain Python, Blender CPU
    python blender/tests/run_all.py --only test_registry  # the tests whose path contains a text
    python blender/tests/run_all.py --failed              # again, the tests the last run did not pass

Each test runs in the mode that checks it without rendering where it has one (--no-render, --build-only, --stage
build, --mode check, render=0 ...). A test that must render to check anything runs through the shared GPU slot
(heavy.sh, then heavy2.sh, then heavy3.sh in the main checkout, retried every 60 s while all are busy); without those
scripts it runs directly. The kinds:

    imports  one Blender process imports every eidoblend module (the package's scripts aside), reaches each family's
             subpackages through its parent's exports (WIRING), and runs every eidoblend import statement of every
             test file: the wiring between the families, in seconds
    py       plain Python (no Blender): parity checks against the WebGPU engine run in Deno, the planning halves
    bl       Blender, rendering nothing (run_blender.sh, through the main checkout's launcher)
    eb       eido_blender.py build <scene.json>: a scene built through the harness (no render)
    gpu      Blender, rendering (through the GPU slot)
    gsh/gpy  an area's own shell / Python runner, rendering (through the GPU slot)

Areas run side by side (--jobs, default 2: each area's tests in order, as some read what the one before wrote);
renders one at a time (--gpu-jobs, default 1), round-robin over the areas, an area's renders once its CPU tests are
done; --gpu-budget N starts no render after N minutes (the rest are NOT RUN: --failed runs them later), and --resume
picks up a run that stopped early. A test is FAIL when it exits non-zero, prints a FAIL line, or raises
(a Traceback: Blender exits 0 after a script error); SKIP when it says SKIP and checks nothing else; else PASS.
Logs, one per test, and summary.json go to blender/tests/out/run_all/ (git-ignored). Nothing starts while the disk
has less than --min-disk GB free (default 10). A PASS here is not a visual review: the renders are the areas' own
stills, in their out/ folders, to look at.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(BLENDER_DIR)                         # the worktree / checkout this file is in
OUT = os.path.join(HERE, 'out', 'run_all')
MAIN = os.environ.get('EIDO_MAIN_CHECKOUT') or r'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01'
if not os.path.isfile(os.path.join(MAIN, 'run_blender.sh')):
    MAIN = ROOT                                             # no main checkout here: this checkout's launcher
SLOT_DIR = os.path.join(MAIN, 'work', 'claude_body', 'work', 'tmp')
SLOTS = [s for s in ('heavy.sh', 'heavy2.sh', 'heavy3.sh') if os.path.isfile(os.path.join(SLOT_DIR, s))]
MEMCAP = os.path.join(SLOT_DIR, 'memcap.py')
LEAVE_OUT = {'terrain', 'terrain_new', 'terrain_ekigar'}    # the terrain build's own suites run on their own


# ------------------------------------------------------------------------------------------------ the manifest ---

class T:
    """One test: area, script (in blender/tests/<area>/ unless it starts with '/' : then from the checkout root),
    args, kind, RAM cap and VRAM estimate (GB), timeout (s), cwd ('root' | 'here' | a path), why (a note)."""

    def __init__(self, kind, area, script, *args, cap=12, vram=4, timeout=None, cwd='root', tag='', why=''):
        self.kind, self.area, self.script, self.args = kind, area, script, list(args)
        self.cap, self.vram, self.cwd, self.why = cap, vram, cwd, why
        self.timeout = timeout or (3600 if kind in ('gpu', 'gsh', 'gpy') else 2400)
        self.tag = tag

    @property
    def path(self):
        if self.script.startswith('/'):
            return os.path.normpath(os.path.join(ROOT, self.script.lstrip('/')))
        return os.path.normpath(os.path.join(HERE, self.area, self.script))

    @property
    def name(self):
        s = self.script.lstrip('/') if self.script.startswith('/') else f'{self.area}/{self.script}'
        return s + (f' [{self.tag}]' if self.tag else (f" {' '.join(self.args)}" if self.args else ''))

    @property
    def log_name(self):
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', self.name).strip('_')[:150] + '.log'


def py(*a, **k):
    return T('py', *a, **k)


def bl(*a, **k):
    return T('bl', *a, **k)


def gpu(*a, **k):
    return T('gpu', *a, **k)


def eb(area, scene_json, **k):
    return T('eb', area, '/eido_blender.py', 'build', scene_json, tag=k.pop('tag', 'build ' + scene_json), **k)


NR = '--no-render'
M = []

# the harness: the runner's own suites (they render small films through eido_blender.py: one slot for each suite)
M += [py('pipeline', 'check_docs.py'),
      T('gpy', 'pipeline', 'run_tests.py', cap=16, timeout=5400, why='T0-T17: the runner end to end, small films'),
      T('gpy', 'pipeline2', 'run_tests.py', cap=16, timeout=5400, why='U0-U6: the harness-rest ports')]
# the examples through the harness (built, no render)
M += [eb('examples', 'blender/examples/obstacle_course/scene.json', tag='the walking course example'),
      eb('claudesona', 'blender/tests/claudesona/basic_vrm/scene.json', tag='basic_vrm (aletheia, MToon outlines)'),
      eb('claudesona', 'blender/tests/claudesona/basic_vrm/scene_claude.json', tag='basic_vrm (claude.vrm)'),
      eb('robotics', 'blender/eidoblend/characters/robotics/scenes/assembly.json', tag='robotics example: assembly'),
      eb('robotics', 'blender/eidoblend/characters/robotics/scenes/mantis.json', tag='robotics example: mantis'),
      eb('robotics', 'blender/eidoblend/characters/robotics/scenes/motion.json', tag='robotics example: motion'),
      eb('fabrication', 'blender/eidoblend/fabrication/scenes/manufacturing.json', tag='fabrication example'),
      eb('fabrication', 'blender/eidoblend/fabrication/scenes/relief.json', tag='fabrication example: relief')]
M += [bl('assets', 'import_all.py', timeout=3600)]
M += [bl('characters', s, NR) for s in ('test_vrma_clips.py', 'test_robot_walk.py', 'test_claude_robot_example.py',
                                        'test_clippy.py', 'test_robotics_arm.py')]
M += [bl('claudesona', s, NR) for s in ('test_face.py', 'test_keyed_film.py', 'test_lipsync.py', 'test_lookat.py',
                                        'test_pbr_tuta.py', 'test_springs.py', 'test_tuta.py', 'test_wardrobe.py')]
M += [bl('claudesona', 'test_face_geometry.py'), gpu('claudesona', 'test_basic_vrm.py'),
      gpu('claudesona', 'test_turntable.py')]
M += [bl('controller', s, timeout=3600) for s in ('test_controller_acting.py', 'test_controller_course.py',
                                                  'test_controller_foot_ik.py', 'test_controller_maneuvers.py',
                                                  'test_controller_options.py', 'test_controller_terrain.py')]
M += [bl('controller', 'test_controller_presets.py', '--preset', 'stairs_small', timeout=3600)]
M += [bl('maneuvers', s, timeout=3600) for s in ('test_emotes.py', 'test_example_bench.py', 'test_maneuver_moves.py',
                                                 'test_robot_seat.py', 'test_seating.py')]
M += [bl('robot_body', 'test_api_coverage.py'), bl('robot_body', 'test_dof_parity.py')]
M += [bl('robot_body', s, NR, timeout=3600) for s in ('test_body_api.py', 'test_body_maneuvers.py',
                                                      'test_claude_robot_example.py', 'test_crown_head_states.py',
                                                      'test_navigate_room.py', 'test_other_vrm.py', 'test_pick_up.py',
                                                      'test_pose_bake.py')]
M += [py('robotics', 'test_solvers_parity.py'), bl('robotics', 'test_attachment_frames.py'),
      bl('robotics', 'test_js_parity.py'), bl('robotics', 'test_runtime.py'),
      T('gsh', 'robotics', 'render_all.sh', timeout=5400, why='catalog, motion, parts, normal parity, examples, '
                                                               'inspector, mech parts, studio: one slot')]
M += [bl('fabrication', s) for s in ('test_fabrication_feed.py', 'test_fabrication_parity.py',
                                     'test_job_keys_seek_dispose_framing_tubes.py', 'test_mesh_input.py',
                                     'test_options.py', 'test_relief.py')]
M += [bl('fabrication', s, NR) for s in ('test_examples_render.py', 'test_fabrication_render.py',
                                         'test_growth_feed_mesh_relief_render.py', 'test_presets_render.py')]
M += [bl('fabrication', 'test_saved_blend.py')]
M += [bl('fabrication_rotary', s, timeout=3600) for s in (
    'test_rotary_parity.py', 'test_rotary_js_tests.py', 'test_rotary_stock_field.py', 'test_rotary_carve_options.py',
    'test_rotary_chips.py', 'test_rotary_shutter.py', 'test_rotary_scene_scripts.py', 'test_rotary_target_vs_carved.py',
    'test_rotary_materials_lineup.py', 'test_rotary_mesh_carve.py', 'test_rotary_examples.py')]
M += [gpu('fabrication_rotary', 'test_rotary_finish_footprint.py')]
M += [py('flora', 'parity_check.py')]
M += [bl('flora', s, NR) for s in ('t_backlit.py', 't_close.py', 't_meadow.py', 't_mix.py', 't_scanned.py',
                                   't_sheen.py')]
M += [gpu('flora', s) for s in ('t_lookdev.py', 't_motion.py', 't_scale.py', 't_species.py', 't_walk.py')]
M += [bl('fx', 'test_noise_parity.py'), bl('fx', 'test_swe_erosion.py', 'render=0', 'end=720')]
M += [gpu('fx', s) for s in ('test_cloth.py', 'test_fire_teapot.py', 'test_iso_field.py', 'test_particles_campfire.py',
                             'test_swe_basin.py')]
M += [bl('particles', 'test_morph_parity.py'), bl('particles', 'test_targets.py', timeout=3600)]
M += [gpu('particles', s) for s in ('test_particles_presets.py', 'test_display_match_numeric.py',
                                    'test_fire_tongue_rotation.py', 'test_procedural_material_cloud.py',
                                    'test_camera_cut_and_motion_blur.py', 'test_body_to_body_teleport.py',
                                    'test_morph_examples.py', 'test_robot_morph.py', 'test_saved_blend_render.py')]
M += [py('water3d', 'test_stable_fluids_parity.py', cwd='here'), bl('water3d', 'test_water3d_guide_example.py'),
      bl('water3d', 'test_water3d_drop_ball.py'), bl('water3d', 'test_stable_fluids.py', 'phase=bake')]
M += [gpu('water3d', s, cap=16 if s == 'test_water3d_pour_basin.py' else 12) for s in (
    'test_water3d_spheretest_parity.py', 'test_water3d_dam_break.py', 'test_water3d_empty_start.py',
    'test_water3d_options.py', 'test_water3d_pour_basin.py', 'test_water3d_spheretest.py',
    'test_water3d_spouts_wader.py', 'test_water_flat.py', 'probe_foam_pick.py', 'probe_lit_palette.py',
    'probe_refraction_thickness.py', 'probe_water_mesh_mirror.py', 'probe_water_mesh_normals.py',
    'probe_water_compute_saved.py')]
M += [gpu('water3d', 'test_reopen_saved_blend.py',
          f'blend={os.path.join(HERE, "water3d", "out", "verify", "wc_saved.blend")}', tag='the saved water compute')]
M += [bl('look', 'test_camera_checks.py'), bl('look', 'test_overlap_audit.py'),
      bl('look', 'test_corner_room.py', '--stage', 'build'), bl('look', 'test_meadow_camera.py', '--stage', 'build'),
      bl('look', 'test_stage.py', '--stage', 'build'),
      gpu('look', 'test_corner_room.py', '--stage', 'render'), gpu('look', 'test_meadow_camera.py', '--stage', 'render'),
      gpu('look', 'test_stage.py', '--stage', 'render'), gpu('look', 'test_debug_passes.py'),
      gpu('look', 'test_key_fill_rim.py'), gpu('look', 'test_post.py'), gpu('look', 'test_probe_modes.py')]
M += [bl('post_era', 'test_registry.py')]
M += [gpu('post_era', s, '--stage', st) for s, st in (
    ('test_era_looks.py', 'sources'), ('test_era_looks.py', 'looks'), ('test_aeropittura.py', 'sources'),
    ('test_aeropittura.py', 'looks'), ('test_after_image.py', 'sources'), ('test_after_image.py', 'post'),
    ('test_screen_effects.py', 'saved'), ('test_screen_effects.py', 'live'))]
M += [gpu('post_era', s) for s in ('test_aero_kuwahara.py', 'test_size_and_view.py', 'test_film_render.py')]
M += [gpu('post_effects', s, '--stage', st) for s, st in (
    ('test_parity.py', 'sources'), ('test_parity.py', 'parity'), ('test_looks.py', 'sheets'), ('test_looks.py', 'time'),
    ('test_verify_probes.py', 'simplex'), ('test_verify_probes.py', 'live'))]
M += [gpu('post_effects', 'test_live.py')]
M += [bl('media', 'check_screens_api.py'), py('media', 'test_weather_audio_parity.py'),
      py('media', 'audio_host.py', why='voicebox on the host (system Python): the audio probe\'s first half')]
M += [gpu('media', s) for s in ('test_screens.py', 'test_text3d.py', 'test_overlay.py', 'test_parole.py',
                                'test_book.py', 'test_book_pdf.py', 'test_audio.py')]
M += [py('media2', 'test_lyrics_parity.py'), py('media2', 'test_canvas_tools.py'), bl('media2', 'check_canvas_bake.py'),
      bl('media2', 'test_book_glb.py', NR), bl('media2', 'test_book_rig.py', NR),
      gpu('media2', 'test_reopen.py'), gpu('media2', 'test_reopen.py', '--reopen'),
      gpu('media2', 'test_overlay_routes.py'), gpu('media2', 'test_era_screens.py'),
      gpu('media2', 'test_tools_film.py')]
M += [bl('sdf', s) for s in ('test_examples_compile.py', 'test_library_parity.py', 'test_rd_parity.py')]
M += [bl('sdf', 'test_volume_density.py', 'render=0')]
M += [gpu('sdf', s) for s in ('test_volume_density.py', 'test_transforms.py', 'test_options.py', 'test_robustness.py',
                              'test_volume.py', 'test_sdf_texture.py', 'test_explosion_texture.py',
                              'test_rhombic_render.py', 'test_mesh_depth_parity.py', 'test_animated_bake.py',
                              'test_animated_examples.py', 'test_examples_render.py', 'test_help_recipes.py',
                              'test_engine_check_scenes.py')]
M += [gpu('sdf_vehicles', 'test_vehicles_compile.py'), gpu('sdf_vehicles', 'test_vehicles_render.py'),
      gpu('sdf_vehicles', 'test_vehicles_options.py', cap=16, vram=6),
      gpu('sdf_vehicles', 'test_vehicles_night_lamps.py', cap=16, vram=6),
      gpu('sdf_vehicles', 'test_vehicles_check_scenes.py', cap=16, vram=8, timeout=5400)]
M += [bl('sdf_volumes', 'test_volume_examples.py', timeout=3600)]
M += [gpu('sdf_volumes', s) for s in ('test_volume_lights.py', 'test_volume_sequences.py', 'test_nuclear_explosion.py',
                                      'test_volume_scene_integration.py')]
M += [gpu('sdf_volumes', 'test_volume_reopen.py', 'mode=build'), gpu('sdf_volumes', 'test_volume_reopen.py', 'mode=open')]
M += [bl('sky', 'state_and_wiring.py')]
M += [gpu('sky', s) for s in ('probe_world_api.py', 'probe_projection.py', 'probe_caster_height.py',
                              'probe_reflection.py', 'probe_subframe.py', 'sky_matrix.py', 'sky_sequence.py',
                              'meadow_cumulus.py')]
M += [bl('sky_worlds', 'state_and_api.py'), bl('sky_worlds', 'ring_relief_v4.py', NR)]
M += [gpu('sky_worlds', s) for s in ('probe_eevee_facts.py', 'shader_variants.py', 'asteroid_moon_pipeline.py',
                                     'corona_probe.py', 'custom_cluster.py', 'dome_and_spatial.py',
                                     'moving_camera_worlds.py', 'redgiant_options.py', 'ring_band_behind_local.py',
                                     'ring_options.py')]
M += [gpu('sky_worlds', 'world_sequence.py', '--world', 'ringworld'),
      gpu('sky_worlds', 'world_views.py', '--world', 'ringworld', '--hours', '11,23', '--views', 'horizon,up')]
M += [py('weather', s) for s in ('test_lightning_parity.py', 'test_moisture_contract.py', 'test_audio_tools.py')]
M += [bl('weather', 'test_blender_build.py'), bl('weather', 'test_facade_records.py'),
      bl('weather', 'storm_street.py', '--mode', 'check')]
M += [gpu('weather', s) for s in ('probe_eevee_facts.py', 'probe_puddles.py', 'probe_strike_on_sand.py',
                                  'rain_ab_blender.py', 'weather_examples.py', 'weather_states.py')]
M += [gpu('weather', 'storm_street.py', '--mode', 'stills')]
M += [bl('trees2', 'addon_gpu.py'), bl('trees2', 'ambience_mixdown.py')]
M += [gpu('trees', s) for s in ('backlight_check.py', 'meadow_oak.py', 'species_probes.py', 'treeline.py',
                                'wind_probe.py')]
M += [gpu('trees2', s) for s in ('demo_scene.py', 'examples_probe.py', 'cards_lod_probe.py', 'forest_export_lod.py',
                                 'billboard_light_match.py', 'glow_silhouette.py', 'haze_edge_check.py',
                                 'mobile_ladder.py', 'spom_probe.py')]
M += [bl('terrain_extras', s, NR, timeout=3600) for s in ('test_csg.py', 'test_material_board.py',
                                                          'test_relief_bounds.py', 'test_course.py')]
M += [py('terrain_extras', 'test_course_parity.py'), py('terrain_extras', 'test_pm_parity.py')]
M += [py('sets_daisy', 'test_registry.py'), bl('sets_daisy', 'test_parity.py'),
      bl('sets_daisy', 'test_asset_options.py', cap=24),
      bl('sets_daisy', 'test_bridge.py', NR), bl('sets_daisy', 'test_funeral.py', NR),
      bl('sets_daisy', 'test_corner.py', NR, cap=24, timeout=3600),
      gpu('sets_daisy', 'render_saved.py', 'funeral', 'bridge', tag='renders the saved funeral and bridge'),
      gpu('sets_daisy', 'render_saved.py', 'corner', cap=24, tag='renders the saved corner'),
      gpu('sets_daisy', 'test_parked.py', cap=24, timeout=5400)]
M += [py('sets_daisy_ocean', s) for s in ('test_util_parity.py', 'parity_atlas.py')]
M += [bl('sets_daisy_ocean', s) for s in ('test_sea_math.py', 'test_human_points_parity.py', 'test_perform_parity.py',
                                          'test_ocean_set.py', 'test_ocean_parked.py')]
M += [bl('sets_daisy_ocean', 'test_daisies.py', NR, cap=24),
      gpu('sets_daisy_ocean', 'test_ocean_stills.py'), gpu('sets_daisy_ocean', 'test_sea_reference.py')]
M += [py('sets_uf_city', 'test_parity.py', cwd='here'), py('sets_uf_city', 'test_canvas_art.py')]
M += [bl('sets_uf_city', s) for s in ('test_build_options.py', 'test_cloud_deck_order.py', 'test_hash_film.py',
                                      'test_two_sets_one_file.py', 'test_window_footprint.py')]
M += [bl('sets_uf_city', 'test_city_render.py', NR, timeout=3600), bl('sets_uf_city', 'test_hole_render.py', NR)]
M += [gpu('sets_uf_city', 'test_city_render.py', timeout=5400), gpu('sets_uf_city', 'test_hole_render.py')]
M += [bl('sets_uf_corridor_news', s) for s in ('test_cn_lib.py', 'test_corridor.py', 'test_news.py', 'test_parity.py')]
M += [gpu('sets_uf_corridor_news', 'render_shots.py', 'both', tag='the stills of both sets'),
      gpu('sets_uf_corridor_news', 'verify_probes.py')]
M += [py('sets_uf_interiors', 'test_art_parity.py', cwd='here'),
      py('sets_uf_interiors', 'test_geometry_parity.py', cwd='here'),
      bl('sets_uf_interiors', 'test_geometry_parity.py'), bl('sets_uf_interiors', 'test_lib_example.py'),
      bl('sets_uf_interiors', 'test_quiet_room.py', '--no_render'),
      bl('sets_uf_interiors', 'test_showroom.py', '--no_render'),
      bl('sets_uf_interiors', 'example_asset_use.py', '--no_render'),
      gpu('sets_uf_interiors', 'test_quiet_room.py'), gpu('sets_uf_interiors', 'test_showroom.py'),
      gpu('sets_uf_interiors', 'verify_probes.py', timeout=5400)]
M += [py('sets_uf_race_bin', s) for s in ('race_parity.py', 'bin_parity.py', 'canvas_parity.py')]
M += [bl('sets_uf_race_bin', 'test_race.py', '--build-only'), bl('sets_uf_race_bin', 'test_bin.py', '--build-only'),
      bl('sets_uf_race_bin', 'test_sections.py'),
      gpu('sets_uf_race_bin', 'test_race.py'), gpu('sets_uf_race_bin', 'test_bin.py')]
M += [py('voice_machines_a', 'test_screens_parity.py'),
      bl('voice_machines_a', 'test_machines.py', NR), bl('voice_machines_a', 'test_instances_clock_ortho.py', NR),
      bl('voice_machines_b', 'run_all.py', why='every voice-machines-b test in one Blender process (checks)')]
M += [py('xr', 'test_xr_serve.py'), py('xr', 'test_xr_quest.py'),
      bl('xr', 'test_xr_survey.py'),
      bl('xr', 'test_xr_city.py', NR), bl('xr', 'test_xr_features.py', NR, cap=16),
      bl('xr', 'test_xr_films.py', NR, cap=16), bl('xr', 'test_xr_tangents_shadows.py', NR),
      T('gsh', 'xr', 'run_all.sh', cap=16, vram=6, timeout=7200, why='the xr steps in order, with their renders')]

# ------------------------------------------------------------------------------------------------- the runner ---

AREA_ORDER = []
for _t in M:
    if _t.area not in AREA_ORDER:
        AREA_ORDER.append(_t.area)
GPU_KINDS = ('gpu', 'gsh', 'gpy')


def find_bash():
    """Git Bash on Windows (never WSL's System32 bash)."""
    env = os.environ.get('EIDO_BASH')
    if env:
        return env
    if os.name == 'nt':
        for c in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files (x86)\Git\bin\bash.exe',
                  os.path.expanduser(r'~\AppData\Local\Programs\Git\bin\bash.exe')):
            if os.path.isfile(c):
                return c
    b = shutil.which('bash')
    return b if b and 'system32' not in b.lower() else None


BASH = find_bash()
PY = sys.executable


def disk_free_gb(path=ROOT):
    try:
        return shutil.disk_usage(path).free / 2 ** 30
    except OSError:
        return 1e9


def q(p):
    return shlex.quote(p.replace('\\', '/'))


def command(t: T, slot=None):
    """(argv, cwd) for a test. Blender runs go through the main checkout's run_blender.sh; a slot wraps a render."""
    args = ' '.join(q(a) for a in t.args)
    cwd = {'root': ROOT, 'here': os.path.dirname(t.path)}.get(t.cwd, t.cwd)
    if t.kind == 'py':
        return [PY, t.path] + t.args, cwd
    if t.kind == 'eb':
        return [PY, t.path] + t.args, ROOT
    if t.kind == 'bl':
        line = f'bash run_blender.sh {q(t.path)} {args}'
        if os.path.isfile(MEMCAP):
            line = f'{q(PY)} -I {q(MEMCAP)} {t.cap} -- {line}'
        return [BASH, '-c', line], MAIN
    inner = {'gpu': f'bash run_blender.sh {q(t.path)} {args}', 'gsh': f'bash {q(t.path)} {args}',
             'gpy': f'{q(PY)} {q(t.path)} {args}'}[t.kind]
    if slot:
        return [BASH, '-c', f'HEAVY_VRAM_GB={t.vram} bash work/claude_body/work/tmp/{slot} {t.cap} {inner}'], MAIN
    return [BASH, '-c', inner], (ROOT if t.kind == 'gpy' else MAIN)


FAIL_RE = re.compile(r'(?<![\w-])FAIL(?:ED|S)?(?![\w-])')
NOT_FAIL_RE = re.compile(r'\b0\s+FAIL|FAIL(?:ED|S)?\s*[:=]?\s*0\b|\bno FAIL|FAIL lines?\b|PASS / FAIL|PASS/FAIL|'
                         r'FAIL\s*/\s*PASS|prints? (?:PASS|FAIL)|PASS or FAIL', re.I)
PASS_RE = re.compile(r'(?<![\w-])(?:PASS(?:ED)?|ok)(?![\w-])')
SKIP_RE = re.compile(r'^\s*\[?SKIP')


def judge(rc, text):
    """-> (status, detail)"""
    lines = text.splitlines()
    fails = [l.strip() for l in lines if FAIL_RE.search(l) and not NOT_FAIL_RE.search(l)]
    tb = [i for i, l in enumerate(lines) if 'Traceback (most recent call last)' in l]
    passes = sum(1 for l in lines if PASS_RE.search(l))
    if rc not in (0, None) or fails or tb:
        why = []
        if rc not in (0, None):
            why.append(f'exit {rc}')
        if fails:
            why.append(f'{len(fails)} FAIL line(s): {fails[0][:160]}')
        if tb:
            err = next((l.strip() for l in lines[tb[0]:tb[0] + 60] if re.match(r'\s*[A-Za-z_.]+(Error|Exception)\b', l)),
                       lines[min(len(lines) - 1, tb[0] + 1)].strip())
            why.append(f'raised: {err[:160]}')
        return 'FAIL', '; '.join(why)
    if not passes and any(SKIP_RE.search(l) for l in lines):
        return 'SKIP', next(l.strip() for l in lines if SKIP_RE.search(l))[:160]
    return 'PASS', f'{passes} PASS line(s)' if passes else 'ran clean (no PASS lines: a probe; look at its stills)'


def run_one(t: T, gpu_lock, log=print):
    os.makedirs(OUT, exist_ok=True)
    logp = os.path.join(OUT, t.log_name)
    if not os.path.isfile(t.path):
        return {'test': t.name, 'kind': t.kind, 'status': 'FAIL', 'detail': f'missing: {t.path}', 'seconds': 0}
    if disk_free_gb() < ARGS.min_disk:
        return {'test': t.name, 'kind': t.kind, 'status': 'NOT RUN',
                'detail': f'the disk has {disk_free_gb():.1f} GB free (< {ARGS.min_disk})', 'seconds': 0}
    t0 = time.time()
    slot_used = None
    needs_slot = t.kind in ('gpu', 'gsh', 'gpy')
    if needs_slot:
        gpu_lock.acquire()
    try:
        while True:
            for slot in (SLOTS if needs_slot and SLOTS else [None]):
                argv, cwd = command(t, slot)
                env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
                try:
                    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8',
                                       errors='replace', timeout=t.timeout)
                    rc, text = p.returncode, (p.stdout or '') + (p.stderr or '')
                except subprocess.TimeoutExpired as e:
                    rc = 'timeout'
                    text = ((e.stdout or b'').decode('utf-8', 'replace') if isinstance(e.stdout, bytes)
                            else (e.stdout or '')) + f'\n[run_all] TIMEOUT after {t.timeout} s'
                if slot and rc == 75 and 'not started' in text:
                    continue                                 # this slot is busy (or short of VRAM): the next one
                slot_used = slot
                break
            else:
                if time.time() - t0 > ARGS.slot_wait * 60:
                    rc, text = 75, f'[run_all] every GPU slot stayed busy for {ARGS.slot_wait} min'
                    break
                time.sleep(60)
                continue
            break
    finally:
        if needs_slot:
            gpu_lock.release()
    with open(logp, 'w', encoding='utf-8') as f:
        f.write(f'# {t.name}  kind={t.kind} slot={slot_used} cwd={cwd}\n# {" ".join(argv)}\n\n{text}')
    if rc == 'timeout':
        status, detail = 'FAIL', f'timeout after {t.timeout} s'
    elif rc == 75 and needs_slot and 'busy' in text:
        status, detail = 'NOT RUN', 'every GPU slot stayed busy'
    else:
        status, detail = judge(rc, text)
    return {'test': t.name, 'kind': t.kind, 'status': status, 'detail': detail, 'slot': slot_used,
            'seconds': round(time.time() - t0, 1), 'log': os.path.relpath(logp, ROOT)}


# ----------------------------------------------------------------------------------------- the import smoke ---

SCRIPTS = {'harness/run_scene.py', 'harness/doctor.py'}     # scripts, run by eido_blender.py: never imported
# each family's subpackages and modules reached from its parent as attributes (the packages' lazy exports)
WIRING = ('characters.controller.Locomotion', 'characters.maneuvers.vault_over', 'characters.emotes.seat_on',
          'characters.robot.VRMRobotBody', 'characters.claudesona.make_wardrobe', 'characters.robotics.make_robot',
          'characters.bake_springs', 'characters.bake_look_at', 'characters.key_lipsync',
          'fx.particle_morph.make_particle_morph', 'fx.particle_targets.target', 'fx.water3d.create_water_sim',
          'fx.water_flat.create_water_mesh', 'fx.stable_fluids.create_fluid_sim', 'sdf.create_sdf_object',
          'sdf.vehicles.make_vehicle', 'sdf.nuclear_explosion.NuclearExplosionFX', 'sdf.light_from_emission',
          'weather.make_weather_system', 'materials.procedural.noise', 'course.template.setup', 'course.EXAMPLES',
          'fabrication.print', 'fabrication.rotary.rotary_carve', 'fabrication.rotary_carve', 'fabrication.EXAMPLES',
          'props.build', 'props.voice_machines.MACHINES', 'props.tandem.build', 'sets.build', 'sets.daisy.BAR',
          'sets.unknown_force.SETS', 'xr.export_xr', 'xr.export.survey_xr', 'xr.EXAMPLES',
          'look.post.custom_effects.apply_to', 'look.post.chain.add_stage', 'look.camera.make_camera',
          'media.screens.make_screen', 'media.overlay.chain_overlay', 'harness.keying.node_inputs',
          'harness.post.apply', 'placement.seat_on', 'sky.make_sky', 'trees.make_seed_tree', 'flora.create_flora')


def imports_worker():
    """Inside Blender: import every eidoblend module, then run every eidoblend import statement of every test file.
    Prints one line per test file: '[imports] PASS <file>' or '[imports] FAIL <file>: <statement>: <error>'."""
    import importlib
    import traceback
    sys.path.insert(0, BLENDER_DIR)
    pkg = os.path.join(BLENDER_DIR, 'eidoblend')
    bad = 0
    for dp, dns, fns in os.walk(pkg):
        dns[:] = sorted(d for d in dns if d not in ('__pycache__', 'terrain', 'js', 'kernels', 'page'))
        for fn in sorted(fns):
            if not fn.endswith('.py'):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), pkg).replace(os.sep, '/')
            if rel in SCRIPTS or '/scenes/' in f'/{rel}':
                continue
            mod = 'eidoblend.' + rel[:-3].replace('/', '.')
            mod = mod[:-len('.__init__')] if mod.endswith('.__init__') else mod
            try:
                importlib.import_module(mod)
            except Exception as e:                               # noqa: BLE001
                bad += 1
                print(f'[imports] FAIL module {mod}: {type(e).__name__}: {e}', flush=True)
                traceback.print_exc(limit=3)
    print(f'[imports] modules imported ({bad} failed)', flush=True)
    import eidoblend
    for chain in WIRING:
        obj = eidoblend
        try:
            for part in chain.split('.'):
                obj = getattr(obj, part)
            print(f'[imports] PASS wiring eidoblend.{chain}', flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f'[imports] FAIL wiring eidoblend.{chain}: {type(e).__name__}: {e}', flush=True)
    for area in sorted(os.listdir(HERE)):
        d = os.path.join(HERE, area)
        if area in LEAVE_OUT or not os.path.isdir(d) or area == 'out':
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py'):
                continue
            p = os.path.join(d, fn)
            try:
                tree = ast.parse(open(p, encoding='utf-8').read())
            except SyntaxError as e:
                print(f'[imports] FAIL {area}/{fn}: syntax error: {e}', flush=True)
                continue
            stmts = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or '').startswith('eidoblend'):
                    stmts.append(node)
                elif isinstance(node, ast.Import) and any(a.name.startswith('eidoblend') for a in node.names):
                    stmts.append(node)
            errs = []
            for node in stmts:
                code = ast.unparse(node)
                try:
                    exec(compile(code, p, 'exec'), {})
                except Exception as e:                           # noqa: BLE001
                    errs.append(f'{code}: {type(e).__name__}: {e}')
            if errs:
                print(f'[imports] FAIL {area}/{fn}: {errs[0][:300]}' + (f' (+{len(errs) - 1} more)' if len(errs) > 1
                                                                         else ''), flush=True)
            else:
                print(f'[imports] PASS {area}/{fn} ({len(stmts)} eidoblend import(s))', flush=True)


def run_imports():
    t0 = time.time()
    line = f'bash run_blender.sh {q(os.path.abspath(__file__))} --imports-worker'
    if os.path.isfile(MEMCAP):
        line = f'{q(PY)} -I {q(MEMCAP)} 16 -- {line}'
    p = subprocess.run([BASH, '-c', line], cwd=MAIN, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=3600)
    text = (p.stdout or '') + (p.stderr or '')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'imports.log'), 'w', encoding='utf-8') as f:
        f.write(text)
    rows = []
    for l in text.splitlines():
        m = re.match(r'\[imports\] (PASS|FAIL) (.*)', l)
        if m:
            rows.append({'test': 'imports: ' + m.group(2)[:200], 'kind': 'imports', 'status': m.group(1),
                         'detail': '', 'seconds': 0})
    done = re.search(r'\[imports\] modules imported \((\d+) failed\)', text)
    rows.append({'test': 'imports: every eidoblend module', 'kind': 'imports',
                 'status': 'PASS' if done and done.group(1) == '0' else 'FAIL',
                 'detail': (f'{done.group(1)} module(s) failed to import' if done else
                            f"the Blender process ended early (exit {p.returncode}): "
                            + (text.strip().splitlines()[-1][:200] if text.strip() else 'no output')),
                 'seconds': round(time.time() - t0, 1), 'log': os.path.relpath(os.path.join(OUT, 'imports.log'), ROOT)})
    return rows


# ------------------------------------------------------------------------------------------------------- main ---

def main():
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--areas', default='')
    ap.add_argument('--skip-areas', default='')
    ap.add_argument('--kinds', default='imports,py,eb,bl,gpu,gsh,gpy')
    ap.add_argument('--only', default='')
    ap.add_argument('--failed', action='store_true', help='only the tests the last run (summary.json, or a run still '
                                                           'going: summary.partial.json) did not pass')
    ap.add_argument('--resume', action='store_true', help='skip the tests the last run already ran (it stopped '
                                                           'early), carrying their results into this summary')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--gpu-jobs', type=int, default=1)
    ap.add_argument('--gpu-budget', type=float, default=0.0, help='minutes after which no new render starts (0: none); '
                                                                  'the renders left are NOT RUN')
    ap.add_argument('--min-disk', type=float, default=10.0)
    ap.add_argument('--slot-wait', type=float, default=120.0, help='minutes to wait for a free GPU slot')
    ARGS = ap.parse_args()
    areas = [a for a in ARGS.areas.split(',') if a] or AREA_ORDER
    skip = {a for a in ARGS.skip_areas.split(',') if a}
    kinds = {k for k in ARGS.kinds.split(',') if k}
    todo = [t for t in M if t.area in areas and t.area not in skip and t.kind in kinds
            and (not ARGS.only or ARGS.only in t.name)]
    carried = []
    if ARGS.failed or ARGS.resume:
        last = None
        found = [os.path.join(OUT, fn) for fn in ('summary.json', 'summary.partial.json')
                 if os.path.isfile(os.path.join(OUT, fn))]
        if found:                                             # the newer of the two
            with open(max(found, key=os.path.getmtime), encoding='utf-8') as f:
                d = json.load(f)
            last = d['results'] if isinstance(d, dict) else d
        if ARGS.failed:
            bad = {r['test'] for r in (last or []) if r['status'] in ('FAIL', 'NOT RUN')}
            todo = [t for t in todo if t.name in bad]
        else:
            carried = [r for r in (last or []) if r['status'] != 'NOT RUN']
            ran = {r['test'] for r in carried}
            todo = [t for t in todo if t.name not in ran]
        kinds.discard('imports')
    if ARGS.list:
        for a in AREA_ORDER:
            for t in [t for t in todo if t.area == a]:
                print(f'{t.kind:4s} {t.name}' + (f'   ({t.why})' if t.why else ''))
        print(f'{len(todo)} tests; GPU slots: {", ".join(SLOTS) or "none (renders run directly)"}; launcher {MAIN}')
        return 0
    if not BASH:
        sys.exit('run_all: Git Bash not found (set EIDO_BASH)')
    os.makedirs(OUT, exist_ok=True)
    results = list(carried)
    if carried:
        print(f'[run_all] resuming: {len(carried)} result(s) carried over, {len(todo)} test(s) to run', flush=True)
    lock = threading.Lock()
    t_start = time.time()

    def report(r):
        with lock:
            results.append(r)
            print(f"{r['status']:7s} {r['test']}  ({r['kind']}, {r['seconds']:.0f} s)"
                  + (f"  -- {r['detail']}" if r['status'] != 'PASS' else ''), flush=True)
            with open(os.path.join(OUT, 'summary.partial.json'), 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=1)                     # so far (a long run read while it runs)
    if 'imports' in kinds and not ARGS.only:
        for r in run_imports():
            report(r)
    # each area's tests in order, the CPU ones (py, eb, bl) and the renders apart. --jobs workers take the areas' CPU
    # chains whole. --gpu-jobs workers take renders one at a time, round-robin over the areas (every area's first
    # render before any area's second), each area's in order and one at a time, and only once that area's CPU tests
    # are done (a render stage reads what a build stage wrote)
    gpu_lock = threading.BoundedSemaphore(max(1, ARGS.gpu_jobs))
    areas_todo = [a for a in AREA_ORDER if any(t.area == a for t in todo)]
    cpu_q = [[t for t in todo if t.area == a and t.kind not in GPU_KINDS] for a in areas_todo]
    gpu_left = {a: [t for t in todo if t.area == a and t.kind in GPU_KINDS] for a in areas_todo}
    gpu_ran = {a: 0 for a in areas_todo}
    gpu_busy = set()
    cpu_done = {a: threading.Event() for a in areas_todo}
    for a, chain in zip(areas_todo, cpu_q):
        if not chain:
            cpu_done[a].set()
    cpu_q = [c for c in cpu_q if c]
    qlock = threading.Lock()

    def cpu_worker():
        while True:
            with qlock:
                if not cpu_q:
                    return
                chain = cpu_q.pop(0)
            for t in chain:
                report(run_one(t, gpu_lock))
            cpu_done[chain[0].area].set()

    def gpu_worker():
        while True:
            spent = []
            with qlock:
                waiting = [a for a in areas_todo if gpu_left[a]]
                if not waiting:
                    return
                if ARGS.gpu_budget and time.time() - t_start > ARGS.gpu_budget * 60:
                    for a in waiting:                       # the budget is spent: what is left is reported, not run
                        spent += gpu_left[a]
                        gpu_left[a] = []
            if spent:
                for t in spent:
                    report({'test': t.name, 'kind': t.kind, 'status': 'NOT RUN', 'seconds': 0,
                            'detail': f'the GPU budget ({ARGS.gpu_budget:g} min) was spent'})
                return
            with qlock:
                waiting = [a for a in areas_todo if gpu_left[a]]
                if not waiting:
                    return
                ready = [a for a in waiting if a not in gpu_busy and cpu_done[a].is_set()]
                a = min(ready, key=lambda x: (gpu_ran[x], areas_todo.index(x))) if ready else None
                if a is not None:
                    t = gpu_left[a].pop(0)
                    gpu_busy.add(a)
            if a is None:
                time.sleep(5)
                continue
            try:
                report(run_one(t, gpu_lock))
            finally:
                with qlock:
                    gpu_ran[a] += 1
                    gpu_busy.discard(a)
    threads = [threading.Thread(target=cpu_worker, daemon=True) for _ in range(max(1, ARGS.jobs))]
    threads += [threading.Thread(target=gpu_worker, daemon=True) for _ in range(max(1, ARGS.gpu_jobs))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    n = {s: sum(1 for r in results if r['status'] == s) for s in ('PASS', 'FAIL', 'SKIP', 'NOT RUN')}
    with open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump({'when': time.strftime('%Y-%m-%d %H:%M'), 'seconds': round(time.time() - t_start), 'counts': n,
                   'results': results}, f, indent=1)
    print(f"\n{n['PASS']} PASS, {n['FAIL']} FAIL, {n['SKIP']} SKIP, {n['NOT RUN']} NOT RUN "
          f"in {(time.time() - t_start) / 60:.0f} min; logs and summary.json in {os.path.relpath(OUT, ROOT)}")
    for r in results:
        if r['status'] in ('FAIL', 'NOT RUN'):
            print(f"  {r['status']}: {r['test']}: {r['detail']}" + (f"  [{r.get('log')}]" if r.get('log') else ''))
    return 1 if n['FAIL'] else 0


ARGS = None
if __name__ == '__main__':
    if '--imports-worker' in sys.argv:
        imports_worker()
    else:
        sys.exit(main())
