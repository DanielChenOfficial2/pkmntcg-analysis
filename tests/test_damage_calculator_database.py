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

    def test_explicit_damage_timing_overrides_modifier_defaults(self):
        reduced_before_weakness = build_damage_database.parse_tool_effect(
            "The Pokémon this card is attached to takes 20 less damage from "
            "attacks from your opponent's [Dragon] Pokémon "
            "(before applying Weakness and Resistance)."
        )
        increased_after_weakness = build_damage_database.parse_tool_effect(
            "Attacks used by the Pokémon this card is attached to do "
            "20 more damage to your opponent's Active Pokémon "
            "(after applying Weakness and Resistance)."
        )

        self.assertEqual(
            reduced_before_weakness["damage_modifier_timing"],
            "before_weakness",
        )
        self.assertEqual(
            increased_after_weakness["damage_modifier_timing"],
            "after_weakness",
        )

    def test_requested_effect_patterns_parse_into_general_conditions(self):
        cases = [
            (
                "light",
                "Attacks used by the Pikachu ex this card is attached to "
                "do 50 more damage to your opponent's Active Pok\u00e9mon ex "
                "(before applying Weakness and Resistance) .",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": 50,
                    "damage_modifier_timing": "before_weakness",
                    "requires_attached_name": "Pikachu ex",
                    "requires_opponent_ex": 1,
                },
            ),
            (
                "thick",
                "The [Dragon] Pok\u00e9mon this card is attached to takes "
                "50 less damage from attacks from your opponent's [Grass] , "
                "[Fire] , [Water] , or [Lightning] Pok\u00e9mon "
                "(after applying Weakness and Resistance) .",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": -50,
                    "damage_modifier_timing": "after_weakness",
                    "requires_attached_type": "Dragon",
                    "requires_opponent_type": "|Grass|Fire|Water|Lightning|",
                },
            ),
            (
                "sacred",
                "The Pok\u00e9mon this card is attached to takes 30 less "
                "damage from attacks from your opponent's Pok\u00e9mon that "
                "have an Ability (after applying Weakness and Resistance) .",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": -30,
                    "damage_modifier_timing": "after_weakness",
                    "requires_opponent_ability": 1,
                },
            ),
            (
                "cynthia",
                "The Cynthia's Pok\u00e9mon this card is attached to gets "
                "+70 HP.",
                {
                    "effect_type": "hp_modifier",
                    "hp_modifier": 70,
                    "requires_attached_name": "Cynthia's",
                    "requires_opponent_ability": 1,
                },
            ),
            (
                "hop",
                "Attacks used by the Hop's Pok\u00e9mon this card is attached "
                "to cost [Colorless] less and do 30 more damage to your "
                "opponent's Active Pok\u00e9mon (before applying Weakness and "
                "Resistance) .",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": 30,
                    "requires_attached_name": "Hop's",
                    "requires_opponent_ex": None,
                },
            ),
            (
                "binding",
                "Attacks used by the Poisoned Pok\u00e9mon this card is "
                "attached to do 40 more damage to your opponent's Active "
                "Pok\u00e9mon (before applying Weakness and Resistance) .",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": 40,
                    "requires_attached_poisoned": 1,
                },
            ),
            (
                "berry",
                "If the Pok\u00e9mon this card is attached to is damaged by "
                "an attack from your opponent's [Dragon] Pok\u00e9mon, it "
                "takes 60 less damage (after applying Weakness and "
                "Resistance) , and discard this card.",
                {
                    "effect_type": "damage_modifier",
                    "damage_modifier": -60,
                    "damage_modifier_timing": "after_weakness",
                    "requires_opponent_type": "|Dragon|",
                },
            ),
            (
                "survival",
                "If the Pok\u00e9mon this card is attached to has full HP and "
                "would be Knocked Out by damage from an attack from your "
                "opponent's Pok\u00e9mon, it is not Knocked Out, and its "
                "remaining HP becomes 10. Then, discard this card.",
                {
                    "effect_type": "knockout_prevention",
                    "prevents_knockout": 1,
                    "requires_attached_full_hp": 1,
                },
            ),
            (
                "cape",
                "The Pok\u00e9mon this card is attached to gets +100 HP.",
                {
                    "effect_type": "hp_modifier",
                    "hp_modifier": 100,
                },
            ),
        ]

        for name, effect_text, expected in cases:
            with self.subTest(tool=name):
                tool = {"card_name": "Cynthia's Power Weight" if name == "cynthia" else name}
                parsed = build_damage_database.parse_tool_effect(
                    effect_text,
                    tool,
                )
                self.assertIsNotNone(parsed)
                for field, value in expected.items():
                    self.assertEqual(parsed[field], value)
                self.assertTrue(tool["implemented"])

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
        self.assertEqual(boosted_results[0]["attacker_tool_modifier"], 30)
        self.assertEqual(boosted_results[0]["damage_before_weakness"], 100)
        self.assertEqual(boosted_results[0]["final_damage"], 200)
        self.assertEqual(boosted_results[0]["match_type"], "weakness")
        self.assertEqual(non_ex_results, [])
        self.assertEqual(len(low_hp_results), 2)
        self.assertTrue(
            all(move["attacker_tool_name"] is None for move in low_hp_results)
        )

    def test_tool_conditions_and_modifiers_are_applied_in_candidate_query(self):
        attackers = [
            ("Pikachu ex", ["ex"], "Lightning", 160, []),
            ("Hop's Raichu", [], "Lightning", 170, []),
            ("Poisoned Eevee", [], "Fire", 170, []),
            ("Grass Attacker", [], "Grass", 100, []),
            ("Ability Dragon", [], "Dragon", 150, [{"name": "Ability"}]),
            ("Ability Fire", [], "Fire", 330, [{"name": "Ability"}]),
            ("No Ability Attacker", [], "Water", 100, []),
        ]
        defenders = [
            ("Target ex", ["ex"], "Normal", 200, None),
            ("Dragon Target", [], "Dragon", 140, "Grass"),
            ("Sacred Target", [], "Fire", 80, None),
            ("Cynthia's Gible", [], "Fighting", 250, None),
            ("Survival Target", [], "Water", 100, None),
            ("Cape Target", [], "Water", 100, None),
            ("Haban Target", [], "Water", 80, None),
        ]
        cards = []

        for name, variants, pokemon_type, damage, abilities in attackers:
            cards.append(
                {
                    "name": name,
                    "card_type": "Pokemon",
                    "card_variants": variants,
                    "evolution_stage": "Basic",
                    "type": pokemon_type,
                    "hp": 100,
                    "abilities": abilities,
                    "moves": [{"name": "Hit", "damage": str(damage)}],
                }
            )

        for name, variants, pokemon_type, hp, weakness in defenders:
            card = {
                "name": name,
                "card_type": "Pokemon",
                "card_variants": variants,
                "evolution_stage": "Basic",
                "type": pokemon_type,
                "hp": hp,
                "abilities": [],
                "moves": [],
            }
            if weakness:
                card["weakness"] = weakness
            cards.append(card)

        tools = [
            (
                "Light Ball",
                "offensive",
                "Attacks used by the Pikachu ex this card is attached to do "
                "50 more damage to your opponent's Active Pokémon ex "
                "(before applying Weakness and Resistance) .",
            ),
            (
                "Thick Scale",
                "defensive",
                "The [Dragon] Pokémon this card is attached to takes 50 less "
                "damage from attacks from your opponent's [Grass] Pokémon "
                "(after applying Weakness and Resistance) .",
            ),
            (
                "Sacred Charm",
                "defensive",
                "The Pokémon this card is attached to takes 30 less damage "
                "from attacks from your opponent's Pokémon that have an "
                "Ability (after applying Weakness and Resistance) .",
            ),
            (
                "Cynthia's Power Weight",
                "defensive",
                "The Cynthia's Pokémon this card is attached to gets +70 HP.",
            ),
            (
                "Hop's Choice Band",
                "offensive",
                "Attacks used by the Hop's Pokémon this card is attached to "
                "cost [Colorless] less and do 30 more damage to your "
                "opponent's Active Pokémon (before applying Weakness and "
                "Resistance) .",
            ),
            (
                "Binding Mochi",
                "offensive",
                "Attacks used by the Poisoned Pokémon this card is attached "
                "to do 40 more damage to your opponent's Active Pokémon "
                "(before applying Weakness and Resistance) .",
            ),
            (
                "Haban Berry",
                "defensive",
                "If the Pokémon this card is attached to is damaged by an "
                "attack from your opponent's [Dragon] Pokémon, it takes 60 "
                "less damage (after applying Weakness and Resistance) , and "
                "discard this card.",
            ),
            (
                "Survival Brace",
                "defensive",
                "If the Pokémon this card is attached to has full HP and "
                "would be Knocked Out by damage from an attack from your "
                "opponent's Pokémon, it is not Knocked Out, and its "
                "remaining HP becomes 10. Then, discard this card.",
            ),
            (
                "Hero's Cape",
                "defensive",
                "The Pokémon this card is attached to gets +100 HP.",
            ),
        ]
        tools = [
            {
                "card_name": name,
                "classification": classification,
                "supported": True,
                "implemented": False,
                "effect_text": effect_text,
            }
            for name, classification, effect_text in tools
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cards_path = temp_path / "cards.json"
            tools_path = temp_path / "tools.json"
            database_path = temp_path / "calculator.sqlite3"
            cards_path.write_text(
                json.dumps({"cards": cards}),
                encoding="utf-8",
            )
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
                query = sql_match.group(1)

                def results_for(defender_name):
                    defender_id = connection.execute(
                        "SELECT id FROM pokemon WHERE name = ?",
                        (defender_name,),
                    ).fetchone()["id"]
                    return connection.execute(
                        query,
                        (defender_id,),
                    ).fetchall()

                ex_results = results_for("Target ex")
                dragon_results = results_for("Dragon Target")
                sacred_results = results_for("Sacred Target")
                cynthia_results = results_for("Cynthia's Gible")
                survival_results = results_for("Survival Target")
                cape_results = results_for("Cape Target")
                haban_results = results_for("Haban Target")
            finally:
                connection.close()

        def matching(rows, attacker_name, attacker_tool=None, defender_tool=None):
            return [
                row for row in rows
                if row["attacker_name"] == attacker_name
                and row["attacker_tool_name"] == attacker_tool
                and row["defender_tool_name"] == defender_tool
            ]

        light_ball = matching(ex_results, "Pikachu ex", "Light Ball")
        self.assertEqual(len(light_ball), 1)
        self.assertEqual(light_ball[0]["final_damage"], 210)
        self.assertEqual(light_ball[0]["attacker_tool_modifier"], 50)

        hop_band = matching(ex_results, "Hop's Raichu", "Hop's Choice Band")
        self.assertEqual(len(hop_band), 1)
        self.assertEqual(hop_band[0]["final_damage"], 200)

        binding_mochi = matching(
            ex_results,
            "Poisoned Eevee",
            "Binding Mochi",
        )
        self.assertEqual(len(binding_mochi), 1)
        self.assertEqual(binding_mochi[0]["final_damage"], 210)
        self.assertEqual(binding_mochi[0]["attacker_tool_requires_poisoned"], 1)

        thick_scale = matching(
            dragon_results,
            "Grass Attacker",
            defender_tool="Thick Scale",
        )
        self.assertEqual(len(thick_scale), 1)
        self.assertEqual(thick_scale[0]["damage_before_weakness"], 100)
        self.assertEqual(thick_scale[0]["final_damage"], 150)
        self.assertEqual(thick_scale[0]["defender_tool_modifier"], -50)

        self.assertTrue(
            matching(sacred_results, "Ability Dragon", defender_tool="Sacred Charm")
        )
        self.assertFalse(
            matching(
                sacred_results,
                "No Ability Attacker",
                defender_tool="Sacred Charm",
            )
        )

        cynthia_weight = matching(
            cynthia_results,
            "Ability Fire",
            defender_tool="Cynthia's Power Weight",
        )
        self.assertEqual(len(cynthia_weight), 1)
        self.assertEqual(cynthia_weight[0]["effective_defender_hp"], 320)

        self.assertFalse(
            any(row["defender_tool_name"] == "Survival Brace" for row in survival_results)
        )
        hero_cape = matching(
            cape_results,
            "Ability Fire",
            defender_tool="Hero's Cape",
        )
        self.assertEqual(len(hero_cape), 1)
        self.assertEqual(hero_cape[0]["effective_defender_hp"], 200)

        haban = matching(
            haban_results,
            "Ability Dragon",
            defender_tool="Haban Berry",
        )
        self.assertEqual(len(haban), 1)
        self.assertEqual(haban[0]["final_damage"], 90)


if __name__ == "__main__":
    unittest.main()
