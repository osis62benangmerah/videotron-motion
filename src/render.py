#!/usr/bin/env python3
"""Render the NOVA videotron package.

Pipeline
    1. Generate one SVG per frame (vector source, deterministic).
    2. Rasterise the SVG with rsvg-convert (straight-alpha PNG).
    3. Encode an AE-friendly ProRes master and a small H.264 review file.

Only Python's standard library, rsvg-convert and ffmpeg are required.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import scene_lower_third  # noqa: E402
import scene_main  # noqa: E402
from motionlib import linear_gradient, radial_gradient, svg_doc  # noqa: E402

FONT_DIR = ROOT / "assets" / "fonts"
OUT_DIR = ROOT / "out"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Environment and helpers
# ---------------------------------------------------------------------------

def check_dependencies() -> None:
    missing = [name for name in ("rsvg-convert", "ffmpeg") if shutil.which(name) is None]
    if missing:
        raise SystemExit(
            "Missing required command(s): "
            + ", ".join(missing)
            + "\nInstall librsvg (rsvg-convert) and ffmpeg, then run again."
        )


def font_environment() -> dict[str, str]:
    """Point fontconfig at the bundled font without touching the system."""
    env = os.environ.copy()
    if not (FONT_DIR / "Sora.ttf").exists():
        raise SystemExit(f"Bundled font not found: {FONT_DIR / 'Sora.ttf'}")
    cache = Path(tempfile.gettempdir()) / "videotron-motion-fontcache"
    cache.mkdir(parents=True, exist_ok=True)
    conf = Path(tempfile.gettempdir()) / "videotron-motion-fonts.conf"
    conf.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig>\n"
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        f"  <dir>{FONT_DIR}</dir>\n"
        f"  <cachedir>{cache}</cachedir>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    env["FONTCONFIG_FILE"] = str(conf)
    return env


def format_time(seconds: float) -> str:
    minutes, sec = divmod(seconds, 60)
    return f"{int(minutes):02d}:{sec:05.2f}"


def run_ffmpeg(args: list[str], label: str) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    print(f"  · {label}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({label}):\n{proc.stderr.strip()}")


# ---------------------------------------------------------------------------
# Per-frame rendering
# ---------------------------------------------------------------------------

def render_frames(
    name: str,
    render_fn,
    duration: float,
    fps: int,
    width: int,
    height: int,
    workers: int,
    keep_svg: bool,
    limit: int | None,
) -> dict:
    out_dir = OUT_DIR / name
    png_dir = out_dir / "png"
    svg_dir = out_dir / "svg"
    if png_dir.exists():
        shutil.rmtree(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)
    if svg_dir.exists():
        shutil.rmtree(svg_dir)
    if keep_svg:
        svg_dir.mkdir(parents=True, exist_ok=True)

    total = int(round(duration * fps))
    if limit:
        total = min(total, limit)
    env = font_environment()

    def job(index: int) -> int:
        t = index / fps
        svg = render_fn(t, CONFIG, width, height)
        if keep_svg:
            (svg_dir / f"{name}_{index:04d}.svg").write_text(svg, encoding="utf-8")
        png = png_dir / f"{name}_{index:04d}.png"
        proc = subprocess.run(
            ["rsvg-convert", "-w", str(width), "-h", str(height), "-o", str(png), "-"],
            input=svg.encode("utf-8"),
            env=env,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rsvg-convert failed on frame {index}:\n"
                + proc.stderr.decode("utf-8", "replace").strip()
            )
        if not png.exists() or png.stat().st_size == 0:
            raise RuntimeError(f"rsvg-convert produced no image for frame {index}")
        return index

    print(f"[{name}] {total} frames · {width}×{height} · {fps} fps · {duration:.2f}s")
    started = datetime.now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job, i): i for i in range(total)}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            future.result()
            done += 1
            if done == total or done % max(1, total // 12) == 0:
                elapsed = (datetime.now() - started).total_seconds()
                rate = done / elapsed if elapsed else 0
                print(
                    f"  frames {done:>4}/{total}  {done/total*100:5.1f}%  "
                    f"{rate:4.1f} fps  elapsed {format_time(elapsed)}"
                )
    return {"frames": total, "seconds": total / fps, "png_dir": png_dir}


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def encode_main(name: str, meta: dict, fps: int, width: int, height: int) -> dict:
    out_dir = OUT_DIR / name
    png_pattern = str(out_dir / "png" / f"{name}_%04d.png")
    common_in = ["-framerate", str(fps), "-start_number", "0", "-i", png_pattern]

    master = out_dir / f"{name}_prores422hq.mov"
    run_ffmpeg(
        [
            *common_in,
            "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv422p10le",
            "-c:v", "prores_ks",
            "-profile:v", "3",
            "-qscale:v", "9",
            "-vendor", "apl0",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-color_range", "tv",
            "-movflags", "+write_colr",
            str(master),
        ],
        "ProRes 422 HQ master (Rec.709, video range)",
    )

    preview = out_dir / f"{name}_preview.mp4"
    run_ffmpeg(
        [
            *common_in,
            "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-movflags", "+faststart",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-color_range", "tv",
            str(preview),
        ],
        "H.264 review file",
    )
    return {"master": master, "preview": preview}


def encode_lower_third(name: str, meta: dict, fps: int, width: int, height: int) -> dict:
    out_dir = OUT_DIR / name
    png_pattern = str(out_dir / "png" / f"{name}_%04d.png")
    common_in = ["-framerate", str(fps), "-start_number", "0", "-i", png_pattern]

    master = out_dir / f"{name}_prores4444_alpha.mov"
    run_ffmpeg(
        [
            *common_in,
            "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuva444p10le",
            "-c:v", "prores_ks",
            "-profile:v", "4",
            "-qscale:v", "10",
            "-alpha_bits", "16",
            "-vendor", "apl0",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-color_range", "tv",
            "-movflags", "+write_colr",
            str(master),
        ],
        "ProRes 4444 master with straight alpha",
    )

    bg = OUT_DIR / "_assets" / "preview_bg.png"
    if not bg.exists():
        make_preview_background(bg, width, height)
    preview = out_dir / f"{name}_preview.mp4"
    run_ffmpeg(
        [
            "-loop", "1", "-framerate", str(fps), "-i", str(bg),
            *common_in,
            "-filter_complex",
            "[0:v][1:v]overlay=shortest=1:format=auto,"
            "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-shortest",
            "-movflags", "+faststart",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-color_range", "tv",
            str(preview),
        ],
        "H.264 review file (on demo background)",
    )
    return {"master": master, "preview": preview}


def make_preview_background(path: Path, width: int, height: int) -> None:
    """A neutral plate used only for the lower-third review video."""
    path.parent.mkdir(parents=True, exist_ok=True)
    u = min(width / 1920.0, height / 1080.0)
    defs = (
        linear_gradient(
            "demoBg",
            [(0, "#0b1424", 1.0), (1, "#20324d", 1.0)],
            x1=0, y1=0, x2=1, y2=1,
        )
        + radial_gradient(
            "demoGlow",
            [(0, "#2f5f7a", 0.55), (1, "#0b1424", 0.0)],
            width * 0.7, height * 0.35, width * 0.55,
            user_space=True,
        )
    )
    body = f'<rect width="{width}" height="{height}" fill="url(#demoBg)"/>'
    body += f'<rect width="{width}" height="{height}" fill="url(#demoGlow)"/>'
    body += (
        f'<circle cx="{width*0.77}" cy="{height*0.28}" r="{220*u}" fill="none" '
        f'stroke="#7fe7ff" stroke-opacity=".12" stroke-width="2"/>'
    )
    svg = svg_doc(width, height, body, defs)
    env = font_environment()
    proc = subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height), "-o", str(path), "-"],
        input=svg.encode("utf-8"),
        env=env,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("Could not create preview background")


# ---------------------------------------------------------------------------
# Stills / manifest
# ---------------------------------------------------------------------------

def extract_still(png_dir: Path, name: str, time_s: float, fps: int, out_path: Path, bg: Path | None = None) -> None:
    index = int(round(time_s * fps))
    frame = png_dir / f"{name}_{index:04d}.png"
    if not frame.exists():
        frame = sorted(png_dir.glob(f"{name}_*.png"))[-1]
    if bg is None:
        shutil.copyfile(frame, out_path)
        return
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(bg), "-i", str(frame),
            "-filter_complex", "[0:v][1:v]overlay=format=auto",
            "-frames:v", "1", str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())


def file_entry(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Render the NOVA videotron package.")
    parser.add_argument("--scene", choices=("all", "main", "lower-third"), default="all")
    parser.add_argument("--scale", type=float, default=float(CONFIG.get("render", {}).get("png_scale", 1)))
    parser.add_argument("--workers", type=int, default=int(CONFIG.get("render", {}).get("workers", 6)))
    parser.add_argument("--keep-svg", action="store_true", help="Keep the per-frame SVG sources (large).")
    parser.add_argument("--frames-only", action="store_true", help="Skip ProRes/H.264 encoding.")
    parser.add_argument("--limit", type=int, default=None, help="Render only the first N frames (smoke test).")
    args = parser.parse_args()

    check_dependencies()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    selected = []
    if args.scene in ("all", "main"):
        selected.append(
            (
                "main_loop",
                scene_main.render_frame,
                float(CONFIG["duration"]),
                False,
            )
        )
    if args.scene in ("all", "lower-third"):
        selected.append(
            (
                "lower_third",
                scene_lower_third.render_frame,
                float(CONFIG["lower_third"]["duration"]),
                True,
            )
        )

    width = int(round(int(CONFIG["width"]) * args.scale))
    height = int(round(int(CONFIG["height"]) * args.scale))
    fps = int(CONFIG["fps"])
    manifest = {
        "project": CONFIG["project"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": {"width": int(CONFIG["width"]), "height": int(CONFIG["height"]), "fps": fps},
        "render": {"width": width, "height": height, "scale": args.scale},
        "font": "Sora (SIL Open Font License 1.1) — assets/fonts/Sora.ttf",
        "color": "Rec.709, video range in ProRes/H.264; full-range sRGB in PNG",
        "scenes": {},
    }

    for name, render_fn, duration, has_alpha in selected:
        meta = render_frames(
            name=name,
            render_fn=render_fn,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            workers=max(1, args.workers),
            keep_svg=args.keep_svg,
            limit=args.limit,
        )
        scene_meta = {
            "width": width,
            "height": height,
            "fps": fps,
            "frames": meta["frames"],
            "duration": round(meta["seconds"], 3),
            "alpha": has_alpha,
            "png_sequence": str(meta["png_dir"].relative_to(ROOT)),
        }
        if args.limit:
            scene_meta["limit"] = args.limit
        if not args.frames_only and not args.limit:
            if name == "lower_third":
                files = encode_lower_third(name, meta, fps, width, height)
            else:
                files = encode_main(name, meta, fps, width, height)
            stills_dir = OUT_DIR / name / "stills"
            if stills_dir.exists():
                shutil.rmtree(stills_dir)
            stills_dir.mkdir(parents=True, exist_ok=True)
            bg = OUT_DIR / "_assets" / "preview_bg.png" if name == "lower_third" else None
            if name == "lower_third" and bg and not bg.exists():
                make_preview_background(bg, width, height)
            still_times = (1.7, 5.9, 9.5) if name == "main_loop" else (1.7, 3.1)
            scene_meta["stills"] = []
            for time_s in still_times:
                still = stills_dir / f"{name}_{time_s:04.1f}s.png"
                extract_still(meta["png_dir"], name, time_s, fps, still, bg)
                scene_meta["stills"].append(file_entry(still))
            scene_meta["files"] = {
                key: file_entry(value) for key, value in files.items()
            }
        manifest["scenes"][name] = scene_meta

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("\nDone.")
    for name, scene in manifest["scenes"].items():
        print(f"  {name}: {scene['frames']} frames · {scene['duration']}s")
        for key, value in scene.get("files", {}).items():
            print(f"    {key}: {value['path']} ({value['bytes']/1e6:.1f} MB)")
    print(f"  manifest: out/manifest.json")


if __name__ == "__main__":
    main()
