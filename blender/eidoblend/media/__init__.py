"""eidoblend.media: screens, type, overlays, subtitles, books and the sound side of the Blender edition.

Guides: tools-guides/motion-graphics.md (screens, the era screens, overlays, subtitles, lyrics, parole, 3D type),
books.md, audio.md, voicebox.md, synthkit.md.

Modules (import the one you need; this package imports nothing heavy on its own):
    timebase       frame <-> film seconds, lyric / caption readers (no bpy needed)
    raster         Pillow canvases, the bundled fonts by name, draw_text_fit (no bpy needed)
    canvas_scenes  the canvas screen scenes without Blender: list, preview, sheet, bench and NaN-sweep them through
                   preview_screens.mjs / screens_nan_sweep.mjs; DAISY_CUES (no bpy needed)
    screens        make_screen, make_video_screen, make_atlas_screen, make_ascii_panel, bake_canvas_scene,
                   bake_canvas_playlist, curved_wall (canvas-2D cores via Deno)
    text3d         create_text_3d, make_title_card (FONT objects with real materials)
    overlay        make_overlay_layer, render_overlay, make_edit_scene, subtitle text strips (the display route);
                   chain_overlay (the signal route: the overlay stage inside look/post's chain, laid over the film
                   in display space so ink, glows and fades land as drawn)
    lyrics         LyricRenderer (lyric_renderer.py, ported; no bpy needed) and make_lyric_layer
    parole         the parole-in-liberta lyric layer: parole.js run in Deno, sprites built and keyed here
    book           the hardcover rig: book_core.js run in Deno, its poses cached into Mesh Cache (PC2) here, its
                   coordinate frames keyed as empties; makeBookFromSpec, makeBookRig specs and makeBook(gltf)
    audio          sound strips, markers, mixdown, visemes keyed onto a VRM's expressions
    weather_audio  the weather-audio recorder over Blender frames (JSON for bake_weather_audio.py)

Only overlay.chain_overlay imports another eidoblend subpackage (look.post.chain, which owns the post chain's order),
and only when it is called. A module is imported when it is first imported or reached as media.<name>.
"""
import importlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                       # <worktree>/blender/eidoblend/media -> <worktree>
ASSETS = REPO / 'eidoverse' / 'assets'
FONTS = ASSETS / 'fonts'
JS = HERE / 'js'

MODULES = ('timebase', 'raster', 'canvas_scenes', 'screens', 'text3d', 'overlay', 'lyrics', 'parole', 'book', 'audio',
           'weather_audio')


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
