"""
pillow_chart.py — 차트/표 이미지 생성 (Phase 8)

Pillow 기반 3종 차트 렌더러 + 디스패처.
- bar: 세로/가로 막대 차트
- timeline: 타임라인
- comparison: 좌/우 비교표

Output: 1200×630 WebP (quality 85)
"""

import json
import os
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

IMAGE_DIR = Path("output/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# ── Brand colors (config에서 로드하지만, 기본값 내장) ──
DEFAULT_COLORS = {
    "primary": "#2563EB",
    "secondary": "#DC2626",
    "tertiary": "#16A34A",
}
COLORS_LIST = list(DEFAULT_COLORS.values())


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    # System fallbacks
    for p in [
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise FileNotFoundError(f"No Korean font found: {font_path}")


def _load_colors(config: dict = None) -> list[str]:
    """Config에서 차트 색상 로드, 없으면 기본값."""
    if config:
        chart_cfg = config.get("chart", {})
        colors_cfg = chart_cfg.get("colors", {})
        return [
            colors_cfg.get("primary", DEFAULT_COLORS["primary"]),
            colors_cfg.get("secondary", DEFAULT_COLORS["secondary"]),
            colors_cfg.get("tertiary", DEFAULT_COLORS["tertiary"]),
        ]
    return COLORS_LIST


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """CJK 텍스트를 max_width에 맞게 래핑."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            test = current + ch
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ── Bar Chart ──

def generate_bar_chart(
    data: dict,
    title: str,
    slug: str,
    font_path: str,
    output_size: tuple[int, int] = (1200, 630),
    config: dict = None,
) -> tuple[Path, str]:
    """
    세로 막대 차트 생성.
    data: {"items": [{"label": "...", "value": 78.5, "unit": "%"}, ...],
           "orientation": "vertical"|"horizontal"}
    Returns: (output_path, 'pillow_chart')
    """
    items = data.get("items", [])
    if not items:
        raise ValueError("bar chart requires items")

    colors = _load_colors(config)
    bg_color = "#F8F9FA"
    text_color = "#1F2937"

    img = Image.new("RGB", output_size, bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(font_path, 42)
    label_font = _load_font(font_path, 24)

    # Title
    title_lines = _wrap_text(title, title_font, output_size[0] - 160, draw)
    y = 40
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((output_size[0] - tw) // 2, y), line, font=title_font, fill=text_color)
        y += 50

    # Chart area
    chart_top = y + 20
    chart_bottom = output_size[1] - 60
    chart_left = 120
    chart_right = output_size[0] - 80
    chart_height = chart_bottom - chart_top
    chart_width = chart_right - chart_left

    max_value = max(item.get("value", 0) for item in items) or 1
    bar_count = len(items)
    bar_gap = 20
    bar_width = max(40, (chart_width - bar_gap * (bar_count + 1)) // bar_count)

    for i, item in enumerate(items):
        val = item.get("value", 0)
        label = item.get("label", "")
        unit = item.get("unit", "")
        color = _hex_to_rgb(colors[i % len(colors)])

        bar_h = int((val / max_value) * (chart_height - 80))
        x = chart_left + bar_gap + i * (bar_width + bar_gap)
        y_top = chart_bottom - bar_h

        # Bar
        draw.rectangle([x, y_top, x + bar_width, chart_bottom], fill=color)

        # Value label
        val_text = f"{val}{unit}"
        val_font = _load_font(font_path, 20)
        bbox = draw.textbbox((0, 0), val_text, font=val_font)
        vw = bbox[2] - bbox[0]
        draw.text((x + (bar_width - vw) // 2, y_top - 28), val_text, font=val_font, fill=text_color)

        # X-axis label
        label_lines = _wrap_text(label, label_font, bar_width + 20, draw)
        ly = chart_bottom + 6
        for ll in label_lines:
            bbox = draw.textbbox((0, 0), ll, font=label_font)
            lw = bbox[2] - bbox[0]
            draw.text((x + (bar_width - lw) // 2, ly), ll, font=label_font, fill=text_color)
            ly += 26

    out_path = IMAGE_DIR / f"chart_{slug}.webp"
    img.save(out_path, "WEBP", quality=85)
    print(f"  [chart] Bar chart saved → {out_path}")
    return (out_path, "pillow_chart")


# ── Timeline ──

def generate_timeline(
    data: dict,
    title: str,
    slug: str,
    font_path: str,
    output_size: tuple[int, int] = (1200, 630),
    config: dict = None,
) -> tuple[Path, str]:
    """
    타임라인 차트 생성.
    data: {"events": [{"label": "...", "date": "2026-05-15"}]}
    Returns: (output_path, 'pillow_chart')
    """
    events = data.get("events", [])
    if not events:
        raise ValueError("timeline requires events")

    colors = _load_colors(config)
    bg_color = "#F8F9FA"
    text_color = "#1F2937"

    img = Image.new("RGB", output_size, bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(font_path, 42)
    label_font = _load_font(font_path, 22)
    date_font = _load_font(font_path, 18)

    # Title
    title_lines = _wrap_text(title, title_font, output_size[0] - 160, draw)
    y = 40
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((output_size[0] - tw) // 2, y), line, font=title_font, fill=text_color)
        y += 50

    # Timeline
    line_y = output_size[1] // 2 + 20
    margin = 100
    usable_w = output_size[0] - margin * 2

    # Horizontal line
    draw.line([(margin, line_y), (output_size[0] - margin, line_y)], fill=_hex_to_rgb(colors[0]), width=3)

    n = len(events)
    step = usable_w // max(n - 1, 1) if n > 1 else 0

    for i, ev in enumerate(events):
        x = margin + i * step if n > 1 else output_size[0] // 2
        color = _hex_to_rgb(colors[i % len(colors)])

        # Dot
        r = 10
        draw.ellipse([x - r, line_y - r, x + r, line_y + r], fill=color)

        # Date above
        date_text = ev.get("date", "")
        bbox = draw.textbbox((0, 0), date_text, font=date_font)
        dw = bbox[2] - bbox[0]
        draw.text((x - dw // 2, line_y - 50), date_text, font=date_font, fill=color)

        # Label below
        label_text = ev.get("label", "")
        label_lines = _wrap_text(label_text, label_font, 180, draw)
        ly = line_y + 30
        for ll in label_lines:
            bbox = draw.textbbox((0, 0), ll, font=label_font)
            lw = bbox[2] - bbox[0]
            draw.text((x - lw // 2, ly), ll, font=label_font, fill=text_color)
            ly += 28

    out_path = IMAGE_DIR / f"chart_{slug}.webp"
    img.save(out_path, "WEBP", quality=85)
    print(f"  [chart] Timeline saved → {out_path}")
    return (out_path, "pillow_chart")


# ── Comparison ──

def _render_column(
    draw: ImageDraw.ImageDraw,
    items: list[dict],
    x_start: int,
    col_w: int,
    label_font: ImageFont.FreeTypeFont,
    value_font: ImageFont.FreeTypeFont,
    label_color: tuple[int, int, int],
    value_color: tuple[int, int, int],
    y_start: int,
    row_height: int = 36,
    key_padding: int = 10,
    val_padding: int = 20,
) -> None:
    """Compare 컬럼 렌더링 — 키 너비 측정 후 값 x좌표 계산."""
    y = y_start
    for item in items:
        key = item.get("key", "")
        val = item.get("value", "")

        draw.text((x_start + key_padding, y), key, font=label_font, fill=label_color)

        key_w = draw.textlength(key, font=label_font)
        value_x = x_start + key_padding + key_w + val_padding
        # 값이 컬럼 폭을 초과하면 폭에 맞게 줄바꿈
        max_val_w = x_start + col_w - value_x - key_padding
        if max_val_w < 100:
            max_val_w = 100
        val_lines = _wrap_text(val, value_font, max_val_w, draw)
        vy = y
        for line in val_lines:
            draw.text((value_x, vy), line, font=value_font, fill=value_color)
            vy += row_height
        y += row_height * max(len(val_lines), 1)


def generate_comparison(
    data: dict,
    title: str,
    slug: str,
    font_path: str,
    output_size: tuple[int, int] = (1200, 630),
    config: dict = None,
) -> tuple[Path, str]:
    """
    좌/우 비교표 생성.
    data: {"left": {"label": "...", "items": [{"key": "...", "value": "..."}]},
           "right": {"label": "...", "items": [...]}}
    Returns: (output_path, 'pillow_chart')
    """
    left = data.get("left", {})
    right = data.get("right", {})
    if not left or not right:
        raise ValueError("comparison requires left and right")

    colors = _load_colors(config)
    bg_color = "#F8F9FA"
    text_color = "#1F2937"

    img = Image.new("RGB", output_size, bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(font_path, 42)
    header_font = _load_font(font_path, 28)
    label_font = _load_font(font_path, 22)
    value_font = _load_font(font_path, 18)

    # Title — top margin 80px for 2-line titles
    title_lines = _wrap_text(title, title_font, output_size[0] - 160, draw)
    y = 40
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((output_size[0] - tw) // 2, y), line, font=title_font, fill=text_color)
        y += 55
    title_bottom = y

    # Two columns
    col_w = (output_size[0] - 200) // 2
    left_x = 80
    right_x = 80 + col_w + 40
    header_h = 40
    row_height = 36
    table_top = title_bottom + 15

    for col_idx, (side, x_start, color_hex) in enumerate([
        (left, left_x, colors[0]),
        (right, right_x, colors[1] if len(colors) > 1 else colors[0]),
    ]):
        color = _hex_to_rgb(color_hex)
        header = side.get("label", "")
        bbox = draw.textbbox((0, 0), header, font=header_font)
        hw = bbox[2] - bbox[0]
        draw.text((x_start + (col_w - hw) // 2, table_top), header, font=header_font, fill=color)

        items = side.get("items", [])
        if not items:
            continue

        # Vertical centering: compute total content height then offset
        max_rows = max(len(items), 1)
        content_h = max_rows * row_height
        canvas_usable = output_size[1] - (table_top + header_h) - 50
        y_offset = max(0, (canvas_usable - content_h) // 2)

        _render_column(
            draw, items, x_start, col_w,
            label_font, value_font,
            text_color, color,
            y_start=table_top + header_h + y_offset,
            row_height=row_height,
        )

    # Center divider
    divider_x = left_x + col_w + 20
    draw.line([(divider_x, table_top - 10), (divider_x, output_size[1] - 40)],
              fill=(200, 200, 200), width=2)

    out_path = IMAGE_DIR / f"chart_{slug}.webp"
    img.save(out_path, "WEBP", quality=85)
    print(f"  [chart] Comparison saved → {out_path}")
    return (out_path, "pillow_chart")


# ── Dispatcher ──

def render_chart(
    chart_type: str,
    chart_data: dict,
    title: str,
    slug: str,
    font_path: str,
    output_size: tuple[int, int] = (1200, 630),
    config: dict = None,
) -> tuple[Path, str]:
    """
    차트 타입에 따라 적절한 렌더러로 라우팅.
    Returns: (output_path, 'pillow_chart')
    """
    renderers = {
        "bar": generate_bar_chart,
        "timeline": generate_timeline,
        "comparison": generate_comparison,
    }
    renderer = renderers.get(chart_type)
    if not renderer:
        raise ValueError(f"Unknown chart_type: {chart_type}. Supported: {list(renderers.keys())}")
    return renderer(chart_data, title, slug, font_path, output_size, config)


# ── CLI test ──
if __name__ == "__main__":
    import sys
    font = "assets/fonts/NotoSansKR-Regular.otf"

    # Test bar chart
    data = {
        "items": [
            {"label": "합격률", "value": 78.5, "unit": "%"},
            {"label": "불합격", "value": 21.5, "unit": "%"},
        ]
    }
    path, src = render_chart("bar", data, "테스트 차트", "test-chart", font)
    print(f"Created: {path}, source: {src}")
