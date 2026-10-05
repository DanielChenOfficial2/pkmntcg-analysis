"""Scrape Pokemon card facts from Limitless TCG into a JSON interchange file."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


DATA_BUILDING_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = DATA_BUILDING_ROOT / "data" / "raw" / "pokemon_cards.json"

LIMITLESS_BASE_URL = "https://limitlesstcg.com"

DEFAULT_SEARCH_URL = (
    "https://limitlesstcg.com/cards"
    "?q=regulation%3E%3DH"
    "&show=all"
    "&unique=cards"
    "&display=text"
)

TEST_SEARCH_URL = (
    "https://limitlesstcg.com/cards"
    "?q=regulation%3E%3DH"
    "&show=50"
    "&unique=cards"
    "&display=text"
)


def _validate_cards(cards):
    warnings = []

    valid_pokemon_types = {
        "Grass",
        "Fire",
        "Water",
        "Lightning",
        "Psychic",
        "Fighting",
        "Darkness",
        "Metal",
        "Dragon",
        "Colorless",
    }

    valid_evolution_stages = {
        "Basic",
        "Stage 1",
        "Stage 2",
    }

    valid_energy_symbols = {
        "C",
        "G",
        "R",
        "W",
        "L",
        "P",
        "F",
        "D",
        "M",
    }

    seen_identities = set()

    for index, card in enumerate(cards, start=1):
        name = card.get("name") or "<unknown>"
        set_code = card.get("set")
        card_number = card.get("card_number")

        prefix = (
            f"{set_code} #{card_number} ({name})"
            if set_code and card_number
            else f"card {index} ({name})"
        )

        # Common card fields

        if not card.get("name"):
            warnings.append(
                f"{prefix}: missing name"
            )

        if not card.get("set"):
            warnings.append(
                f"{prefix}: missing set"
            )

        if not card.get("card_number"):
            warnings.append(
                f"{prefix}: missing card number"
            )

        if not card.get("source_url"):
            warnings.append(
                f"{prefix}: missing source URL"
            )

        # Duplicate card identity

        identity = (
            card.get("set"),
            card.get("card_number"),
        )

        if identity in seen_identities:
            warnings.append(
                f"{prefix}: duplicate set/card number"
            )
        else:
            seen_identities.add(identity)

        # Card type

        if card.get("card_type") == "Pokemon":
            hp = card.get("hp")

            if not isinstance(hp, int) or hp <= 0:
                warnings.append(
                    f"{prefix}: invalid HP: {hp!r}"
                )

            pokemon_type = card.get("type")

            if pokemon_type not in valid_pokemon_types:
                warnings.append(
                    f"{prefix}: invalid Pokémon type: "
                    f"{pokemon_type!r}"
                )

            evolution_stage = card.get("evolution_stage")

            if evolution_stage not in valid_evolution_stages:
                warnings.append(
                    f"{prefix}: invalid evolution stage: "
                    f"{evolution_stage!r}"
                )

            retreat_cost = card.get("retreat_cost")

            if not isinstance(retreat_cost, int) or retreat_cost < 0:
                warnings.append(
                    f"{prefix}: invalid retreat cost: "
                    f"{retreat_cost!r}"
                )

            # Abilities

            for ability in card.get("abilities", []):
                if not ability.get("name"):
                    warnings.append(
                        f"{prefix}: ability is missing name"
                    )

                if not ability.get("effect_text"):
                    warnings.append(
                        f"{prefix}: ability "
                        f"{ability.get('name')!r} is missing effect text"
                    )

            # Attacks

            for attack in card.get("moves", []):
                attack_name = attack.get("name")

                if not attack_name:
                    warnings.append(
                        f"{prefix}: attack is missing name"
                    )

                cost = attack.get("cost")

                if cost:
                    invalid_symbols = set(cost) - valid_energy_symbols

                    if invalid_symbols:
                        warnings.append(
                            f"{prefix}: attack "
                            f"{attack_name!r} has invalid energy cost "
                            f"{cost!r}"
                        )

                damage = attack.get("damage")

                if damage is not None:
                    if not isinstance(damage, int) or damage < 0:
                        warnings.append(
                            f"{prefix}: attack "
                            f"{attack_name!r} has invalid damage "
                            f"{damage!r}"
                        )

                damage_modifier = attack.get("damage_modifier")

                if damage_modifier not in (None, "+", "×"):
                    warnings.append(
                        f"{prefix}: attack "
                        f"{attack_name!r} has invalid damage modifier "
                        f"{damage_modifier!r}"
                    )

    return warnings

def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _page_soup(url, session=None):
    getter = session.get if session is not None else requests.get

    try:
        response = getter(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError(f"Could not fetch page {url}: {error}") from error

    return BeautifulSoup(response.content, "html.parser")


def _parse_limitless_attack(info_tag, effect_tag):
    symbol = info_tag.select_one(".ptcg-symbol")
    cost = (
        clean_text(symbol.get_text(" ", strip=True))
        if symbol is not None
        else None
    )

    raw_text = clean_text(info_tag.get_text(" ", strip=True))

    if cost:
        raw_text = raw_text.replace(cost, "", 1).strip()

    damage = None
    damage_modifier = None
    # damage_text = None

    match = re.match(
        r"^(?P<name>.+?)\s+(?P<damage>\d+)(?P<modifier>[+×])?$",
        raw_text,
    )

    if match:
        raw_text = match.group("name")
        damage = int(match.group("damage"))
        damage_modifier = match.group("modifier")
        # damage_text = f"{match.group('damage')}{damage_modifier or ''}"

    effect_text = (
        clean_text(effect_tag.get_text(" ", strip=True))
        if effect_tag is not None
        else None
    )

    return {
        "name": raw_text or None,
        "cost": cost,
        "damage": damage,
        "damage_modifier": damage_modifier,
        # "damage_text": damage_text,
        "effect_text": effect_text or None,
    }


def _extract_limitless_wrr(card):
    wrr_block = card.select_one(".card-text-wrr")

    if wrr_block is None:
        return None, None, None

    text = clean_text(wrr_block.get_text(" ", strip=True))

    weakness = None
    resistance = None
    retreat_cost = None

    weakness_match = re.search(
        r"Weakness\s*:\s*(.*?)(?=\s*Resistance\s*:|\s*Retreat\s*:|$)",
        text,
        flags=re.IGNORECASE,
    )

    if weakness_match:
        weakness = clean_text(weakness_match.group(1))

    resistance_match = re.search(
        r"Resistance\s*:\s*(.*?)(?=\s*Retreat\s*:|$)",
        text,
        flags=re.IGNORECASE,
    )

    if resistance_match:
        resistance = clean_text(resistance_match.group(1))

    if resistance and resistance.lower() == "none":
        resistance = None

    retreat_match = re.search(
        r"Retreat\s*:\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )

    if retreat_match:
        retreat_cost = int(retreat_match.group(1))

    return weakness, resistance, retreat_cost


def _extract_card_variants(name):
    variants = []
    normalized = clean_text(name or "").lower()

    if normalized.endswith(" ex") or "-ex" in normalized:
        variants.append("ex")

    return variants


def _parse_limitless_card(card):
    title_block = card.select_one(".card-text-title")
    type_block = card.select_one(".card-text-type")
    set_info = card.select_one(".card-set-info")
    name_tag = card.select_one(".card-text-name a")

    if title_block is None:
        raise ValueError("Card is missing title information")

    if type_block is None:
        raise ValueError("Card is missing type information")

    if set_info is None:
        raise ValueError("Card is missing set information")

    if name_tag is None:
        raise ValueError("Card is missing card name/link")

    name = clean_text(name_tag.get_text(" ", strip=True))

    source_url = urljoin(
        LIMITLESS_BASE_URL,
        name_tag.get("href", ""),
    )

    title_text = clean_text(title_block.get_text(" ", strip=True))

    hp = None
    pokemon_type = None

    hp_match = re.search(r"(\d+)\s*HP\s*$", title_text)

    if hp_match:
        hp = int(hp_match.group(1))

        type_text = title_text[:hp_match.start()].strip()
        type_text = type_text.rstrip("-").strip()

        if " - " in type_text:
            pokemon_type = type_text.rsplit(" - ", 1)[-1].strip()
        else:
            pokemon_type = type_text or None

    type_text = clean_text(type_block.get_text(" ", strip=True))

    if not re.match(r"^Pokémon\b", type_text, flags=re.IGNORECASE):
        raise ValueError(f"Card is not a Pokémon card: {name}")

    evolution_stage = None
    previous_evolution = None

    stage_match = re.search(
        r"\b(Basic|Stage 1|Stage 2)\b",
        type_text,
        flags=re.IGNORECASE,
    )

    if stage_match:
        evolution_stage = stage_match.group(1)

    evolves_from = type_block.find(
        string=re.compile(r"Evolves from", flags=re.IGNORECASE)
    )

    if evolves_from is not None:
        evolution_link = evolves_from.find_next("a")

        if evolution_link is not None:
            previous_evolution = clean_text(
                evolution_link.get_text(" ", strip=True)
            )

    weakness, resistance, retreat_cost = _extract_limitless_wrr(card)

    abilities = []

    for ability_block in card.select(".card-text-ability"):
        info = ability_block.select_one(".card-text-ability-info")
        effect = ability_block.select_one(".card-text-ability-effect")

        if info is None:
            continue

        ability_name = clean_text(
            info.get_text(" ", strip=True)
        )

        ability_name = re.sub(
            r"^Ability\s*:\s*",
            "",
            ability_name,
            flags=re.IGNORECASE,
        ).strip()

        effect_text = (
            clean_text(effect.get_text(" ", strip=True))
            if effect is not None
            else None
        )

        abilities.append(
            {
                "name": ability_name or None,
                "effect_text": effect_text or None,
            }
        )

    moves = []

    for attack_block in card.select(".card-text-attack"):
        info = attack_block.select_one(".card-text-attack-info")
        effect = attack_block.select_one(".card-text-attack-effect")

        if info is None:
            continue

        moves.append(
            _parse_limitless_attack(info, effect)
        )

    set_info_text = clean_text(
        set_info.get_text(" ", strip=True)
    )

    set_match = re.match(
        r"^(.*?)\s+#\s*(\d+)\s*$",
        set_info_text,
    )

    if set_match:
        set_code = clean_text(set_match.group(1))
        card_number = set_match.group(2)
    else:
        set_code = set_info_text or None
        card_number = None

    # name_with_set = (
    #     f"{name} ({set_code})"
    #     if set_code
    #     else name
    # )

    return {
        "name": name,
        # "name_with_set": name_with_set,
        "card_type": "Pokemon",
        "card_variants": _extract_card_variants(name),
        "evolution_stage": evolution_stage,
        "previous_evolution": previous_evolution,
        "hp": hp,
        "type": pokemon_type,
        "weakness": weakness,
        "resistance": resistance,
        "retreat_cost": retreat_cost,
        "abilities": abilities,
        "moves": moves,
        "card_number": card_number,
        "card_mark": None,
        "rarity": None,
        "set": set_code,
        "source_url": source_url,
    }


def _parse_limitless_card_page(soup, url):
    card = soup.select_one(".card")

    if card is None:
        raise ValueError(
            f"Individual card page is missing card wrapper: {url}"
        )

    return _parse_limitless_card(card)


def _limitless_search_cards(search_url):
    cards = []
    seen = set()
    page = 1

    while True:
        parsed = urlsplit(search_url)

        query = re.sub(
            r"(^|&)page=\d+",
            "",
            parsed.query,
        ).strip("&")

        if page > 1:
            query = f"{query}&page={page}" if query else f"page={page}"

        page_url = parsed._replace(query=query).geturl()

        print(
            f"Fetching Limitless search page {page}: {page_url}",
            file=sys.stderr,
        )

        soup = _page_soup(page_url)
        page_cards = soup.select(".cards-text .card")

        if not page_cards:
            break

        for card_element in page_cards:
            try:
                card = _parse_limitless_card(card_element)
            except ValueError as error:
                print(
                    f"Skipping card on search page {page}: {error}",
                    file=sys.stderr,
                )
                continue

            identity = (
                card.get("set"),
                card.get("card_number"),
            )

            if identity in seen:
                continue

            seen.add(identity)
            cards.append(card)

        show_match = re.search(
            r"(?:^|&)show=(\d+)(?:&|$)",
            parsed.query,
        )

        if show_match:
            page_size = int(show_match.group(1))

            if len(page_cards) < page_size:
                break

        page += 1

    return cards


def _extract_regulation_mark(soup):
    regulation_tag = soup.select_one(".regulation-mark")

    if regulation_tag is None:
        return None

    text = clean_text(
        regulation_tag.get_text(" ", strip=True)
    )

    match = re.search(
        r"([A-Z0-9]+)\s+Regulation\s+Mark",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return text.split()[0] if text else None


def _populate_set_metadata(cards):
    cards_by_set = {}

    for card in cards:
        set_code = card.get("set")

        if not set_code:
            continue

        cards_by_set.setdefault(set_code, []).append(card)

    total_sets = len(cards_by_set)

    for index, (set_code, set_cards) in enumerate(
        cards_by_set.items(),
        start=1,
    ):
        representative = set_cards[0]
        source_url = representative.get("source_url")

        if not source_url:
            print(
                f"[{index}/{total_sets}] Set {set_code}: no source URL",
                file=sys.stderr,
            )
            continue

        print(
            f"[{index}/{total_sets}] Getting regulation mark for set {set_code}",
            end="",
            flush=True,
            file=sys.stderr,
        )

        try:
            soup = _page_soup(source_url)
            regulation_mark = _extract_regulation_mark(soup)
        except ValueError as error:
            print(
                f"\r\033[K[{index}/{total_sets}] "
                f"Failed metadata for set {set_code}: {error}",
                file=sys.stderr,
            )
            continue

        print(
            f"\r\033[K[{index}/{total_sets}] "
            f"Set {set_code}: regulation mark = {regulation_mark}",
            file=sys.stderr,
        )

        for card in set_cards:
            card["card_mark"] = regulation_mark


def scrape_all_pokemon_cards(search_url):
    print(
        "Scraping cards from Limitless text search...",
        file=sys.stderr,
    )

    cards = _limitless_search_cards(search_url)

    print(
        f"Found {len(cards)} Pokémon cards.",
        file=sys.stderr,
    )

    print(
        "Fetching one representative card per set for regulation marks...",
        file=sys.stderr,
    )

    _populate_set_metadata(cards)

    print(
        "Validating scraped cards...",
        file=sys.stderr,
    )

    warnings = _validate_cards(cards)

    if warnings:
        print(
            f"Found {len(warnings)} validation warning(s):",
            file=sys.stderr,
        )

        for warning in warnings:
            print(
                f"  WARNING: {warning}",
                file=sys.stderr,
            )
    else:
        print(
            "Validation passed with no warnings.",
            file=sys.stderr,
        )

    return cards


def write_cards(cards, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "schema_version": 1,
                "cards": cards,
            },
            output_file,
            ensure_ascii=False,
            indent=2,
        )

        output_file.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Pokemon cards from Limitless TCG into JSON."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file.",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Scrape the first 50 search results.",
    )

    parser.add_argument(
        "--card-url",
        help="Scrape one Limitless card page, useful for testing.",
    )

    args = parser.parse_args()

    try:
        if args.card_url:
            soup = _page_soup(args.card_url)

            card = _parse_limitless_card_page(
                soup,
                args.card_url,
            )

            card["card_mark"] = _extract_regulation_mark(soup)

            cards = [card]

        elif args.test:
            cards = scrape_all_pokemon_cards(
                TEST_SEARCH_URL
            )

        else:
            cards = scrape_all_pokemon_cards(
                DEFAULT_SEARCH_URL
            )

        write_cards(
            cards,
            args.output,
        )

    except (requests.RequestException, ValueError) as error:
        parser.exit(
            1,
            f"Scraping failed: {error}\n",
        )

    print(
        f"Wrote {len(cards)} Pokémon cards to {args.output}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()