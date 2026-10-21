"""Main 12-second, seamless videotron ident.

Timeline
    0.0 - 4.6   signal / mark / wordmark / tagline
    4.6 - 7.8   kinetic type: EVERY PIXEL ALIVE
    7.8 - 11.6  resolved brand lockup
    11.6 - 12.0 return to black (seamless loop)
"""

from __future__ import annotations

import math

from motionlib import (
    EASE,
    anim,
    arc_length,
    arc_path,
    blur_filter,
    circle,
    clip_rect,
    draw_progress,
    fade_in,
    fade_out,
    fmt,
    group,
    line,
    linear_gradient,
    mark,
    mark_defs,
    path,
    pulse,
    radial_gradient,
    rect,
    rgba,
    safe_guides,
    stagger,
    svg_doc,
    text,
    window,
)


def _geometry(width: float, height: float):
    u = min(width / 1920.0, height / 1080.0)
    return {
        "u": u,
        "cx": width / 2,
        "cy": height * 0.48,
        "w": width,
        "h": height,
        "duration": 12.0,
        "margin": min(width, height) * 0.05,
    }


def _background(t: float, cfg: dict, g: dict) -> tuple[str, str]:
    w, h, u, cx, cy, duration = g["w"], g["h"], g["u"], g["cx"], g["cy"], g["duration"]
    colors = cfg["colors"]
    phase = 2 * math.pi * t / duration

    defs = [
        radial_gradient(
            "bgCyan",
            [(0, colors["cyan"], 0.20), (0.45, colors["cyan"], 0.07), (1, colors["cyan"], 0.0)],
            cx + 260 * u + 120 * u * math.cos(phase),
            cy - 40 * u + 90 * u * math.sin(phase),
            620 * u,
            user_space=True,
        ),
        radial_gradient(
            "bgViolet",
            [(0, colors["violet"], 0.20), (0.5, colors["violet"], 0.07), (1, colors["violet"], 0.0)],
            cx - 420 * u + 90 * u * math.cos(phase + 2.1),
            cy + 230 * u + 70 * u * math.sin(phase + 2.1),
            700 * u,
            user_space=True,
        ),
        radial_gradient(
            "vignette",
            [(0, colors["bg"], 0.0), (0.58, colors["bg"], 0.0), (1, colors["bg"], 0.82)],
            cx,
            cy,
            max(w, h) * 0.78,
            user_space=True,
        ),
    ]

    body = [rect(0, 0, w, h, fill=colors["bg"])]
    body.append(rect(0, 0, w, h, fill="url(#bgCyan)"))
    body.append(rect(0, 0, w, h, fill="url(#bgViolet)"))

    # LED-friendly grid. Spacing is deliberately large and lines are soft so
    # the pattern does not alias into moire on a real LED wall.
    grid_in = fade_in(t, 0.35, 1.4, "inOutSine")
    grid_out = fade_out(t, 11.25, 11.9)
    grid_op = 0.075 * grid_in * grid_out
    spacing = 72 * u
    offset_x = (t / duration) * spacing
    offset_y = (t / duration) * spacing
    grid = []
    x = -spacing + offset_x
    while x < w + spacing:
        grid.append(line(x, 0, x, h, stroke=colors["cyan"], width=1.0 * u, opacity=1.0))
        x += spacing
    y = -spacing + offset_y
    while y < h + spacing:
        grid.append(line(0, y, w, y, stroke=colors["cyan"], width=1.0 * u, opacity=0.8))
        y += spacing
    body.append(group("".join(grid), opacity=grid_op))
    body.append(rect(0, 0, w, h, fill="url(#vignette)"))

    defs.append(blur_filter("softGlow", 22 * u))
    return "".join(body), "".join(defs)


def _rings(t: float, cfg: dict, g: dict) -> str:
    w, h, u, cx, cy, duration = g["w"], g["h"], g["u"], g["cx"], g["cy"], g["duration"]
    colors = cfg["colors"]
    turn = t / duration

    master = window(t, 0.3, 1.35, 11.15, 11.85)
    kinetic = window(t, 4.55, 5.1, 7.15, 7.8)
    master *= 1.0 - 0.45 * kinetic

    pieces = []

    # Tick ring: 72 marks, rotating one full revolution over the loop.
    ticks = []
    for i in range(72):
        a = math.radians(i * 5 + turn * 360)
        r0, r1 = 505 * u, 518 * u
        ticks.append(
            line(
                cx + r0 * math.cos(a),
                cy + r0 * math.sin(a),
                cx + r1 * math.cos(a),
                cy + r1 * math.sin(a),
                stroke=colors["ink"],
                width=1.4 * u,
                opacity=0.40 if i % 6 == 0 else 0.18,
            )
        )
    pieces.append("".join(ticks))

    pieces.append(
        circle(
            cx,
            cy,
            438 * u,
            stroke=colors["ink"],
            stroke_width=1.2 * u,
            opacity=0.10,
            extra=f'stroke-dasharray="{fmt(3*u)} {fmt(19*u)}"',
        )
    )

    # Hero arc, drawn on with a glow duplicate.
    draw = fade_in(t, 0.45, 1.65, "inOutQuint")
    arc = arc_path(cx, cy, 348 * u, 118, 372)
    arc_len = arc_length(348 * u, 118, 372)
    pieces.append(
        draw_progress(
            arc,
            arc_len,
            draw,
            stroke=colors["cyan"],
            width=13 * u,
            opacity=0.12,
            extra='filter="url(#softGlow)"',
        )
    )
    pieces.append(
        draw_progress(
            arc,
            arc_len,
            draw,
            stroke="url(#ringGrad)",
            width=5.5 * u,
            opacity=0.95,
        )
    )

    # Counter-rotating dashed ring.
    pieces.append(
        group(
            circle(
                cx,
                cy,
                212 * u,
                stroke=colors["violet"],
                stroke_width=2.2 * u,
                opacity=0.55,
                extra=f'stroke-dasharray="{fmt(2*u)} {fmt(12*u)}"',
            ),
            transform=f"rotate({fmt(-turn*360)} {fmt(cx)} {fmt(cy)})",
        )
    )

    # Fine inner orbit, plus a bright satellite.
    pieces.append(
        circle(cx, cy, 150 * u, stroke=colors["ink"], stroke_width=1.0 * u, opacity=0.10)
    )
    sat_a = 2 * math.pi * turn + 1.2
    pieces.append(
        circle(
            cx + 348 * u * math.cos(sat_a),
            cy + 348 * u * math.sin(sat_a),
            8.5 * u,
            fill=colors["lime"],
            opacity=0.95,
            extra='filter="url(#softGlow)"',
        )
    )
    pieces.append(
        circle(
            cx + 348 * u * math.cos(sat_a),
            cy + 348 * u * math.sin(sat_a),
            4.0 * u,
            fill="#FFFFFF",
            opacity=0.95,
        )
    )

    # Registration marks at the cardinal points.
    marks = []
    for a_deg in (0, 90, 180, 270):
        a = math.radians(a_deg)
        rr = 505 * u
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        arm = 9 * u
        marks.append(line(x - arm, y, x + arm, y, stroke=colors["ink"], width=1.4 * u, opacity=0.3))
        marks.append(line(x, y - arm, x, y + arm, stroke=colors["ink"], width=1.4 * u, opacity=0.3))
    pieces.append("".join(marks))

    defs = (
        linear_gradient(
            "ringGrad",
            [(0, colors["cyan"], 1.0), (0.55, colors["violet"], 0.9), (1, colors["lime"], 1.0)],
            user_space=False,
        )
        + blur_filter("ringGlow", 12 * u)
    )
    return group("".join(pieces), opacity=master) + f"<defs>{defs}</defs>"


def _signal_line(t: float, cfg: dict, g: dict) -> str:
    cx, cy, u = g["cx"], g["cy"], g["u"]
    colors = cfg["colors"]
    op = window(t, 0.0, 0.35, 0.95, 1.55) + window(t, 11.35, 11.7, 11.94, 12.0)
    if op <= 0.001:
        return ""
    p = fade_in(t, 0.0, 0.55, "outExpo") if t < 6 else fade_out(t, 11.25, 11.9, "inCubic")
    half = 180 * u * p
    return group(
        line(cx - half, cy, cx + half, cy, stroke=colors["cyan"], width=2.2 * u, opacity=0.75)
        + circle(cx, cy, 3.2 * u, fill=colors["lime"], opacity=0.9),
        opacity=op,
    )


def _micro_copy(t: float, cfg: dict, g: dict) -> str:
    w, h, u = g["w"], g["h"], g["u"]
    colors = cfg["colors"]
    op = window(t, 1.65, 2.35, 10.95, 11.45) * 0.7
    if op <= 0.001:
        return ""
    left = rect(55 * u, 70 * u, 7 * u, 7 * u, fill=colors["lime"], opacity=0.9)
    left += text(
        74 * u,
        78 * u,
        "NOVA / IDENT",
        16 * u,
        weight=500,
        fill=colors["ink"],
        spacing=3.8 * u,
        opacity=0.55,
    )
    right = text(
        w - 55 * u,
        78 * u,
        f"{cfg['duration']:.0f}S LOOP  /  {cfg['fps']} FPS",
        15 * u,
        weight=400,
        fill=colors["ink"],
        anchor="end",
        spacing=2.6 * u,
        opacity=0.38,
    )
    # A hairline that frames the lower edge without becoming a visible border.
    edge = line(55 * u, h - 58 * u, w - 55 * u, h - 58 * u, stroke=colors["ink"], width=1 * u, opacity=0.10)
    return group(left + right + edge, opacity=op)


def _hero(t: float, cfg: dict, g: dict) -> str:
    cx, cy, u = g["cx"], g["cy"], g["u"]
    colors = cfg["colors"]
    brand_cfg = cfg["brand"]

    out = fade_out(t, 4.0, 4.4, "inCubic")
    if out <= 0.001:
        return ""

    mark_p = fade_in(t, 0.65, 1.55, "inOutQuint")
    brand_p = fade_in(t, 1.10, 2.05, "snap")
    tag_p = fade_in(t, 2.15, 2.85, "outCubic")

    baseline = cy + 58 * u + (1 - brand_p) * 74 * u - (1 - out) * 46 * u
    size = 300 * u
    spacing = anim(t, 1.10, 2.05, 42, -12, "snap")
    opacity = brand_p * out

    # Clip reveal rises from the baseline. Coordinates are global, so the
    # moving baseline is folded into the clip rectangle.
    clip_y = 0.18 * size - brand_p * 1.18 * size
    clip_h = brand_p * 1.18 * size
    clip = clip_rect("brandClip", -850 * u, clip_y, 1700 * u, clip_h)

    brand_text = text(
        0,
        0,
        brand_cfg["name"],
        size,
        weight=800,
        fill="url(#brandGrad)",
        anchor="middle",
        spacing=spacing,
    )
    # A restrained cyan glow is layered under the fill for broadcast pop.
    glow_text = text(
        0,
        0,
        brand_cfg["name"],
        size,
        weight=800,
        fill=colors["cyan"],
        anchor="middle",
        spacing=spacing,
        opacity=0.22,
        extra='filter="url(#brandGlow)"',
    )
    brand = group(
        glow_text + f'<g clip-path="url(#brandClip)">{brand_text}</g>',
        transform=f"translate({fmt(cx)} {fmt(baseline)})",
        opacity=opacity,
    )

    mark_rotation = anim(t, 0.0, 12.0, -35, 325, "inOutCubic")
    mark_el = mark(
        cx,
        cy - 286 * u,
        64 * u,
        draw=mark_p,
        rotation=mark_rotation,
        cyan=colors["cyan"],
        lime=colors["lime"],
        opacity=out,
    )

    tagline = text(
        cx,
        cy + 188 * u + (1 - tag_p) * 24 * u - (1 - out) * 28 * u,
        brand_cfg["tagline"],
        30 * u,
        weight=500,
        fill=colors["muted"],
        anchor="middle",
        spacing=10 * u,
        opacity=tag_p * out,
    )
    rule_w = 82 * u * tag_p
    rule_y = cy + 177 * u
    rule = line(cx - 280 * u - rule_w, rule_y, cx - 280 * u, rule_y, stroke=colors["cyan"], width=2 * u, opacity=0.55 * out)
    rule += line(cx + 280 * u, rule_y, cx + 280 * u + rule_w, rule_y, stroke=colors["cyan"], width=2 * u, opacity=0.55 * out)

    # A low halo anchors the lockup on the background.
    halo = circle(
        cx,
        cy + 20 * u,
        500 * u,
        fill="url(#heroHalo)",
        opacity=0.55 * brand_p * out,
    )

    defs = (
        linear_gradient(
            "brandGrad",
            [(0, "#FFFFFF", 1.0), (0.52, "#E9FBFF", 1.0), (1, colors["cyan"], 1.0)],
            x1=0,
            y1=0,
            x2=0,
            y2=1,
        )
        + radial_gradient(
            "heroHalo",
            [(0, colors["cyan"], 0.15), (0.55, colors["cyan"], 0.05), (1, colors["cyan"], 0.0)],
            cx,
            cy + 20 * u,
            500 * u,
            user_space=True,
        )
        + blur_filter("brandGlow", 18 * u)
    )
    return f"<defs>{clip}{defs}</defs>" + halo + mark_el + brand + tagline + rule


def _kinetic(t: float, cfg: dict, g: dict) -> str:
    w, h, u, cy = g["w"], g["h"], g["u"], g["cy"]
    colors = cfg["colors"]
    brand_cfg = cfg["brand"]
    duration = g["duration"]

    master = window(t, 4.55, 5.15, 7.1, 7.7)
    if master <= 0.001:
        return ""

    mx = max(w * 0.085, 88 * u)
    y1 = cy - 188 * u
    y2 = cy + 66 * u
    y3 = cy + 238 * u
    rail_x = mx - 68 * u

    # Editorial rail.
    rail_top, rail_bottom = y1 - 132 * u, y3 + 45 * u
    rail_progress = EASE["inOutCubic"]((t - 4.55) / 3.0)
    rail = line(rail_x, rail_top, rail_x, rail_bottom, stroke=colors["ink"], width=1.2 * u, opacity=0.16)
    rail += line(
        rail_x,
        rail_top,
        rail_x,
        rail_top + (rail_bottom - rail_top) * rail_progress,
        stroke=colors["lime"],
        width=2.2 * u,
        opacity=0.8,
    )
    for i, yy in enumerate((y1, y2, y3)):
        rail += line(rail_x - 6 * u, yy, rail_x + 6 * u, yy, stroke=colors["ink"], width=1.2 * u, opacity=0.35)
        rail += text(
            rail_x - 18 * u,
            yy - 6 * u,
            f"0{i + 1}",
            13 * u,
            weight=500,
            fill=colors["muted"],
            anchor="end",
            spacing=2 * u,
            opacity=0.55,
        )

    lines = []
    specs = [
        ("EVERY", y1, 148 * u, "fill", colors["ink"], -1),
        ("PIXEL", y2, 282 * u, "gradient", "url(#kineticGrad)", 1),
        ("ALIVE.", y3, 148 * u, "outline", colors["lime"], -1),
    ]
    for i, (word, yy, size, mode, paint, direction) in enumerate(specs):
        p = stagger(t, i, 4.62, 0.13, 0.58, "snap")
        q = anim(t, 7.06 + i * 0.045, 7.48 + i * 0.045, 0.0, 1.0, "inCubic")
        x_off = (1 - p) * (-95 * u) + (1 - q) * (direction * 70 * u)
        letter_spacing = (-7 * u) if i == 1 else (-1 * u)
        if mode == "gradient":
            fill, stroke, stroke_w = paint, None, 0
        elif mode == "outline":
            fill, stroke, stroke_w = "none", paint, 3.4 * u
        else:
            fill, stroke, stroke_w = paint, None, 0
        extra = f'stroke="{stroke}" stroke-width="{fmt(stroke_w)}"' if stroke else ""
        # Clip is wide enough for the longest configured word; it creates a
        # directional wipe while the text itself slides into place.
        cw = (1080 if i == 1 else 760) * u * p
        clip_id = f"kinClip{i}"
        clip = clip_rect(clip_id, mx - 40 * u, yy - size * 1.15, cw + 80 * u, size * 1.42)
        content = text(
            mx + x_off,
            yy,
            word,
            size,
            weight=800 if i == 1 else 700,
            fill=fill,
            anchor="start",
            spacing=letter_spacing,
            extra=extra,
        )
        if mode == "outline":
            content += text(
                mx + x_off + 5 * u,
                yy + 5 * u,
                word,
                size,
                weight=700,
                fill="none",
                anchor="start",
                spacing=letter_spacing,
                opacity=0.20,
                extra=f'stroke="{colors["cyan"]}" stroke-width="{fmt(1.2*u)}"',
            )
        lines.append(clip)
        lines.append(group(f'<g clip-path="url(#{clip_id})">{content}</g>', opacity=p * (1 - q) * master))

    # Context label on the right edge.
    side = text(
        w * 0.935,
        cy,
        "SIGNAL / 02",
        13 * u,
        weight=500,
        fill=colors["ink"],
        anchor="middle",
        spacing=4 * u,
        opacity=0.35 * master,
        extra=f'transform="rotate(90 {fmt(w*0.935)} {fmt(cy)})"',
    )

    # A big, low-contrast outline circle adds depth behind the type.
    ghost = circle(
        w * 0.80,
        cy + 30 * u,
        310 * u,
        stroke=colors["violet"],
        stroke_width=1.5 * u,
        opacity=0.18 * master,
        extra=f'stroke-dasharray="{fmt(2*u)} {fmt(14*u)}"',
    )

    top_rule = line(
        mx,
        y1 - 120 * u,
        mx + (540 * u) * EASE["outCubic"](pulse(t, 5.0, 1.2)),
        y1 - 120 * u,
        stroke=colors["cyan"],
        width=2 * u,
        opacity=0.45 * master,
    )

    defs = linear_gradient(
        "kineticGrad",
        [(0, colors["lime"], 1.0), (0.48, "#FFFFFF", 1.0), (1, colors["cyan"], 1.0)],
        x1=0,
        y1=0,
        x2=1,
        y2=0,
    )
    return f"<defs>{defs}</defs>" + ghost + rail + top_rule + "".join(lines) + side


def _transition(t: float, cfg: dict, g: dict) -> str:
    w, h, u, duration = g["w"], g["h"], g["u"], g["duration"]
    colors = cfg["colors"]
    flash = pulse(t, 7.6, 0.2) * 0.07
    x = anim(t, 7.35, 7.95, -w * 0.25, w * 1.25, "inOutCubic")
    beam_w = 150 * u
    beam = rect(
        x,
        0,
        beam_w,
        h,
        fill="url(#beamGrad)",
        opacity=0.42 * pulse(t, 7.65, 0.3),
    )
    defs = linear_gradient(
        "beamGrad",
        [(0, "#FFFFFF", 0.0), (0.42, colors["cyan"], 0.4), (0.5, "#FFFFFF", 0.9), (0.58, colors["violet"], 0.35), (1, "#FFFFFF", 0.0)],
        x1=0,
        y1=0,
        x2=1,
        y2=0,
    )
    veil = rect(0, 0, w, h, fill="#FFFFFF", opacity=flash)
    return f"<defs>{defs}</defs>" + beam + veil


def _final(t: float, cfg: dict, g: dict) -> str:
    cx, cy, u = g["cx"], g["cy"], g["u"]
    colors = cfg["colors"]
    brand_cfg = cfg["brand"]

    p = fade_in(t, 7.6, 8.45, "snap")
    out = fade_out(t, 10.9, 11.58, "inCubic")
    if p * out <= 0.001:
        return ""

    zoom = 0.94 + 0.06 * p + 0.012 * clamp01((t - 8.8) / 2.2)
    group_tf = f"translate({fmt(cx)} {fmt(cy)}) scale({fmt(zoom)}) translate({fmt(-cx)} {fmt(-cy)})"

    baseline = cy + 62 * u
    brand = text(
        cx,
        baseline,
        brand_cfg["name"],
        250 * u,
        weight=800,
        fill="url(#finalGrad)",
        anchor="middle",
        spacing=-9 * u,
    )
    tag = text(
        cx,
        cy + 154 * u,
        brand_cfg["tagline"],
        26 * u,
        weight=500,
        fill=colors["muted"],
        anchor="middle",
        spacing=8 * u,
    )
    rule_w = 120 * u * p
    rules = line(cx - 230 * u, cy + 146 * u, cx - 230 * u - rule_w, cy + 146 * u, stroke=colors["cyan"], width=1.6 * u, opacity=0.65)
    rules += line(cx + 230 * u, cy + 146 * u, cx + 230 * u + rule_w, cy + 146 * u, stroke=colors["cyan"], width=1.6 * u, opacity=0.65)

    mark_el = mark(
        cx,
        cy - 238 * u,
        54 * u,
        draw=fade_in(t, 7.55, 8.35, "inOutQuint"),
        rotation=anim(t, 8.0, 11.6, -20, 70, "inOutCubic"),
        cyan=colors["cyan"],
        lime=colors["lime"],
    )

    # Soft expanding signal rings during the hold.
    rings = []
    for start in (8.7, 9.7):
        rp = clamp01((t - start) / 2.1)
        if 0 < rp < 1:
            rings.append(
                circle(
                    cx,
                    cy - 70 * u,
                    (150 + 470 * rp) * u,
                    stroke=colors["cyan"],
                    stroke_width=1.4 * u,
                    opacity=0.22 * (1 - rp) ** 2,
                )
            )

    halo = circle(cx, cy - 70 * u, 430 * u, fill="url(#finalHalo)", opacity=0.65 * p * out)

    content = mark_el + brand + tag + rules + "".join(rings)
    defs = (
        linear_gradient(
            "finalGrad",
            [(0, "#FFFFFF", 1.0), (0.58, "#ECFBFF", 1.0), (1, colors["cyan"], 1.0)],
            x1=0,
            y1=0,
            x2=0,
            y2=1,
        )
        + radial_gradient(
            "finalHalo",
            [(0, colors["violet"], 0.13), (0.55, colors["cyan"], 0.05), (1, colors["cyan"], 0.0)],
            cx,
            cy - 70 * u,
            430 * u,
            user_space=True,
        )
    )
    return f"<defs>{defs}</defs>" + halo + group(content, transform=group_tf, opacity=p * out)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def render_frame(t: float, cfg: dict, width: float, height: float) -> str:
    # The piece is authored on a 12 s timeline. Changing `duration` in
    # config.json time-stretches the whole piece rather than truncating it.
    authored = 12.0
    t = t * authored / float(cfg["duration"])
    g = _geometry(width, height)
    bg, bg_defs = _background(t, cfg, g)
    body = bg
    body += _rings(t, cfg, g)
    body += _signal_line(t, cfg, g)
    body += _hero(t, cfg, g)
    body += _kinetic(t, cfg, g)
    body += _transition(t, cfg, g)
    body += _final(t, cfg, g)
    body += _micro_copy(t, cfg, g)
    return svg_doc(width, height, body, mark_defs() + bg_defs)
