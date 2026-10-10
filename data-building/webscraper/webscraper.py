
"""Scrape Pokemon card facts from Limitless TCG into a JSON interchange file."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

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


def _build_set_search_url(set_code):
    set_code = set_code.upper()

    params = {
        "q": f"!set:{set_code}",
        "show": "all",
        "unique": "cards",
        "display": "text",
    }

    return f"{LIMITLESS_BASE_URL}/cards?{urlencode(params)}"


def _load_cards(input_path):
    if not input_path.exists():
        raise ValueError(f"Dataset does not exist: {input_path}")

    try:
        with input_path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Could not read dataset {input_path}: {error}"
        ) from error

    if not isinstance(data, dict) or "cards" not in data:
        raise ValueError(f"Invalid dataset format: {input_path}")

    return data["cards"]


def _add_set(cards, set_code):
    set_code = set_code.upper()
    search_url = _build_set_search_url(set_code)

    print(f"Scraping set {set_code}...", file=sys.stderr)

    new_cards = _limitless_search_cards(search_url)

    if not new_cards:
        raise ValueError(f"No cards found for set {set_code}")

    found_sets = {card.get("set") for card in new_cards}

    if set_code not in found_sets:
        raise ValueError(
            f"Limitless returned no cards for set {set_code}"
        )

    new_cards = [
        card for card in new_cards
        if card.get("set") == set_code
    ]

    print(
        f"Found {len(new_cards)} cards in set {set_code}.",
        file=sys.stderr,
    )

    _populate_set_metadata(new_cards)

    cards = [
        card for card in cards
        if card.get("set") != set_code
    ]

    cards.extend(new_cards)

    return cards


def _remove_mark(cards, regulation_mark):
    regulation_mark = regulation_mark.upper()
    original_count = len(cards)

    cards = [
        card for card in cards
        if (card.get("card_mark") or "").upper() != regulation_mark
    ]

    removed_count = original_count - len(cards)

    print(
        f"Removed {removed_count} cards with regulation mark "
        f"{regulation_mark}.",
        file=sys.stderr,
    )

    return cards


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

    valid_trainer_types = {
        "Item",
        "Supporter",
        "Tool",
        "Stadium",
    }

    valid_energy_types = {
        "Basic Energy",
        "Special Energy",
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
            warnings.append(f"{prefix}: missing name")

        if not card.get("set"):
            warnings.append(f"{prefix}: missing set")

        if not card.get("card_number"):
            warnings.append(f"{prefix}: missing card number")

        if not card.get("source_url"):
            warnings.append(f"{prefix}: missing source URL")

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

        # Pokémon-specific fields

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
                    invalid_symbols = (
                        set(cost) - valid_energy_symbols
                    )

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

        # Trainer-specific fields

        elif card.get("card_type") == "Trainer":
            trainer_type = card.get("trainer_type")

            if trainer_type not in valid_trainer_types:
                warnings.append(
                    f"{prefix}: invalid Trainer subtype: "
                    f"{trainer_type!r}"
                )

            if not card.get("effect_text"):
                warnings.append(
                    f"{prefix}: Trainer card is missing effect text"
                )

        # Energy-specific fields

        elif card.get("card_type") == "Energy":
            energy_type = card.get("energy_type")

            if energy_type not in valid_energy_types:
                warnings.append(
                    f"{prefix}: invalid Energy subtype: "
                    f"{energy_type!r}"
                )

            if not card.get("effect_text"):
                warnings.append(
                    f"{prefix}: Energy card is missing effect text"
                )

        else:
            warnings.append(
                f"{prefix}: unknown card type: "
                f"{card.get('card_type')!r}"
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
        raise ValueError(
            f"Could not fetch page {url}: {error}"
        ) from error

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

    match = re.match(
        r"^(?P<name>.+?)\s+(?P<damage>\d+)(?P<modifier>[+×])?$",
        raw_text,
    )

    if match:
        raw_text = match.group("name")
        damage = int(match.group("damage"))
        damage_modifier = match.group("modifier")

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

    if weakness and weakness.lower() == "none":
        weakness = None

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


def _extract_card_variants(name, abilities=None):
    variants = []
    normalized = clean_text(name or "").lower()

    if normalized.endswith(" ex") or "-ex" in normalized:
        variants.append("ex")

    if re.search(r"\bmega\b", normalized, flags=re.IGNORECASE):
        variants.append("Mega")

    if any(
        clean_text(ability.get("name")).lower() == "tera"
        for ability in (abilities or [])
    ):
        variants.append("Tera")

    return variants


def _extract_trainer_type(type_text):
    match = re.search(
        r"\b(Item|Supporter|Tool|Stadium)\b",
        type_text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return match.group(1).title()


def _extract_energy_type(type_text):
    match = re.search(
        r"\b(Basic|Special)\s+Energy\b",
        type_text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return f"{match.group(1).title()} Energy"


def _extract_card_effect(card):
    sections = card.select(".card-text-section")

    # The first section contains the name and category.
    # The second section contains the effect text.
    if len(sections) < 2:
        return None

    effect_section = BeautifulSoup(
        str(sections[1]),
        "html.parser",
    )

    # Remove symbols' copy-only bracket decorations.
    for tag in effect_section.select(".copy-only"):
        tag.decompose()

    # Replace energy symbols with readable energy names.
    for symbol in effect_section.select(
        '.ptcg-symbol, [style*="ptcg-font"]'
    ):
        tooltip = symbol.get("data-tooltip")

        if tooltip:
            symbol.replace_with(f"[{tooltip}]")

    effect_text = clean_text(
        effect_section.get_text(" ", strip=True)
    )

    return effect_text or None


def _extract_set_and_number(set_info, name_tag):
    """Extract the set code and card number from the page or card URL."""
    if set_info is not None:
        set_info_text = clean_text(
            set_info.get_text(" ", strip=True)
        )

        match = re.match(
            r"^(.*?)\s+#\s*(\d+)\s*$",
            set_info_text,
        )

        if match:
            return clean_text(match.group(1)), match.group(2)

    if name_tag is not None:
        href = name_tag.get("href", "")
        path_parts = urlsplit(href).path.strip("/").split("/")

        if (
            len(path_parts) >= 3
            and path_parts[0] == "cards"
            and path_parts[1]
            and path_parts[2].isdigit()
        ):
            return path_parts[1].upper(), path_parts[2]

    raise ValueError(
        "Card is missing set and card number information"
    )


def _parse_limitless_non_pokemon_card(
    card,
    card_type,
    subtype_field,
    subtype,
):
    title_block = card.select_one(".card-text-title")
    type_block = card.select_one(".card-text-type")
    set_info = card.select_one(".card-set-info")
    name_tag = card.select_one(".card-text-name a")

    if title_block is None:
        raise ValueError("Card is missing title information")

    if type_block is None:
        raise ValueError("Card is missing type information")

    if name_tag is None:
        raise ValueError("Card is missing card name/link")

    name = clean_text(name_tag.get_text(" ", strip=True))

    source_url = urljoin(
        LIMITLESS_BASE_URL,
        name_tag.get("href", ""),
    )

    set_code, card_number = _extract_set_and_number(
        set_info,
        name_tag,
    )

    result = {
        "name": name,
        "card_type": card_type,
        "card_variants": [],
        "effect_text": _extract_card_effect(card),
        "card_number": card_number,
        "card_mark": None,
        "rarity": None,
        "set": set_code,
        "source_url": source_url,
    }

    result[subtype_field] = subtype

    return result


def _parse_limitless_pokemon_card(card):
    title_block = card.select_one(".card-text-title")
    type_block = card.select_one(".card-text-type")
    set_info = card.select_one(".card-set-info")
    name_tag = card.select_one(".card-text-name a")

    if title_block is None:
        raise ValueError("Card is missing title information")

    if type_block is None:
        raise ValueError("Card is missing type information")

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

        title_type_text = title_text[:hp_match.start()].strip()
        title_type_text = title_type_text.rstrip("-").strip()

        if " - " in title_type_text:
            pokemon_type = title_type_text.rsplit(" - ", 1)[-1].strip()
        else:
            pokemon_type = title_type_text or None

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
        stage_value = stage_match.group(1)
        evolution_stage = {
            "basic": "Basic",
            "stage 1": "Stage 1",
            "stage 2": "Stage 2",
        }[stage_value.casefold()]

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

        ability_name = clean_text(info.get_text(" ", strip=True))

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

        moves.append(_parse_limitless_attack(info, effect))

    set_code, card_number = _extract_set_and_number(
        set_info,
        name_tag,
    )

    return {
        "name": name,
        "card_type": "Pokemon",
        "card_variants": _extract_card_variants(name, abilities),
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


def _parse_limitless_card(card):
    """Parse a card from either a search result or a detail page."""
    # On detail pages, .card is an image. The text sections live
    # elsewhere in the document, so this function accepts either the
    # search-result card element or the full BeautifulSoup document.
    title_block = card.select_one(".card-text-title")
    type_block = card.select_one(".card-text-type")

    title_text = (
        clean_text(title_block.get_text(" ", strip=True))
        if title_block is not None
        else ""
    )

    type_text = (
        clean_text(type_block.get_text(" ", strip=True))
        if type_block is not None
        else ""
    )

    if not title_text and not type_text:
        raise ValueError("Card is missing title and type information")

    normalized_type = type_text.casefold()
    normalized_title = title_text.casefold()

    # Use the explicit category from the type section when available.
    # Pokémon type sections commonly start with "Pokémon", while
    # Trainer and Energy sections start with those category names.
    if re.search(r"\btrainer\b", normalized_type):
        subtype = _extract_trainer_type(type_text)

        if subtype is None:
            subtype = _extract_trainer_type(title_text)

        if subtype is None:
            raise ValueError(
                f"Could not determine Trainer subtype from: {type_text}"
            )

        return _parse_limitless_non_pokemon_card(
            card,
            "Trainer",
            "trainer_type",
            subtype,
        )

    if re.search(r"\benergy\b", normalized_type):
        subtype = _extract_energy_type(type_text)

        if subtype is None:
            subtype = _extract_energy_type(title_text)

        if subtype is None:
            raise ValueError(
                f"Could not determine Energy subtype from: {type_text}"
            )

        return _parse_limitless_non_pokemon_card(
            card,
            "Energy",
            "energy_type",
            subtype,
        )

    if (
        re.search(r"\bpok[eé]mon\b", normalized_type)
        or re.search(r"\b\d+\s*hp\b", normalized_title)
    ):
        return _parse_limitless_pokemon_card(card)

    # Some search-result layouts may omit the category prefix from
    # the type section. Use the card's title as a fallback.
    if "trainer" in normalized_title:
        subtype = _extract_trainer_type(title_text)

        if subtype is not None:
            return _parse_limitless_non_pokemon_card(
                card,
                "Trainer",
                "trainer_type",
                subtype,
            )

    if "energy" in normalized_title:
        subtype = _extract_energy_type(title_text)

        if subtype is not None:
            return _parse_limitless_non_pokemon_card(
                card,
                "Energy",
                "energy_type",
                subtype,
            )

    raise ValueError(
        f"Could not determine card category from: "
        f"{type_text} {title_text}"
    )


def _parse_limitless_card_page(soup, url):
    # On a Limitless detail page, ".card" selects the card image rather
    # than the text wrapper. Parse the full document instead.
    if soup.select_one(".card-text-section") is None:
        raise ValueError(
            f"Individual card page is missing card text sections: {url}"
        )

    return _parse_limitless_card(soup)


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

    text = clean_text(regulation_tag.get_text(" ", strip=True))

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
            f"[{index}/{total_sets}] Getting regulation mark "
            f"for set {set_code}",
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
        f"Found {len(cards)} cards.",
        file=sys.stderr,
    )

    print(
        "Fetching one representative card per set for regulation marks...",
        file=sys.stderr,
    )

    _populate_set_metadata(cards)

    print("Validating scraped cards...", file=sys.stderr)

    warnings = _validate_cards(cards)

    if warnings:
        print(
            f"Found {len(warnings)} validation warning(s):",
            file=sys.stderr,
        )

        for warning in warnings:
            print(f"  WARNING: {warning}", file=sys.stderr)
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

    parser.add_argument(
        "--add-set",
        metavar="SET",
        help="Add or replace all cards from a set.",
    )

    parser.add_argument(
        "--remove-mark",
        metavar="MARK",
        help="Remove all cards with a regulation mark.",
    )

    args = parser.parse_args()

    operation_count = sum(
        bool(value)
        for value in (
            args.test,
            args.card_url,
            args.add_set,
            args.remove_mark,
        )
    )

    if operation_count > 1:
        parser.error(
            "--test, --card-url, --add-set, and --remove-mark "
            "cannot be used together."
        )

    try:
        if args.card_url:
            soup = _page_soup(args.card_url)

            card = _parse_limitless_card_page(
                soup,
                args.card_url,
            )

            card["card_mark"] = _extract_regulation_mark(soup)

            cards = [card]

        elif args.add_set:
            cards = _load_cards(args.output)

            cards = _add_set(cards, args.add_set)

            warnings = _validate_cards(cards)

            if warnings:
                print(
                    f"Found {len(warnings)} validation warning(s):",
                    file=sys.stderr,
                )

                for warning in warnings:
                    print(f"  WARNING: {warning}", file=sys.stderr)
            else:
                print(
                    "Validation passed with no warnings.",
                    file=sys.stderr,
                )

        elif args.remove_mark:
            cards = _load_cards(args.output)

            cards = _remove_mark(cards, args.remove_mark)

            warnings = _validate_cards(cards)

            if warnings:
                print(
                    f"Found {len(warnings)} validation warning(s):",
                    file=sys.stderr,
                )

                for warning in warnings:
                    print(f"  WARNING: {warning}", file=sys.stderr)
            else:
                print(
                    "Validation passed with no warnings.",
                    file=sys.stderr,
                )

        elif args.test:
            cards = scrape_all_pokemon_cards(TEST_SEARCH_URL)

        else:
            cards = scrape_all_pokemon_cards(DEFAULT_SEARCH_URL)

        write_cards(cards, args.output)

    except (requests.RequestException, ValueError) as error:
        parser.exit(1, f"Scraping failed: {error}\n")

    print(
        f"Wrote {len(cards)} cards to {args.output}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
