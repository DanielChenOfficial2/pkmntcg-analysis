#!/usr/bin/env python3
"""Extract, review, and classify Pokémon card effects."""

import argparse
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = (
    SCRIPT_DIR.parent.parent
    / "data-building"
    / "data"
    / "raw"
    / "pokemon_cards.json"
)
DEFAULT_OUTPUT = SCRIPT_DIR / "effects_to_review.json"

CLASSIFICATIONS = {
    "o": "offensive",
    "d": "defensive",
    "b": "both",
    "x": "neither",
}
VALID_CLASSIFICATIONS = set(CLASSIFICATIONS.values())

# Conservative starter rules. Add new patterns here when you encounter an
# effect the script cannot classify. Unmatched or conflicting effects require
# manual classification. These are suggestions, never silently auto-approved.
AUTO_RULES = [
    (
        "defensive_damage_prevention",
        r"\b(?:prevent all damage|prevent any damage|prevent damage done to|"
        r"takes no damage from attacks|damage done to this pok[eé]mon is "
        r"reduced by|reduce the damage done to this pok[eé]mon by|"
        r"prevent all effects of attacks)\b",
        "defensive",
    ),
    (
        "defensive_healing",
        r"\b(?:heal \d+ damage from|heal all damage from|"
        r"remove \d+ damage counters from this pok[eé]mon|"
        r"remove all damage counters from this pok[eé]mon)\b",
        "defensive",
    ),
    (
        "offensive_damage_bonus",
        r"\b(?:this attack does \d+ more damage|"
        r"damage done by this attack is increased by|"
        r"add \d+ damage to this attack|"
        r"this attack does \d+ damage for each)\b",
        "offensive",
    ),
    (
        "offensive_direct_damage",
        r"\b(?:put \d+ damage counters? on your opponent's|"
        r"put \d+ damage counters? on the defending pok[eé]mon|"
        r"this attack does \d+ damage)\b",
        "offensive",
    ),
    (
        "neither_draw_search",
        r"\b(?:draw \d+ cards?|search your deck for|shuffle your deck|"
        r"look at the top \d+ cards? of your deck)\b",
        "neither",
    ),
]


def normalize_effect(text):
    """Normalize whitespace for matching effect text."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def effect_key(effect):
    """Identify an individual effect, including its position on the card."""
    return (
        effect.get("source_url"),
        effect.get("card_type"),
        effect.get("entry_index"),
        effect.get("entry_name"),
        normalize_effect(effect["effect_text"]),
    )


def legacy_effect_key(effect):
    """Support review decisions saved by older script versions."""
    return (
        effect.get("source_url"),
        effect.get("card_type"),
        effect.get("entry_name"),
        normalize_effect(effect["effect_text"]),
    )


def classify_effect_automatically(text):
    """Return (classification, rule_name), or (None, None) if uncertain."""
    normalized = normalize_effect(text).casefold()
    matches = []
    for rule_name, pattern, classification in AUTO_RULES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            matches.append((classification, rule_name))

    # Avoid making a guess if rules for different categories match.
    categories = {classification for classification, _ in matches}
    if not matches or len(categories) != 1:
        return None, None
    return matches[0]


def extract_effects(cards):
    """Collect individual ability, move, and Trainer effects."""
    results = []
    for card in cards:
        common = {
            "card_name": card.get("name", "Unknown card"),
            "set": card.get("set"),
            "card_number": card.get("card_number"),
            "source_url": card.get("source_url"),
        }

        for field, output_type in (("abilities", "Ability"), ("moves", "Move")):
            for index, entry in enumerate(card.get(field) or []):
                if not isinstance(entry, dict):
                    continue
                text = entry.get("effect_text")
                if not isinstance(text, str) or not text.strip():
                    continue
                results.append({
                    **common,
                    "card_type": output_type,
                    "entry_index": index,
                    "entry_name": entry.get("name"),
                    "effect_text": text.strip(),
                })

        # Trainer effects are stored at the card level.
        if str(card.get("card_type", "")).lower() == "trainer":
            text = card.get("effect_text")
            if isinstance(text, str) and text.strip():
                results.append({
                    **common,
                    "card_type": "Trainer",
                    "entry_index": 0,
                    "entry_name": card.get("name"),
                    "effect_text": text.strip(),
                })
    return results


def load_cards(path, parser):
    """Load cards from a JSON list or an object containing 'cards'."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    cards = data.get("cards") if isinstance(data, dict) else data
    if not isinstance(cards, list):
        parser.error(
            "Input JSON must contain a list of cards, either directly or under the 'cards' key."
        )
    return cards


def load_existing(path):
    """Load previously saved review entries."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of effect records.")
    return data


def collect_decisions(existing):
    """Recover saved support and classification decisions."""
    decisions = {}
    for effect in existing:
        if not isinstance(effect, dict) or not isinstance(effect.get("effect_text"), str):
            continue
        saved = {}
        supported = effect.get("supported")
        if isinstance(supported, bool):
            saved["supported"] = supported
        classification = effect.get("classification")
        if classification in VALID_CLASSIFICATIONS:
            saved["classification"] = classification
            # Existing classifications are treated as reviewed for compatibility.
            saved["classification_reviewed"] = effect.get("classification_reviewed", True)
        if not saved:
            continue
        key = effect_key(effect) if "entry_index" in effect else legacy_effect_key(effect)
        decisions[key] = saved
    return decisions


def apply_decisions(effects, decisions):
    """Restore saved decisions and refresh suggestions without overwriting them."""
    for effect in effects:
        saved = decisions.get(effect_key(effect))
        if saved is None:
            saved = decisions.get(legacy_effect_key(effect), {})

        if "supported" in saved:
            effect["supported"] = saved["supported"]
        else:
            effect.pop("supported", None)

        if "classification" in saved:
            effect["classification"] = saved["classification"]
            effect["classification_reviewed"] = saved.get("classification_reviewed", True)
        else:
            effect.pop("classification", None)
            effect["classification_reviewed"] = False

        automatic, rule = classify_effect_automatically(effect["effect_text"])
        effect["auto_classification"] = automatic
        effect["auto_rule"] = rule

        if effect.get("supported") is False:
            effect["classification"] = "neither"
            effect["classification_reviewed"] = True


def save_effects(path, effects):
    """Write current review progress to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(effects, file, indent=2, ensure_ascii=False)
        file.write("\n")


def ask_supported():
    """Ask whether an effect is supported by the calculator."""
    while True:
        try:
            answer = input("Supported? [y/n/s/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer in ("s", "skip"):
            return "skip"
        if answer in ("q", "quit"):
            return "quit"
        print("Please enter y, n, s, or q.")


def ask_classification(automatic=None):
    """Approve an automatic suggestion or choose a classification manually."""
    if automatic:
        print(f"Automatic suggestion: {automatic}")
        print("  Enter = approve suggestion")
    else:
        print("No automatic suggestion; please classify manually.")
    print("  o = offensive; d = defensive; b = both; x = neither")
    print("  s = skip classification; q = save and quit")

    while True:
        try:
            answer = input("Classification [Enter/o/d/b/x/s/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        if answer == "" and automatic:
            return automatic
        if answer in CLASSIFICATIONS:
            return CLASSIFICATIONS[answer]
        if answer in ("s", "skip"):
            return "skip"
        if answer in ("q", "quit"):
            return "quit"
        if answer == "" and not automatic:
            print("No suggestion is available. Choose o, d, b, x, s, or q.")
        else:
            print("Please enter Enter, o, d, b, x, s, or q.")


def review_effects(effects, output_path):
    """Review each effect and save decisions immediately."""
    total = len(effects)
    print(f"\nIndividual effects: {total}")
    print("Press Enter to approve an automatic classification.")
    print("Use o/d/b/x to override it. Unmatched effects need manual classification.\n")

    for index, effect in enumerate(effects, start=1):
        if effect.get("supported") is False:
            effect["classification"] = "neither"
            effect["classification_reviewed"] = True
            save_effects(output_path, effects)
            continue

        supported_done = isinstance(effect.get("supported"), bool)
        classification_done = (
            effect.get("classification") in VALID_CLASSIFICATIONS
            and effect.get("classification_reviewed") is True
        )
        if supported_done and classification_done:
            continue

        print("=" * 72)
        print(f"Effect {index}/{total}")
        print(f"Category: {effect['card_type']}")
        print(f"Name:     {effect.get('entry_name') or '(unnamed)'}")
        print(f"Card:     {effect['card_name']}")
        print(f"Set/card: {effect.get('set')} / {effect.get('card_number')}")
        print(f"Effect:   {effect['effect_text']}")
        print(f"Source:   {effect.get('source_url')}")
        print(f"Supported: {effect.get('supported', 'not reviewed')}")
        print(f"Automatic classification: {effect.get('auto_classification') or 'no confident match'}")
        if effect.get("auto_rule"):
            print(f"Matched rule: {effect['auto_rule']}")
        print(f"Saved classification: {effect.get('classification', 'not reviewed')}\n")

        if not supported_done:
            answer = ask_supported()
            if answer == "quit":
                save_effects(output_path, effects)
                print("\nReview stopped. Progress saved.")
                return
            if answer != "skip":
                effect["supported"] = answer
            save_effects(output_path, effects)
            if effect.get("supported") is False:
                effect["classification"] = "neither"
                effect["classification_reviewed"] = True
                save_effects(output_path, effects)
                continue

        if effect.get("supported") is False:
            effect["classification"] = "neither"
            effect["classification_reviewed"] = True
            save_effects(output_path, effects)
            continue

        classification_done = (
            effect.get("classification") in VALID_CLASSIFICATIONS
            and effect.get("classification_reviewed") is True
        )
        if not classification_done:
            answer = ask_classification(effect.get("auto_classification"))
            if answer == "quit":
                save_effects(output_path, effects)
                print("\nReview stopped. Progress saved.")
                return
            if answer != "skip":
                effect["classification"] = answer
                effect["classification_reviewed"] = True
            save_effects(output_path, effects)

    save_effects(output_path, effects)
    print("\nReview complete.")


# Adapted version of the old can_use_card() condition logic.
RULE_BOX_TYPES = {"ex", "V", "VMAX", "VSTAR"}


def _as_list(value):
    """Treat a list as-is and a scalar as a one-element list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _format_condition_parts(parts):
    return " and " + " and ".join(parts) if parts else ""


def parse_card_conditions(pokemon, enemy_pokemon, card_condition):
    """Check card-metadata conditions; describe live-state requirements only.

    Card records are dictionaries in the current JSON schema. Legacy condition
    keys are accepted. Prize Cards and Lost Zone Min Cards are not evaluated
    because this helper has no live game-state information.
    """
    condition_parts = []
    pokemon_card_types = set(str(v) for v in _as_list(
        pokemon.get("card_subtypes", pokemon.get("Card Type", []))
    ))

    for key, value in card_condition.items():
        if key == "Pkmn Card Type":
            eligible = set(str(v) for v in _as_list(value))
            if not pokemon_card_types.intersection(eligible):
                return False, _format_condition_parts(condition_parts)
        elif key == "Enemy Pkmn Card Type":
            if not isinstance(enemy_pokemon, dict):
                return False, _format_condition_parts(condition_parts)
            enemy_card_types = set(str(v) for v in _as_list(
                enemy_pokemon.get("card_subtypes", enemy_pokemon.get("Card Type", []))
            ))
            eligible = set(str(v) for v in _as_list(value))
            if not enemy_card_types.intersection(eligible):
                return False, _format_condition_parts(condition_parts)
        elif key == "Prize Cards":
            if value == "more":
                condition_parts.append(
                    "this card's player must have more Prize cards than the opposing player's"
                )
        elif key == "Rule Box":
            has_rule_box = bool(pokemon_card_types.intersection(RULE_BOX_TYPES))
            if value == "None" and has_rule_box:
                return False, _format_condition_parts(condition_parts)
        elif key == "Evolution":
            stage = pokemon.get("evolution_stage", pokemon.get("Evolution Stage"))
            if value != stage:
                return False, _format_condition_parts(condition_parts)
        elif key == "Type":
            pokemon_type = pokemon.get("type", pokemon.get("Type"))
            if value != pokemon_type:
                return False, _format_condition_parts(condition_parts)
        elif key == "Enemy Pkmn Type":
            if not isinstance(enemy_pokemon, dict):
                return False, _format_condition_parts(condition_parts)
            enemy_type = enemy_pokemon.get("type", enemy_pokemon.get("Type"))
            if enemy_type not in _as_list(value):
                return False, _format_condition_parts(condition_parts)
        elif key == "Lost Zone Min Cards":
            condition_parts.append(f"you must have at least {value} cards in your Lost Zone")
        else:
            raise ValueError(f"Unknown card condition key: {key!r}")

    return True, _format_condition_parts(condition_parts)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract Pokémon card effects and review support "
            "and offensive/defensive classifications."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"Input JSON file (default: {DEFAULT_INPUT})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Review JSON file (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    try:
        cards = load_cards(args.input, parser)
        existing = load_existing(args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    effects = extract_effects(cards)
    decisions = collect_decisions(existing)
    apply_decisions(effects, decisions)
    save_effects(args.output, effects)

    supported_count = sum(isinstance(e.get("supported"), bool) for e in effects)
    reviewed_count = sum(
        e.get("classification") in VALID_CLASSIFICATIONS
        and e.get("classification_reviewed") is True
        for e in effects
    )
    automatic_count = sum(e.get("auto_classification") in VALID_CLASSIFICATIONS for e in effects)

    print(f"Cards processed: {len(cards)}")
    print(f"Effect entries: {len(effects)}")
    print(f"Automatic suggestions: {automatic_count}/{len(effects)}")
    print(f"Support decisions saved: {supported_count}/{len(effects)}")
    print(f"Reviewed classifications saved: {reviewed_count}/{len(effects)}")

    review_effects(effects, args.output)

    supported_count = sum(isinstance(e.get("supported"), bool) for e in effects)
    reviewed_count = sum(
        e.get("classification") in VALID_CLASSIFICATIONS
        and e.get("classification_reviewed") is True
        for e in effects
    )
    print(f"\nSupport decisions: {supported_count}/{len(effects)}")
    print(f"Reviewed classifications: {reviewed_count}/{len(effects)}")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
