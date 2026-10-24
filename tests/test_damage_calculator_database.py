import contextlib
import importlib.util
import io
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = (
    ROOT / "data-analysis" / "calculator" / "build_damage_database.py"
)
DATABASE_JS_PATH = ROOT / "website" / "database.js"

SPEC = importlib.util.spec_from_file_location(
    "build_damage_database",
    BUILDER_PATH,
)
build_damage_database = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_damage_database)


class DamageCalculatorToolTests(unittest.TestCase):
    def test_missing_tool_catalog_reports_an_error(self):
        missing_catalog = ROOT / "missing-supported-tools.json"

        with self.assertRaisesRegex(ValueError, "Tool file not found"):
            build_damage_database.load_tools(missing_catalog)

    def test_unconditional_damage_bonus_has_no_inferred_conditions(self):
        parsed = build_damage_database.parse_tool_effect(
            "Attacks used by the Pokémon this card is attached to do "
            "30 more damage to your opponent's Active Pokémon "
            "(before applying Weakness and Resistance)."
        )

        self.assertEqual(parsed["damage_modifier"], 30)
        self.assertIsNone(parsed["requires_attached_no_rule_box"])
        self.assertIsNone(parsed["requires_opponent_ex"])

    def test_brave_bangle_only_boosts_non_rule_box_attacker_against_ex(self):
        cards = {
            "cards": [
                {
                    "name": "Basic Attacker",
                    "card_type": "Pokemon",
                    "card_variants": [],
                    "evolution_stage": "Basic",
                    "type": "Fire",
                    "hp": 100,
                    "moves": [{"name": "Attack", "damage": "70"}],
                },
                {
                    "name": "Rule Box Attacker",
                    "card_type": "Pokemon",
                    "card_variants": ["V"],
                    "evolution_stage": "Basic",
                    "type": "Fire",
                    "hp": 100,
                    "moves": [{"name": "Attack", "damage": "70"}],
                },
                {
                    "name": "Target ex",
                    "card_type": "Pokemon",
                    "card_variants": ["ex"],
                    "evolution_stage": "Basic",
                    "type": "Water",
                    "weakness": "Fire",
                    "hp": 190,
                    "moves": [],
                },
                {
                    "name": "Target",
                    "card_type": "Pokemon",
                    "card_variants": [],
                    "evolution_stage": "Basic",
                    "type": "Water",
                    "weakness": "Fire",
                    "hp": 190,
                    "moves": [],
                },
                {
                    "name": "Low HP target ex",
                    "card_type": "Pokemon",
                    "card_variants": ["ex"],
                    "evolution_stage": "Basic",
                    "type": "Water",
                    "weakness": "Fire",
                    "hp": 130,
                    "moves": [],
                },
            ]
        }
        tools = [
            {
                "card_name": "Brave Bangle",
                "set": "PBL",
                "card_number": "104",
                "effect_text": (
                    "If the Pokémon this card is attached to doesn't have "
                    "a Rule Box, the attacks it uses do 30 more damage to "
                    "your opponent's Active Pokémon ex (before applying "
                    "Weakness and Resistance) . (Pokémon ex, Pokémon V, "
                    "etc. have Rule Boxes.)"
                ),
                "classification": "offensive",
                "supported": True,
                "implemented": False,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cards_path = temp_path / "cards.json"
            tools_path = temp_path / "tools.json"
            database_path = temp_path / "calculator.sqlite3"
            cards_path.write_text(json.dumps(cards), encoding="utf-8")
            tools_path.write_text(json.dumps(tools), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                build_damage_database.build_database(
                    cards_path,
                    database_path,
                    tools_path,
                )

            sql_match = re.search(
                r"const statement = db\.prepare\(\s*`(.*?)`\s*\);",
                DATABASE_JS_PATH.read_text(encoding="utf-8"),
                re.DOTALL,
            )
            self.assertIsNotNone(sql_match)

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            try:
                tool = connection.execute(
                    """
                    SELECT effect_type, damage_modifier,
                           requires_attached_no_rule_box, requires_opponent_ex
                    FROM tools
                    WHERE card_name = 'Brave Bangle'
                    """,
                ).fetchone()
                defender_id = connection.execute(
                    "SELECT id FROM pokemon WHERE name = 'Target ex'"
                ).fetchone()["id"]
                non_ex_defender_id = connection.execute(
                    "SELECT id FROM pokemon WHERE name = 'Target'"
                ).fetchone()["id"]
                low_hp_defender_id = connection.execute(
                    "SELECT id FROM pokemon WHERE name = 'Low HP target ex'"
                ).fetchone()["id"]

                candidate_query = sql_match.group(1)
                boosted_results = connection.execute(
                    candidate_query,
                    (defender_id,),
                ).fetchall()
                non_ex_results = connection.execute(
                    candidate_query,
                    (non_ex_defender_id,),
                ).fetchall()
                low_hp_results = connection.execute(
                    candidate_query,
                    (low_hp_defender_id,),
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(
            tuple(tool),
            ("damage_modifier", 30, 1, 1),
        )
        self.assertEqual(len(boosted_results), 1)
        self.assertEqual(boosted_results[0]["attacker_name"], "Basic Attacker")
        self.assertEqual(
            boosted_results[0]["attacker_tool_name"],
            "Brave Bangle",
        )
        self.assertIsNone(boosted_results[0]["defender_tool_name"])
        self.assertEqual(boosted_results[0]["attacker_damage_modifier"], 30)
        self.assertEqual(boosted_results[0]["final_damage"], 200)
        self.assertEqual(boosted_results[0]["match_type"], "weakness")
        self.assertEqual(non_ex_results, [])
        self.assertEqual(len(low_hp_results), 2)
        self.assertTrue(
            all(move["attacker_tool_name"] is None for move in low_hp_results)
        )


if __name__ == "__main__":
    unittest.main()
