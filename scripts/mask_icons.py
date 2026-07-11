#!/usr/bin/env python3
"""
Align all icon WebPs to the same circle position/size, then clip with outline.svg mask
(circle + right flag tab). Pixels outside the mask become fully transparent.

Usage:
  python scripts/mask_icons.py
  python scripts/mask_icons.py --dry-run --limit 3
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "assests" / "icons"
OUTLINE_SVG = ROOT / "assests" / "tool" / "outline.svg"
MASK_CACHE = ROOT / "assests" / "tool" / "outline_mask_792.png"

# SVG path geometry (from outline.svg)
SVG_CX, SVG_CY, SVG_R = 293.0, 419.9, 302.6
SVG_BOUNDS = (-9.6, 117.3, 629.0, 722.5)  # x0,y0,x1,y1 of circle+flag

SIZE = 792
TARGET_R = 300.0
TARGET_CX = SIZE / 2.0
TARGET_CY = SIZE / 2.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--icons", type=Path, default=ICONS)
    p.add_argument("--svg", type=Path, default=OUTLINE_SVG)
    p.add_argument("--size", type=int, default=SIZE)
    p.add_argument("--radius", type=float, default=TARGET_R)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--preview", type=Path, default=None, help="Save first result preview PNG here")
    return p.parse_args()


def build_mask(size: int, target_cx: float, target_cy: float, target_r: float) -> np.ndarray:
    x0, y0, x1, y1 = SVG_BOUNDS
    pad = 2.0
    vb_x, vb_y = x0 - pad, y0 - pad
    vb_w, vb_h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad

    # Read original path from file if present, else use known path
    path_d = (
        "M559.8,562.9H629v-114c0,0-34.8,0-34.8,0c0.9-9.5,1.4-19.2,1.4-29"
        "c0-167.1-135.5-302.6-302.6-302.6S-9.6,252.8-9.6,419.9S125.9,722.5,293,722.5"
        "C408.4,722.5,508.7,657.9,559.8,562.9z"
    )
    svg = f'''<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_x} {vb_y} {vb_w} {vb_h}" width="{vb_w}" height="{vb_h}">
<path fill="#ffffff" d="{path_d}"/>
</svg>'''

    with tempfile.TemporaryDirectory() as td:
        svg_path = Path(td) / "mask.svg"
        png_path = Path(td) / "mask.png"
        svg_path.write_text(svg)
        render_w = 2000
        render_h = int(round(render_w * vb_h / vb_w))
        subprocess.check_call(
            ["rsvg-convert", "-w", str(render_w), "-h", str(render_h), "-o", str(png_path), str(svg_path)]
        )
        raw = np.asarray(Image.open(png_path).convert("L"))

    sx = render_w / vb_w
    sy = render_h / vb_h
    mcx = (SVG_CX - vb_x) * sx
    mcy = (SVG_CY - vb_y) * sy
    mr = SVG_R * ((sx + sy) / 2.0)

    ys, xs = np.where(raw > 128)
    mb = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    crop = raw[mb[1] : mb[3], mb[0] : mb[2]]
    mcx_c = mcx - mb[0]
    mcy_c = mcy - mb[1]

    scale = target_r / mr
    new_w = max(1, int(round(crop.shape[1] * scale)))
    new_h = max(1, int(round(crop.shape[0] * scale)))
    scaled = Image.fromarray(crop).resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("L", (size, size), 0)
    paste_x = int(round(target_cx - mcx_c * scale))
    paste_y = int(round(target_cy - mcy_c * scale))
    canvas.paste(scaled, (paste_x, paste_y))
    return np.asarray(canvas)


def estimate_circle(alpha: np.ndarray) -> tuple[float, float, float]:
    a = alpha > 0
    ys, xs = np.where(a)
    if len(xs) < 50:
        h, w = alpha.shape
        return w / 2.0, h / 2.0, min(w, h) * 0.38
    cy, cx = float(ys.mean()), float(xs.mean())
    angs = np.arctan2(ys - cy, xs - cx)
    not_right = ~((angs > -0.8) & (angs < 0.8) & (xs > cx))
    pts = not_right if not_right.sum() > 50 else np.ones(len(xs), dtype=bool)
    r = float(np.percentile(np.sqrt((ys[pts] - cy) ** 2 + (xs[pts] - cx) ** 2), 99))
    return cx, cy, r


def align_and_mask(
    im: Image.Image,
    mask: np.ndarray,
    size: int,
    target_cx: float,
    target_cy: float,
    target_r: float,
) -> Image.Image:
    arr = np.asarray(im.convert("RGBA"))
    cx, cy, r = estimate_circle(arr[:, :, 3])
    if r < 1:
        r = 1.0
    scale = target_r / r
    new_w = max(1, int(round(arr.shape[1] * scale)))
    new_h = max(1, int(round(arr.shape[0] * scale)))
    scaled = Image.fromarray(arr).resize((new_w, new_h), Image.Resampling.LANCZOS)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    paste_x = int(round(target_cx - cx * scale))
    paste_y = int(round(target_cy - cy * scale))
    out.paste(scaled, (paste_x, paste_y), scaled)

    out_arr = np.asarray(out).copy()
    m = mask.astype(np.float32) / 255.0
    out_arr[:, :, 3] = (out_arr[:, :, 3].astype(np.float32) * m).round().astype(np.uint8)
    out_arr[out_arr[:, :, 3] == 0, :3] = 0
    return Image.fromarray(out_arr, "RGBA")


def main() -> int:
    args = parse_args()
    size = args.size
    tcx = size / 2.0
    tcy = size / 2.0
    tr = args.radius

    print(f"Building mask from {args.svg.name} -> {size}x{size}, r={tr}")
    mask = build_mask(size, tcx, tcy, tr)
    MASK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask).save(MASK_CACHE)
    print(f"Mask cached: {MASK_CACHE}")

    files = sorted(args.icons.glob("*.webp"))
    if args.limit:
        files = files[: args.limit]
    print(f"Processing {len(files)} icons...")

    for i, path in enumerate(files, 1):
        im = Image.open(path)
        result = align_and_mask(im, mask, size, tcx, tcy, tr)
        if args.preview and i == 1:
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            result.save(args.preview)
            print(f"Preview: {args.preview}")
        if not args.dry_run:
            result.save(path, "WEBP", lossless=True, exact=True)
        if i % 25 == 0 or i == len(files):
            print(f"  {i}/{len(files)}")

    print("Done." + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
