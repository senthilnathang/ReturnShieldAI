from __future__ import annotations

import math
import struct
import zlib
from base64 import b64encode
from typing import Iterable
from urllib.parse import quote

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _data_uri_png(png_bytes: bytes) -> str:
    return "data:image/png;base64," + b64encode(png_bytes).decode("ascii")


def _initials(name: str) -> str:
    tokens = [part for part in name.replace("-", " ").split() if part]
    letters = "".join(token[0] for token in tokens[:2]).upper()
    return letters or "PR"


def _cricket_palette(name: str, sku: str | None = None) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    text = f"{name} {sku or ''}".lower()
    if "white" in text:
        return (248, 250, 252), (226, 232, 240), (124, 58, 237), (30, 41, 59)
    if "practice" in text:
        return (245, 158, 11), (251, 146, 60), (120, 45, 18), (69, 26, 3)
    if "test" in text:
        return (127, 29, 29), (220, 38, 38), (254, 243, 199), (63, 29, 29)
    if "limited" in text:
        return (153, 27, 27), (239, 68, 68), (251, 191, 36), (254, 243, 199)
    return (185, 28, 28), (239, 68, 68), (252, 165, 165), (76, 5, 25)


def _generic_palette(accent: str = "#2563eb") -> tuple[int, int, int]:
    accent = accent.lstrip("#")
    if len(accent) != 6:
        return (37, 99, 235)
    return tuple(int(accent[idx : idx + 2], 16) for idx in (0, 2, 4))


def _blend(bottom: tuple[int, int, int, int], top: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    top_a = top[3] / 255.0
    bottom_a = bottom[3] / 255.0
    out_a = top_a + bottom_a * (1.0 - top_a)
    if out_a <= 0:
        return (0, 0, 0, 0)
    out = []
    for idx in range(3):
        channel = int(
            round(
                ((top[idx] * top_a) + (bottom[idx] * bottom_a * (1.0 - top_a))) / out_a
            )
        )
        out.append(max(0, min(255, channel)))
    out.append(max(0, min(255, int(round(out_a * 255)))))
    return tuple(out)  # type: ignore[return-value]


def _set_pixel(canvas: list[bytearray], x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if y < 0 or y >= len(canvas):
        return
    row = canvas[y]
    width = len(row) // 4
    if x < 0 or x >= width:
        return
    idx = x * 4
    existing = (row[idx], row[idx + 1], row[idx + 2], row[idx + 3])
    blended = _blend(existing, color)
    row[idx : idx + 4] = bytes(blended)


def _make_canvas(width: int, height: int, color: tuple[int, int, int, int] = (0, 0, 0, 0)) -> list[bytearray]:
    row = bytearray(color * width)
    return [bytearray(row) for _ in range(height)]


def _draw_disc(canvas: list[bytearray], cx: float, cy: float, radius: float, color: tuple[int, int, int, int]) -> None:
    min_x = max(0, int(math.floor(cx - radius - 1)))
    max_x = min(len(canvas[0]) // 4 - 1, int(math.ceil(cx + radius + 1)))
    min_y = max(0, int(math.floor(cy - radius - 1)))
    max_y = min(len(canvas) - 1, int(math.ceil(cy + radius + 1)))
    radius_sq = radius * radius
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            if dx * dx + dy * dy <= radius_sq:
                _set_pixel(canvas, x, y, color)


def _draw_line(canvas: list[bytearray], points: Iterable[tuple[float, float]], color: tuple[int, int, int, int], thickness: float) -> None:
    pts = list(points)
    if len(pts) < 2:
        return
    for start, end in zip(pts, pts[1:]):
        x0, y0 = start
        x1, y1 = end
        steps = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) * 2))
        for idx in range(steps + 1):
            t = idx / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            _draw_disc(canvas, x, y, thickness / 2.0, color)


def _cubic_bezier(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], steps: int = 120) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for idx in range(steps + 1):
        t = idx / steps
        u = 1.0 - t
        x = (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0]
        y = (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1]
        points.append((x, y))
    return points


def _write_png(width: int, height: int, canvas: list[bytearray]) -> bytes:
    raw = bytearray()
    for row in canvas:
        raw.append(0)
        raw.extend(row)
    compressed = zlib.compress(bytes(raw), level=9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"".join(
        [
            PNG_SIGNATURE,
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", compressed),
            chunk(b"IEND", b""),
        ]
    )


def _draw_gradient_background(canvas: list[bytearray], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    height = len(canvas)
    width = len(canvas[0]) // 4
    for y in range(height):
        t = y / max(1, height - 1)
        # Gentle easing so the center stays darker and more cinematic.
        ease = t * t * (3 - 2 * t)
        r = int(round(top[0] * (1.0 - ease) + bottom[0] * ease))
        g = int(round(top[1] * (1.0 - ease) + bottom[1] * ease))
        b = int(round(top[2] * (1.0 - ease) + bottom[2] * ease))
        for x in range(width):
            row = canvas[y]
            idx = x * 4
            row[idx : idx + 4] = bytes((r, g, b, 255))


def _draw_ball(canvas: list[bytearray], name: str, sku: str | None = None) -> None:
    base, seam, highlight, shadow = _cricket_palette(name, sku)
    width = len(canvas[0]) // 4
    height = len(canvas)
    ball_cx = width * 0.5
    ball_cy = height * 0.46
    radius = min(width, height) * 0.33

    # Background atmosphere.
    _draw_gradient_background(canvas, (17, 24, 39), (2, 6, 23))
    _draw_disc(canvas, width * 0.38, height * 0.28, radius * 0.95, (59, 130, 246, 28))
    _draw_disc(canvas, width * 0.67, height * 0.18, radius * 0.75, (239, 68, 68, 24))
    _draw_disc(canvas, width * 0.50, height * 0.82, radius * 1.10, (15, 23, 42, 88))

    # Shadow.
    _draw_disc(canvas, ball_cx, height * 0.76, radius * 0.52, (2, 6, 23, 150))

    # Main ball with radial gradients and vignette.
    min_x = max(0, int(ball_cx - radius - 2))
    max_x = min(width - 1, int(ball_cx + radius + 2))
    min_y = max(0, int(ball_cy - radius - 2))
    max_y = min(height - 1, int(ball_cy + radius + 2))
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dx = (x + 0.5 - ball_cx) / radius
            dy = (y + 0.5 - ball_cy) / radius
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 1.0:
                continue
            light = max(0.0, 1.0 - ((dx + 0.38) ** 2 + (dy + 0.34) ** 2) * 1.05)
            glow = max(0.0, 1.0 - dist)
            r = int(round(base[0] * (0.66 + 0.34 * glow) + highlight[0] * light * 0.52 + shadow[0] * dist * 0.36))
            g = int(round(base[1] * (0.66 + 0.34 * glow) + highlight[1] * light * 0.52 + shadow[1] * dist * 0.36))
            b = int(round(base[2] * (0.66 + 0.34 * glow) + highlight[2] * light * 0.52 + shadow[2] * dist * 0.36))
            alpha = 255
            _set_pixel(canvas, x, y, (r, g, b, alpha))

    # Shine and specular spots.
    _draw_disc(canvas, ball_cx - radius * 0.35, ball_cy - radius * 0.33, radius * 0.38, (255, 255, 255, 56))
    _draw_disc(canvas, ball_cx - radius * 0.20, ball_cy - radius * 0.25, radius * 0.18, (255, 255, 255, 74))
    _draw_disc(canvas, ball_cx - radius * 0.28, ball_cy - radius * 0.38, radius * 0.12, (255, 255, 255, 88))

    # Seam and stitching.
    seam_points = _cubic_bezier(
        (ball_cx - radius * 0.48, ball_cy - radius * 0.70),
        (ball_cx - radius * 0.18, ball_cy - radius * 0.34),
        (ball_cx + radius * 0.18, ball_cy + radius * 0.28),
        (ball_cx + radius * 0.52, ball_cy + radius * 0.74),
        steps=160,
    )
    _draw_line(canvas, seam_points, (*seam, 255), thickness=radius * 0.11)

    stitch_points = _cubic_bezier(
        (ball_cx - radius * 0.46, ball_cy - radius * 0.60),
        (ball_cx - radius * 0.14, ball_cy - radius * 0.22),
        (ball_cx + radius * 0.17, ball_cy + radius * 0.25),
        (ball_cx + radius * 0.46, ball_cy + radius * 0.63),
        steps=120,
    )
    for idx in range(0, len(stitch_points) - 1, 8):
        _draw_line(canvas, stitch_points[idx : idx + 2], (255, 247, 237, 208), thickness=radius * 0.025)

    reverse_points = _cubic_bezier(
        (ball_cx - radius * 0.50, ball_cy + radius * 0.22),
        (ball_cx - radius * 0.16, ball_cy + radius * 0.08),
        (ball_cx + radius * 0.18, ball_cy - radius * 0.22),
        (ball_cx + radius * 0.50, ball_cy - radius * 0.70),
        steps=140,
    )
    _draw_line(canvas, reverse_points, (*seam, 255), thickness=radius * 0.085)

    reverse_stitch_points = _cubic_bezier(
        (ball_cx - radius * 0.48, ball_cy + radius * 0.30),
        (ball_cx - radius * 0.14, ball_cy + radius * 0.10),
        (ball_cx + radius * 0.16, ball_cy - radius * 0.16),
        (ball_cx + radius * 0.46, ball_cy - radius * 0.58),
        steps=100,
    )
    for idx in range(0, len(reverse_stitch_points) - 1, 8):
        _draw_line(canvas, reverse_stitch_points[idx : idx + 2], (255, 247, 237, 200), thickness=radius * 0.022)

    # Small highlight streaks to make the image pop.
    _draw_line(
        canvas,
        [
            (ball_cx + radius * 0.42, ball_cy - radius * 0.04),
            (ball_cx + radius * 0.63, ball_cy + radius * 0.06),
        ],
        (255, 255, 255, 74),
        thickness=radius * 0.04,
    )
    _draw_line(
        canvas,
        [
            (ball_cx + radius * 0.40, ball_cy + radius * 0.28),
            (ball_cx + radius * 0.58, ball_cy + radius * 0.38),
        ],
        (255, 255, 255, 52),
        thickness=radius * 0.03,
    )


def _cricket_ball_png(name: str, sku: str | None = None) -> bytes:
    width = 720
    height = 520
    canvas = _make_canvas(width, height, (0, 0, 0, 255))
    _draw_ball(canvas, name, sku)
    return _write_png(width, height, canvas)


def _generic_product_svg(name: str, accent: str = "#2563eb") -> str:
    initials = _initials(name)
    return f"""
<svg xmlns='http://www.w3.org/2000/svg' width='720' height='520' viewBox='0 0 720 520'>
  <defs>
    <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
      <stop offset='0%' stop-color='#0f172a'/>
      <stop offset='100%' stop-color='#111827'/>
    </linearGradient>
    <radialGradient id='card' cx='35%' cy='30%' r='90%'>
      <stop offset='0%' stop-color='{accent}' stop-opacity='1'/>
      <stop offset='100%' stop-color='#1e293b' stop-opacity='1'/>
    </radialGradient>
  </defs>
  <rect width='720' height='520' fill='url(#bg)' rx='32'/>
  <rect x='120' y='74' width='480' height='372' rx='48' fill='url(#card)' opacity='0.95'/>
  <circle cx='540' cy='145' r='64' fill='rgba(255,255,255,0.14)'/>
  <text x='360' y='255' text-anchor='middle' font-family='Georgia, serif' font-size='128' fill='white' opacity='0.9'>{initials}</text>
  <text x='360' y='324' text-anchor='middle' font-family='Inter, Arial, sans-serif' font-size='24' fill='#e2e8f0' opacity='0.95'>{name}</text>
</svg>
""".strip()


def product_image_data_uri(name: str, *, sku: str | None = None, category: str | None = None, accent: str = "#2563eb") -> str:
    label = name or "Product"
    if (category or "").lower() == "sports" and "cricket ball" in label.lower():
        return _data_uri_png(_cricket_ball_png(label, sku))
    if "cricket ball" in label.lower():
        return _data_uri_png(_cricket_ball_png(label, sku))
    # Keep the generic product card as SVG for non-vision-critical assets. The
    # cricket demo uses PNG so OpenRouter vision can compare it directly.
    svg = _generic_product_svg(label, accent=accent)
    return "data:image/svg+xml;utf8," + quote(svg, safe="")
