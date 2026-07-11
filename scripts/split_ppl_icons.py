#!/usr/bin/env python3
"""
Pure clipper for PPL sprite sheets.

- Requires RGBA sheets (transparent background already present)
- Only crops; does not recolor, threshold, or rebuild alpha
- Outputs fixed-size square WebP (lossless) with circle consistently centered
- Names from labels.csv when available: {country}_{gender}_{tag}.webp

Usage:
  python scripts/split_ppl_icons.py
  python scripts/split_ppl_icons.py --sheet assests/PPL_ASIA1.png
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assests"
DEFAULT_OUT = ASSETS / "icons"
DEFAULT_LABELS = DEFAULT_OUT / "labels.csv"
ROWS, COLS = 5, 5


@dataclass
class CellBox:
    row: int
    col: int
    x0: int
    y0: int
    x1: int
    y1: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", action="append", default=[], help="Sheet path(s). Default: all assests/PPL*.png")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    p.add_argument("--size", type=int, default=0, help="Output square size. 0 = auto from sheet")
    p.add_argument("--format", choices=["webp", "png"], default="webp")
    p.add_argument("--clear-out", action="store_true", help="Delete existing *.webp/*.png in out before writing")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def list_sheets(explicit: list[str]) -> list[Path]:
    if explicit:
        return [Path(s) for s in explicit]
    return sorted(ASSETS.glob("PPL*.png"))


def slug(s: str) -> str:
    s = s.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_\-]+", "", s)
    return re.sub(r"_+", "_", s).strip("_") or "unknown"


def load_labels(path: Path) -> dict[tuple[str, int, int], tuple[str, str, str]]:
    if not path.exists():
        return {}
    labels: dict[tuple[str, int, int], tuple[str, str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            country = (row.get("country") or "").strip().lower()
            gender = (row.get("gender") or "").strip().lower()
            tag = (row.get("tag") or "").strip().lower()
            if not (country and gender and tag):
                continue
            key = (Path(row["source"]).name, int(row["row"]), int(row["col"]))
            labels[key] = (country, gender, tag)
    return labels


def require_rgba(im: Image.Image, path: Path) -> Image.Image:
    if im.mode != "RGBA":
        raise SystemExit(
            f"STOP: {path.name} is {im.mode}, not RGBA transparent.\n"
            "Export the sheet with transparency first, then re-run."
        )
    return im


def alpha_gaps(density: np.ndarray, thr: float = 0.005) -> list[tuple[int, int]]:
    gaps: list[tuple[int, int]] = []
    in_gap = False
    start = 0
    for i, d in enumerate(density):
        if d < thr:
            if not in_gap:
                in_gap = True
                start = i
        elif in_gap:
            gaps.append((start, i - 1))
            in_gap = False
    if in_gap:
        gaps.append((start, len(density) - 1))
    return gaps


def segments(gaps: list[tuple[int, int]], length: int) -> list[tuple[int, int]]:
    bounds: list[tuple[int, int]] = []
    prev = 0
    for a, b in gaps:
        if a > prev:
            bounds.append((prev, a - 1))
        prev = b + 1
    if prev < length:
        bounds.append((prev, length - 1))
    return bounds


def detect_cells(alpha: np.ndarray) -> list[CellBox]:
    """Split sheet into 5x5 cells using transparent gutters, else equal content split."""
    content = alpha > 0
    rseg = segments(alpha_gaps(content.mean(axis=1)), alpha.shape[0])
    cseg = segments(alpha_gaps(content.mean(axis=0)), alpha.shape[1])

    if len(rseg) == ROWS and len(cseg) == COLS:
        return [CellBox(r, c, x0, y0, x1, y1) for r, (y0, y1) in enumerate(rseg) for c, (x0, x1) in enumerate(cseg)]

    # fallback: equal split of content bbox
    ys, xs = np.where(content)
    if len(xs) == 0:
        raise SystemExit("No opaque pixels found in sheet")
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    cells: list[CellBox] = []
    for r in range(ROWS):
        for c in range(COLS):
            x0 = x_min + (x_max - x_min + 1) * c // COLS
            x1 = x_min + (x_max - x_min + 1) * (c + 1) // COLS - 1
            y0 = y_min + (y_max - y_min + 1) * r // ROWS
            y1 = y_min + (y_max - y_min + 1) * (r + 1) // ROWS - 1
            cells.append(CellBox(r, c, x0, y0, x1, y1))
    return cells


def content_center(alpha_cell: np.ndarray) -> tuple[float, float]:
    ys, xs = np.where(alpha_cell > 0)
    if len(xs) == 0:
        h, w = alpha_cell.shape
        return w / 2.0, h / 2.0
    return float(xs.mean()), float(ys.mean())


def auto_size(arr: np.ndarray, cells: list[CellBox]) -> int:
    """Smallest square that fits every icon's opaque pixels, centered."""
    need = 0
    for box in cells:
        cell = arr[box.y0 : box.y1 + 1, box.x0 : box.x1 + 1]
        a = cell[:, :, 3]
        ys, xs = np.where(a > 0)
        if len(xs) == 0:
            continue
        cx, cy = content_center(a)
        # radius to farthest opaque pixel from center
        dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        need = max(need, int(np.ceil(dist.max() * 2)) + 2)
    # prefer even size, clamp to sensible range
    need = max(need, 512)
    if need % 2:
        need += 1
    return need


def crop_square(arr: np.ndarray, box: CellBox, size: int) -> Image.Image:
    """Crop a fixed square from the sheet around the cell content center. No pixel edits."""
    cell = arr[box.y0 : box.y1 + 1, box.x0 : box.x1 + 1]
    cx_local, cy_local = content_center(cell[:, :, 3])
    cx = box.x0 + cx_local
    cy = box.y0 + cy_local
    half = size / 2.0
    x0 = int(round(cx - half))
    y0 = int(round(cy - half))
    x1 = x0 + size
    y1 = y0 + size

    h, w = arr.shape[:2]
    # paste into transparent canvas if crop hits sheet edge
    out = np.zeros((size, size, 4), dtype=np.uint8)
    src_x0, src_y0 = max(0, x0), max(0, y0)
    src_x1, src_y1 = min(w, x1), min(h, y1)
    dst_x0, dst_y0 = src_x0 - x0, src_y0 - y0
    dst_x1 = dst_x0 + (src_x1 - src_x0)
    dst_y1 = dst_y0 + (src_y1 - src_y0)
    out[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]
    return Image.fromarray(out, "RGBA")


def unique_path(out_dir: Path, stem: str, ext: str) -> Path:
    path = out_dir / f"{stem}.{ext}"
    if not path.exists():
        return path
    i = 2
    while True:
        path = out_dir / f"{stem}_{i}.{ext}"
        if not path.exists():
            return path
        i += 1


def save_image(im: Image.Image, path: Path, fmt: str) -> None:
    if fmt == "webp":
        # lossless to avoid quality damage
        im.save(path, "WEBP", lossless=True, exact=True)
    else:
        im.save(path, "PNG", optimize=True)


def clear_outputs(out_dir: Path) -> None:
    for pat in ("*.webp", "*.png"):
        for p in out_dir.glob(pat):
            if p.name.startswith("_"):
                continue
            p.unlink()
    manifest = out_dir / "manifest.csv"
    if manifest.exists():
        manifest.unlink()


def process_sheet(
    sheet: Path,
    out_dir: Path,
    labels: dict[tuple[str, int, int], tuple[str, str, str]],
    size: int,
    fmt: str,
    dry_run: bool,
    rows_out: list[dict],
) -> int:
    im = require_rgba(Image.open(sheet), sheet)
    arr = np.asarray(im)
    cells = detect_cells(arr[:, :, 3])
    sheet_size = size or auto_size(arr, cells)
    print(f"{sheet.name}: {len(cells)} cells, crop {sheet_size}x{sheet_size}")

    count = 0
    for box in cells:
        key = (sheet.name, box.row, box.col)
        if key in labels:
            country, gender, tag = labels[key]
            stem = f"{slug(country)}_{slug(gender)}_{slug(tag)}"
        else:
            stem = f"{sheet.stem.lower()}_r{box.row}c{box.col}"

        dest = unique_path(out_dir, stem, fmt)
        if not dry_run:
            icon = crop_square(arr, box, sheet_size)
            save_image(icon, dest, fmt)

        rows_out.append(
            {
                "source": sheet.name,
                "row": box.row,
                "col": box.col,
                "filename": dest.name,
                "size": sheet_size,
                "labeled": key in labels,
            }
        )
        print(f"  [{box.row},{box.col}] -> {dest.name}")
        count += 1
    return count


def main() -> int:
    args = parse_args()
    sheets = list_sheets(args.sheet)
    if not sheets:
        print("No sheets found", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    if args.clear_out and not args.dry_run:
        clear_outputs(args.out)
        print(f"Cleared previous icons in {args.out}")

    labels = load_labels(args.labels)
    print(f"Labels loaded: {len(labels)}")

    # If size not set, compute one global size from first sheet so all icons match
    global_size = args.size
    if global_size <= 0:
        first = require_rgba(Image.open(sheets[0]), sheets[0])
        arr = np.asarray(first)
        cells = detect_cells(arr[:, :, 3])
        global_size = auto_size(arr, cells)
        # verify other sheets don't need larger
        for sheet in sheets[1:]:
            im = require_rgba(Image.open(sheet), sheet)
            a = np.asarray(im)
            c = detect_cells(a[:, :, 3])
            global_size = max(global_size, auto_size(a, c))
        print(f"Auto square size: {global_size}")

    rows: list[dict] = []
    total = 0
    for sheet in sheets:
        total += process_sheet(
            sheet=sheet,
            out_dir=args.out,
            labels=labels,
            size=global_size,
            fmt=args.format,
            dry_run=args.dry_run,
            rows_out=rows,
        )

    if not args.dry_run:
        with (args.out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["source", "row", "col", "filename", "size", "labeled"])
            w.writeheader()
            w.writerows(rows)

    labeled = sum(1 for r in rows if r["labeled"])
    print(f"\nDone: {total} icons ({labeled} labeled, {total - labeled} placeholder names) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
