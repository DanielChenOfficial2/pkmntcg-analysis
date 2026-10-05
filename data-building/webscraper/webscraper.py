"""Scrape Pokemon card facts from Limitless TCG into a JSON interchange file."""

import argparse
import json
import re
import sys
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
    if "-VSTAR" in normalized or " VSTAR" in normalized:
        variants.append("VSTAR")
    elif "-VMAX" in normalized or " VMAX" in normalized:
        variants.append("VMAX")
    elif "-V" in normalized or " V " in f" {normalized} ":
        variants.append("V")
    if any(marker in normalized for marker in ("Ancient", "Future")):
        if "Ancient" in normalized:
            variants.append("Ancient")
        if "Future" in normalized:
            variants.append("Future")
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


def _scrape_limitless_card(soup, url, set_name=None):
    raw_title = _card_page_metadata(soup)
    if raw_title is None:
        raise ValueError(f"Limitless page is missing a title: {url}")

    name = raw_title
    for split_value in (" — ", " - ", " | "):
        if split_value in name:
            name = name.split(split_value, 1)[0]
            break

    name = re.sub(r"\s*\([^)]*\)$", "", name).strip()
    name = clean_text(name)
    if not name:
        raise ValueError(f"Limitless page has an empty title: {url}")

    hp = None
    hp_match = re.search(r"\bHP\s*(\d+)\b", soup.get_text(" ", strip=True), flags=re.IGNORECASE)
    if hp_match:
        hp = int(hp_match.group(1))
        hp_text = hp_match.group(0)
    else:
        hp_text = None

    pokemon_type = _scan_text(soup, ["[data-type]", "[data-testid='type']", ".type"]) or None
    weakness = _scan_text(soup, ["[data-weakness]", "[data-testid='weakness']", ".weakness"]) or None
    resistance = _scan_text(soup, ["[data-resistance]", "[data-testid='resistance']", ".resistance"]) or None
    retreat_cost = None
    retreat_match = re.search(r"\bRetreat Cost\s*[:\-]?\s*(\d+)", soup.get_text(" ", strip=True), flags=re.IGNORECASE)
    if retreat_match:
        retreat_cost = int(retreat_match.group(1))

    card_number = _scan_text(soup, ["[data-card-number]", "[data-number]", ".card-number"]) or None
    rarity = _scan_text(soup, ["[data-rarity]", "[data-testid='rarity']", ".rarity"]) or None
    card_mark = _scan_text(soup, ["[data-regulation]", "[data-testid='regulation']", ".regulation"]) or None
    set_name = set_name or _scan_text(soup, ["[data-set]", "[data-testid='set']", ".set"]) or None
    if set_name:
        set_name = re.sub(r"^.*?\s+-\s+", "", set_name).strip()
        set_name = re.sub(r"\s*\(.*?\)$", "", set_name).strip() or set_name

    abilities = []
    moves = []
    for script in soup.find_all("script"):
        script_text = script.string or ""
        if not script_text.strip().startswith(("{", "[")):
            continue
        try:
            payload = json.loads(script_text)
        except (TypeError, ValueError):
            continue
        for value in _extract_json_literals(payload):
            if isinstance(value, dict):
                if "name" in value and "effectText" in value and not value.get("cost"):
                    abilities.append({"name": value.get("name"), "effect_text": value.get("effectText")})
                if "name" in value and "text" in value and "cost" in value:
                    moves.append({
                        "name": value.get("name"),
                        "cost": value.get("cost", {}),
                        "damage": value.get("damage"),
                        "damage_modifier": None,
                        "damage_text": value.get("damageText"),
                        "effect_text": value.get("text"),
                    })

    if not abilities and not moves:
        body_text = clean_text(soup.get_text(" ", strip=True))
        if re.search(r"\bAbilities\b", body_text, flags=re.IGNORECASE):
            for section in soup.select("section, article, div"):
                section_text = clean_text(section.get_text(" ", strip=True))
                if not re.search(r"\bAbilities\b", section_text, flags=re.IGNORECASE):
                    continue
                for item in section.select("li, tr, p, div"):
                    item_text = clean_text(item.get_text(" ", strip=True))
                    if not item_text or item_text.lower() == "abilities":
                        continue
                    if ":" in item_text:
                        title, effect = item_text.split(":", 1)
                        abilities.append({"name": clean_text(title), "effect_text": clean_text(effect)})

    return {
        "name": name,
        "name_with_set": f"{name} ({set_name})" if set_name else name,
        "card_type": "pokemon",
        "card_variants": _extract_card_variants(name),
        "evolution_stage": None,
        "previous_evolution": None,
        "hp": hp,
        "hp_text": hp_text,
        "type": pokemon_type,
        "weakness": weakness,
        "resistance": resistance,
        "retreat_cost": retreat_cost,
        "abilities": abilities,
        "moves": moves,
        "card_number": card_number,
        "card_mark": card_mark,
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
        try:
            card = _scrape_limitless_card(soup, url, set_name=set_name)
            if card.get("moves") or card.get("abilities") or card.get("type") or card.get("card_number"):
                return card
        except ValueError:
            pass
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
