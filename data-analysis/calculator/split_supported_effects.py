#!/usr/bin/env python3

"""Write all supported effects to category-specific JSON files."""

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REVIEW_DIR = SCRIPT_DIR / "review"
DEFAULT_INPUT = REVIEW_DIR / "supported_effects.json"
DEFAULT_OUTPUT_DIR = REVIEW_DIR

CATEGORIES = {
    "supported_moves": ("Move", None),
    "supported_abilities": ("Ability", None),
    "supported_items": ("Trainer", "Item"),
    "supported_supporters": ("Trainer", "Supporter"),
    "supported_tools": ("Trainer", "Tool"),
    "supported_stadiums": ("Trainer", "Stadium"),
}


def load_effects(input_path):
    """Load and validate the supported-effects JSON list."""
    try:
        with input_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise ValueError(f"Input file not found: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {input_path}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("The input JSON root must be a list.")

    return data


def select_effects(effects):
    """Group all effects matching each requested category."""
    selected = {name: [] for name in CATEGORIES}

    for filename, (card_type, trainer_subtype) in CATEGORIES.items():
        for effect in effects:
            if not isinstance(effect, dict):
                continue

            effect_card_type = effect.get("card_type")
            if (
                not isinstance(effect_card_type, str)
                or effect_card_type.casefold() != card_type.casefold()
            ):
                continue

            if trainer_subtype is not None:
                subtype = effect.get("trainer_subtype")
                if (
                    not isinstance(subtype, str)
                    or subtype.casefold() != trainer_subtype.casefold()
                ):
                    continue

            effect.setdefault("implemented", False)
            selected[filename].append(effect)

    missing = [name for name, matches in selected.items() if not matches]
    if missing:
        raise ValueError(
            "No matching effect found for: " + ", ".join(missing)
        )

    return selected


def write_effects(selected, output_dir):
    """Write each category's effects to a JSON list."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, effects in selected.items():
        output_path = output_dir / f"{name}.json"
        with output_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(effects, file, indent=2, ensure_ascii=False)
            file.write("\n")

        print(f"Wrote {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Write all supported effects for each Pokémon card category."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to supported_effects.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the six generated supported_*.json files",
    )
    args = parser.parse_args()

    try:
        selected = select_effects(load_effects(args.input))
        write_effects(selected, args.output_dir)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
