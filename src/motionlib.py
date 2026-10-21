"""Small, dependency-free motion design toolkit.

The renderer deliberately keeps the design data in plain Python/SVG so it can
be reviewed, versioned, and rendered deterministically on any machine with
`rsvg-convert` and `ffmpeg`.
"""

from __future__ import annotations

import html
import math
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# Numbers, colour, easing
# ---------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix_hex(a: str, b: str, t: float) -> str:
    """Linear RGB mix between two #rrggbb colours."""
    t = clamp(t)
    pa = [int(a.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(lerp(x, y, t)):02x}" for x, y in zip(pa, pb))


def rgba(hex_color: str, alpha: float = 1.0) -> str:
    """CSS rgba() string; rsvg supports this in SVG 1.1 attributes."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{clamp(alpha):.4f})"


def fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def _ease_in_expo(t: float) -> float:
    return 0.0 if t <= 0 else 2 ** (10 * (t - 1))


def _ease_in_out_quint(t: float) -> float:
    return 16 * t**5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2


def _ease_out_back(t: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def cubic_bezier(x1: float, y1: float, x2: float, y2: float):
    """Return an ease function matching an After Effects cubic-bezier keyframe."""

    def sample(t: float, a: float, b: float) -> float:
        return 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t**2 * b + t**3

    def ease(t: float) -> float:
        t = clamp(t)
        if t in (0.0, 1.0):
            return t
        lo, hi = 0.0, 1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            if sample(mid, x1, x2) < t:
                lo = mid
            else:
                hi = mid
        return sample((lo + hi) / 2, y1, y2)

    return ease


EASE = {
    "linear": lambda t: t,
    "inQuad": lambda t: t * t,
    "outQuad": lambda t: 1 - (1 - t) ** 2,
    "inOutQuad": lambda t: 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,
    "inCubic": lambda t: t**3,
    "outCubic": lambda t: 1 - (1 - t) ** 3,
    "inOutCubic": lambda t: 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,
    "inQuart": lambda t: t**4,
    "outQuart": lambda t: 1 - (1 - t) ** 4,
    "inOutQuart": lambda t: 8 * t**4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2,
    "inOutQuint": _ease_in_out_quint,
    "outExpo": _ease_out_expo,
    "inExpo": _ease_in_expo,
    "inOutExpo": lambda t: (
        _ease_out_expo(t * 2) / 2 if t < 0.5 else 1 - _ease_out_expo((1 - t) * 2) / 2
    ),
    "outBack": _ease_out_back,
    "inOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "outSine": lambda t: math.sin(t * math.pi / 2),
    # Common motion-design curves, expressed as cubic-bezier.
    "aeEase": cubic_bezier(0.33, 0.0, 0.2, 1.0),
    "aeEaseIn": cubic_bezier(0.4, 0.0, 1.0, 1.0),
    "snap": cubic_bezier(0.16, 1.0, 0.3, 1.0),
}


def anim(
    t: float,
    start: float,
    end: float,
    value_in: float,
    value_out: float,
    ease: str = "inOutCubic",
) -> float:
    """Animate one value over a time range."""
    if end <= start:
        return value_out if t >= end else value_in
    return lerp(value_in, value_out, EASE[ease](clamp((t - start) / (end - start))))


def fade_in(t: float, start: float, end: float, ease: str = "outCubic") -> float:
    return anim(t, start, end, 0.0, 1.0, ease)


def fade_out(t: float, start: float, end: float, ease: str = "inCubic") -> float:
    return anim(t, start, end, 1.0, 0.0, ease)


def window(t: float, in_a: float, in_b: float, out_a: float, out_b: float) -> float:
    """Fade in, hold, then fade out. Returns 0 outside the window."""
    if t <= in_a or t >= out_b:
        return 0.0
    if t < in_b:
        return fade_in(t, in_a, in_b)
    if t > out_a:
        return fade_out(t, out_a, out_b)
    return 1.0


def stagger(
    t: float, index: int, start: float, step: float, duration: float, ease: str = "outCubic"
) -> float:
    return EASE[ease](clamp((t - (start + index * step)) / duration))


def pulse(t: float, center: float, width: float) -> float:
    """A smooth 0 -> 1 -> 0 pulse around a point in time."""
    distance = abs(t - center) / max(width, 1e-6)
    return 0.0 if distance >= 1 else math.cos(distance * math.pi / 2) ** 2


# ---------------------------------------------------------------------------
# SVG primitives
# ---------------------------------------------------------------------------

def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = "none",
    opacity: float = 1.0,
    rx: float = 0.0,
    stroke: str | None = None,
    stroke_width: float = 1.0,
    extra: str = "",
) -> str:
    parts = [
        f'x="{fmt(x)}"',
        f'y="{fmt(y)}"',
        f'width="{fmt(max(0, w))}"',
        f'height="{fmt(max(0, h))}"',
        f'fill="{fill}"',
    ]
    if rx:
        parts.append(f'rx="{fmt(rx)}"')
    if opacity < 1:
        parts.append(f'opacity="{fmt(opacity)}"')
    if stroke:
        parts.append(f'stroke="{stroke}" stroke-width="{fmt(stroke_width)}"')
    if extra:
        parts.append(extra)
    return "<rect " + " ".join(parts) + "/>"


def circle(
    cx: float,
    cy: float,
    r: float,
    fill: str = "none",
    opacity: float = 1.0,
    stroke: str | None = None,
    stroke_width: float = 1.0,
    extra: str = "",
) -> str:
    parts = [
        f'cx="{fmt(cx)}"',
        f'cy="{fmt(cy)}"',
        f'r="{fmt(max(0, r))}"',
        f'fill="{fill}"',
    ]
    if opacity < 1:
        parts.append(f'opacity="{fmt(opacity)}"')
    if stroke:
        parts.append(f'stroke="{stroke}" stroke-width="{fmt(stroke_width)}"')
    if extra:
        parts.append(extra)
    return "<circle " + " ".join(parts) + "/>"


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str,
    width: float = 1.0,
    opacity: float = 1.0,
    cap: str = "butt",
    dash: str | None = None,
    extra: str = "",
) -> str:
    parts = [
        f'x1="{fmt(x1)}"',
        f'y1="{fmt(y1)}"',
        f'x2="{fmt(x2)}"',
        f'y2="{fmt(y2)}"',
        f'stroke="{stroke}"',
        f'stroke-width="{fmt(width)}"',
        f'stroke-linecap="{cap}"',
    ]
    if opacity < 1:
        parts.append(f'opacity="{fmt(opacity)}"')
    if dash:
        parts.append(f'stroke-dasharray="{dash}"')
    if extra:
        parts.append(extra)
    return "<line " + " ".join(parts) + "/>"


def path(
    d: str,
    fill: str = "none",
    stroke: str | None = None,
    stroke_width: float = 1.0,
    opacity: float = 1.0,
    cap: str = "round",
    join: str = "round",
    extra: str = "",
) -> str:
    parts = [f'd="{d}"', f'fill="{fill}"']
    if stroke:
        parts += [f'stroke="{stroke}"', f'stroke-width="{fmt(stroke_width)}"']
    if opacity < 1:
        parts.append(f'opacity="{fmt(opacity)}"')
    if cap:
        parts.append(f'stroke-linecap="{cap}"')
    if join:
        parts.append(f'stroke-linejoin="{join}"')
    if extra:
        parts.append(extra)
    return "<path " + " ".join(parts) + "/>"


def text(
    x: float,
    y: float,
    content: str,
    size: float,
    weight: int | str = 400,
    fill: str = "#ffffff",
    opacity: float = 1.0,
    anchor: str = "start",
    spacing: float = 0.0,
    family: str = "Sora",
    extra: str = "",
) -> str:
    parts = [
        f'x="{fmt(x)}"',
        f'y="{fmt(y)}"',
        f'font-family="{family}"',
        f'font-size="{fmt(size)}"',
        f'font-weight="{weight}"',
        f'fill="{fill}"',
        f'text-anchor="{anchor}"',
    ]
    if opacity < 1:
        parts.append(f'opacity="{fmt(opacity)}"')
    if spacing:
        parts.append(f'letter-spacing="{fmt(spacing)}"')
    if extra:
        parts.append(extra)
    return f"<text {' '.join(parts)}>{esc(content)}</text>"


def group(content: str, transform: str = "", opacity: float = 1.0, extra: str = "") -> str:
    attrs = []
    if transform:
        attrs.append(f'transform="{transform}"')
    if opacity < 1:
        attrs.append(f'opacity="{fmt(opacity)}"')
    if extra:
        attrs.append(extra)
    return f"<g {' '.join(attrs)}>{content}</g>" if attrs else f"<g>{content}</g>"


def svg_doc(width: float, height: float, body: str, defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" '
        f'height="{fmt(height)}" viewBox="0 0 {fmt(width)} {fmt(height)}">'
        f"<defs>{defs}</defs>{body}</svg>"
    )


def clip_rect(clip_id: str, x: float, y: float, w: float, h: float) -> str:
    return (
        f'<clipPath id="{clip_id}"><rect x="{fmt(x)}" y="{fmt(y)}" '
        f'width="{fmt(max(0, w))}" height="{fmt(max(0, h))}"/></clipPath>'
    )


def blur_filter(filter_id: str, deviation: float) -> str:
    return (
        f'<filter id="{filter_id}" x="-80%" y="-80%" width="260%" height="260%" '
        f'color-interpolation-filters="sRGB">'
        f'<feGaussianBlur stdDeviation="{fmt(deviation)}"/></filter>'
    )


def linear_gradient(
    gradient_id: str,
    stops: Sequence[tuple[float, str, float]],
    x1: float = 0,
    y1: float = 0,
    x2: float = 1,
    y2: float = 0,
    user_space: bool = False,
) -> str:
    units = ' gradientUnits="userSpaceOnUse"' if user_space else ""
    content = "".join(
        f'<stop offset="{fmt(offset)}" stop-color="{color}" stop-opacity="{fmt(alpha)}"/>'
        for offset, color, alpha in stops
    )
    return (
        f'<linearGradient id="{gradient_id}" x1="{fmt(x1)}" y1="{fmt(y1)}" '
        f'x2="{fmt(x2)}" y2="{fmt(y2)}"{units}>{content}</linearGradient>'
    )


def radial_gradient(
    gradient_id: str,
    stops: Sequence[tuple[float, str, float]],
    cx: float = 0.5,
    cy: float = 0.5,
    r: float = 0.5,
    user_space: bool = False,
) -> str:
    units = ' gradientUnits="userSpaceOnUse"' if user_space else ""
    content = "".join(
        f'<stop offset="{fmt(offset)}" stop-color="{color}" stop-opacity="{fmt(alpha)}"/>'
        for offset, color, alpha in stops
    )
    return (
        f'<radialGradient id="{gradient_id}" cx="{fmt(cx)}" cy="{fmt(cy)}" '
        f'r="{fmt(r)}"{units}>{content}</radialGradient>'
    )


def arc_path(cx: float, cy: float, radius: float, start_deg: float, end_deg: float) -> str:
    a0 = math.radians(start_deg)
    a1 = math.radians(end_deg)
    x0, y0 = cx + radius * math.cos(a0), cy + radius * math.sin(a0)
    x1, y1 = cx + radius * math.cos(a1), cy + radius * math.sin(a1)
    large = 1 if abs(end_deg - start_deg) > 180 else 0
    sweep = 1 if end_deg > start_deg else 0
    return f"M {fmt(x0)} {fmt(y0)} A {fmt(radius)} {fmt(radius)} 0 {large} {sweep} {fmt(x1)} {fmt(y1)}"


def arc_length(radius: float, start_deg: float, end_deg: float) -> float:
    return abs(math.radians(end_deg - start_deg)) * radius


def draw_progress(
    d: str, length: float, progress: float, stroke: str, width: float, opacity: float = 1.0,
    cap: str = "round", extra: str = "",
) -> str:
    """Draw-on effect using a normalized dash offset."""
    progress = clamp(progress)
    if progress <= 0.0001:
        return ""
    dash = f"{fmt(length * progress)} {fmt(length + 1)}"
    return path(
        d,
        stroke=stroke,
        stroke_width=width,
        opacity=opacity,
        cap=cap,
        extra=f'stroke-dasharray="{dash}" stroke-dashoffset="0" {extra}',
    )


# ---------------------------------------------------------------------------
# Shared brand elements
# ---------------------------------------------------------------------------

def mark(
    cx: float,
    cy: float,
    radius: float,
    draw: float = 1.0,
    rotation: float = 0.0,
    cyan: str = "#00E5FF",
    lime: str = "#D6FF3F",
    opacity: float = 1.0,
    glow: bool = True,
) -> str:
    """Orbit/pulse brand mark: an incomplete ring, a core and a satellite."""
    draw = clamp(draw)
    if draw <= 0.001 or opacity <= 0.001:
        return ""
    stroke = max(2.0, radius * 0.11)
    start, end = -90.0, 188.0
    ring = arc_path(cx, cy, radius, start, end)
    ring_len = arc_length(radius, start, end)
    satellite_angle = math.radians(rotation + 42)
    sx = cx + radius * math.cos(satellite_angle)
    sy = cy + radius * math.sin(satellite_angle)
    core_r = radius * 0.29 * anim(draw, 0, 0.7, 0.4, 1.0, "outBack")

    pieces = []
    if glow:
        pieces.append(
            path(
                ring,
                stroke=cyan,
                stroke_width=stroke * 2.2,
                opacity=0.16 * draw,
                cap="round",
                extra='filter="url(#markGlow)"',
            )
        )
    pieces.append(
        draw_progress(
            ring,
            ring_len,
            draw,
            stroke=cyan,
            width=stroke,
            opacity=opacity,
            cap="round",
        )
    )
    pieces.append(
        circle(
            cx,
            cy,
            core_r,
            fill=lime,
            opacity=opacity * fade_in(draw, 0.25, 1.0),
        )
    )
    pieces.append(
        circle(
            sx,
            sy,
            radius * 0.12 * draw,
            fill="#FFFFFF",
            opacity=opacity * 0.95 * draw,
        )
    )
    return group(
        "".join(pieces),
        transform=f"rotate({fmt(rotation)} {fmt(cx)} {fmt(cy)})",
    )


def mark_defs() -> str:
    return blur_filter("markGlow", 10)


def safe_guides(width: float, height: float, margin: float) -> str:
    """Optional non-rendering guide layer used by the AE import script."""
    x, y = margin, margin
    w, h = width - margin * 2, height - margin * 2
    return (
        rect(x, y, w, h, stroke="#FF3B6B", stroke_width=2, opacity=0.5)
        + rect(width / 2, y, 1, h, fill="#FF3B6B", opacity=0.35)
        + rect(x, height / 2, w, 1, fill="#FF3B6B", opacity=0.35)
    )
