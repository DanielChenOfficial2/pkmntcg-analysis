"""Scrape Pokemon card facts from Limitless TCG into a JSON interchange file."""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "raw" / "pokemon_cards.json"
LIMITLESS_BASE_URL = "https://limitlesstcg.com"
DEFAULT_TEST_URL = "https://limitlesstcg.com/cards?q=regulation%3E%3DH&show=all&unique=cards"


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_ascii(value):
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")


def normalize_pokemon_name(value):
    return clean_text(value).replace("♂", "-M").replace("♀", "-F")


def _page_soup(url, session=None):
    getter = session.get if session is not None else requests.get
    try:
        response = getter(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError(f"Could not fetch page {url}: {error}") from error
    return BeautifulSoup(response.content, "html.parser")


def _extract_abilities_and_moves(soup, page_url):
    card_text = soup.select_one("#Card_text")
    if card_text is None:
        return [], []

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
        move_table_row = row.find("td")
        nested_table = move_table_row.find("table") if move_table_row else None
        move_info = nested_table.find("tr") if nested_table else None
        if move_info is None:
            index += 1
            continue

        ability_link = move_info.find(href=re.compile(r"Ability", re.IGNORECASE))
        if ability_link is not None:
            ability_name_tag = move_info.find("td", style=re.compile(r"text-align: center; color:#7E0A0E;", re.I))
            ability_name = clean_text(
                (ability_name_tag.get_text(" ", strip=True) if ability_name_tag else ability_link.get_text(" ", strip=True))
            )
            effect = clean_text(rows[index + 1].get_text(" ", strip=True)) if index + 1 < len(rows) else ""
            abilities.append({"name": ability_name or None, "effect_text": effect or None})
            index += 2
            continue

        cost_header = move_info.find("th", class_="roundyleft")
        cost = {}
        if cost_header is not None:
            for anchor in cost_header.find_all("a"):
                energy_type = anchor.get("title")
                if energy_type:
                    cost[energy_type] = cost.get(energy_type, 0) + 1

        name_cell = cost_header.find_next_sibling() if cost_header is not None else None
        if name_cell is None:
            index += 1
            continue

        name = clean_text(name_cell.get_text(" ", strip=True))
        damage_cell = move_info.find("th", class_="roundyright")
        damage_text = clean_text(damage_cell.get_text(" ", strip=True)) if damage_cell is not None else ""
        match = re.match(r"^\s*(\d+)(.*)$", damage_text)
        damage = int(match.group(1)) if match else None
        damage_modifier = clean_text(match.group(2)) if match and match.group(2) else None
        effect = clean_text(rows[index + 1].get_text(" ", strip=True)) if index + 1 < len(rows) else ""
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


def _extract_card_variants(name):
    variants = []
    normalized = clean_text(name or "")
    if "-ex" in normalized or " ex" in normalized.lower():
        variants.append("ex")
    return variants


def _card_page_metadata(soup):
    meta_title = soup.select_one("meta[property='og:title']")
    if meta_title:
        title = clean_text(meta_title.get("content", ""))
        if title:
            return title

    title = soup.select_one("h1")
    if title:
        text = clean_text(title.get_text(" ", strip=True))
        if text:
            return text
    return None


def _scan_text(soup, selectors):
    for selector in selectors:
        element = soup.select_one(selector)
        if element is not None:
            text = clean_text(element.get_text(" ", strip=True))
            if text:
                return text
    return None


def _extract_json_literals(obj):
    if isinstance(obj, dict):
        values = []
        for key, value in obj.items():
            values.extend(_extract_json_literals(value))
            if isinstance(key, str):
                lowered = key.lower()
                if any(token in lowered for token in ("name", "type", "set", "number", "rarity", "weakness", "resistance", "hp")):
                    values.append(value)
        return values
    if isinstance(obj, list):
        values = []
        for item in obj:
            values.extend(_extract_json_literals(item))
        return values
    return [obj]


def _extract_limitless_set_details(soup):
    current = soup.select_one(".card-prints-current")
    if current is None:
        return None, None, None

    set_name = None
    set_text = current.select_one(".text-lg")
    if set_text is not None:
        set_name = clean_text(set_text.get_text(" ", strip=True))
    if not set_name:
        set_image = current.select_one("img.set")
        if set_image is not None:
            set_name = clean_text(set_image.get("alt") or "")

    card_number = None
    rarity = None
    detail_text = None
    for span in current.select(".prints-current-details span"):
        value = clean_text(span.get_text(" ", strip=True))
        if not value:
            continue
        if re.search(r"#\s*\d+|\b(Common|Uncommon|Rare|Promo|Trainer|Holo|Ultra)\b", value, flags=re.IGNORECASE):
            detail_text = value
            break

    if detail_text:
        number_match = re.search(r"#\s*(\d+)", detail_text)
        if number_match:
            card_number = number_match.group(1)
        rarity_match = re.search(r"(?:#\s*\d+\s*[•·-]?\s*)([A-Za-z][A-Za-z\s/-]*)$", detail_text)
        if rarity_match:
            rarity = clean_text(rarity_match.group(1))
        else:
            rarity = clean_text(re.sub(r"^.*?#\s*\d+\s*[•·-]?\s*", "", detail_text).strip())
        rarity = re.sub(r"^[^A-Za-z]+", "", rarity or "").strip()

    return set_name, card_number, rarity


def _extract_limitless_wrr(soup):
    wrr_block = soup.select_one(".card-text-wrr")
    if wrr_block is None:
        return None, None, None

    text = clean_text(wrr_block.get_text(" ", strip=True))
    weakness = None
    resistance = None
    retreat_cost = None

    weakness_match = re.search(r"Weakness\s*:\s*(.*?)(?=\s*Resistance\s*:|\s*Retreat\s*:|$)", text, flags=re.IGNORECASE)
    if weakness_match:
        weakness = clean_text(weakness_match.group(1))

    resistance_match = re.search(r"Resistance\s*:\s*(.*?)(?=\s*Retreat\s*:|$)", text, flags=re.IGNORECASE)
    if resistance_match:
        resistance = clean_text(resistance_match.group(1))

    retreat_match = re.search(r"Retreat\s*:\s*(\d+)", text, flags=re.IGNORECASE)
    if retreat_match:
        retreat_cost = int(retreat_match.group(1))

    return weakness, resistance, retreat_cost


def _parse_limitless_attack(info_tag):
    symbol = info_tag.select_one(".ptcg-symbol")
    cost = clean_text(symbol.get_text(" ", strip=True)) if symbol is not None else None
    raw_text = clean_text(info_tag.get_text(" ", strip=True))
    if cost:
        raw_text = raw_text.replace(cost, "", 1).strip()

    damage = None
    damage_modifier = None
    damage_text = None
    if raw_text:
        match = re.search(r"^(?P<name>.+?)\s+(?P<damage>\d+)$", raw_text)
        if match:
            raw_text = match.group("name")
            damage_text = match.group("damage")
            damage = int(damage_text)
            damage_modifier = None
        elif re.search(r"\d+", raw_text):
            raw_text = re.sub(r"\s+\d+$", "", raw_text).strip()

    return cost, raw_text or None, damage, damage_modifier, damage_text, raw_text or None


def _scrape_limitless_card(soup, url, set_name=None):
    name_tag = soup.select_one(".card-text-name")
    if name_tag is None:
        raise ValueError(f"Limitless page is missing a card name: {url}")
    name = clean_text(name_tag.get_text(" ", strip=True))
    if not name:
        raise ValueError(f"Limitless page has an empty card name: {url}")

    type_block = soup.select_one(".card-text-type")
    if type_block is None:
        raise ValueError(f"Limitless page is missing card type info: {url}")

    type_text = clean_text(type_block.get_text(" ", strip=True))
    normalized_type_text = normalize_ascii(type_text).lower()
    if "pokemon" not in normalized_type_text:
        raise ValueError(f"Limitless page is not a Pokémon card: {url}")

    card_type = "pokemon"
    evolution_stage = None
    previous_evolution = None

    stage_match = re.search(r"(Basic|Stage 1|Stage 2)", type_text, flags=re.IGNORECASE)
    if stage_match:
        evolution_stage = stage_match.group(1).strip()
    if "Evolves from" in type_text and type_block.select_one("a") is not None:
        previous_evolution = clean_text(type_block.select_one("a").get_text(" ", strip=True))

    title_block = soup.select_one(".card-text-title")
    hp = None
    hp_text = None
    pokemon_type = None
    if title_block is not None:
        title_text = clean_text(title_block.get_text(" ", strip=True))
        parts = [part.strip() for part in re.split(r"\s*-\s*", title_text) if part.strip()]
        if len(parts) >= 2:
            pokemon_type = parts[-2]
            hp_text = parts[-1]
            hp_match = re.search(r"(\d+)", hp_text)
            if hp_match:
                hp = int(hp_match.group(1))

    weakness, resistance, retreat_cost = _extract_limitless_wrr(soup)

    set_name_override, card_number, rarity = _extract_limitless_set_details(soup)
    if set_name_override:
        set_name = set_name_override
    elif set_name is None:
        set_name = None

    regulation_mark = None
    regulation_tag = soup.select_one(".regulation-mark")
    if regulation_tag is not None:
        mark_text = clean_text(regulation_tag.get_text(" ", strip=True))
        mark_match = re.search(r"([A-Z0-9]+)\s+Regulation\s+Mark", mark_text, flags=re.IGNORECASE)
        if mark_match:
            regulation_mark = mark_match.group(1)
        elif mark_text:
            regulation_mark = mark_text.split()[0]

    abilities = []
    for ability_block in soup.select(".card-text-ability"):
        info = ability_block.select_one(".card-text-ability-info")
        effect = ability_block.select_one(".card-text-ability-effect")
        if info is None:
            continue
        ability_name = clean_text(info.get_text(" ", strip=True))
        if ability_name.lower().startswith("ability:"):
            ability_name = ability_name[8:].strip()
        effects = clean_text(effect.get_text(" ", strip=True)) if effect is not None else None
        abilities.append({
            "name": ability_name or None,
            "effect_text": effects or None,
        })

    moves = []
    for attack_block in soup.select(".card-text-attack"):
        info = attack_block.select_one(".card-text-attack-info")
        effect = attack_block.select_one(".card-text-attack-effect")
        if info is None:
            continue

        cost, attack_name, damage, damage_modifier, damage_text, effect_text = _parse_limitless_attack(info)
        effect_text = clean_text(effect.get_text(" ", strip=True)) if effect is not None else None
        moves.append({
            "name": attack_name or None,
            "cost": cost,
            "damage": damage,
            "damage_modifier": damage_modifier,
            "damage_text": damage_text,
            "effect_text": effect_text or None,
        })

    name_with_set = f"{name} ({set_name})" if set_name else name
    return {
        "name": name,
        "name_with_set": name_with_set,
        "card_type": card_type,
        "card_variants": _extract_card_variants(name),
        "evolution_stage": evolution_stage,
        "previous_evolution": previous_evolution,
        "hp": hp,
        "hp_text": hp_text,
        "type": pokemon_type,
        "weakness": weakness,
        "resistance": resistance,
        "retreat_cost": retreat_cost,
        "abilities": abilities,
        "moves": moves,
        "card_number": card_number,
        "card_mark": regulation_mark,
        "rarity": rarity,
        "set": set_name,
        "expansion": set_name,
        "source_url": url,
    }


def _scrape_compatibility_card(soup, url, set_name=None):
    heading = soup.select_one("h1#firstHeading span.mw-page-title-main")
    if heading is None:
        heading = soup.select_one("h1")
    if heading is None:
        raise ValueError(f"Page is missing a card title: {url}")
    name_with_set = normalize_pokemon_name(heading.get_text())

    info_rows = soup.select("div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr")
    if len(info_rows) < 4:
        raise ValueError(f"Page has an unexpected Pokémon info table: {url}")

    first_info = info_rows[0].find("td")
    evolution_text = clean_text(first_info.get_text(" ", strip=True)) if first_info else ""
    evolution_stage = re.sub(r"\s*Pokémon.*$", "", evolution_text).strip() or None

    previous_evolution = None
    previous_tag = first_info.find("small") if first_info else None
    if previous_tag is not None:
        previous_text = clean_text(previous_tag.get_text(" ", strip=True))
        previous_evolution = re.sub(r"^Evolves from\s+", "", previous_text, flags=re.IGNORECASE).strip() or None
        if previous_evolution:
            previous_evolution = normalize_pokemon_name(previous_evolution)

    name_tag = info_rows[1].find("td")
    name = normalize_pokemon_name(name_tag.get_text(" ", strip=True).replace("\xa0", "-") if name_tag else "")
    type_tag = info_rows[2].find("td")
    pokemon_type = clean_text(type_tag.get_text(" ", strip=True)) if type_tag else None
    hp_tag = info_rows[3].find("td")
    hp_text = clean_text(hp_tag.get_text(" ", strip=True)) if hp_tag else ""
    hp_match = re.search(r"\d+", hp_text)

    stat_headers = soup.select("div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr:nth-child(5) td table tbody tr th")
    weakness = None
    resistance = None
    retreat_cost = None
    if len(stat_headers) > 0:
        weakness = stat_headers[0].find("a").get("title") if stat_headers[0].find("a") else None
    if len(stat_headers) > 1:
        resistance = stat_headers[1].find("a").get("title") if stat_headers[1].find("a") else None
    if len(stat_headers) > 2:
        retreat_cost = len(stat_headers[2].find_all("img"))

    expansions = soup.select("div#mw-content-text table tr:nth-child(3) > td > table:nth-child(2) > tbody > tr td:nth-child(2)")
    expansion = clean_text(expansions[0].get_text(" ", strip=True)) if expansions else None
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


def scrape_pokemon_info(url, set_name=None):
    soup = _page_soup(url)
    host = urlsplit(url).netloc.lower()
    if "limitlesstcg.com" in host:
        return _scrape_limitless_card(soup, url, set_name=set_name)
    return _scrape_compatibility_card(soup, url, set_name=set_name)


def _limitless_card_urls(page_url):
    soup = _page_soup(page_url)
    candidates = []
    seen = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        candidate = urljoin(LIMITLESS_BASE_URL, href)
        if candidate in seen:
            continue
        if not candidate.lower().startswith(LIMITLESS_BASE_URL.lower()):
            continue
        parsed = urlsplit(candidate)
        if "/cards" not in parsed.path and "/card" not in parsed.path:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def _set_name_from_url(url):
    slug = unquote(url.rsplit("/", 1)[-1])
    slug = slug.replace("%20", " ")
    return re.sub(r"\s*\(.*?\)$", "", slug).strip() or slug


def scrape_expansion(url, set_list_id):
    soup = _page_soup(url)
    selector = f"#{set_list_id}" if set_list_id else None
    if selector is None:
        candidate_ids = ("Set_list", "Set_lists", "Card_lists")
        selector = next((f"#{candidate}" for candidate in candidate_ids if soup.select_one(f"#{candidate}")), None)
        if selector is None:
            raise ValueError(f"Page {url} is missing a card list section; tried selectors {', '.join(f'#{item}' for item in ('Set_list', 'Set_lists', 'Card_lists'))}")

    section = soup.select_one(selector)
    if section is None:
        raise ValueError(f"Page {url} is missing {selector}; tried selector {selector!r}")

    list_table = section.parent.find_next_sibling()
    if list_table is None:
        raise ValueError(f"Page {url} has no table immediately after {selector}; expected the set card list table")

    card_table = list_table.find("table", class_="roundy") if list_table else None
    if card_table is None:
        return []

    tbody = card_table.find("tbody")
    if tbody is None:
        return []
    rows = tbody.find_all("tr", recursive=False)
    if len(rows) < 2:
        return []

    cards = []
    for row in rows[1:-1]:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        card_link = cells[2].find("a", href=True)
        if card_link is None:
            continue
        card_url = card_link["href"]
        if not card_url.startswith("http"):
            card_url = urljoin(LIMITLESS_BASE_URL, card_url)
        try:
            card = scrape_pokemon_info(card_url, set_name=_set_name_from_url(url))
        except Exception as error:
            raise ValueError(f"Failed scraping card in set page {url}, card URL {card_url}: {error}") from error
        cards.append(card)
    return cards


def scrape_all_pokemon_cards():
    cards = []
    seen = set()
    for url in _limitless_card_urls(DEFAULT_TEST_URL):
        try:
            card = scrape_pokemon_info(url)
        except Exception as error:
            print(f"Failed card {url}: {error}", file=sys.stderr)
            continue
        identity = card.get("name_with_set") or card.get("name")
        if identity in seen:
            continue
        seen.add(identity)
        cards.append(card)
    return cards


def write_cards(cards, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump({"schema_version": 1, "cards": cards}, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Scrape Pokemon cards from Limitless TCG into JSON.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test", action="store_true", help="Scrape the default Limitless search page instead of the whole dataset.")
    parser.add_argument("--card-url", help="Scrape one card page, useful for testing extraction.")
    args = parser.parse_args()

    try:
        if args.card_url:
            cards = [scrape_pokemon_info(args.card_url)]
        elif args.test:
            cards = [scrape_pokemon_info(DEFAULT_TEST_URL)]
        else:
            cards = scrape_all_pokemon_cards()
        write_cards(cards, args.output)
    except (requests.RequestException, ValueError) as error:
        parser.exit(1, f"Scraping failed: {error}\n")
    print(f"Wrote {len(cards)} Pokémon cards to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
