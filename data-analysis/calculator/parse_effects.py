#!/usr/bin/env python3

"""Extract, review, and classify Pokémon card effects."""

import argparse
import json
import re
import os
import time
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
EFFECT_REVIEW_DIR = SCRIPT_DIR / "review" / "first-pass"
DEFAULT_OUTPUT = EFFECT_REVIEW_DIR / "effects_to_review.json"
DEFAULT_SUPPORTED_OUTPUT = EFFECT_REVIEW_DIR / "supported_effects.json"
DEFAULT_UNSUPPORTED_OUTPUT = EFFECT_REVIEW_DIR / "unsupported_effects.json"


CLASSIFICATIONS = {
    "o": "offensive",
    "d": "defensive",
    "b": "both",
    "x": "neither",
}
VALID_CLASSIFICATIONS = set(CLASSIFICATIONS.values())


# Explicit unsupported cases take priority over general rules.
# These return "neither", but can be overwritten by another offensive/defensive/both rule.
UNSUPPORTED_RULES = [
    (
        "unsupported_bench_self_recycling",
        r"\bonce during your turn\b.*?"
        r"if this pok[eé]mon is on your bench\b.*?"
        r"discard the bottom card of your deck\b.*?"
        r"discard all cards from this pok[eé]mon\b.*?"
        r"put this pok[eé]mon on top of your deck\b",
    ),
    (
        "unsupported_coin_flip_paralysis",
        r"\bflip a coin\b.*?\bif heads\b.*?"
        r"your opponent's active pok[eé]mon is now paralyzed\b",
    ),
    (
        "unsupported_next_turn_attack_lock",
        r"\bduring your next turn\b.*?"
        r"this pok[eé]mon can't attack\b",
    ),
    (
        "unsupported_self_bench_damage",
        r"\bthis attack also does \d+ damage to \d+ "
        r"of your benched pok[eé]mon\b",
    ),
    (
        "unsupported_switch_with_benched_pokemon",
        r"\bswitch this pok[eé]mon with \d+ of your benched pok[eé]mon\b",
    ),
    (
        "unsupported_cant_retreat",
        r"\bcan't retreat\b",
    ),
    (
        "unsupported_switch_in_opponent_benched_pokemon",
        r"\bswitch in \d+ of your opponent's benched pok[eé]mon "
        r"to the active spot\b",
    ),
    (
        "unsupported_attach_energy_from_discard",
        r"\battach up to \d+ basic energy cards? from your discard pile "
        r"to \d+ of your pok[eé]mon\b",
    ),
    (
        "unsupported_shuffle_self_and_attached_cards_into_deck",
        r"\byou may shuffle this pok[eé]mon and all attached cards "
        r"into your deck\b",
    ),
    (
        "unsupported_opponent_next_turn_attack_damage_reduction",
        r"\bduring your opponent's next turn\b.*?"
        r"attacks used by the defending pok[eé]mon do \d+ less damage\b",
    ),
    (
        "unsupported_recover_from_special_conditions",
        r"\bthis pok[eé]mon recovers from all special conditions\b",
    ),
    (
        "unsupported_retrieve_basic_energy_from_discard",
        r"\bput up to \d+ basic energy cards? from your discard pile "
        r"into your hand\b",
    ),
    (
        "unsupported_draw_until_hand_size",
        r"\bdraw cards until you have \d+ cards? in your hand\b",
    ),
    (
        "unsupported_next_turn_attack_restriction",
        r"\bduring your next turn, this pok[eé]mon can't use\b",
    ),
    (
        "unsupported_discard_top_deck_cards",
        r"\bdiscard the top \d+ cards? of your deck\b",
    ),
    (
        "unsupported_opponent_shuffle_hand_draw",
        r"\byour opponent shuffles their hand into their deck and draws \d+ cards?\b",
    ),
    (
        "unsupported_shuffle_pokemon_and_basic_energy_from_discard",
        r"\bshuffle up to \d+ in any combination of pok[eé]mon and basic energy cards? "
        r"from your discard pile into your deck\b",
    ),
    (
        "unsupported_discard_opponent_deck_top_card",
        r"\bdiscard the top (?:card|\d+ cards?) of your opponent's deck\b",
    ),
    (
        "unsupported_shuffle_self_and_attached_cards_into_deck",
        r"\bshuffle this pok[eé]mon and all attached cards into your deck\b",
    ),
    (
        "unsupported_delayed_discard_defending_pokemon",
        r"\bat the end of your opponent's next turn, discard the defending pok[eé]mon "
        r"and all attached cards\b",
    ),
    (
        "unsupported_place_damage_counters_on_opponent_benched_pokemon",
        r"\bplace \d+ damage counters? on \d+ of your opponent's benched pok[eé]mon\b",
    ),
    (
        "unsupported_switch_opponent_active_pokemon",
        r"\bswitch out your opponent's active pok[eé]mon to the bench\b",
    ),
    (
        "unsupported_put_self_and_attached_cards_into_hand",
        r"\bput this Pokémon and all attached cards into your hand\b",
    ),
    (
        "unsupported_move_energy_from_opponent_active_to_benched",
        r"\bmove an Energy from your opponent's Active Pokémon to 1 of their Benched Pokémon\b",
    ),
    (
        "unsupported_discard_top_card_of_deck",
        r"\bdiscard the top card of your deck\b",
    ),
    (
        "unsupported_return_attached_energy_to_hand",
        r"\bput an Energy attached to this Pokémon into your hand\b",
    ),
    (
        "unsupported_attach_basic_energy_from_discard_to_benched",
        r"\battach a Basic \[[^\]]+\] Energy card from your discard pile to 1 of your Benched \w+ Pokémon\b",
    ),
    (
        "unsupported_switch_this_pokemon_with_benched_pokemon",
        r"\bswitch this Pokémon with 1 of your Benched Pokémon\b",
    ),
    (
        "unsupported_switch_this_pokemon_with_benched_typed_pokemon",
        r"\bswitch this Pokémon with 1 of your Benched \w+ Pokémon\b",
    ),
    (
        "unsupported_attach_basic_energy_from_discard_to_self",
        r"\battach up to \d+ Basic \[[^\]]+\] Energy cards? from your discard pile to this Pokémon\b",
    ),
    (
        "unsupported_move_energy_from_self_to_benched",
        r"\bmove an Energy from this Pokémon to 1 of your Benched Pokémon\b",
    ),
    (
        "unsupported_discard_random_opponent_hand_card",
        r"\bdiscard a random card from your opponent's hand\b",
    ),
    (
        "unsupported_move_energy_from_self_to_benched",
        r"\bmove an Energy from this Pokémon to 1 of your Benched Pokémon\b",
    ),
    (
        "unsupported_discard_random_opponent_hand_card",
        r"\bdiscard a random card from your opponent's hand\b",
    ),
    (
        "unsupported_move_basic_energy_between_own_pokemon",
        r"\bmove a Basic \[[^\]]+\] Energy from 1 of your Pokémon to another of your Pokémon\b",
    ),
    (
        "unsupported_return_multiple_attached_energy_to_hand",
        r"\bput \d+ \[[^\]]+\] Energy attached to this Pokémon into your hand\b",
    ),
]


SPECIAL_RULES = [
    (
        "special_volbeat_apply_weakness_both_active_x3",
        r"\bif you have volbeat in play, apply weakness for both active "
        r"pok[eé]mon as x3\b",
    ),
    (
        "special_opponent_active_attack_damage_reduction_while_active",
        r"\bas long as this pok[eé]mon is in the active spot, attacks used "
        r"by your opponent's active pok[eé]mon do \d+ less damage "
        r"\(before applying weakness and resistance\)",
    ),
    (
        "special_bench_attack_damage_and_effect_prevention",
        r"\bas long as this pok[eé]mon is on your bench, prevent all damage "
        r"from and effects of attacks from your opponent's pok[eé]mon "
        r"done to this pok[eé]mon\b",
    ),
    (
        "special_use_attacks_of_benched_pokemon",
        r"\bthis pok[eé]mon can use the attacks of any of your benched "
        r"pok[eé]mon\b",
    ),
    (
        "special_devolve_opponent_evolved_pokemon",
        r"\bdevolve each of your opponent's evolved pok[eé]mon by putting "
        r"the highest stage evolution card on it into your opponent's hand\b",
    ),
    (
        "special_opponent_next_turn_damage_reduction",
        r"\bduring your opponent's next turn, this pok[eé]mon takes "
        r"\d+ less damage from attacks "
        r"\(after applying weakness and resistance\)",
    ),
    (
        "special_bench_active_retreat_cost_reduction",
        r"\bas long as this pok[eé]mon is on your bench, your active "
        r"pok[eé]mon's retreat cost is \d+ less\b",
    ),
    (
        "special_prevent_opponent_active_healing",
        r"\byour opponent's active pok[eé]mon can't be healed\b",
    ),
    (
        "special_next_turn_defending_pokemon_damage_increase",
        r"\bduring your next turn, the defending pok[eé]mon takes "
        r"\d+ more damage from attacks "
        r"\(after applying weakness and resistance\)",
    ),
    (
        "special_change_defending_pokemon_weakness",
        r"\bthe defending pok[eé]mon's weakness is now "
        r"\[[^\]]+\] until the end of your next turn\b",
    ),
    (
        "special_evolved_pokemon_use_previous_evolution_attacks",
        r"\beach of your evolved pok[eé]mon can use any attack from "
        r"its previous evolutions\b",
    ),
    (
        "special_copy_benched_ns_pokemon_attack",
        r"\bchoose 1 of your benched .+? pok[eé]mon's attacks "
        r"and use it as this attack\b",
    ),
    (
        "special_change_weakness_of_opponent_type_pokemon",
        r"\bthe weakness of each of your opponent's \[[^\]]+\] "
        r"pok[eé]mon in play is now \[[^\]]+\]",
    ),
    (
        "special_energy_based_damage_reduction",
        r"\ball of your pok[eé]mon that have any \[[^\]]+\] energy "
        r"attached take \d+ less damage from attacks from your "
        r"opponent's pok[eé]mon "
        r"\(after applying weakness and resistance\)",
    ),
    (
        "special_wild_growth_energy_multiplier",
        r"\beach basic \[[^\]]+\] energy attached to all of your "
        r"pok[eé]mon provides \[[^\]]+\] \[[^\]]+\] energy\. "
        r"the effect of wild growth doesn't stack\b",
    ),
    (
        "special_prevent_moving_damage_counters",
        r"\bdamage counters on each pok[eé]mon "
        r"\(both yours and your opponent's\) can't be moved "
        r"to other pok[eé]mon\b",
    ),
    (
        "special_next_turn_self_attack_damage_increase",
        r"\bduring your next turn, attacks used by this Pokémon do \d+ more damage to your opponent's Active Pokémon \(before applying Weakness and Resistance\)",
    ),
    (
        "special_copy_opponent_attack_with_empty_hand",
        r"\bif you have no cards in your hand, choose an attack from 1 of your opponent's Pokémon in play and use it as this attack\b",
    ),
    (
        "special_opponent_next_turn_item_lock",
        r"\bduring your opponent's next turn, they can't play any Item cards from their hand\b",
    ),
    (
        "special_devolve_opponent_active_pokemon",
        r"\bif your opponent's Active Pokémon is an evolved Pokémon, devolve it by putting the highest Stage Evolution card on it into your opponent's hand\b",
    ),
    (
        "special_prevent_opponent_ability_effects",
        r"\bprevent all effects of your opponent's Pokémon's Abilities done to this Pokémon\b",
    ),
    (
        "special_opponent_attack_lock_next_turn",
        r"\bchoose 1 of your opponent's Active Pokémon's attacks\. during your opponent's next turn, that Pokémon can't use that attack\b",
    ),
    (
        "special_remove_self_knockout_abilities",
        r"\bPokémon in play \(both yours and your opponent's\) lose any Ability that requires the Pokémon using it to Knock Out itself\b",
    ),
    (
        "special_double_opponent_damage_counters",
        r"\bdouble the number of damage counters on each of your opponent's Pokémon\b",
    ),
    (
        "special_copy_opponent_active_tera_attack",
        r"\bchoose 1 of your opponent's Active Tera Pokémon's attacks and use it as this attack\b",
    ),
    (
        "special_copy_opponent_active_attack",
        r"\bchoose 1 of your opponent's Active Pokémon's attacks and use it as this attack\b",
    ),
    (
        "special_change_own_pokemon_types_while_in_play",
        r"\bas long as this Pokémon is in play, it is \[\s*[A-Z]\s*\](?: and \[\s*[A-Z]\s*\])? type\b",
    ),
    (
    "special_change_own_pokemon_types_while_in_play",
        r"\bas long as this Pokémon is in play, it is \[\s*[A-Z]\s*\](?: and \[\s*[A-Z]\s*\])? type\b",
    ),
    (
        "special_next_turn_specific_attack_damage_increase",
        r"\bduring your next turn, this Pokémon's .+ attack does \d+ more damage \(before applying Weakness and Resistance\)",
    ),
    (
        "special_own_attacks_damage_increase",
        r"\battacks used by your Pokémon do \d+ more damage to your opponent's Active Pokémon \(before applying Weakness and Resistance\)",
    ),
]


# Each rule recognizes a kind of effect, not merely the first matching phrase.
# The classifier evaluates every rule over the whole text so composite effects
# (for example, damage plus protection on the next turn) are not truncated.
AUTO_RULES = [
    (
        "neither_noncombat",
        r"\b(?:draw a card|draw \d+ cards?|search your deck for|shuffle your deck|"
        r"your opponent reveals their hand|reveal your opponent's hand|"
        r"look at the top \d+ cards? of your deck|take a card from your discard pile|"
        r"evolve this pok[eé]mon|play this card as if it were)",
        "neither",
    ),
    (
        "neither_coin_flip_setup",
        r"\bflip (?:a|one|\d+) coins?\b",
        "neither",
    ),
    (
        "neither_healing_and_energy_discard",
        r"\b(?:heal \d+ damage|heal all damage|remove \d+ damage counters?|"
        r"discard .* energy from)\b",
        "neither",
    ),
    (
        "neither_draw_search",
        r"\b(?:draw a card|draw \d+ cards?|search your deck for|shuffle your deck|"
        r"look at the top \d+ cards? of your deck)\b",
        "neither",
    ),
    (
        "offensive_special_conditions",
        r"\b(?:is now poisoned|is now burned|is now confused|"
        r"is now paralyzed|is now asleep)\b",
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
        "offensive_damage_to_each_opponent_pokemon",
        r"\bthis attack does \d+ damage to each of your opponent's "
        r"pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_damage_per_target_damage_counter",
        r"\bthis attack does \d+ damage to \d+ of your opponent's "
        r"pok[eé]mon for each damage counter on that pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_damage_to_opponent_pokemon",
        r"\bthis attack (?:also )?does \d+ damage to \d+ of your "
        r"opponent's pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_opponent_bench_damage",
        r"\bthis attack also does \d+ damage to \d+ of your opponent's "
        r"benched pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_attack_does_nothing_on_tails",
        r"\bif tails\b.*?\bthis attack does nothing\b",
        "offensive",
    ),
    (
        "offensive_tool_target",
        r"\b(?:\w+(?: ex| v| vmax| vstar)? takes? \+\d+ damage|"
        r"damage done to .* pok[eé]mon ex|pok[eé]mon tool attached|"
        r"pok[eé]mon named|has \".*\" in its name)",
        "offensive",
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
        r"\b(?:put \d+ damage counters? on the defending pok[eé]mon|"
        r"this attack does \d+ damage)\b",
        "offensive",
    ),
    (
        "offensive_place_damage_counters_on_opponent_pokemon",
        r"\bplace \d+ damage counters? on \d+ of your opponent's pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_discard_opponent_active_pokemon_tools",
        r"\bbefore doing damage, discard all pok[eé]mon tools from "
        r"your opponent's active pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_damage_unaffected_by_opponent_active_effects",
        r"\bthis attack's damage isn't affected by any effects on your opponent's "
        r"active pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_attack_does_nothing_without_energy",
        r"\bif this pok[eé]mon has no .+ attached, this attack does nothing\b",
        "offensive",
    ),
    (
        "offensive_attack_does_nothing_if_condition_absent",
        r"\bif your opponent's active pok[eé]mon isn't .+, this attack does nothing\b",
        "offensive",
    ),
    (
        "offensive_place_damage_counter_on_opponent_active",
        r"\bplace \d+ damage counters? on your opponent's active pok[eé]mon\b",
        "offensive",
    ),
    (
        "offensive_conditional_attack_does_nothing",
        r"\bif you don't .+, this attack does nothing\b",
        "offensive",
    ),
    (
        "offensive_conditional_attack_does_nothing",
        r"\bif .+, this attack does nothing\b",
        "offensive",
    ),
    (
        "offensive_own_typed_pokemon_attacks_damage_increase",
        r"\battacks used by your (?:\[[^\]]+\]|\{[^}]+\}) Pokémon do (?:\d+|\{[^}]+\}) more damage to your opponent's Active Pokémon\b",
        "offensive",
    ),
    (
        "offensive_damage_increase_against_damaged_active",
        r"\bif your opponent's Active Pokémon already has any damage counters on it, this attack's base damage is (?:\d+|\{[^}]+\})\b",
        "offensive",
    ),
    (
        "defensive_prevent_opponent_attacks_and_abilities",
        r"\bprevent all effects of your opponent's pok[eé]mon's "
        r"attacks and abilities done to this pok[eé]mon\b",
        "defensive",
    ),
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
        "defensive_opponent_active_attack_damage_reduction",
        r"\bas long as this pok[eé]mon is in the active spot\b.*?"
        r"attacks used by your opponent's active pok[eé]mon do "
        r"\d+ less damage\b",
        "defensive",
    ),
    (
        "defensive_opponent_attack_effect_prevention",
        r"\bprevent all effects of attacks used by your opponent's "
        r"pok[eé]mon done to your\b",
        "defensive",
    ),
    (
        "defensive_coin_flip_attack_protection",
        r"\bif heads\b.*?"
        r"prevent all damage from and effects of attacks done to this pok[eé]mon\b",
        "defensive",
    ),
    (
        "defensive_hp_and_survival",
        r"\b(?:gets? \+\d+ hp|\+\d+ hp|increases? this pok[eé]mon's max hp|"
        r"not knocked out|isn't knocked out|remaining hp becomes)\b",
        "defensive",
    ),
    (
        "defensive_attack_restrictions",
        r"\b(?:can't use attacks|cannot use attacks)\b",
        "defensive",
    ),
    (
        "defensive_opponent_attack_coin_flip_prevention",
        r"\bduring your opponent's next turn, if the Defending Pokémon tries to use an attack, your opponent flips a coin\. if tails, that attack doesn't happen\b",
        "defensive",
    ),
    (
        "both_retreat_cost_manipulation",
        r"\b(?:opponent's? active pok[eé]mon's? retreat cost|"
        r"your retreat cost|retreat cost of .* (?:increased|reduced)|"
        r"retreat cost is \d+ less|retreat cost is \d+ more|"
        r"has no retreat cost)",
        "both",
    ),
    (
        "both_attached_pokemon_retreat_cost_reduction",
        r"\bthe Retreat Cost of the Pokémon this card is attached to is (?:\d+|\{[^}]+\}) less\b",
        "both",
    ),
]


def match_special_rule(text):
    normalized = normalize_effect(text)

    for rule_name, pattern in SPECIAL_RULES:
        if re.search(pattern, normalized, re.IGNORECASE):
            return rule_name

    return None


def normalize_effect(text):
    """Normalize whitespace for matching effect text."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


TOOL_OPPONENT_ATTACK_REACTION = re.compile(
    r"\b(?:damaged by (?:an attack from your opponent|an opponent's attack)|"
    r"takes \d+ or more damage from an attack from your opponent|"
    r"knocked out by damage from an attack from your opponent)\b",
    re.IGNORECASE,
)


def is_reference_classification_eligible(record):
    """Exclude Tool effects triggered by taking damage or being Knocked Out."""
    if (
        str(record.get("card_type", "")).casefold() == "trainer"
        and str(record.get("trainer_subtype", "")).casefold() == "tool"
        and TOOL_OPPONENT_ATTACK_REACTION.search(record["effect_text"])
    ):
        return False
    return True


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
        and is_reference_classification_eligible(record)
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
    """Prefer offensive/defensive classifications over unsupported matches."""
    normalized = normalize_effect(text).casefold()

    reference = REFERENCE_CLASSIFICATIONS.get(normalize_effect(text))
    if reference:
        return reference

    # Collect all explicit unsupported matches without returning early.
    unsupported_matches = [
        rule_name
        for rule_name, pattern in UNSUPPORTED_RULES
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
    ]

    # Collect all general classification matches.
    matches = [
        (classification, rule_name)
        for rule_name, pattern, classification in AUTO_RULES
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
    ]

    # Only offensive/defensive/both classifications override unsupported
    # matches. A "neither" rule alone does not override an unsupported match.
    substantive_matches = [
        (classification, rule_name)
        for classification, rule_name in matches
        if classification in ("offensive", "defensive", "both")
    ]

    if substantive_matches:
        matches = substantive_matches
    elif unsupported_matches:
        return "neither", "+".join(dict.fromkeys(unsupported_matches))
    elif not matches:
        return None, None

    # Every sentence-like clause must contain a recognized signal.
    clauses = [
        part.strip(" .;:")
        for part in re.split(r"[.;]", normalized)
        if part.strip(" .;:")
    ]

    print("DEBUG normalized:", repr(normalized))
    print("DEBUG clauses:", clauses)

    for clause in clauses:
        matching_rules = [
            rule_name
            for rule_name, pattern, _ in AUTO_RULES
            if re.search(pattern, clause, flags=re.IGNORECASE | re.DOTALL)
        ]
        print(f"DEBUG clause: {clause!r}")
        print(f"DEBUG matching rules: {matching_rules}")

    categories = {classification for classification, _ in matches}

    if "both" in categories or (
        "offensive" in categories and "defensive" in categories
    ):
        classification = "both"
    elif "offensive" in categories:
        classification = "offensive"
    elif "defensive" in categories:
        classification = "defensive"
    else:
        classification = "neither"

    return classification, "+".join(
        dict.fromkeys(rule for _, rule in matches)
    )


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
                    "trainer_subtype": card.get("trainer_type"),
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

        special_rule = match_special_rule(effect["effect_text"])

        if special_rule:
            effect["supported"] = True
            effect["special_rule"] = special_rule
            effect["classification"] = None
            effect["classification_reviewed"] = False
            continue

        automatic, rule = classify_effect_automatically(
            effect["effect_text"]
        )

        if (
            automatic is None
            and effect.get("supported") is False
            and effect.get("classification_reviewed") is True
        ):
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
    """Save JSON atomically, retrying transient Windows filesystem errors."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)

    # Finish writing the complete replacement before touching the destination.
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(effects, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    # Windows can temporarily prevent replacement of a file on /mnt/c.
    last_error = None

    for attempt in range(8):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError as error:
            last_error = error
            if attempt < 7:
                time.sleep(min(0.25 * (2 ** attempt), 2.0))
        except OSError as error:
            raise OSError(
                f"Could not replace {path}: {error}\n"
                f"The complete new JSON is preserved at: {temp_path}"
            ) from error

    # Do not delete the completed temporary file: it may contain the
    # latest review decisions and can be recovered if replacement is blocked.
    raise PermissionError(
        f"Could not replace {path} after 8 attempts.\n"
        f"Another process may be locking the destination.\n"
        f"The complete new JSON is preserved at: {temp_path}\n"
        f"Original error: {last_error}"
    ) from last_error



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


def export_unsupported_effects(review_path, unsupported_path):
    """Export every effect whose saved support decision is exactly False."""
    effects = load_existing(review_path)
    unsupported = [
        effect
        for effect in effects
        if isinstance(effect, dict) and effect.get("supported") is False
    ]

    save_effects(unsupported_path, unsupported)

    print(f"Unsupported effects exported: {len(unsupported)}")
    print(f"Unsupported effects saved to: {unsupported_path}")



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

        if effect.get("special_rule"):
            print(f"Special rule: {effect['special_rule']}")
            continue

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
                    "than the attacking player's"
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
    parser.add_argument(
        "--unsupported-output",
        type=Path,
        default=DEFAULT_UNSUPPORTED_OUTPUT,
        help=(
            "JSON file for effects marked supported=false "
            f"(default: {DEFAULT_UNSUPPORTED_OUTPUT})"
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
        export_unsupported_effects(args.output, args.unsupported_output)

    # Reload the review file for accurate final counts.
    try:
        final_effects = load_existing(args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    supported_count = sum(isinstance(effect.get("supported"), bool) for effect in final_effects)
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
