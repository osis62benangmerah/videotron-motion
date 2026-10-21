"""Six-second lower third with a straight-alpha render for compositing."""

from __future__ import annotations

import math

from motionlib import (
    anim,
    blur_filter,
    clamp,
    clip_rect,
    fade_in,
    fmt,
    group,
    line,
    linear_gradient,
    mark,
    mark_defs,
    path,
    radial_gradient,
    rect,
    svg_doc,
    text,
    window,
)


def _geometry(width: float, height: float, cfg: dict):
    u = min(width / 1920.0, height / 1080.0)
    safe = float(cfg.get("safe_area", 0.05))
    return {
        "u": u,
        "w": width,
        "h": height,
        "margin_x": width * safe,
        "margin_y": height * safe,
        "duration": float(cfg["lower_third"]["duration"]),
    }


def render_frame(t: float, cfg: dict, width: float, height: float) -> str:
    # Authored on a 6 s timeline; config duration time-stretches it.
    authored = 6.0
    t = t * authored / float(cfg["lower_third"]["duration"])
    g = _geometry(width, height, cfg)
    u, w, h = g["u"], g["w"], g["h"]
    margin_x, margin_y = g["margin_x"], g["margin_y"]
    colors = cfg["colors"]
    data = cfg["lower_third"]

    panel_w = min(980 * u, w - margin_x * 2)
    panel_h = 190 * u
    panel_x = margin_x
    panel_y = h - margin_y - panel_h

    page_in = fade_in(t, 0.12, 0.78, "snap")
    page_out = anim(t, 4.86, 5.46, 0.0, -panel_w - margin_x, "inCubic")
    x_offset = -panel_w * (1 - page_in) + page_out

    bar_p = fade_in(t, 0.3, 0.9, "inOutQuint")
    kicker_p = fade_in(t, 0.55, 0.95, "outCubic")
    name_p = fade_in(t, 0.64, 1.12, "snap")
    role_p = fade_in(t, 0.82, 1.24, "outCubic")
    mark_p = fade_in(t, 0.7, 1.38, "inOutQuint")
    exit_soft = 1 - clamp((t - 4.75) / 0.55) * 0.35

    defs = [
        linear_gradient(
            "panelGrad",
            [
                (0, colors["panel"], 0.95),
                (0.62, colors["panel"], 0.9),
                (1, colors["panel"], 0.74),
            ],
            x1=0,
            y1=0,
            x2=1,
            y2=0,
        ),
        radial_gradient(
            "panelGlow",
            [(0, colors["cyan"], 0.16), (1, colors["cyan"], 0.0)],
            panel_x + panel_w * 0.12,
            panel_y + panel_h * 0.5,
            300 * u,
            user_space=True,
        ),
        blur_filter("panelShadow", 18 * u),
    ]

    shadow = rect(
        panel_x + 10 * u,
        panel_y + 14 * u,
        panel_w,
        panel_h,
        fill="#000000",
        opacity=0.42 * page_in,
        rx=3 * u,
        extra='filter="url(#panelShadow)"',
    )
    panel = rect(
        panel_x,
        panel_y,
        panel_w,
        panel_h,
        fill="url(#panelGrad)",
        rx=3 * u,
        stroke="rgba(255,255,255,0.13)",
        stroke_width=1.0 * u,
    )
    panel += rect(panel_x, panel_y, panel_w, panel_h, fill="url(#panelGlow)", rx=3 * u)
    panel += rect(
        panel_x,
        panel_y,
        panel_w,
        2.0 * u,
        fill=colors["cyan"],
        opacity=0.55,
    )

    bar = rect(
        panel_x,
        panel_y + (1 - bar_p) * panel_h,
        9 * u,
        panel_h * bar_p,
        fill=colors["lime"],
        opacity=0.95 * exit_soft,
    )

    kicker = text(
        panel_x + 52 * u,
        panel_y + 48 * u,
        data["kicker"],
        17 * u,
        weight=600,
        fill=colors["cyan"],
        spacing=5.0 * u,
        opacity=kicker_p * exit_soft,
    )

    name_size = 58 * u
    name_baseline = panel_y + 118 * u
    clip_y = name_baseline - name_size * 1.12
    clip_h = name_size * 1.35 * name_p
    clip_y = name_baseline + name_size * 0.24 - clip_h
    clip = clip_rect("nameClip", panel_x + 44 * u, clip_y, panel_w - 180 * u, clip_h)
    name = text(
        panel_x + 50 * u,
        name_baseline,
        data["name"],
        name_size,
        weight=700,
        fill=colors["ink"],
        spacing=-1.4 * u,
        extra=f'clip-path="url(#nameClip)"',
    )

    role = text(
        panel_x + 52 * u,
        panel_y + 158 * u,
        data["role"],
        23 * u,
        weight=500,
        fill=colors["muted"],
        spacing=4.2 * u,
        opacity=role_p * exit_soft,
    )

    divider_x = panel_x + panel_w - 158 * u
    divider = line(
        divider_x,
        panel_y + 28 * u,
        divider_x,
        panel_y + panel_h - 28 * u,
        stroke=colors["ink"],
        width=1.0 * u,
        opacity=0.16 * name_p * exit_soft,
    )

    mark_el = mark(
        panel_x + panel_w - 82 * u,
        panel_y + panel_h / 2 + 2 * u,
        38 * u,
        draw=mark_p,
        rotation=anim(t, 0.0, 6.0, -30, 210, "inOutCubic"),
        cyan=colors["cyan"],
        lime=colors["lime"],
        opacity=exit_soft,
    )

    # A thin progress line gives the hold a quiet sense of life.
    progress = clamp((t - 1.1) / 3.65)
    progress_w = (panel_w - 2 * 0) * progress
    progress_line = rect(
        panel_x,
        panel_y + panel_h - 2.5 * u,
        progress_w,
        2.5 * u,
        fill=colors["lime"],
        opacity=0.55 * name_p * exit_soft,
    )

    content = (
        shadow
        + panel
        + bar
        + kicker
        + name
        + role
        + divider
        + mark_el
        + progress_line
    )

    # The panel and its contents slide as one unit.
    return svg_doc(
        width,
        height,
        group(content, transform=f"translate({fmt(x_offset)} 0)", opacity=page_in),
        mark_defs() + "".join(defs) + clip,
    )
