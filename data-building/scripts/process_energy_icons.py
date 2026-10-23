#!/usr/bin/env python3
"""Extract configured Pokémon TCG Energy symbols from card images."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPOSITORY_ROOT / "data-building" / "data" / "raw"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "website" / "images" / "energy"
DEFAULT_CONFIG = Path(__file__).with_name("energy_icons.json")
CONTACT_SHEET_NAME = "energy-contact-sheet.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract configured circular Energy symbols from PNG card images. "
            "Review the generated contact sheet before using the new assets."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--only",
        help="Process one source filename (for example fire.png), not every PNG.",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Override the configured square output canvas size.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        help="Override the configured padding around the visible circular icon.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing -128px output after it has been reviewed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible files without writing icons or a contact sheet.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read configuration {path}: {error}") from error

    if not isinstance(config, dict) or not isinstance(config.get("icons"), dict):
        raise ValueError("Configuration must contain an 'icons' object.")
    return config


def validate_geometry(
    source_size: tuple[int, int], settings: dict[str, Any]
) -> tuple[tuple[int, int, int, int], float, float, float]:
    try:
        crop_box = tuple(int(value) for value in settings["crop_box"])
        center_x, center_y = (float(value) for value in settings["center"])
        mask_radius = float(settings["mask_radius"])
        mask_inset = float(settings.get("mask_inset", 0))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "settings need crop_box [left, top, right, bottom], "
            "center [x, y], and mask_radius"
        ) from error

    if len(crop_box) != 4:
        raise ValueError("crop_box must contain four integer coordinates")
    left, top, right, bottom = crop_box
    width, height = source_size
    if left < 0 or top < 0 or right > width or bottom > height:
        raise ValueError(f"crop_box {crop_box} is outside source size {source_size}")
    if right <= left or bottom <= top:
        raise ValueError("crop_box must have positive width and height")
    if not all(math.isfinite(value) for value in (center_x, center_y, mask_radius, mask_inset)):
        raise ValueError("center, mask_radius, and mask_inset must be finite numbers")
    if mask_radius <= 0 or mask_inset < 0 or mask_inset >= mask_radius:
        raise ValueError("mask_radius must be positive and mask_inset smaller than it")

    visible_radius = mask_radius - mask_inset
    if (
        center_x - mask_radius < left
        or center_y - mask_radius < top
        or center_x + mask_radius > right
        or center_y + mask_radius > bottom
    ):
        raise ValueError("crop_box must contain the complete configured mask circle")

    return crop_box, center_x, center_y, visible_radius


def render_icon(
    source: Image.Image,
    settings: dict[str, Any],
    output_size: int,
    padding: int,
) -> tuple[Image.Image, float]:
    crop_box, center_x, center_y, visible_radius = validate_geometry(
        source.size, settings
    )
    left, top, right, bottom = crop_box
    crop = source.crop(crop_box).convert("RGBA")

    scale = 4
    mask = Image.new("L", (crop.width * scale, crop.height * scale), 0)
    center_in_crop = ((center_x - left) * scale, (center_y - top) * scale)
    radius = visible_radius * scale
    ImageDraw.Draw(mask).ellipse(
        (
            center_in_crop[0] - radius,
            center_in_crop[1] - radius,
            center_in_crop[0] + radius,
            center_in_crop[1] + radius,
        ),
        fill=255,
    )
    mask = mask.resize(crop.size, Image.Resampling.LANCZOS)
    crop.putalpha(ImageChops.multiply(crop.getchannel("A"), mask))

    target_diameter = output_size - 2 * padding
    transform_scale = (2 * visible_radius) / target_diameter
    tile = crop.transform(
        (target_diameter, target_diameter),
        Image.Transform.AFFINE,
        (
            transform_scale,
            0,
            center_x - visible_radius - left,
            0,
            transform_scale,
            center_y - visible_radius - top,
        ),
        resample=Image.Resampling.BICUBIC,
    )

    output = Image.new("RGBA", (output_size, output_size), (0, 0, 0, 0))
    output.alpha_composite(tile, (padding, padding))
    return output, 2 * visible_radius


def make_contact_sheet(
    output_dir: Path, sources: dict[str, float], output_size: int
) -> Path | None:
    assets: list[tuple[str, Image.Image, float]] = []
    for path in sorted(
        output_dir.glob(f"*-{output_size}px.png"), key=lambda item: item.name.lower()
    ):
        try:
            with Image.open(path) as image:
                icon = image.convert("RGBA")
                if icon.size != (output_size, output_size):
                    print(
                        f"SKIPPED preview {path.name}: expected "
                        f"{output_size}x{output_size}, got {icon.size}"
                    )
                    continue
                assets.append((path.name, icon.copy(), sources.get(path.name, 0)))
        except OSError as error:
            print(f"SKIPPED preview {path.name}: {error}")

    if not assets:
        print(
            f"Contact sheet not created: no valid "
            f"-{output_size}px.png assets found."
        )
        return None

    cell_width = 320
    cell_height = 156
    sheet = Image.new(
        "RGB",
        (cell_width * 2, cell_height * len(assets) + 38),
        (235, 237, 240),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((cell_width // 2 - 25, 12), "Light background", fill="#111111", font=font)
    draw.text((cell_width + cell_width // 2 - 25, 12), "Dark background", fill="#111111", font=font)

    preview_size = 112
    for index, (name, icon, source_diameter) in enumerate(assets):
        y = 38 + index * cell_height
        label = name
        if source_diameter:
            label += f"  (source circle: {source_diameter:g}px)"

        for column, background, label_color in (
            (0, (248, 248, 248, 255), "#111111"),
            (1, (38, 42, 48, 255), "#ffffff"),
        ):
            x = column * cell_width
            panel = Image.new("RGBA", (cell_width, cell_height), background)
            preview = icon.resize(
                (preview_size, preview_size), Image.Resampling.LANCZOS
            )
            panel.alpha_composite(preview, (12, 32))
            ImageDraw.Draw(panel).text((12, 8), label, fill=label_color, font=font)
            sheet.paste(panel.convert("RGB"), (x, y))

    output_path = output_dir / CONTACT_SHEET_NAME
    sheet.save(output_path, format="PNG")
    return output_path


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    output_size = args.size if args.size is not None else config.get("output_size", 128)
    padding = args.padding if args.padding is not None else config.get("padding", 6)
    if not isinstance(output_size, int) or output_size < 2:
        print("ERROR: output size must be an integer of at least 2.", file=sys.stderr)
        return 2
    if not isinstance(padding, int) or padding < 0 or padding * 2 >= output_size:
        print("ERROR: padding must be nonnegative and less than half the output size.", file=sys.stderr)
        return 2
    icons: dict[str, Any] = config["icons"]
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not input_dir.is_dir():
        print(f"ERROR: input directory does not exist: {input_dir}", file=sys.stderr)
        return 2

    png_files = sorted(
        (path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png"),
        key=lambda path: path.name.lower(),
    )
    if args.only:
        png_files = [path for path in png_files if path.name.lower() == args.only.lower()]
        if not png_files:
            print(f"SKIPPED: no input PNG matches --only {args.only!r}")

    outcomes = {"processed": 0, "skipped": 0, "manual": 0}
    source_diameters: dict[str, float] = {}
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for path in png_files:
        settings = icons.get(path.name)
        if not isinstance(settings, dict):
            print(f"MANUAL: {path.name}: no crop configuration; add it to {args.config}")
            outcomes["manual"] += 1
            continue

        output_name = settings.get("output")
        if not isinstance(output_name, str) or not output_name.lower().endswith(".png"):
            print(f"SKIPPED: {path.name}: configuration needs a PNG 'output' filename")
            outcomes["skipped"] += 1
            continue
        if output_size != 128:
            output_stem = Path(output_name).stem
            if re.search(r"-\d+px$", output_stem):
                output_stem = re.sub(r"-\d+px$", f"-{output_size}px", output_stem)
            else:
                output_stem += f"-{output_size}px"
            output_name = output_stem + Path(output_name).suffix
        output_path = output_dir / output_name

        try:
            with Image.open(path) as opened:
                opened.load()
                source = opened.convert("RGBA")
            _, _, _, visible_radius = validate_geometry(source.size, settings)
        except (OSError, ValueError) as error:
            print(f"SKIPPED: {path.name}: {error}")
            outcomes["skipped"] += 1
            continue

        source_diameter = 2 * visible_radius
        source_diameters[output_path.name] = source_diameter
        if output_path.exists() and not args.overwrite:
            print(f"SKIPPED: {path.name}: {output_path.name} exists; use --overwrite after review")
            outcomes["skipped"] += 1
            continue
        if args.dry_run:
            print(f"READY: {path.name} -> {output_path.name}")
            outcomes["processed"] += 1
            continue

        try:
            rendered, source_diameter = render_icon(source, settings, output_size, padding)
            rendered.save(output_path, format="PNG", optimize=False)
        except (OSError, ValueError) as error:
            print(f"SKIPPED: {path.name}: {error}")
            outcomes["skipped"] += 1
            continue

        source_diameters[output_path.name] = source_diameter
        quality_note = (
            f"LOW RES ({source_diameter:g}px source circle enlarged)"
            if source_diameter < 32
            else f"{source_diameter:g}px source circle"
        )
        print(f"PROCESSED: {path.name} -> {output_path.name} [{quality_note}]")
        outcomes["processed"] += 1

    if not args.dry_run:
        sheet_path = make_contact_sheet(output_dir, source_diameters, output_size)
        if sheet_path:
            print(f"PREVIEW: {sheet_path}")

    print(
        "Summary: "
        f"{outcomes['processed']} "
        f"{'ready' if args.dry_run else 'processed'}, "
        f"{outcomes['skipped']} skipped, "
        f"{outcomes['manual']} need crop configuration."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
