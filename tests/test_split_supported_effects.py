import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data-analysis" / "calculator"))

import split_supported_effects


class PreserveImplementedStatusTests(unittest.TestCase):
    def test_preserves_existing_values_and_defaults_new_effects_to_false(self):
        existing_effect = {
            "source_url": "https://example.test/cards/1",
            "card_type": "Trainer",
            "trainer_subtype": "Tool",
            "entry_index": 0,
            "entry_name": "Implemented Tool",
            "effect_text": "Existing effect.",
            "implemented": True,
        }
        new_effect = {
            "source_url": "https://example.test/cards/2",
            "card_type": "Trainer",
            "trainer_subtype": "Tool",
            "entry_index": 0,
            "entry_name": "New Tool",
            "effect_text": "New effect.",
        }
        selected = {
            "supported_tools": [
                {key: value for key, value in existing_effect.items() if key != "implemented"},
                new_effect,
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "supported_tools.json").write_text(
                json.dumps([existing_effect]),
                encoding="utf-8",
            )

            split_supported_effects.preserve_implemented_status(
                selected,
                output_dir,
            )

        self.assertIs(selected["supported_tools"][0]["implemented"], True)
        self.assertIs(selected["supported_tools"][1]["implemented"], False)


if __name__ == "__main__":
    unittest.main()
