PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    set_id INTEGER REFERENCES sets(id),
    name TEXT,
    name_with_set TEXT UNIQUE,
    card_type TEXT NOT NULL,
    card_number TEXT,
    card_mark TEXT,
    rarity TEXT,
    expansion TEXT,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS pokemon (
    card_id INTEGER PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
    evolution_stage TEXT,
    previous_evolution TEXT,
    hp INTEGER,
    hp_text TEXT,
    type TEXT,
    weakness TEXT,
    resistance TEXT,
    retreat_cost INTEGER
);

CREATE TABLE IF NOT EXISTS card_variants (
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    PRIMARY KEY (card_id, variant)
);

CREATE TABLE IF NOT EXISTS attacks (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name TEXT,
    damage INTEGER,
    damage_modifier TEXT,
    damage_text TEXT,
    effect_text TEXT
);

CREATE TABLE IF NOT EXISTS attack_costs (
    attack_id INTEGER NOT NULL REFERENCES attacks(id) ON DELETE CASCADE,
    energy_type TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (attack_id, energy_type)
);

CREATE TABLE IF NOT EXISTS abilities (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name TEXT,
    effect_text TEXT
);

CREATE INDEX IF NOT EXISTS cards_set_id_idx ON cards(set_id);
CREATE INDEX IF NOT EXISTS attacks_card_id_idx ON attacks(card_id);
CREATE INDEX IF NOT EXISTS abilities_card_id_idx ON abilities(card_id);
