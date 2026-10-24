import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data-analysis" / "calculator"))

import parse_effects


class ReferenceClassificationTests(unittest.TestCase):
    def test_excludes_reactive_tool_effects_from_automatic_classification(self):
        effect = {
            "card_type": "Trainer",
            "trainer_subtype": "Tool",
            "effect_text": (
                "If the [Darkness] Pokémon this card is attached to is in the "
                "Active Spot and is damaged by an attack from your opponent's "
                "Pokémon (even if this Pokémon is Knocked Out), place 4 damage "
                "counters on the Attacking Pokémon."
            ),
        }

        parse_effects.apply_decisions([effect], {})

        self.assertEqual(effect["auto_classification"], "neither")
        self.assertEqual(
            effect["auto_rule"],
            "unsupported_tool_opponent_attack_reaction",
        )
        self.assertIs(effect["supported"], False)

    def test_excludes_opponent_attack_reaction_tools_as_references(self):
        excluded_effects = [
            "If this Pokémon is damaged by an attack from your opponent's Pokémon, draw 3 cards.",
            "Whenever this Pokémon is damaged by an opponent's attack, draw 2 cards.",
            "If this Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon, draw a card.",
            "If this Pokémon takes 240 or more damage from an attack from your opponent's Pokémon, put damage counters on the Attacking Pokémon.",
        ]
        records = [
            {
                "effect_text": text,
                "card_type": "Trainer",
                "trainer_subtype": "Tool",
                "supported": True,
                "classification": "offensive",
            }
            for text in excluded_effects
        ]
        passive_tool_effect = {
            "effect_text": "Attacks used by this Pokémon do 30 more damage.",
            "card_type": "Trainer",
            "trainer_subtype": "Tool",
            "supported": True,
            "classification": "offensive",
        }
        non_tool_effect = {
            "effect_text": (
                "If this Pokémon is damaged by an attack from your opponent, "
                "draw a card."
            ),
            "card_type": "Pokémon",
            "supported": True,
            "classification": "offensive",
        }
        records.extend([passive_tool_effect, non_tool_effect])

        with tempfile.TemporaryDirectory() as temp_dir:
            reference_path = Path(temp_dir) / "supported_effects.json"
            reference_path.write_text(
                json.dumps(records),
                encoding="utf-8",
            )
            with patch.object(parse_effects, "DEFAULT_SUPPORTED_OUTPUT", reference_path):
                references = parse_effects.load_reference_classifications()

        for text in excluded_effects:
            self.assertNotIn(parse_effects.normalize_effect(text), references)
        self.assertIn(
            parse_effects.normalize_effect(passive_tool_effect["effect_text"]),
            references,
        )
        self.assertIn(
            parse_effects.normalize_effect(non_tool_effect["effect_text"]),
            references,
        )


if __name__ == "__main__":
    unittest.main()
