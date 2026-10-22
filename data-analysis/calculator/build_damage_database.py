
#!/usr/bin/env python3

"""Build a SQLite database for the One Shot Calculator.

Reads:
    data-building/data/raw/pokemon_cards.json

Writes:
    data-analysis/calculator/damage_calculator.sqlite3

Only Pokémon cards and their moves are stored. Moves without a
recognizable numeric damage value are skipped.

The numeric damage field stores the printed numeric base. For example,
"30+" stores 30 and marks the move as variable damage. This allows the
prototype to include potentially relevant moves without pretending that
their final damage is fixed.
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]

DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data-building"
    / "data"
    / "raw"
    / "pokemon_cards.json"
)

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data-analysis"
    / "datasets"
    / "damage_calculator.sqlite3"
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE pokemon (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    card_number TEXT,
    is_ex INTEGER NOT NULL DEFAULT 0,
    is_mega INTEGER NOT NULL DEFAULT 0,
    is_tera INTEGER NOT NULL DEFAULT 0,
    set_code TEXT,
    card_mark TEXT,
    hp INTEGER,
    pokemon_type TEXT,
    weakness TEXT,
    resistance TEXT,
    retreat_cost INTEGER,
    source_url TEXT
);

CREATE TABLE moves (
    id INTEGER PRIMARY KEY,
    pokemon_id INTEGER NOT NULL,
    move_index INTEGER NOT NULL,
    name TEXT NOT NULL,
    cost TEXT,
    damage INTEGER NOT NULL,
    damage_text TEXT NOT NULL,
    damage_modifier TEXT,
    damage_kind TEXT NOT NULL,
    effect_text TEXT,
    FOREIGN KEY (pokemon_id)
        REFERENCES pokemon(id)
        ON DELETE CASCADE,
    UNIQUE (pokemon_id, move_index)
);

CREATE INDEX idx_pokemon_name
    ON pokemon(name);

CREATE INDEX idx_pokemon_hp
    ON pokemon(hp);

CREATE INDEX idx_pokemon_type
    ON pokemon(pokemon_type);

CREATE INDEX idx_pokemon_weakness
    ON pokemon(weakness);

CREATE INDEX idx_pokemon_resistance
    ON pokemon(resistance);

CREATE INDEX idx_moves_pokemon_id
    ON moves(pokemon_id);

CREATE INDEX idx_moves_damage
    ON moves(damage);
"""


def normalize_type(value):
    """Normalize a Pokémon type or return None if unavailable."""
    if isinstance(value, dict):
        value = value.get("type") or value.get("name")

    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def parse_integer(value):
    """Return an integer for an integer-like value, otherwise None."""
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, float):
        if value.is_integer() and value >= 0:
            return int(value)
        return None

    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"\d+", value):
            return int(value)

    return None


def parse_damage(value):
    """Parse a printed damage value.

    Returns:
        (base_damage, original_text, damage_kind)

    Examples:
        30     -> (30, "30", "fixed")
        "30"   -> (30, "30", "fixed")
        "30+"  -> (30, "30+", "plus")
        "20x"  -> (20, "20x", "multiplier")
        "20×"  -> (20, "20×", "multiplier")

    Returns None if no numeric base damage can be identified.
    """
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        damage = parse_integer(value)
        if damage is None:
            return None
        return damage, str(value), "fixed"

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # Only recognize a numeric value at the start of the string.
    # Keep the original notation so the UI can distinguish fixed
    # damage from damage that depends on additional conditions.
    match = re.match(r"^(\d+)\s*(.*)$", text)
    if not match:
        return None

    damage = int(match.group(1))
    suffix = match.group(2).strip()

    if not suffix:
        kind = "fixed"
    elif suffix.startswith("+"):
        kind = "plus"
    elif suffix.lower().startswith("x") or suffix.startswith("×"):
        kind = "multiplier"
    else:
        kind = "other"

    return damage, text, kind


def is_pokemon_card(card):
    """Recognize Pokémon cards using the input schema."""
    card_type = card.get("card_type")
    if not isinstance(card_type, str):
        return False

    return card_type.strip().lower() in {
        "pokemon",
        "pokémon",
    }


def has_card_variant(card, variant_name):
    """Return whether card_variants contains the specified variant."""
    variants = card.get("card_variants", [])

    if not isinstance(variants, list):
        return False

    return any(
        isinstance(variant, str)
        and variant.strip().casefold() == variant_name.casefold()
        for variant in variants
    )


def is_ex_pokemon(card):
    """Return whether the card is classified as Pokémon ex."""
    return has_card_variant(card, "ex")


def is_mega_pokemon(card):
    """Return whether the card is a Mega Pokémon ex."""
    return (
        is_ex_pokemon(card)
        and has_card_variant(card, "Mega")
    )


def is_tera_pokemon(card):
    """Return whether the card is a Tera Pokémon ex."""
    return (
        is_ex_pokemon(card)
        and has_card_variant(card, "Tera")
    )

def load_cards(input_path):
    """Load and validate the JSON input."""
    try:
        with input_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise ValueError(f"Input file not found: {input_path}")
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {input_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("The JSON root must be an object.")

    cards = data.get("cards")
    if not isinstance(cards, list):
        raise ValueError(
            'Expected the JSON root to contain a "cards" list.'
        )

    return cards


def build_database(input_path, output_path):
    """Create the SQLite database from the card JSON."""
    cards = load_cards(input_path)

    pokemon_count = 0
    move_count = 0
    skipped_moves = 0
    skipped_cards = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build a fresh database rather than leaving stale rows from
    # previous runs. A failed build will not leave partial inserts.
    if output_path.exists():
        output_path.unlink()

    connection = sqlite3.connect(output_path)

    try:
        with connection:
            connection.executescript(SCHEMA)

            for card in cards:
                if not isinstance(card, dict):
                    skipped_cards += 1
                    continue

                if not is_pokemon_card(card):
                    continue

                name = card.get("name")
                if not isinstance(name, str) or not name.strip():
                    skipped_cards += 1
                    continue

                name = name.strip()

                hp = parse_integer(card.get("hp"))
                retreat_cost = parse_integer(
                    card.get("retreat_cost")
                )

                pokemon_type = normalize_type(card.get("type"))
                weakness = normalize_type(card.get("weakness"))
                resistance = normalize_type(
                    card.get("resistance")
                )

                cursor = connection.execute(
                    """
                    INSERT INTO pokemon (
                        name,
                        card_type,
                        is_ex,
                        is_mega,
                        is_tera,
                        card_number,
                        set_code,
                        card_mark,
                        hp,
                        pokemon_type,
                        weakness,
                        resistance,
                        retreat_cost,
                        source_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        card.get("card_type"),
                        int(is_ex_pokemon(card)),
                        int(is_mega_pokemon(card)),
                        int(is_tera_pokemon(card)),
                        (
                            str(card["card_number"])
                            if card.get("card_number") is not None
                            else None
                        ),
                        card.get("set"),
                        card.get("card_mark"),
                        hp,
                        pokemon_type,
                        weakness,
                        resistance,
                        retreat_cost,
                        card.get("source_url"),
                    ),
                )

                pokemon_id = cursor.lastrowid
                pokemon_count += 1

                moves = card.get("moves", [])
                if not isinstance(moves, list):
                    continue

                for move_index, move in enumerate(moves):
                    if not isinstance(move, dict):
                        skipped_moves += 1
                        continue

                    parsed = parse_damage(move.get("damage"))
                    if parsed is None:
                        skipped_moves += 1
                        continue

                    damage, damage_text, damage_kind = parsed

                    move_name = move.get("name")
                    if not isinstance(move_name, str):
                        move_name = "Unnamed move"

                    connection.execute(
                        """
                        INSERT INTO moves (
                            pokemon_id,
                            move_index,
                            name,
                            cost,
                            damage,
                            damage_text,
                            damage_modifier,
                            damage_kind,
                            effect_text
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pokemon_id,
                            move_index,
                            move_name,
                            move.get("cost"),
                            damage,
                            damage_text,
                            move.get("damage_modifier"),
                            damage_kind,
                            move.get("effect_text"),
                        ),
                    )

                    move_count += 1

            # Store a schema version so future migrations can be
            # handled deliberately as the calculator grows.
            connection.execute(
                """
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                [
                    ("schema_version", "2"),
                    ("source_file", input_path.name),
                    ("pokemon_count", str(pokemon_count)),
                    ("move_count", str(move_count)),
                ],
            )

    except Exception:
        connection.close()
        if output_path.exists():
            output_path.unlink()
        raise
    else:
        connection.close()

    print("SQLite database created successfully.")
    print(f"Input:          {input_path}")
    print(f"Output:         {output_path}")
    print(f"Pokémon cards:  {pokemon_count}")
    print(f"Moves stored:   {move_count}")
    print(f"Moves skipped:  {skipped_moves}")
    print(f"Cards skipped:  {skipped_cards}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build the One Shot Calculator SQLite database."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to pokemon_cards.json",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for the generated SQLite database",
    )

    args = parser.parse_args()

    try:
        build_database(
            args.input.resolve(),
            args.output.resolve(),
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
