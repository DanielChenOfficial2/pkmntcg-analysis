"""Build the queryable SQLite card database from scraper-produced JSON."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPOSITORY_ROOT / "data" / "raw" / "pokemon_cards.json"
DEFAULT_DATABASE = REPOSITORY_ROOT / "data" / "pokemon.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _read_cards(json_path):
    with json_path.open("r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, dict) or not isinstance(payload.get("cards"), list):
        raise ValueError("Input JSON must be an object with a 'cards' array")
    for index, card in enumerate(payload["cards"]):
        if not isinstance(card, dict):
            raise ValueError(f"cards[{index}] must be a JSON object")
        for collection in ("abilities", "moves", "card_variants"):
            if not isinstance(card.get(collection, []), list):
                raise ValueError(f"cards[{index}].{collection} must be an array")
    return payload["cards"]


def _optional_integer(value, field_name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer or null")
    return value


def _insert_or_update_card(connection, card):
    set_id = None
    set_name = card.get("set")
    if set_name:
        connection.execute(
            "INSERT INTO sets(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
            (set_name,),
        )
        set_id = connection.execute(
            "SELECT id FROM sets WHERE name = ?", (set_name,)
        ).fetchone()[0]

    card_type = card.get("card_type") or "pokemon"
    card_values = (
        set_id,
        card.get("name"),
        card.get("name_with_set"),
        card_type,
        card.get("card_number"),
        card.get("card_mark"),
        card.get("rarity"),
        card.get("expansion"),
        card.get("source_url"),
    )
    if card.get("name_with_set") is None:
        cursor = connection.execute(
            """
            INSERT INTO cards (
                set_id, name, name_with_set, card_type, card_number, card_mark,
                rarity, expansion, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            card_values,
        )
        card_id = cursor.lastrowid
    else:
        connection.execute(
            """
            INSERT INTO cards (
                set_id, name, name_with_set, card_type, card_number, card_mark,
                rarity, expansion, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name_with_set) DO UPDATE SET
                set_id = excluded.set_id,
                name = excluded.name,
                card_type = excluded.card_type,
                card_number = excluded.card_number,
                card_mark = excluded.card_mark,
                rarity = excluded.rarity,
                expansion = excluded.expansion,
                source_url = excluded.source_url
            """,
            card_values,
        )
        card_id = connection.execute(
            "SELECT id FROM cards WHERE name_with_set = ?",
            (card["name_with_set"],),
        ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO pokemon (
            card_id, evolution_stage, previous_evolution, hp, hp_text, type,
            weakness, resistance, retreat_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id) DO UPDATE SET
            evolution_stage = excluded.evolution_stage,
            previous_evolution = excluded.previous_evolution,
            hp = excluded.hp,
            hp_text = excluded.hp_text,
            type = excluded.type,
            weakness = excluded.weakness,
            resistance = excluded.resistance,
            retreat_cost = excluded.retreat_cost
        """,
        (
            card_id,
            card.get("evolution_stage"),
            card.get("previous_evolution"),
            _optional_integer(card.get("hp"), "hp"),
            card.get("hp_text"),
            card.get("type"),
            card.get("weakness"),
            card.get("resistance"),
            _optional_integer(card.get("retreat_cost"), "retreat_cost"),
        ),
    )

    for table in ("card_variants", "attacks", "abilities"):
        connection.execute(f"DELETE FROM {table} WHERE card_id = ?", (card_id,))
    for variant in card.get("card_variants", []):
        if not isinstance(variant, str):
            raise ValueError("card_variants entries must be strings")
        connection.execute(
            "INSERT INTO card_variants(card_id, variant) VALUES (?, ?)",
            (card_id, variant),
        )

    for move in card.get("moves", []):
        if not isinstance(move, dict):
            raise ValueError("moves entries must be objects")
        cost = move.get("cost", {})
        if not isinstance(cost, dict):
            raise ValueError("move cost must be an object mapping energy types to counts")
        damage = _optional_integer(move.get("damage"), "move damage")
        cursor = connection.execute(
            """
            INSERT INTO attacks (
                card_id, name, damage, damage_modifier, damage_text, effect_text
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                move.get("name"),
                damage,
                move.get("damage_modifier"),
                move.get("damage_text"),
                move.get("effect_text"),
            ),
        )
        attack_id = cursor.lastrowid
        for energy_type, amount in cost.items():
            if not isinstance(energy_type, str):
                raise ValueError("energy type keys must be strings")
            amount = _optional_integer(amount, "energy cost amount")
            if amount is None or amount < 0:
                raise ValueError("energy cost amount must be a non-negative integer")
            connection.execute(
                """
                INSERT INTO attack_costs(attack_id, energy_type, amount)
                VALUES (?, ?, ?)
                """,
                (attack_id, energy_type, amount),
            )

    for ability in card.get("abilities", []):
        if not isinstance(ability, dict):
            raise ValueError("abilities entries must be objects")
        connection.execute(
            "INSERT INTO abilities(card_id, name, effect_text) VALUES (?, ?, ?)",
            (card_id, ability.get("name"), ability.get("effect_text")),
        )


def build_database(json_path=DEFAULT_INPUT, database_path=DEFAULT_DATABASE):
    """Create/update the SQLite database using only a local JSON file."""
    cards = _read_cards(Path(json_path))
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        with connection:
            for card in cards:
                _insert_or_update_card(connection, card)
    finally:
        connection.close()
    return len(cards)


def main():
    parser = argparse.ArgumentParser(
        description="Build the Pokémon card SQLite database from local JSON."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        count = build_database(args.input, args.database)
    except (OSError, json.JSONDecodeError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"Database build failed: {error}\n")
    print(f"Loaded {count} Pokémon cards into {args.database}", file=sys.stderr)


if __name__ == "__main__":
    main()
