#!/usr/bin/env python3

"""Extract, review, and classify Pokémon card effects."""

import argparse
import json
import re
import os
import tempfile
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
DEFAULT_SUPPORTED_OUTPUT = SCRIPT_DIR / "supported_effects.json"


CLASSIFICATIONS = {
    "o": "offensive",
    "d": "defensive",
    "b": "both",
    "x": "neither",
}
VALID_CLASSIFICATIONS = set(CLASSIFICATIONS.values())


# Each rule recognizes a kind of effect, not merely the first matching phrase.
# The classifier evaluates every rule over the whole text so composite effects
# (for example, damage plus protection on the next turn) are not truncated.
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
        "defensive_prevention_and_reduction",
        r"\b(?:takes? \d+ less damage|\d+ less damage from attacks|"
        r"damage from attacks? (?:is )?reduced by \d+|"
        r"prevent all damage from and effects of attacks|"
        r"can't be affected by any special conditions|"
        r"immune to special conditions|can't retreat|has no retreat cost|"
        r"prevent all effects of attacks|can't be damaged by attacks|"
        r"cannot be damaged by attacks|damage counters? (?:can't|cannot) be placed)",
        "defensive",
    ),
    (
        "defensive_hp_and_survival",
        r"\b(?:gets? \+\d+ hp|\+\d+ hp|increases? this pok[eé]mon's max hp|"
        r"not knocked out|isn't knocked out|remaining hp becomes)\b",
        "defensive",
    ),
    (
        "defensive_special_conditions_and_control",
        r"\b(?:is now poisoned|is now burned|is now confused|is now paralyzed|"
        r"is now asleep|is now (?:poisoned|burned|confused|paralyzed|asleep)|"
        r"can't use attacks|cannot use attacks|switch in .* opponent's benched)",
        "offensive",
    ),
    (
        "offensive_damage_and_knockout",
        r"\b(?:this attack does? (?:\d+ damage|\d+ more damage|\d+ less damage|"
        r"\d+ damage for each|that much more damage)|"
        r"this attack also does? \d+ damage|does? \d+ damage to|"
        r"put \d+ damage counters? on|is knocked out|apply weakness|"
        r"apply resistance|damage isn't affected by weakness|"
        r"damage isn't affected by resistance|don't apply weakness|"
        r"don't apply resistance)",
        "offensive",
    ),
    (
        "offensive_retreat_manipulation",
        r"\b(?:opponent's? active pok[eé]mon's? retreat cost|"
        r"your retreat cost|retreat cost of .* (?:increased|reduced)|"
        r"retreat cost is \d+ less|retreat cost is \d+ more)",
        "both",
    ),
    (
        "offensive_tool_target",
        r"\b(?:\w+(?: ex| v| vmax| vstar)? takes? \+\d+ damage|"
        r"damage done to .* pok[eé]mon ex|pok[eé]mon tool attached|"
        r"pok[eé]mon named|has \".*\" in its name)",
        "offensive",
    ),
    (
        "neither_noncombat",
        r"\b(?:draw \d+ cards?|search your deck for|shuffle your deck|"
        r"your opponent reveals their hand|reveal your opponent's hand|"
        r"look at the top \d+ cards? of your deck|take a card from your discard pile|"
        r"evolve this pok[eé]mon|play this card as if it were)",
        "neither",
    ),
    (
        "neither_healing_and_energy_discard",
        r"\b(?:heal \d+ damage|heal all damage|remove \d+ damage counters?|"
        r"discard .* energy from)\b",
        "neither",
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


def load_reference_classifications():
    """Use the user's labeled examples as exact-match authoritative cases."""
    if not DEFAULT_SUPPORTED_OUTPUT.exists():
        return {}
    try:
        with DEFAULT_SUPPORTED_OUTPUT.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        normalize_effect(record["effect_text"]): (
            record["classification"], "classified_effect_reference"
        )
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("effect_text"), str)
        and record.get("supported") is True
        and record.get("classification") in VALID_CLASSIFICATIONS
    }


REFERENCE_CLASSIFICATIONS = load_reference_classifications()


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
    """Classify the entire effect text, returning None if any clause is unknown."""
    normalized = normalize_effect(text).casefold()
    reference = REFERENCE_CLASSIFICATIONS.get(normalize_effect(text))
    if reference:
        return reference
    matches = []

    for rule_name, pattern, classification in AUTO_RULES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            matches.append((classification, rule_name))

    if not matches:
        return None, None

    # Rules intentionally inspect the whole text: multiple matching facets are
    # retained and combined, including the explicitly supported both case.
    categories = {classification for classification, _ in matches}
    if "both" in categories or ("offensive" in categories and "defensive" in categories):
        classification = "both"
    elif "offensive" in categories:
        classification = "offensive"
    elif "defensive" in categories:
        classification = "defensive"
    else:
        classification = "neither"

    # A match is complete only if each sentence-like clause contains a known
    # combat/noncombat signal. This deliberately leaves unfamiliar text for
    # review instead of silently treating a partial match as fully parsed.
    clauses = [
        part.strip(" .;:")
        for part in re.split(r"[.;]", normalized)
        if part.strip(" .;:")
    ]
    for clause in clauses:
        if not any(
            re.search(pattern, clause, flags=re.IGNORECASE)
            for _, pattern, _ in AUTO_RULES
        ):
            return None, None
    return classification, "+".join(dict.fromkeys(rule for _, rule in matches))


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

        for field, output_type in (
            ("abilities", "Ability"),
            ("moves", "Move"),
        ):
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
            "Input JSON must contain a list of cards, "
            "either directly or under the 'cards' key."
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
        if (
            not isinstance(effect, dict)
            or not isinstance(effect.get("effect_text"), str)
        ):
            continue

        saved = {}

        supported = effect.get("supported")
        if isinstance(supported, bool):
            saved["supported"] = supported

        classification = effect.get("classification")
        if classification in VALID_CLASSIFICATIONS:
            saved["classification"] = classification
            saved["classification_reviewed"] = effect.get(
                "classification_reviewed", True
            )

        if not saved:
            continue

        key = (
            effect_key(effect)
            if "entry_index" in effect
            else legacy_effect_key(effect)
        )
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
            effect["classification_reviewed"] = saved.get(
                "classification_reviewed", True
            )
        else:
            effect.pop("classification", None)
            effect["classification_reviewed"] = False

        automatic, rule = classify_effect_automatically(effect["effect_text"])
        if (
            automatic is None
            and effect.get("supported") is False
            and effect.get("classification_reviewed") is True
        ):
            # A saved unsupported decision means a prior review found no
            # offensive, defensive, or combined effect for the calculator.
            automatic, rule = "neither", "saved_unsupported_decision"
        effect["auto_classification"] = automatic
        effect["auto_rule"] = rule

        if automatic in VALID_CLASSIFICATIONS:
            reference_result = rule == "classified_effect_reference"
            effect.setdefault(
                "supported", reference_result or automatic != "neither"
            )
            if "classification" not in saved:
                effect["classification"] = automatic
                effect["classification_reviewed"] = True

        if effect.get("supported") is False:
            effect["classification"] = "neither"
            effect["classification_reviewed"] = True


def save_effects(path, effects):
    """Write JSON atomically to avoid leaving a partially written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(effects, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def export_supported_effects(review_path, supported_path):
    """Export every effect whose saved support decision is exactly True."""
    effects = load_existing(review_path)
    supported = [
        effect
        for effect in effects
        if isinstance(effect, dict) and effect.get("supported") is True
    ]

    save_effects(supported_path, supported)

    print(f"Supported effects exported: {len(supported)}")
    print(f"Supported effects saved to: {supported_path}")


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


def report_skipped_effect(effect, index, total, reason):
    """Print a compact record whenever review bypasses an effect."""
    print(f"Skipped effect {index}/{total} ({reason})")
    print(f"  Category:      {effect.get('card_type')}")
    print(f"  Name:          {effect.get('entry_name') or '(unnamed)'}")
    print(f"  Card:          {effect.get('card_name')}")
    print(f"  Set/card:      {effect.get('set')} / {effect.get('card_number')}")
    print(f"  Effect:        {effect.get('effect_text')}")
    print(f"  Supported:     {effect.get('supported', 'not reviewed')}")
    print(f"  Classification:{' '}{effect.get('classification', 'not reviewed')}")


def review_effects(effects, output_path):
    """Review each effect and save decisions immediately."""
    total = len(effects)

    print(f"\nIndividual effects: {total}")
    print("Press Enter to approve an automatic classification.")
    print(
        "Use o/d/b/x to override it. "
        "Unmatched effects need manual classification.\n"
    )

    for index, effect in enumerate(effects, start=1):
        if effect.get("classification") == "both":
            print(
                "WARNING: offensive and defensive effects were both detected: "
                f"{effect['card_name']} / {effect.get('entry_name') or '(unnamed)'}"
            )
        if effect.get("supported") is False:
            effect["classification"] = "neither"
            effect["classification_reviewed"] = True
            save_effects(output_path, effects)
            report_skipped_effect(effect, index, total, "marked unsupported")
            continue

        supported_done = isinstance(effect.get("supported"), bool)
        classification_done = (
            effect.get("classification") in VALID_CLASSIFICATIONS
            and effect.get("classification_reviewed") is True
        )

        if supported_done and classification_done:
            report_skipped_effect(effect, index, total, "already classified")
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
        print(
            "Automatic classification: "
            f"{effect.get('auto_classification') or 'no confident match'}"
        )

        if effect.get("auto_rule"):
            print(f"Matched rule: {effect['auto_rule']}")

        print(
            f"Saved classification: "
            f"{effect.get('classification', 'not reviewed')}\n"
        )

        if not supported_done:
            answer = ask_supported()

            if answer == "quit":
                save_effects(output_path, effects)
                print("\nReview stopped. Progress saved.")
                return

            if answer != "skip":
                effect["supported"] = answer
            else:
                report_skipped_effect(effect, index, total, "support skipped")

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
            else:
                report_skipped_effect(effect, index, total, "classification skipped")

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

    pokemon_card_types = set(
        str(v)
        for v in _as_list(
            pokemon.get("card_subtypes", pokemon.get("Card Type", []))
        )
    )

    for key, value in card_condition.items():
        if key == "Pkmn Card Type":
            eligible = set(str(v) for v in _as_list(value))
            if not pokemon_card_types.intersection(eligible):
                return False, _format_condition_parts(condition_parts)

        elif key == "Enemy Pkmn Card Type":
            if not isinstance(enemy_pokemon, dict):
                return False, _format_condition_parts(condition_parts)

            enemy_card_types = set(
                str(v)
                for v in _as_list(
                    enemy_pokemon.get(
                        "card_subtypes", enemy_pokemon.get("Card Type", [])
                    )
                )
            )
            eligible = set(str(v) for v in _as_list(value))
            if not enemy_card_types.intersection(eligible):
                return False, _format_condition_parts(condition_parts)

        elif key == "Prize Cards":
            if value == "more":
                condition_parts.append(
                    "this card's player must have more Prize cards "
                    "than the opposing player's"
                )

        elif key == "Rule Box":
            has_rule_box = bool(pokemon_card_types.intersection(RULE_BOX_TYPES))
            if value == "None" and has_rule_box:
                return False, _format_condition_parts(condition_parts)

        elif key == "Evolution":
            stage = pokemon.get(
                "evolution_stage", pokemon.get("Evolution Stage")
            )
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
            condition_parts.append(
                f"you must have at least {value} cards in your Lost Zone"
            )

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
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSON file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Review JSON file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--supported-output",
        type=Path,
        default=DEFAULT_SUPPORTED_OUTPUT,
        help=(
            "JSON file for effects marked supported=true "
            f"(default: {DEFAULT_SUPPORTED_OUTPUT})"
        ),
    )
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

    supported_count = sum(
        isinstance(effect.get("supported"), bool) for effect in effects
    )
    reviewed_count = sum(
        effect.get("classification") in VALID_CLASSIFICATIONS
        and effect.get("classification_reviewed") is True
        for effect in effects
    )
    automatic_count = sum(
        effect.get("auto_classification") in VALID_CLASSIFICATIONS
        for effect in effects
    )

    print(f"Cards processed: {len(cards)}")
    print(f"Effect entries: {len(effects)}")
    print(f"Automatic suggestions: {automatic_count}/{len(effects)}")
    print(f"Support decisions saved: {supported_count}/{len(effects)}")
    print(
        f"Reviewed classifications saved: "
        f"{reviewed_count}/{len(effects)}"
    )

    try:
        review_effects(effects, args.output)
    finally:
        # Reload the saved file so the export reflects the latest decisions,
        # including when review is stopped with q or Ctrl+C.
        export_supported_effects(args.output, args.supported_output)

    # Reload the review file for accurate final counts.
    try:
        final_effects = load_existing(args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    supported_count = sum(
        isinstance(effect.get("supported"), bool) for effect in final_effects
    )
    reviewed_count = sum(
        effect.get("classification") in VALID_CLASSIFICATIONS
        and effect.get("classification_reviewed") is True
        for effect in final_effects
    )

    print(f"\nSupport decisions: {supported_count}/{len(final_effects)}")
    print(
        f"Reviewed classifications: {reviewed_count}/{len(final_effects)}"
    )
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
