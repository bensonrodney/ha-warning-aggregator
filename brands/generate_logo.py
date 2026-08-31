#!/usr/bin/env python3
"""Generate the Warning Aggregator brand assets (icon + logo, light + dark).

Output goes to ``brands/custom_integrations/warning_aggregator/`` in the layout
expected by https://github.com/home-assistant/brands.

    uv run --no-project --with pillow brands/generate_logo.py
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
# Source of truth for the home-assistant/brands PR.
OUT = HERE / "custom_integrations" / "warning_aggregator"
# In-repo copy HACS serves and its `brands` check looks for.
BRAND = ROOT / "custom_components" / "warning_aggregator" / "brand"
FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

AMBER_TOP = (255, 187, 58)
AMBER_BOT = (231, 121, 0)
WHITE = (255, 255, 255, 255)
SLATE = (28, 39, 50, 255)
OFFWHITE = (240, 242, 245, 255)

SS = 4  # supersampling factor


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=False))


def _vgradient(size: int) -> Image.Image:
    col = Image.new("RGB", (1, size))
    for y in range(size):
        col.putpixel((0, y), _lerp(AMBER_TOP, AMBER_BOT, y / (size - 1)))
    return col.resize((size, size)).convert("RGBA")


def _squircle_mask(size: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.235), fill=255
    )
    return m


def render_icon(px: int) -> Image.Image:
    c = px * SS
    grad = _vgradient(c)

    icon = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), _squircle_mask(c))

    cx, cy = c / 2, c * 0.510
    w, h = c * 0.70, c * 0.60
    apex = (cx, cy - h * 0.52)
    bl = (cx - w / 2, cy + h * 0.48)
    br = (cx + w / 2, cy + h * 0.48)
    r = int(c * 0.075)

    tri = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    td = ImageDraw.Draw(tri)
    td.polygon([apex, bl, br], fill=WHITE)
    td.line([apex, bl, br, apex, bl], fill=WHITE, width=2 * r, joint="curve")
    icon = Image.alpha_composite(icon, tri)

    # Exclamation mark as negative space (the gradient shows through).
    exm = Image.new("L", (c, c), 0)
    ed = ImageDraw.Draw(exm)
    bw = c * 0.100
    bar_top, bar_bot = c * 0.335, c * 0.628
    ed.rounded_rectangle(
        [cx - bw / 2, bar_top, cx + bw / 2, bar_bot], radius=bw / 2, fill=255
    )
    dot_r = bw * 0.56
    dcy = c * 0.716
    ed.ellipse([cx - dot_r, dcy - dot_r, cx + dot_r, dcy + dot_r], fill=255)
    icon.paste(grad, (0, 0), exm)

    return icon.resize((px, px), Image.LANCZOS)


def _tracked_width(draw, text, font, tracking):
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (
        len(text) - 1
    )


def _draw_tracked(draw, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def render_logo(dark: bool) -> Image.Image:
    scale = 3
    canvas = Image.new("RGBA", (1600 * scale, 900 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    text_col = OFFWHITE if dark else SLATE

    mark_px = 470 * scale
    mark = render_icon(mark_px)
    cx = canvas.width // 2
    canvas.alpha_composite(mark, (cx - mark_px // 2, 20 * scale))

    font = ImageFont.truetype(FONT_PATH, 150 * scale)
    tracking = 12 * scale
    y = 20 * scale + mark_px + 44 * scale
    for line in ("WARNING", "AGGREGATOR"):
        tw = _tracked_width(draw, line, font, tracking)
        _draw_tracked(draw, (cx - tw / 2, y), line, font, text_col, tracking)
        y += 170 * scale

    return canvas.crop(canvas.getbbox())


def _fit(img: Image.Image, box: int) -> Image.Image:
    ratio = min(box / img.width, box / img.height)
    return img.resize(
        (round(img.width * ratio), round(img.height * ratio)), Image.LANCZOS
    )


def _save(img: Image.Image, out_dir: pathlib.Path, name: str) -> None:
    img.save(out_dir / name, optimize=True)
    print(f"  {name:22} {img.width}x{img.height}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    BRAND.mkdir(parents=True, exist_ok=True)

    icon = render_icon(256)
    icon2x = render_icon(512)
    logos = {}
    for dark in (False, True):
        logo2x = _fit(render_logo(dark), 512)
        logo1x = logo2x.resize((logo2x.width // 2, logo2x.height // 2), Image.LANCZOS)
        logos["dark_logo" if dark else "logo"] = (logo1x, logo2x)

    print(f"writing brands assets to {OUT}")
    _save(icon, OUT, "icon.png")
    _save(icon2x, OUT, "icon@2x.png")
    for prefix, (logo1x, logo2x) in logos.items():
        _save(logo1x, OUT, f"{prefix}.png")
        _save(logo2x, OUT, f"{prefix}@2x.png")

    print(f"writing in-repo brand/ assets to {BRAND}")
    _save(icon, BRAND, "icon.png")
    _save(logos["logo"][0], BRAND, "logo.png")
    _save(logos["dark_logo"][0], BRAND, "dark_logo.png")


if __name__ == "__main__":
    main()
