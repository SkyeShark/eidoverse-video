"""Lyric subtitles drawn on frames: eidoverse/lyric_renderer.py's LyricRenderer, ported (no bpy needed for it).

    from eidoblend.media import lyrics, overlay
    r = lyrics.LyricRenderer('work/<id>/lyrics_aligned.json', width=1920, height=1080, font='mono', glow=True)
    r.debug_timeline()                                    # when each line shows
    frame = r.draw(frame, t)                              # a PIL image or a numpy (H, W, 3) frame, as before
    ov = overlay.make_overlay_layer(film_scene)
    lyrics.make_lyric_layer(ov, r)                        # or: the same through the overlay and the edit scene

The renderer's rules are the original's, unchanged: a line shows for at least ``min_duration`` seconds, a gap
shorter than ``max_gap`` keeps the previous line up, lines fade in and out over ``fade_duration``, long lines wrap at
``max_chars_per_line``, and each sits on a rounded backing pill (``bg_opacity``) centred at ``y_position`` (85 % of
the height by default), clamped to a 5 % safe margin, with an optional glow. ``draw_karaoke`` falls back to ``draw``,
as in the original (karaoke styling: overlay.add_subtitles' ASS route or the parole layer).

Fonts: the original named Docker paths (/usr/share/fonts/truetype/custom/...); here the same names resolve to the
bundled files in eidoverse/assets/fonts ('default' and 'rajdhani' Rajdhani Bold, 'mono' Share Tech Mono, 'pixel'
Pixelify Sans, 'display' Audiowide, 'handwriting' Caveat Brush ...), any other bundled font by name, or a path.
'dejavu' and 'noto' were the container's system faces: they resolve when the system has them. A font that does not
resolve falls back to Rajdhani Bold, as the original did, and says so.
"""
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from . import raster

_FONT_FILES = {
    # sci-fi / tech
    'default': 'Rajdhani-Bold.ttf', 'rajdhani': 'Rajdhani-Bold.ttf', 'orbitron': 'Orbitron.ttf',
    'mono': 'ShareTechMono-Regular.ttf', 'sharetechmono': 'ShareTechMono-Regular.ttf',
    'audiowide': 'Audiowide-Regular.ttf', 'display': 'Audiowide-Regular.ttf', 'exo2': 'Exo2.ttf',
    'michroma': 'Michroma-Regular.ttf',
    # pixel / retro
    'pixel': 'PixelifySans.ttf', 'pressstart': 'PressStart2P-Regular.ttf', 'silkscreen': 'Silkscreen-Regular.ttf',
    'vt323': 'VT323-Regular.ttf',
    # handwriting / organic
    'handwriting': 'CaveatBrush-Regular.ttf', 'caveat': 'CaveatBrush-Regular.ttf', 'kalam': 'Kalam-Bold.ttf',
    'sedgwick': 'SedgwickAveDisplay-Regular.ttf',
    # display / decorative
    'monoton': 'Monoton-Regular.ttf', 'neon': 'Monoton-Regular.ttf', 'blackops': 'BlackOpsOne-Regular.ttf',
    'military': 'BlackOpsOne-Regular.ttf', 'creepster': 'Creepster-Regular.ttf', 'horror': 'Creepster-Regular.ttf',
    'typewriter': 'SpecialElite-Regular.ttf', 'specialelite': 'SpecialElite-Regular.ttf',
}
_SYSTEM = {'dejavu': ('DejaVuSans.ttf',), 'noto': ('NotoSans-Regular.ttf',)}
_SYSTEM_DIRS = ('C:/Windows/Fonts', '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/noto',
                '/Library/Fonts', '/System/Library/Fonts')


def font_file(name_or_path):
    """The file a LyricRenderer font name resolves to, or None."""
    key = str(name_or_path)
    if key in _FONT_FILES:
        return raster.FONT_DIR / _FONT_FILES[key]
    if key in _SYSTEM:
        for d in _SYSTEM_DIRS:
            for f in _SYSTEM[key]:
                if (Path(d) / f).is_file():
                    return Path(d) / f
        return None
    try:
        return raster.font_path(key)
    except KeyError:
        return None


def _load_font(name_or_path, size):
    path = font_file(name_or_path)
    if path is None:
        print(f'[lyrics] font {name_or_path!r} does not resolve here: Rajdhani Bold instead (as the original fell back)')
        path = raster.FONT_DIR / 'Rajdhani-Bold.ttf'
    return raster.font(path, size)


def _raw_lines(src):
    """align_lyrics.py output (a path or the list), or any {text, start|t0, end|t1} list / {lines|captions} dict."""
    if isinstance(src, (str, Path)):
        src = json.loads(Path(src).read_text(encoding='utf-8'))
    if isinstance(src, dict):
        src = src.get('lines') or src.get('captions') or []
    out = []
    for line in src:
        d = dict(line)
        if 'start' not in d and 't0' in d:
            d['start'] = d['t0']
        if 'end' not in d and 't1' in d:
            d['end'] = d['t1']
        out.append(d)
    return out


class LyricRenderer:
    """Renders lyric subtitles onto video frames (lyric_renderer.py's, ported; same arguments and defaults).

    lyrics_json_path: align_lyrics.py output (a path), or the lines themselves. font: a name ('default', 'mono',
    'pixel', 'display', 'handwriting' ...) or a path; font_size: at least 30. min_duration: the least time a line
    stays up; max_gap: a shorter gap keeps the previous line up; fade_duration: the fade in and out; y_position:
    the block's centre in pixels (default 85 % of the height); bg_opacity, bg_padding, bg_color: the backing pill;
    max_chars_per_line: wrap width; glow / glow_color: a coloured glow behind the text."""

    def __init__(self, lyrics_json_path, width=1280, height=720, font='default', font_size=42, min_duration=1.2,
                 max_gap=0.6, fade_duration=0.2, y_position=None, bg_opacity=160, bg_padding=(20, 12),
                 text_color=(255, 255, 255), bg_color=(10, 10, 15), max_chars_per_line=45, glow=False,
                 glow_color=(255, 45, 149)):
        self.width = width
        self.height = height
        self.font = _load_font(font, max(30, font_size))
        self.font_size = max(30, font_size)
        self.min_duration = min_duration
        self.max_gap = max_gap
        self.fade_duration = fade_duration
        self.y_pos = y_position or int(height * 0.85)
        self.bg_opacity = bg_opacity
        self.bg_pad = bg_padding
        self.text_color = text_color
        self.bg_color = bg_color
        self.max_chars = max_chars_per_line
        self.glow = glow
        self.glow_color = glow_color
        self.display_lines = self._process_lines(_raw_lines(lyrics_json_path))

    def _process_lines(self, raw_lines):
        """Post-process aligned lyrics for clean display timing (minimum duration, short gaps filled)."""
        if not raw_lines:
            return []
        lines = []
        for line in raw_lines:
            text = line.get('text', '').strip()
            if not text:
                continue
            start = line.get('start', 0)
            end = line.get('end', start + 1)
            if end - start < self.min_duration:
                end = start + self.min_duration
            lines.append({'text': text, 'start': start, 'end': end})
        if not lines:
            return []
        for i in range(len(lines) - 1):
            gap = lines[i + 1]['start'] - lines[i]['end']
            if 0 < gap < self.max_gap:
                lines[i]['end'] = lines[i + 1]['start']
        return lines

    def get_line_at(self, t):
        """The display line and alpha at time t: (text, alpha) or (None, 0)."""
        for line in self.display_lines:
            if line['start'] - self.fade_duration <= t <= line['end'] + self.fade_duration:
                alpha = 1.0
                if t < line['start']:
                    alpha = max(0, (t - (line['start'] - self.fade_duration)) / self.fade_duration)
                elif t > line['end'] - self.fade_duration:
                    remaining = line['end'] - t
                    if remaining < self.fade_duration:
                        alpha = max(0, remaining / self.fade_duration)
                return line['text'], alpha
        return None, 0

    def layer(self, t):
        """The subtitle alone at time t: a transparent RGBA image the frame's size (None when nothing shows).
        draw() composites exactly this over the frame; the overlay layer shows it as a panel."""
        text, alpha = self.get_line_at(t)
        if not text or alpha <= 0:
            return None
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        wrapped = textwrap.wrap(text, width=self.max_chars)
        if not wrapped:
            return None
        line_bboxes = []
        for line_text in wrapped:
            bbox = self.font.getbbox(line_text)
            line_bboxes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))
        max_w = max(w for w, h in line_bboxes)
        line_height = max(h for w, h in line_bboxes)
        spacing = int(line_height * 1.3)
        total_h = spacing * len(wrapped)
        bg_x1 = (self.width - max_w) // 2 - self.bg_pad[0]
        bg_y1 = self.y_pos - total_h // 2 - self.bg_pad[1]
        bg_x2 = (self.width + max_w) // 2 + self.bg_pad[0]
        bg_y2 = self.y_pos + total_h // 2 + self.bg_pad[1]
        margin_x = int(self.width * 0.05)
        margin_y = int(self.height * 0.05)
        bg_x1 = max(margin_x, bg_x1)
        bg_y1 = max(margin_y, bg_y1)
        bg_x2 = min(self.width - margin_x, bg_x2)
        bg_y2 = min(self.height - margin_y, bg_y2)
        bg_alpha = int(self.bg_opacity * alpha)
        draw.rounded_rectangle([bg_x1, bg_y1, bg_x2, bg_y2], radius=10, fill=(*self.bg_color, bg_alpha))
        if self.glow:
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                for i, line_text in enumerate(wrapped):
                    lw = line_bboxes[i][0]
                    x = (self.width - lw) // 2 + dx
                    y = self.y_pos - total_h // 2 + i * spacing + dy
                    draw.text((x, y), line_text, font=self.font, fill=(*self.glow_color, int(80 * alpha)))
        text_alpha = int(255 * alpha)
        for i, line_text in enumerate(wrapped):
            lw = line_bboxes[i][0]
            x = (self.width - lw) // 2
            y = self.y_pos - total_h // 2 + i * spacing
            draw.text((x, y), line_text, font=self.font, fill=(*self.text_color, text_alpha))
        return overlay

    def draw(self, frame, t):
        """Draw the subtitle onto a PIL Image or a numpy (H, W, 3) uint8 frame; returns the same type."""
        import numpy as np
        overlay = self.layer(t)
        if overlay is None:
            return frame
        is_numpy = isinstance(frame, np.ndarray)
        img = Image.fromarray(frame) if is_numpy else frame.copy()
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        return np.array(img) if is_numpy else img

    def draw_karaoke(self, frame, t):
        """Karaoke-style subtitles: falls back to draw(), as the original does."""
        return self.draw(frame, t)

    def burn(self, frames, out_dir, fps, first_frame=1, frame0=1):
        """draw() over a rendered PNG sequence: ``frames`` its files in order (film frame first_frame onward),
        written to ``out_dir`` under the same names; t = (frame - frame0) / fps (the film convention: frame 1 is
        0 s). Returns the written paths."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        done = []
        for k, f in enumerate(frames):
            t = (first_frame + k - frame0) / fps
            with Image.open(f) as im:
                res = self.draw(im.convert('RGB'), t)
                done.append(raster.save_png(res, out / Path(f).name))
        return done

    @property
    def duration(self):
        """Total subtitle duration (end of the last line)."""
        if not self.display_lines:
            return 0
        return self.display_lines[-1]['end']

    @property
    def line_count(self):
        """Number of display lines."""
        return len(self.display_lines)

    def debug_timeline(self):
        """Print a timeline of when each line appears."""
        for line in self.display_lines:
            print(f"  [{line['start']:6.2f}s - {line['end']:6.2f}s] ({line['end'] - line['start']:.1f}s) {line['text']}")


def make_lyric_layer(ov, lyrics, frames=None, out_dir=None, name='lyric_layer', **renderer_kwargs):
    """A LyricRenderer's subtitles on the overlay layer (display space, colours as authored): one full-frame
    transparent panel at the film's resolution, drawn per frame with the renderer's own layer(t). ``lyrics`` is a
    LyricRenderer or what it takes (then ``renderer_kwargs`` go to it; width and height default to the frame's).
    Render with overlay.render_overlay and lay it over the film with overlay.make_edit_scene. Returns the
    panel's Screen; its ``renderer`` attribute holds the LyricRenderer."""
    sc = ov.scene
    pct = sc.render.resolution_percentage / 100.0
    W, H = int(sc.render.resolution_x * pct), int(sc.render.resolution_y * pct)
    if isinstance(lyrics, LyricRenderer):
        r = lyrics
    else:
        renderer_kwargs.setdefault('width', W)
        renderer_kwargs.setdefault('height', H)
        r = LyricRenderer(lyrics, **renderer_kwargs)

    def draw(c, t, w, h):
        c.clear((0, 0, 0, 0))
        im = r.layer(t)
        if im is not None:
            c.image.paste(im if im.size == (w, h) else im.resize((w, h), Image.Resampling.LANCZOS), (0, 0))

    scr = ov.panel(draw=draw, x=0.0, y=0.0, w=1.0, h=1.0, px=r.width, frames=frames, out_dir=out_dir, name=name,
                   supersample=1)
    scr.renderer = r
    return scr
