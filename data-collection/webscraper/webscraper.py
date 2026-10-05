"""Scrape Pokémon card facts from Bulbapedia into a JSON interchange file."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "raw" / "pokemon_cards.json"
BASE_URL = "https://bulbapedia.bulbagarden.net"
DEFAULT_TEST_URL = (
    "https://bulbapedia.bulbagarden.net/wiki/"
    "Registeel_(Astral_Radiance_108)"
)

EXPANSIONS = [
    ("https://bulbapedia.bulbagarden.net/wiki/Brilliant_Stars_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Astral_Radiance_(TCG)", "Set_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_GO_(TCG)", "Set_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Lost_Origin_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Silver_Tempest_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Crown_Zenith_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Scarlet_%26_Violet_(TCG)", "Set_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Paldea_Evolved_(TCG)", "Card_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Obsidian_Flames_(TCG)", "Card_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/151_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Paradox_Rift_(TCG)", "Card_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Paldean_Fates_(TCG)", "Set_list"),
    ("https://bulbapedia.bulbagarden.net/wiki/Temporal_Forces_(TCG)", "Card_lists"),
    ("https://bulbapedia.bulbagarden.net/wiki/Twilight_Masquerade_(TCG)", "Card_lists"),
]

ANCIENT_POKEMON = {
    "Great Tusk", "Scream Tail", "Brute Bonnet", "Flutter Mane", "Slither Wing",
    "Sandy Shocks", "Roaring Moon", "Koraidon", "Walking Wake", "Gouging Fire",
    "Raging Bolt",
}
FUTURE_POKEMON = {
    "Iron Treads", "Iron Bundle", "Iron Hands", "Iron Jugulis", "Iron Moth",
    "Iron Thorns", "Iron Valiant", "Miraidon", "Iron Leaves", "Iron Boulder",
    "Iron Crown",
}


def clean_text(value):
    """Normalize visible Bulbapedia text without interpreting its meaning."""
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_pokemon_name(value):
    return clean_text(value).replace("♂", "-M").replace("♀", "-F")


def extract_english_text(value, keep_punctuation=True):
    """Keep the scraper's existing English-facing name cleanup behavior."""
    value = re.sub(r"[ぁ-んァ-ンﾞﾟー]", "", value or "")
    if not keep_punctuation:
        value = re.sub(r"[^\w\s]", "", value)
    return value


def _required_one(soup, selector, description, page_url):
    result = soup.select_one(selector)
    if result is None:
        raise ValueError(
            f"Bulbapedia page {page_url} is missing {description}; "
            f"tried selector {selector!r}"
        )
    return result


def _page_soup(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError(f"Could not fetch Bulbapedia page {url}: {error}") from error
    return BeautifulSoup(response.content, "html.parser")


def _extract_card_variants(name):
    variants = []
    if "-ex" in name:
        variants.append("ex")
    if "-VSTAR" in name:
        variants.append("VSTAR")
    elif "-VMAX" in name:
        variants.append("VMAX")
    elif "-V" in name:
        variants.append("V")
    if any(pokemon in name for pokemon in ANCIENT_POKEMON):
        variants.append("Ancient")
    if any(pokemon in name for pokemon in FUTURE_POKEMON):
        variants.append("Future")
    return variants


def _parse_damage(damage_text):
    """Split numeric damage from its literal modifier; do not infer mechanics."""
    if not damage_text:
        return None, None
    match = re.match(r"^\s*(\d+)(.*)$", damage_text)
    if match is None:
        return None, None
    modifier = clean_text(match.group(2)) or None
    return int(match.group(1)), modifier


def _extract_abilities_and_moves(soup, page_url):
    card_text = _required_one(
        soup, "#Card_text", "card text section", page_url
    )
    move_table = card_text.parent.find_next_sibling()
    if move_table is None:
        return [], []
    tbody = move_table.find("tbody")
    if tbody is None:
        return [], []
    rows = tbody.find_all("tr", recursive=False)

    abilities = []
    moves = []
    index = 0
    while index < len(rows):
        row = rows[index]
        if row.find("img", alt="Future paradox") is not None:
            index += 1
            if index >= len(rows):
                break
            row = rows[index]

        move_table_row = row.find("td")
        nested_table = move_table_row.find("table") if move_table_row else None
        move_info = nested_table.find("tr") if nested_table else None
        if move_info is None:
            index += 1
            continue

        ability_link = move_info.find(href=re.compile("Ability"))
        if ability_link is not None:
            ability_name_tag = move_info.find(
                "td", style="text-align: center; color:#7E0A0E;"
            )
            ability_name = clean_text(
                extract_english_text(
                    ability_name_tag.get_text(" ", strip=True)
                    if ability_name_tag else ability_link.get_text(" ", strip=True)
                )
            )
            effect = clean_text(rows[index + 1].get_text(" ", strip=True)) \
                if index + 1 < len(rows) else ""
            abilities.append({
                "name": ability_name or None,
                "effect_text": effect or None,
            })
            index += 2
            continue

        cost_header = move_info.find("th", class_="roundyleft")
        cost = {}
        if cost_header is not None:
            for anchor in cost_header.find_all("a"):
                energy_type = anchor.get("title")
                if energy_type:
                    cost[energy_type] = cost.get(energy_type, 0) + 1

        name_cell = (
            cost_header.find_next_sibling()
            if cost_header is not None else None
        )
        if name_cell is None:
            index += 1
            continue
        name = clean_text(
            extract_english_text(name_cell.get_text(" ", strip=True))
        )
        damage_cell = move_info.find("th", class_="roundyright")
        damage_text = clean_text(damage_cell.get_text(" ", strip=True)) \
            if damage_cell is not None else ""
        damage, damage_modifier = _parse_damage(damage_text)
        effect = clean_text(rows[index + 1].get_text(" ", strip=True)) \
            if index + 1 < len(rows) else ""
        moves.append({
            "name": name or None,
            "cost": cost,
            "damage": damage,
            "damage_modifier": damage_modifier,
            "damage_text": damage_text or None,
            "effect_text": effect or None,
        })
        index += 2
    return abilities, moves


def scrape_pokemon_info(url, set_name=None):
    """Extract one Pokémon card's displayed facts from its Bulbapedia page."""
    soup = _page_soup(url)
    heading = _required_one(
        soup,
        "h1#firstHeading span.mw-page-title-main",
        "card page title",
        url,
    )
    name_with_set = normalize_pokemon_name(heading.get_text())

    info_rows = soup.select(
        "div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr"
    )
    if len(info_rows) < 4:
        raise ValueError(f"Bulbapedia page has an unexpected Pokémon info table: {url}")

    first_info = info_rows[0].find("td")
    evolution_text = clean_text(first_info.get_text(" ", strip=True)) \
        if first_info else ""
    evolution_stage = re.sub(r"\s*Pokémon.*$", "", evolution_text).strip() or None
    previous_evolution = None
    previous_tag = first_info.find("small") if first_info else None
    if previous_tag is not None:
        previous_text = clean_text(previous_tag.get_text(" ", strip=True))
        previous_evolution = re.sub(
            r"^Evolves from\s+", "", previous_text, flags=re.IGNORECASE
        ).strip() or None
        if previous_evolution:
            previous_evolution = normalize_pokemon_name(previous_evolution)

    name_tag = info_rows[1].find("td")
    name = normalize_pokemon_name(
        name_tag.get_text(" ", strip=True).replace("\xa0", "-")
        if name_tag else ""
    )
    type_tag = info_rows[2].find("td")
    pokemon_type = clean_text(type_tag.get_text(" ", strip=True)) \
        if type_tag else None
    hp_tag = info_rows[3].find("td")
    hp_text = clean_text(hp_tag.get_text(" ", strip=True)) if hp_tag else ""
    hp_match = re.search(r"\d+", hp_text)

    stat_headers = soup.select(
        "div#mw-content-text table tr:nth-child(3) > td > table > "
        "tbody > tr:nth-child(5) td table tbody tr th"
    )
    weakness = None
    resistance = None
    retreat_cost = None
    if len(stat_headers) > 0:
        link = stat_headers[0].find("a")
        weakness = link.get("title") if link else None
    if len(stat_headers) > 1:
        link = stat_headers[1].find("a")
        resistance = link.get("title") if link else None
    if len(stat_headers) > 2:
        retreat_cost = len(stat_headers[2].find_all("img"))

    set_info = soup.select(
        "div#mw-content-text table tr:nth-child(3) > td > "
        "table:nth-child(2) > tbody > tr td:nth-child(2)"
    )
    expansion = clean_text(set_info[0].get_text(" ", strip=True)) \
        if set_info else None
    abilities, moves = _extract_abilities_and_moves(soup, url)

    return {
        "name": name or None,
        "name_with_set": name_with_set or None,
        "card_type": "pokemon",
        "card_variants": _extract_card_variants(name),
        "evolution_stage": evolution_stage,
        "previous_evolution": previous_evolution,
        "hp": int(hp_match.group()) if hp_match else None,
        "hp_text": hp_text or None,
        "type": pokemon_type,
        "weakness": weakness,
        "resistance": resistance,
        "retreat_cost": retreat_cost,
        "abilities": abilities,
        "moves": moves,
        "card_number": None,
        "card_mark": None,
        "rarity": None,
        "set": set_name,
        "expansion": expansion,
        "source_url": url,
    }


def _set_name_from_url(url):
    slug = unquote(url.rsplit("/", 1)[-1])
    return re.sub(r"\s*\(TCG\)$", "", slug.replace("_", " "))


def scrape_expansion(url, set_list_id):
    """Extract the Pokémon-card rows from one Bulbapedia set listing."""
    soup = _page_soup(url)
    selector = f"#{set_list_id}"
    section = _required_one(soup, selector, "set card list section", url)
    list_table = section.parent.find_next_sibling()
    if list_table is None:
        raise ValueError(
            f"Bulbapedia set page {url} has no table immediately after "
            f"section {selector}; expected the set card list table"
        )
    card_table = list_table.find("table", class_="roundy") if list_table else None
    if card_table is None:
        raise ValueError(
            f"Bulbapedia set page {url}: expected a table with class 'roundy' "
            f"after section {selector}"
        )
    tbody = card_table.find("tbody")
    if tbody is None:
        raise ValueError(
            f"Bulbapedia set page {url}: expected a <tbody> in the 'roundy' "
            f"table after section {selector}"
        )
    table_rows = tbody.find_all("tr", recursive=False)
    if len(table_rows) < 2:
        raise ValueError(
            f"Bulbapedia set page {url}: expected at least 2 rows in the "
            f"'roundy' table after section {selector}, found {len(table_rows)}"
        )
    card_container = table_rows[1].find("td")
    nested_table = card_container.find("table") if card_container else None
    card_tbody = nested_table.find("tbody") if nested_table else None
    if card_tbody is None:
        raise ValueError(
            f"Bulbapedia set page {url}: could not find the nested card-list "
            f"table in row 2 after section {selector}"
        )
    card_rows = card_tbody.find_all("tr", recursive=False)

    cards = []
    for row_number, row in enumerate(card_rows[1:-1], start=2):
        type_header = row.find("th", style="background:#FFFFFF;")
        if type_header is None:
            break
        image = type_header.find("img")
        if image is not None and "Pok" not in image.get("alt", ""):
            break

        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        card_link = cells[2].find("a", href=True)
        mark_link = cells[1].find("a")
        rarity_link = cells[3].find("a")
        if card_link is None:
            raise ValueError(
                f"Bulbapedia set page {url}, card row {row_number}: "
                "expected a card link in the third cell"
            )
        card_url = card_link["href"]
        if not card_url.startswith("http"):
            card_url = BASE_URL + card_url
        try:
            card = scrape_pokemon_info(
                card_url, set_name=_set_name_from_url(url)
            )
        except (ValueError, requests.RequestException) as error:
            raise ValueError(
                f"Failed scraping Pokémon card in set page {url}, "
                f"card row {row_number} ({card_url}): {error}"
            ) from error
        card["card_number"] = clean_text(cells[0].get_text(" ", strip=True)) or None
        card["card_mark"] = mark_link.get("title") if mark_link else None
        card["rarity"] = rarity_link.get("title") if rarity_link else None
        cards.append(card)
    return cards


def scrape_all_pokemon_cards():
    cards = []
    seen = set()
    for url, set_list_id in EXPANSIONS:
        print(
            f"Scraping set {_set_name_from_url(url)} "
            f"(page {url}; looking for #{set_list_id})...",
            file=sys.stderr,
        )
        for card in scrape_expansion(url, set_list_id):
            identity = card["name_with_set"]
            if identity in seen:
                print(f"Skipping duplicate card {identity}", file=sys.stderr)
                continue
            seen.add(identity)
            cards.append(card)
    return cards


def write_cards(cards, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {"schema_version": 1, "cards": cards},
            output_file,
            ensure_ascii=False,
            indent=2,
        )
        output_file.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Pokémon cards from Bulbapedia into JSON."
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"JSON output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Scrape the existing single-card test page instead of all sets.",
    )
    parser.add_argument(
        "--card-url", help="Scrape one card page, useful for testing extraction."
    )
    args = parser.parse_args()

    try:
        if args.card_url or args.test:
            card = scrape_pokemon_info(args.card_url or DEFAULT_TEST_URL)
            cards = [card]
        else:
            cards = scrape_all_pokemon_cards()
        write_cards(cards, args.output)
    except (requests.RequestException, ValueError) as error:
        parser.exit(1, f"Scraping failed: {error}\n")
    print(f"Wrote {len(cards)} Pokémon cards to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
