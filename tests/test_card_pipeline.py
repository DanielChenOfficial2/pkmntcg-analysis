import json
import sqlite3
import sys
import tempfile
import unittest
from bs4 import BeautifulSoup
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data-collection" / "webscraper"))
sys.path.insert(0, str(ROOT / "database"))

import build_database
import webscraper


SAMPLE_CARD_HTML = """
<h1 id="firstHeading"><span class="mw-page-title-main">Bulbasaur (151 1)</span></h1>
<div id="mw-content-text">
  <table><tbody>
    <tr><td>unused</td></tr>
    <tr><td>unused</td></tr>
    <tr><td>
      <table><tbody>
        <tr><td>Basic Pokémon</td></tr>
        <tr><td>Bulbasaur</td></tr>
        <tr><td>Grass</td></tr>
        <tr><td>70</td></tr>
        <tr><td><table><tbody><tr>
          <th><a title="Fire">Fire</a></th>
          <th></th>
          <th><img src="colorless.png"><img src="colorless.png"></th>
        </tr></tbody></table></td></tr>
      </tbody></table>
      <table><tbody><tr><td>Set</td><td>151</td></tr></tbody></table>
    </td></tr>
  </tbody></table>
</div>
<div id="card-heading"><h2 id="Card_text">Card text</h2></div>
<table><tbody>
  <tr><td><table><tbody><tr>
    <th class="roundyleft"><a title="Grass">Grass</a><a title="Colorless">Colorless</a></th>
    <td>Leech Seed</td>
    <th class="roundyright">20</th>
  </tr></tbody></table></td></tr>
  <tr><td>Heal 20 damage from this Pokémon.</td></tr>
</tbody></table>
"""


class FakeResponse:
    content = SAMPLE_CARD_HTML.encode("utf-8")

    def raise_for_status(self):
        return None


class CardPipelineTests(unittest.TestCase):
    def test_missing_set_section_reports_page_and_selector(self):
        page_url = "https://bulbapedia.bulbagarden.net/wiki/Missing_Set_(TCG)"
        with patch.object(
            webscraper,
            "_page_soup",
            return_value=BeautifulSoup("<html><body></body></html>", "html.parser"),
        ):
            with self.assertRaisesRegex(
                ValueError, r"Missing_Set_\(TCG\).*#Set_list"
            ):
                webscraper.scrape_expansion(page_url, "Set_list")

    def test_scraper_json_builds_queryable_database_without_web_access(self):
        with patch.object(webscraper.requests, "get", return_value=FakeResponse()):
            card = webscraper.scrape_pokemon_info(
                "https://bulbapedia.bulbagarden.net/wiki/Bulbasaur_(151_1)",
                set_name="151",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "pokemon_cards.json"
            database_path = Path(temp_dir) / "pokemon.db"
            webscraper.write_cards([card], json_path)

            serialized = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(serialized["cards"][0]["name"], "Bulbasaur")
            self.assertEqual(
                serialized["cards"][0]["moves"][0]["effect_text"],
                "Heal 20 damage from this Pokémon.",
            )

            with patch("requests.get", side_effect=AssertionError("unexpected web request")):
                self.assertEqual(
                    build_database.build_database(json_path, database_path), 1
                )
                self.assertEqual(
                    build_database.build_database(json_path, database_path), 1
                )

            connection = sqlite3.connect(database_path)
            try:
                card_row = connection.execute(
                    """
                    SELECT cards.name, pokemon.hp, sets.name
                    FROM cards
                    JOIN pokemon ON pokemon.card_id = cards.id
                    LEFT JOIN sets ON sets.id = cards.set_id
                    """
                ).fetchone()
                attack_rows = connection.execute(
                    """
                    SELECT attacks.name, attacks.damage, attacks.effect_text,
                           attack_costs.energy_type, attack_costs.amount
                    FROM attacks
                    JOIN cards ON cards.id = attacks.card_id
                    JOIN attack_costs ON attack_costs.attack_id = attacks.id
                    WHERE cards.name = ?
                    ORDER BY attack_costs.energy_type
                    """,
                    ("Bulbasaur",),
                ).fetchall()
                attack_count = connection.execute(
                    "SELECT COUNT(*) FROM attacks"
                ).fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(card_row, ("Bulbasaur", 70, "151"))
            self.assertEqual(
                attack_rows,
                [
                    ("Leech Seed", 20, "Heal 20 damage from this Pokémon.", "Colorless", 1),
                    ("Leech Seed", 20, "Heal 20 damage from this Pokémon.", "Grass", 1),
                ],
            )
            self.assertEqual(attack_count, 1)


if __name__ == "__main__":
    unittest.main()
