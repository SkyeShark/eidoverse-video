"""Lyric subtitle renderer for music videos.

Post-processes align_lyrics.py output and renders clean subtitles onto frames.
Handles minimum display duration, gap filling, fade in/out, and text measurement
so the subagent doesn't have to write fragile timing logic every time.

Usage:
    from lyric_renderer import LyricRenderer

    renderer = LyricRenderer("lyrics_aligned.json", width=1280, height=720)
    # In frame loop:
    frame = renderer.draw(frame, t)  # returns frame with subtitle composited
"""

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Default fonts (available in Docker sandbox)
_FONT_PATHS = {
    # Sci-fi / tech
    "default": "/usr/share/fonts/truetype/custom/Rajdhani-Bold.ttf",
    "rajdhani": "/usr/share/fonts/truetype/custom/Rajdhani-Bold.ttf",
    "orbitron": "/usr/share/fonts/truetype/custom/Orbitron-VariableFont_wght.ttf",
    "mono": "/usr/share/fonts/truetype/custom/ShareTechMono-Regular.ttf",
    "sharetechmono": "/usr/share/fonts/truetype/custom/ShareTechMono-Regular.ttf",
    "audiowide": "/usr/share/fonts/truetype/custom/Audiowide-Regular.ttf",
    "display": "/usr/share/fonts/truetype/custom/Audiowide-Regular.ttf",
    "exo2": "/usr/share/fonts/truetype/custom/Exo2-VariableFont_wght.ttf",
    "michroma": "/usr/share/fonts/truetype/custom/Michroma-Regular.ttf",
    # Pixel / retro
    "pixel": "/usr/share/fonts/truetype/custom/PixelifySans-Regular.ttf",
    "pressstart": "/usr/share/fonts/truetype/custom/PressStart2P-Regular.ttf",
    "silkscreen": "/usr/share/fonts/truetype/custom/Silkscreen-Regular.ttf",
    "vt323": "/usr/share/fonts/truetype/custom/VT323-Regular.ttf",
    # Handwriting / organic
    "handwriting": "/usr/share/fonts/truetype/custom/CaveatBrush-Regular.ttf",
    "caveat": "/usr/share/fonts/truetype/custom/CaveatBrush-Regular.ttf",
    "kalam": "/usr/share/fonts/truetype/custom/Kalam-Bold.ttf",
    "sedgwick": "/usr/share/fonts/truetype/custom/SedgwickAveDisplay-Regular.ttf",
    # Display / decorative
    "monoton": "/usr/share/fonts/truetype/custom/Monoton-Regular.ttf",
    "neon": "/usr/share/fonts/truetype/custom/Monoton-Regular.ttf",
    "blackops": "/usr/share/fonts/truetype/custom/BlackOpsOne-Regular.ttf",
    "military": "/usr/share/fonts/truetype/custom/BlackOpsOne-Regular.ttf",
    "creepster": "/usr/share/fonts/truetype/custom/Creepster-Regular.ttf",
    "horror": "/usr/share/fonts/truetype/custom/Creepster-Regular.ttf",
    "typewriter": "/usr/share/fonts/truetype/custom/SpecialElite-Regular.ttf",
    "specialelite": "/usr/share/fonts/truetype/custom/SpecialElite-Regular.ttf",
    # System
    "dejavu": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "noto": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
}


def _load_font(name_or_path, size):
    path = _FONT_PATHS.get(name_or_path, name_or_path)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype("/usr/share/fonts/truetype/custom/Rajdhani-Bold.ttf", size)


class LyricRenderer:
    """Renders lyric subtitles onto video frames.

    Processes aligned lyrics JSON and handles:
    - Minimum display duration (no flashing 0.2s segments)
    - Gap filling (keeps previous line visible during short gaps)
    - Fade in/out (smooth alpha transitions)
    - Safe text placement (measured, centered, within margins)
    - Word wrap for long lines
    """

    def __init__(
        self,
        lyrics_json_path,
        width=1280,
        height=720,
        font="default",
        font_size=42,
        min_duration=1.2,
        max_gap=0.6,
        fade_duration=0.2,
        y_position=None,
        bg_opacity=160,
        bg_padding=(20, 12),
        text_color=(255, 255, 255),
        bg_color=(10, 10, 15),
        max_chars_per_line=45,
        glow=False,
        glow_color=(255, 45, 149),
    ):
        """
        Args:
            lyrics_json_path: Path to align_lyrics.py output JSON
            width, height: Video resolution
            font: Font name ('default','mono','pixel','display','handwriting') or path
            font_size: Text size (minimum 30)
            min_duration: Minimum seconds a line stays visible (prevents flashing)
            max_gap: If gap between lines < this, keep previous line visible
            fade_duration: Seconds for fade in/out
            y_position: Y pixel position for subtitle center (default: 85% of height)
            bg_opacity: Background pill alpha (0-255)
            bg_padding: (horizontal, vertical) padding around text
            text_color: RGB tuple
            bg_color: RGB tuple for background pill
            max_chars_per_line: Wrap lines longer than this
            glow: Add colored glow behind text
            glow_color: RGB for glow effect
        """
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

        # Load and process lyrics
        with open(lyrics_json_path) as f:
            raw_lines = json.load(f)

        self.display_lines = self._process_lines(raw_lines)

    def _process_lines(self, raw_lines):
        """Post-process aligned lyrics for clean display timing."""
        if not raw_lines:
            return []

        lines = []
        for line in raw_lines:
            text = line.get("text", "").strip()
            if not text:
                continue
            start = line.get("start", 0)
            end = line.get("end", start + 1)

            # Enforce minimum duration
            if end - start < self.min_duration:
                end = start + self.min_duration

            lines.append({
                "text": text,
                "start": start,
                "end": end,
            })

        if not lines:
            return []

        # Fill short gaps — if next line starts within max_gap of previous end,
        # extend previous line to meet it (prevents flicker between lines)
        for i in range(len(lines) - 1):
            gap = lines[i + 1]["start"] - lines[i]["end"]
            if 0 < gap < self.max_gap:
                lines[i]["end"] = lines[i + 1]["start"]

        return lines

    def get_line_at(self, t):
        """Get the display line and alpha for time t. Returns (text, alpha) or (None, 0)."""
        for line in self.display_lines:
            if line["start"] - self.fade_duration <= t <= line["end"] + self.fade_duration:
                # Calculate fade alpha
                alpha = 1.0
                if t < line["start"]:
                    # Fading in
                    alpha = max(0, (t - (line["start"] - self.fade_duration)) / self.fade_duration)
                elif t > line["end"] - self.fade_duration:
                    # Fading out
                    remaining = line["end"] - t
                    if remaining < self.fade_duration:
                        alpha = max(0, remaining / self.fade_duration)
                return line["text"], alpha
        return None, 0

    def draw(self, frame, t):
        """Draw subtitle onto a PIL Image or numpy array. Returns same type as input.

        Args:
            frame: PIL Image or numpy array (H, W, 3) uint8
            t: Current time in seconds
        Returns:
            Frame with subtitle composited (same type as input)
        """
        import numpy as np

        text, alpha = self.get_line_at(t)
        if not text or alpha <= 0:
            return frame

        # Convert numpy to PIL if needed
        is_numpy = isinstance(frame, np.ndarray)
        if is_numpy:
            img = Image.fromarray(frame)
        else:
            img = frame.copy()

        # Create RGBA overlay for subtitle
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Wrap long lines
        wrapped = textwrap.wrap(text, width=self.max_chars)
        if not wrapped:
            return frame

        # Measure text block
        line_bboxes = []
        for line_text in wrapped:
            bbox = self.font.getbbox(line_text)
            line_bboxes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

        max_w = max(w for w, h in line_bboxes)
        line_height = max(h for w, h in line_bboxes)
        spacing = int(line_height * 1.3)
        total_h = spacing * len(wrapped)

        # Background pill
        bg_x1 = (self.width - max_w) // 2 - self.bg_pad[0]
        bg_y1 = self.y_pos - total_h // 2 - self.bg_pad[1]
        bg_x2 = (self.width + max_w) // 2 + self.bg_pad[0]
        bg_y2 = self.y_pos + total_h // 2 + self.bg_pad[1]

        # Clamp to safe margins
        margin_x = int(self.width * 0.05)
        margin_y = int(self.height * 0.05)
        bg_x1 = max(margin_x, bg_x1)
        bg_y1 = max(margin_y, bg_y1)
        bg_x2 = min(self.width - margin_x, bg_x2)
        bg_y2 = min(self.height - margin_y, bg_y2)

        bg_alpha = int(self.bg_opacity * alpha)
        draw.rounded_rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2],
            radius=10,
            fill=(*self.bg_color, bg_alpha),
        )

        # Glow effect (optional)
        if self.glow:
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                for i, line_text in enumerate(wrapped):
                    lw = line_bboxes[i][0]
                    x = (self.width - lw) // 2 + dx
                    y = self.y_pos - total_h // 2 + i * spacing + dy
                    draw.text(
                        (x, y), line_text, font=self.font,
                        fill=(*self.glow_color, int(80 * alpha)),
                    )

        # Draw text
        text_alpha = int(255 * alpha)
        for i, line_text in enumerate(wrapped):
            lw = line_bboxes[i][0]
            x = (self.width - lw) // 2
            y = self.y_pos - total_h // 2 + i * spacing
            draw.text(
                (x, y), line_text, font=self.font,
                fill=(*self.text_color, text_alpha),
            )

        # Composite
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        if is_numpy:
            return np.array(img)
        return img

    def draw_karaoke(self, frame, t):
        """Draw karaoke-style subtitles where sung words highlight progressively.

        Uses word-level timestamps from the aligned lyrics for per-word highlighting.
        Falls back to regular draw() if word timestamps aren't available.
        """
        # This requires the original word-level data — store it in _process_lines
        # For now, fall back to regular draw
        return self.draw(frame, t)

    @property
    def duration(self):
        """Total subtitle duration (end of last line)."""
        if not self.display_lines:
            return 0
        return self.display_lines[-1]["end"]

    @property
    def line_count(self):
        """Number of display lines."""
        return len(self.display_lines)

    def debug_timeline(self):
        """Print a timeline of when each line appears. Call to verify timing."""
        for line in self.display_lines:
            print(f"  [{line['start']:6.2f}s - {line['end']:6.2f}s] ({line['end']-line['start']:.1f}s) {line['text']}")
