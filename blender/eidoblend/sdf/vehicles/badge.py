"""The cyberpunk sedan's badge decal: _BADGE_GLYPH_ATLAS and _buildBadgeDecal, for the Blender edition.

The engine drew `text` onto a 1024 x 256 canvas from a 5 x 7 pixel font (each '#' a 12 x 12 px square on a 14 px
grid, a one-cell gap between glyphs, the line centred), wrapped it in a CanvasTexture and sampled its alpha in the
badge plate's shade branch. Here the same canvas is a numpy array; badge_image() turns it into a packed Blender image
that the badge material samples per pixel, at any distance, and the SDF program binds as uDecal (the example's
shade() and surface() read it there).

    from eidoblend.sdf.vehicles import build_badge_decal, badge_image, BADGE_GLYPH_ATLAS
    canvas = build_badge_decal('ALETH8APO')     # (256, 1024, 4) float32, row 0 at the TOP (the canvas's rows)
    img = badge_image('ALETH8APO')              # bpy image, row 0 at the bottom (three's flipY = true)

Glyphs not in the atlas are skipped, their slot left blank (as the engine did); add letters to BADGE_GLYPH_ATLAS
(seven rows of five '#' / '.' cells) to widen the alphabet. A line longer than the canvas (13 glyphs or more) runs
off both edges, as it did on the engine's canvas.
"""

from __future__ import annotations

import numpy as np

# 5x7 pixel font. '#' is a filled cell, '.' is empty.
BADGE_GLYPH_ATLAS = {
    'A': ['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'E': ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
    'T': ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    '8': ['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    'O': ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
}

CANVAS_W, CANVAS_H = 1024, 256
CELL_W = CELL_H = 14
COLS, ROWS = 5, 7


def build_badge_decal(text, atlas=None):
    """_buildBadgeDecal(text): the canvas as a (256, 1024, 4) float32 RGBA array, row 0 at the top. Filled cells are
    white with alpha 1, the rest is transparent black (clearRect)."""
    atlas = BADGE_GLYPH_ATLAS if atlas is None else atlas
    canvas = np.zeros((CANVAS_H, CANVAS_W, 4), np.float32)
    text = str(text)
    if not text:
        return canvas
    gap = CELL_W                                     # 1-cell gap between glyphs
    glyph_w = COLS * CELL_W
    total_w = len(text) * glyph_w + (len(text) - 1) * gap
    start_x = (CANVAS_W - total_w) / 2.0
    start_y = (CANVAS_H - ROWS * CELL_H) / 2.0
    for i, ch in enumerate(text):
        pat = atlas.get(ch)
        if not pat:
            continue
        gx = start_x + i * (glyph_w + gap)
        for r in range(ROWS):
            for c in range(COLS):
                if pat[r][c] != '#':
                    continue
                # ctx.fillRect(x, y, cellW - 2, cellH - 2): integer here for any text (start_x = 519 - 42 n)
                x0 = int(round(gx + c * CELL_W))
                y0 = int(round(start_y + r * CELL_H))
                x1, y1 = x0 + CELL_W - 2, y0 + CELL_H - 2
                xa, xb = max(0, x0), min(CANVAS_W, x1)
                ya, yb = max(0, y0), min(CANVAS_H, y1)
                if xa < xb and ya < yb:
                    canvas[ya:yb, xa:xb] = 1.0
    return canvas


_DEFAULT = {}


def get_default_badge_decal():
    """_getDefaultBadgeDecal(): the default 'ALETH8APO' canvas, built once."""
    if 'canvas' not in _DEFAULT:
        _DEFAULT['canvas'] = build_badge_decal('ALETH8APO')
    return _DEFAULT['canvas']


def decal_texture_array(text=None):
    """The canvas in GL order (row 0 at the bottom), as three's CanvasTexture uploaded it (flipY = true): what a
    GLSL texture2D(uDecal, uv) reads, uv (0, 0) at the canvas's bottom-left. The program's textures take this."""
    canvas = get_default_badge_decal() if text is None else build_badge_decal(text)
    return np.ascontiguousarray(canvas[::-1])


def badge_image(text, name=None, pack=True):
    """The decal as a Blender image (Non-Color, linear filtering in the material), packed into the .blend so a saved
    file keeps it. Reused when an image of this name already holds the same text."""
    import bpy
    name = name or f'badge_decal_{text}'
    img = bpy.data.images.get(name)
    if img is not None and img.get('badge_text') == str(text) and tuple(img.size) == (CANVAS_W, CANVAS_H):
        return img
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, CANVAS_W, CANVAS_H, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'STRAIGHT'
    img.pixels.foreach_set(decal_texture_array(text).ravel())
    img['badge_text'] = str(text)
    if pack:
        img.pack()
    return img
