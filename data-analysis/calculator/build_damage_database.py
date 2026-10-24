
#!/usr/bin/env python3

"""Build a SQLite database for the One Shot Calculator.

Reads:
    data-building/data/raw/pokemon_cards.json
    data-analysis/calculator/review/supported_tools.json

Writes:
    data-analysis/datasets/damage_calculator.sqlite3

Pokémon cards and their moves are stored, and supported Tool effects are
parsed into structured fields for the website calculator. Moves without a
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

DEFAULT_TOOLS_INPUT = (
    SCRIPT_DIR
    / "review"
    / "supported_tools.json"
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE pokemon (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    card_number TEXT,
    is_ex INTEGER NOT NULL DEFAULT 0,
    has_rule_box INTEGER NOT NULL DEFAULT 0,
    is_mega INTEGER NOT NULL DEFAULT 0,
    is_tera INTEGER NOT NULL DEFAULT 0,
    evolution_stage TEXT,
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

CREATE TABLE tools (
    id INTEGER PRIMARY KEY,
    card_name TEXT NOT NULL,
    set_code TEXT,
    card_number TEXT,
    source_url TEXT,
    effect_text TEXT,
    classification TEXT,
    supported INTEGER NOT NULL DEFAULT 0,
    effect_type TEXT,
    damage_modifier INTEGER,
    requires_attached_no_rule_box INTEGER,
    requires_opponent_ex INTEGER
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

CREATE INDEX idx_tools_effect_lookup
    ON tools(supported, effect_type, classification);
"""

RULE_BOX_VARIANTS = {
    "ex",
}


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


def has_rule_box(card):
    """Return whether the card has a Pokémon Rule Box variant."""
    variants = card.get("card_variants", [])

    if not isinstance(variants, list):
        return False

    return any(
        isinstance(variant, str)
        and variant.strip().casefold() in RULE_BOX_VARIANTS
        for variant in variants
    )


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


def load_tools(input_path):
    """Load and validate the supported Pokémon Tool entries."""
    try:
        with input_path.open("r", encoding="utf-8") as file:
            tools = json.load(file)
    except FileNotFoundError:
        raise ValueError(f"Tool file not found: {input_path}")
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {input_path}: {exc}"
        ) from exc

    if not isinstance(tools, list):
        raise ValueError("The tools JSON root must be a list.")

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise ValueError(f"Tool entry {index} must be an object.")

        card_name = tool.get("card_name")
        if not isinstance(card_name, str) or not card_name.strip():
            raise ValueError(
                f"Tool entry {index} must have a non-empty card_name."
            )

        if tool.get("classification") not in (
            None,
            "offensive",
            "defensive",
            "both",
        ):
            raise ValueError(
                f"Tool entry {index} has an invalid classification."
            )

    return tools


def parse_tool_effect(effect_text):
    """Parse the currently modeled, pre-Weakness Tool damage effects."""
    if not isinstance(effect_text, str):
        return None

    normalized = re.sub(r"\s+", " ", effect_text.strip())
    normalized = normalized.replace(" .", ".")

    brave_bangle_pattern = re.compile(
        r"^If the Pokémon this card is attached to doesn't have a Rule Box, "
        r"the attacks it uses do (?P<amount>\d+) more damage to your "
        r"opponent's Active Pokémon(?P<opponent_ex> ex)? "
        r"\(before applying Weakness and Resistance\)",
        re.IGNORECASE,
    )
    general_pattern = re.compile(
        r"^Attacks used by the Pokémon this card is attached to do "
        r"(?P<amount>\d+) more damage to your opponent's Active Pokémon"
        r"(?P<opponent_ex> ex)? "
        r"\(before applying Weakness and Resistance\)",
        re.IGNORECASE,
    )

    match = brave_bangle_pattern.match(normalized)
    requires_attached_no_rule_box = 1 if match is not None else None
    if match is None:
        match = general_pattern.match(normalized)

    if match is None:
        return None

    return {
        "effect_type": "damage_modifier",
        "damage_modifier": int(match.group("amount")),
        "requires_attached_no_rule_box": requires_attached_no_rule_box,
        "requires_opponent_ex": (
            1 if match.group("opponent_ex") is not None else None
        ),
    }


def build_database(
    input_path,
    output_path,
    tools_path=DEFAULT_TOOLS_INPUT,
):
    """Create the SQLite database from the card JSON."""
    cards = load_cards(input_path)
    tools = load_tools(tools_path)

    pokemon_count = 0
    move_count = 0
    tool_count = 0
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
                        has_rule_box,
                        is_mega,
                        is_tera,
                        evolution_stage,
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        card.get("card_type"),
                        int(is_ex_pokemon(card)),
                        int(has_rule_box(card)),
                        int(is_mega_pokemon(card)),
                        int(is_tera_pokemon(card)),
                        card.get("evolution_stage"),
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

            tool_rows = []
            for tool in tools:
                parsed = parse_tool_effect(tool.get("effect_text")) or {}
                tool_rows.append(
                    (
                        tool["card_name"].strip(),
                        tool.get("set"),
                        (
                            str(tool["card_number"])
                            if tool.get("card_number") is not None
                            else None
                        ),
                        tool.get("source_url"),
                        tool.get("effect_text"),
                        tool.get("classification"),
                        int(tool.get("supported") is True),
                        parsed.get("effect_type"),
                        parsed.get("damage_modifier"),
                        parsed.get("requires_attached_no_rule_box"),
                        parsed.get("requires_opponent_ex"),
                    )
                )

            connection.executemany(
                """
                INSERT INTO tools (
                    card_name,
                    set_code,
                    card_number,
                    source_url,
                    effect_text,
                    classification,
                    supported,
                    effect_type,
                    damage_modifier,
                    requires_attached_no_rule_box,
                    requires_opponent_ex
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tool_rows,
            )
            tool_count = len(tools)

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
                    ("schema_version", "5"),
                    ("source_file", input_path.name),
                    ("pokemon_count", str(pokemon_count)),
                    ("move_count", str(move_count)),
                    ("tool_count", str(tool_count)),
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
    print(f"Tools stored:   {tool_count}")


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

    parser.add_argument(
        "--tools",
        type=Path,
        default=DEFAULT_TOOLS_INPUT,
        help="Path to supported_tools.json",
    )

    args = parser.parse_args()

    try:
        build_database(
            args.input.resolve(),
            args.output.resolve(),
            args.tools.resolve(),
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
