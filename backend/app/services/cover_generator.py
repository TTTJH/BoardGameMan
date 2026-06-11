"""
Generated default cover art for uploaded rulebooks.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple
from uuid import uuid4

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.config import settings


Color = Tuple[int, int, int]


@dataclass(frozen=True)
class CoverProfile:
    genre: str
    mechanic: str
    palette: Tuple[Color, Color, Color, Color]
    accent_shape: str


THEME_RULES = [
    (
        "Fantasy Adventure",
        ("quest", "adventure", "hero", "magic", "spell", "dragon", "castle", "dungeon", "kingdom", "legend", "monster"),
        ((20, 49, 88), (26, 84, 92), (221, 165, 78), (239, 236, 210)),
        "crest",
    ),
    (
        "Dark Fantasy",
        ("witcher", "curse", "shadow", "monster", "beast", "hunt", "blood", "dark", "wound", "mutation"),
        ((16, 18, 22), (64, 49, 38), (139, 25, 28), (225, 218, 199)),
        "blade",
    ),
    (
        "Science Fiction",
        ("space", "ship", "planet", "alien", "galaxy", "sector", "mission", "oxygen", "robot", "laser"),
        ((9, 19, 36), (19, 65, 96), (86, 192, 224), (232, 244, 248)),
        "orbit",
    ),
    (
        "Mystery",
        ("clue", "suspect", "case", "mystery", "detective", "evidence", "secret", "hidden", "deduction"),
        ((23, 29, 38), (63, 73, 84), (197, 142, 70), (238, 229, 208)),
        "keyhole",
    ),
    (
        "Historical Strategy",
        ("empire", "war", "army", "battle", "soldier", "ancient", "civilization", "province", "conquest"),
        ((38, 36, 31), (91, 70, 48), (180, 125, 70), (234, 224, 200)),
        "standard",
    ),
    (
        "Nature",
        ("forest", "animal", "wildlife", "garden", "tree", "river", "island", "ecosystem", "habitat"),
        ((18, 54, 45), (38, 93, 68), (132, 174, 96), (232, 240, 214)),
        "leaf",
    ),
    (
        "Economic Strategy",
        ("market", "trade", "coin", "resource", "income", "auction", "contract", "build", "production"),
        ((23, 40, 48), (47, 74, 83), (210, 169, 88), (235, 231, 211)),
        "coin",
    ),
    (
        "Party Game",
        ("team", "guess", "word", "round", "timer", "party", "laugh", "challenge", "score"),
        ((39, 39, 70), (190, 70, 92), (244, 183, 89), (248, 241, 222)),
        "burst",
    ),
]

MECHANIC_RULES = [
    ("Cooperative", ("cooperative", "together", "team", "group", "players win", "players lose")),
    ("Campaign", ("campaign", "scenario", "chapter", "quest", "save", "progress")),
    ("Deck Building", ("deck", "shuffle", "discard", "draw", "hand", "card")),
    ("Area Control", ("area", "territory", "region", "control", "occupy")),
    ("Worker Placement", ("worker", "action space", "place", "assign")),
    ("Exploration", ("explore", "map", "tile", "discover", "location")),
    ("Combat", ("attack", "defense", "damage", "enemy", "combat")),
    ("Puzzle", ("solve", "deduce", "code", "logic", "hint")),
]


class CoverGenerator:
    """Infer a rulebook profile and render a default cover image."""

    WIDTH = 900
    HEIGHT = 1350

    @classmethod
    def generate_for_game(cls, game_id: int, game_name: str, pdf_text: str, filename: str = "") -> str:
        profile = cls.infer_profile(game_name, pdf_text, filename)
        covers_dir = Path(settings.UPLOAD_DIR) / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        output_name = f"game_{game_id}_{uuid4().hex}.png"
        output_path = covers_dir / output_name
        image = cls.render_cover(game_name, profile)
        image.save(output_path, "PNG", optimize=True)
        return f"/covers/{output_name}"

    @classmethod
    def infer_profile(cls, game_name: str, pdf_text: str, filename: str = "") -> CoverProfile:
        sample = f"{game_name}\n{filename}\n{pdf_text[:18000]}".lower()

        def score(words: Iterable[str]) -> int:
            return sum(len(re.findall(rf"\b{re.escape(word)}\b", sample)) for word in words)

        theme_name, _, palette, shape = max(
            enumerate(THEME_RULES),
            key=lambda item: (score(item[1][1]), -item[0]),
        )[1]
        mechanic = max(
            enumerate(MECHANIC_RULES),
            key=lambda item: (score(item[1][1]), -item[0]),
        )[1][0]
        return CoverProfile(theme_name, mechanic, palette, shape)

    @classmethod
    def render_cover(cls, game_name: str, profile: CoverProfile) -> Image.Image:
        base, mid, accent, text_color = profile.palette
        image = cls._gradient(base, mid)
        draw = ImageDraw.Draw(image, "RGBA")
        seed = int(hashlib.sha256(f"{game_name}:{profile.genre}".encode("utf-8")).hexdigest()[:8], 16)

        cls._paint_texture(draw, seed, accent)
        cls._paint_frame(draw, accent, text_color)
        cls._paint_shape(draw, profile.accent_shape, accent, text_color)
        cls._paint_title(draw, game_name, profile, text_color, accent)

        image = ImageEnhance.Contrast(image).enhance(1.06)
        return image

    @classmethod
    def _gradient(cls, top: Color, bottom: Color) -> Image.Image:
        image = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), top)
        pixels = image.load()
        for y in range(cls.HEIGHT):
            ratio = y / max(cls.HEIGHT - 1, 1)
            vignette = 0.80 + 0.20 * math.cos((ratio - 0.5) * math.pi)
            for x in range(cls.WIDTH):
                side = abs((x / cls.WIDTH) - 0.5) * 0.36
                blend = min(1, ratio + side)
                color = tuple(int((top[i] * (1 - blend) + bottom[i] * blend) * vignette) for i in range(3))
                pixels[x, y] = color
        return image.filter(ImageFilter.GaussianBlur(0.2))

    @classmethod
    def _paint_texture(cls, draw: ImageDraw.ImageDraw, seed: int, accent: Color) -> None:
        for i in range(38):
            x = (seed * (i + 7) * 37) % cls.WIDTH
            y = (seed * (i + 11) * 29) % cls.HEIGHT
            radius = 90 + ((seed >> (i % 15)) % 210)
            alpha = 12 + i % 24
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*accent, alpha))

        for x in range(-cls.HEIGHT, cls.WIDTH, 42):
            draw.line((x, 0, x + cls.HEIGHT, cls.HEIGHT), fill=(255, 255, 255, 15), width=2)

    @classmethod
    def _paint_frame(cls, draw: ImageDraw.ImageDraw, accent: Color, text_color: Color) -> None:
        margin = 46
        draw.rectangle((margin, margin, cls.WIDTH - margin, cls.HEIGHT - margin), outline=(*accent, 190), width=5)
        draw.rectangle((margin + 16, margin + 16, cls.WIDTH - margin - 16, cls.HEIGHT - margin - 16), outline=(*text_color, 55), width=2)
        draw.line((95, 1000, cls.WIDTH - 95, 1000), fill=(*accent, 165), width=3)

    @classmethod
    def _paint_shape(cls, draw: ImageDraw.ImageDraw, shape: str, accent: Color, text_color: Color) -> None:
        cx, cy = cls.WIDTH // 2, 520
        if shape == "orbit":
            for angle in (-18, 18, 0):
                box = (cx - 280, cy - 95 + angle, cx + 280, cy + 95 + angle)
                draw.ellipse(box, outline=(*accent, 160), width=5)
            draw.ellipse((cx - 92, cy - 92, cx + 92, cy + 92), fill=(*accent, 72), outline=(*text_color, 120), width=3)
        elif shape == "blade":
            draw.polygon([(cx, 220), (cx + 54, 650), (cx, 820), (cx - 54, 650)], fill=(*accent, 145))
            draw.line((cx, 250, cx, 800), fill=(*text_color, 110), width=4)
        elif shape == "keyhole":
            draw.ellipse((cx - 100, cy - 150, cx + 100, cy + 50), fill=(*accent, 126))
            draw.polygon([(cx - 50, cy + 20), (cx + 50, cy + 20), (cx + 92, cy + 270), (cx - 92, cy + 270)], fill=(*accent, 126))
        elif shape == "leaf":
            draw.ellipse((cx - 260, cy - 190, cx + 260, cy + 190), fill=(*accent, 96), outline=(*text_color, 96), width=3)
            draw.line((cx - 210, cy + 130, cx + 210, cy - 130), fill=(*text_color, 120), width=5)
        elif shape == "coin":
            for r in (260, 205, 145):
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(*accent, 170), width=7)
        elif shape == "burst":
            points = []
            for i in range(24):
                angle = math.pi * 2 * i / 24
                radius = 290 if i % 2 == 0 else 150
                points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
            draw.polygon(points, fill=(*accent, 120))
        elif shape == "standard":
            draw.polygon([(cx - 230, 320), (cx + 230, 320), (cx + 180, 730), (cx, 850), (cx - 180, 730)], fill=(*accent, 112))
            draw.rectangle((cx - 8, 230, cx + 8, 850), fill=(*text_color, 120))
        else:
            draw.polygon([(cx, 260), (cx + 245, 420), (cx + 150, 760), (cx, 860), (cx - 150, 760), (cx - 245, 420)], fill=(*accent, 112))
            draw.ellipse((cx - 140, cy - 140, cx + 140, cy + 140), outline=(*text_color, 110), width=5)

    @classmethod
    def _paint_title(
        cls,
        draw: ImageDraw.ImageDraw,
        game_name: str,
        profile: CoverProfile,
        text_color: Color,
        accent: Color,
    ) -> None:
        title_font = cls._font(72, bold=True)
        subtitle_font = cls._font(28, bold=True)
        small_font = cls._font(24)

        lines = cls._wrap_title(draw, game_name.upper(), title_font, cls.WIDTH - 150, max_lines=4)
        line_height = 76
        y = 1040 - (len(lines) - 1) * line_height // 2
        for line in lines:
            box = draw.textbbox((0, 0), line, font=title_font)
            x = (cls.WIDTH - (box[2] - box[0])) // 2
            draw.text((x + 3, y + 4), line, font=title_font, fill=(0, 0, 0, 145))
            draw.text((x, y), line, font=title_font, fill=(*text_color, 245))
            y += line_height

        meta = f"{profile.genre} / {profile.mechanic}"
        meta_box = draw.textbbox((0, 0), meta.upper(), font=subtitle_font)
        draw.text(((cls.WIDTH - (meta_box[2] - meta_box[0])) // 2, 1238), meta.upper(), font=subtitle_font, fill=(*accent, 230))

        footer = "RULEBOOK ASSISTANT"
        footer_box = draw.textbbox((0, 0), footer, font=small_font)
        draw.text(((cls.WIDTH - (footer_box[2] - footer_box[0])) // 2, 1288), footer, font=small_font, fill=(*text_color, 150))

    @staticmethod
    def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates: List[str] = []
        if bold:
            candidates.extend([
                "C:/Windows/Fonts/georgiab.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ])
        candidates.extend([
            "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])

        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)
        return ImageFont.load_default()

    @staticmethod
    def _wrap_title(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
        max_lines: int,
    ) -> List[str]:
        words = text.split()
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            box = draw.textbbox((0, 0), candidate, font=font)
            if current and box[2] - box[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        if len(lines) <= max_lines:
            return lines

        compact = lines[:max_lines]
        compact[-1] = re.sub(r"\s+\S+$", "", compact[-1]).rstrip() + "..."
        return compact
