/**
 * One Shot Calculator — browser-side SQLite access.
 *
 * Requires sql.js to be loaded before this script.
 * The SQLite database must be available at ./data/damage_calculator.sqlite3
 * relative to the website page.
 */

let databasePromise = null;

/**
 * Load the SQLite database once and reuse it.
 *
 * @returns {Promise<Database>}
 */
async function loadDatabase() {
    if (databasePromise) {
        return databasePromise;
    }

    databasePromise = (async () => {
        if (typeof initSqlJs !== "function") {
            throw new Error(
                "sql.js is not loaded. Load sql-wasm.js first."
            );
        }

        const SQL = await initSqlJs({
            locateFile: file =>
                `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
        });

        const response = await fetch(
            "./data/damage_calculator.sqlite3"
        );

        if (!response.ok) {
            throw new Error(
                `Failed to load SQLite database: HTTP ${response.status}`
            );
        }

        const bytes = await response.arrayBuffer();

        return new SQL.Database(new Uint8Array(bytes));
    })().catch(error => {
        // Allow a later retry if loading failed.
        databasePromise = null;
        throw error;
    });

    return databasePromise;
}

/**
 * Find Pokémon cards that can meet the initial damage thresholds
 * against a selected defending Pokémon.
 *
 * Finds move and Tool combinations whose final damage reaches defender HP.
 *
 * @param {number} defenderId - ID from the pokemon table.
 * @param {boolean} includeSurvivalBrace - Whether to include Survival Brace.
 * @returns {Promise<Array<object>>}
 */
async function findCandidateMoves(defenderId, includeSurvivalBrace = false) {
    const db = await loadDatabase();

    const statement = db.prepare(`
        WITH attacker_tools AS (
            SELECT DISTINCT
                card_name,
                classification,
                effect_type,
                damage_modifier,
                damage_modifier_timing,
                hp_modifier,
                prevents_knockout,
                requires_attached_no_rule_box,
                requires_attached_name,
                requires_attached_type,
                requires_attached_poisoned,
                requires_attached_full_hp,
                requires_opponent_name,
                requires_opponent_type,
                requires_opponent_ex,
                requires_opponent_ability
            FROM tools
            WHERE supported = 1
                AND effect_type IN (
                    'damage_modifier',
                    'hp_modifier',
                    'knockout_prevention'
                )
                AND classification IN ('offensive', 'both')
            UNION ALL
            SELECT
                NULL, NULL, NULL, 0, NULL, 0, 0, NULL, NULL, NULL, 0, 0,
                NULL, NULL, NULL, 0
        ),
        defender_tools AS (
            SELECT DISTINCT
                card_name,
                classification,
                effect_type,
                damage_modifier,
                damage_modifier_timing,
                hp_modifier,
                prevents_knockout,
                requires_attached_no_rule_box,
                requires_attached_name,
                requires_attached_type,
                requires_attached_poisoned,
                requires_attached_full_hp,
                requires_opponent_name,
                requires_opponent_type,
                requires_opponent_ex,
                requires_opponent_ability
            FROM tools
            WHERE supported = 1
                AND effect_type IN (
                    'damage_modifier',
                    'hp_modifier',
                    'knockout_prevention'
                )
                AND classification IN ('defensive', 'both')
                AND (? = 1 OR card_name != 'Survival Brace')
            UNION ALL
            SELECT
                NULL, NULL, NULL, 0, NULL, 0, 0, NULL, NULL, NULL, 0, 0,
                NULL, NULL, NULL, 0
        ),
        move_data AS (
            SELECT
                attacker.id AS attacker_id,
                attacker.name AS attacker_name,
                attacker.is_ex AS attacker_is_ex,
                attacker.is_mega AS attacker_is_mega,
                attacker.is_tera AS attacker_is_tera,
                attacker.has_rule_box AS attacker_has_rule_box,
                attacker.evolution_stage AS attacker_evolution_stage,
                attacker.pokemon_type AS attacker_type,
                attacker.set_code AS attacker_set_code,
                attacker.card_number AS attacker_card_number,
                moves.name AS move_name,
                moves.cost AS move_cost,
                moves.damage,
                moves.damage_text,
                moves.damage_kind,
                defender.id AS defender_id,
                defender.name AS defender_name,
                defender.hp AS defender_hp,
                defender.is_ex AS defender_is_ex,
                defender.weakness,
                defender.resistance,
                attacker.has_ability AS attacker_has_ability,
                moves.id AS move_id,
                attacking_tool.card_name AS attacker_tool_name,
                defending_tool.card_name AS defender_tool_name,
                attacking_tool.effect_type AS attacker_tool_effect_type,
                defending_tool.effect_type AS defender_tool_effect_type,
                attacking_tool.damage_modifier AS attacker_tool_modifier,
                attacking_tool.damage_modifier_timing
                    AS attacker_tool_modifier_timing,
                defending_tool.damage_modifier AS defender_tool_modifier,
                defending_tool.damage_modifier_timing
                    AS defender_tool_modifier_timing,
                defending_tool.hp_modifier AS defender_hp_modifier,
                defending_tool.prevents_knockout AS prevents_knockout,
                COALESCE(
                    attacking_tool.requires_attached_poisoned,
                    0
                ) AS attacker_tool_requires_poisoned,
                CASE
                    WHEN attacking_tool.card_name IS NULL THEN 1
                    WHEN attacking_tool.requires_attached_no_rule_box = 1
                        AND attacker.has_rule_box = 1 THEN 0
                    WHEN attacking_tool.requires_attached_name IS NOT NULL
                        AND instr(
                            lower(attacker.name),
                            lower(attacking_tool.requires_attached_name)
                        ) = 0 THEN 0
                    WHEN attacking_tool.requires_attached_type IS NOT NULL
                        AND COALESCE(lower(attacker.pokemon_type), '') !=
                            lower(attacking_tool.requires_attached_type)
                        THEN 0
                    WHEN attacking_tool.requires_opponent_name IS NOT NULL
                        AND instr(
                            lower(defender.name),
                            lower(attacking_tool.requires_opponent_name)
                        ) = 0 THEN 0
                    WHEN attacking_tool.requires_opponent_type IS NOT NULL
                        AND instr(
                            lower(attacking_tool.requires_opponent_type),
                            '|' || COALESCE(lower(defender.pokemon_type), '') || '|'
                        ) = 0 THEN 0
                    WHEN attacking_tool.requires_opponent_ex = 1
                        AND defender.is_ex != 1 THEN 0
                    WHEN attacking_tool.requires_opponent_ability = 1
                        AND COALESCE(defender.has_ability, 0) != 1 THEN 0
                    ELSE 1
                END AS attacker_tool_is_applicable,
                CASE
                    WHEN defending_tool.card_name IS NULL THEN 1
                    WHEN defending_tool.requires_attached_no_rule_box = 1
                        AND defender.has_rule_box = 1 THEN 0
                    WHEN defending_tool.requires_attached_name IS NOT NULL
                        AND instr(
                            lower(defender.name),
                            lower(defending_tool.requires_attached_name)
                        ) = 0 THEN 0
                    WHEN defending_tool.requires_attached_type IS NOT NULL
                        AND COALESCE(lower(defender.pokemon_type), '') !=
                            lower(defending_tool.requires_attached_type)
                        THEN 0
                    WHEN defending_tool.requires_opponent_name IS NOT NULL
                        AND instr(
                            lower(attacker.name),
                            lower(defending_tool.requires_opponent_name)
                        ) = 0 THEN 0
                    WHEN defending_tool.requires_opponent_type IS NOT NULL
                        AND instr(
                            lower(defending_tool.requires_opponent_type),
                            '|' || COALESCE(lower(attacker.pokemon_type), '') || '|'
                        ) = 0 THEN 0
                    WHEN defending_tool.requires_opponent_ex = 1
                        AND attacker.is_ex != 1 THEN 0
                    WHEN defending_tool.requires_opponent_ability = 1
                        AND COALESCE(attacker.has_ability, 0) != 1 THEN 0
                    ELSE 1
                END AS defender_tool_is_applicable,
                CASE
                    WHEN defender.weakness IS NOT NULL
                        AND attacker.pokemon_type = defender.weakness
                        THEN 'weakness'
                    WHEN defender.resistance IS NOT NULL
                        AND attacker.pokemon_type = defender.resistance
                        THEN 'resistance'
                    ELSE 'neither'
                END AS match_type
            FROM moves
            JOIN pokemon AS attacker
                ON attacker.id = moves.pokemon_id
            JOIN pokemon AS defender
                ON defender.id = ?
            CROSS JOIN attacker_tools AS attacking_tool
            CROSS JOIN defender_tools AS defending_tool
        ),
        eligible_moves AS (
            SELECT
                *,
                damage
                    + CASE
                        WHEN attacker_tool_modifier_timing =
                            'before_weakness'
                            THEN COALESCE(attacker_tool_modifier, 0)
                        ELSE 0
                    END
                    + CASE
                        WHEN defender_tool_modifier_timing =
                            'before_weakness'
                            THEN COALESCE(defender_tool_modifier, 0)
                        ELSE 0
                    END AS damage_before_weakness,
                COALESCE(defender_hp_modifier, 0) AS applied_hp_modifier,
                defender_hp + COALESCE(defender_hp_modifier, 0)
                    AS effective_defender_hp
            FROM move_data
            WHERE attacker_tool_is_applicable = 1
                AND defender_tool_is_applicable = 1
        ),
        calculated_damage AS (
            SELECT
                *,
                CASE match_type
                    WHEN 'weakness' THEN damage_before_weakness * 2
                    WHEN 'resistance' THEN damage_before_weakness - 30
                    ELSE damage_before_weakness
                END
                    + CASE
                        WHEN attacker_tool_modifier_timing =
                            'after_weakness'
                            THEN COALESCE(attacker_tool_modifier, 0)
                        ELSE 0
                    END
                    + CASE
                        WHEN defender_tool_modifier_timing =
                            'after_weakness'
                            THEN COALESCE(defender_tool_modifier, 0)
                        ELSE 0
                    END AS final_damage,
                CASE match_type
                    WHEN 'weakness' THEN damage * 2
                    WHEN 'resistance' THEN damage - 30
                    ELSE damage
                END AS damage_without_tools
            FROM eligible_moves
        ),
        tool_outcomes AS (
            SELECT
                *,
                COUNT(*) OVER (
                    PARTITION BY attacker_id, move_id, attacker_tool_name
                ) AS applicable_defender_tool_count,
                SUM(
                    CASE
                        WHEN final_damage >= effective_defender_hp
                            AND COALESCE(prevents_knockout, 0) = 0
                            THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY attacker_id, move_id, attacker_tool_name
                ) AS knockout_defender_tool_count
            FROM calculated_damage
        )
        SELECT
            attacker_id,
            move_id,
            attacker_name,
            attacker_is_ex,
            attacker_is_mega,
            attacker_is_tera,
            attacker_has_rule_box,
            attacker_evolution_stage,
            attacker_type,
            attacker_set_code,
            attacker_card_number,
            move_name,
            move_cost,
            damage,
            damage_text,
            damage_kind,
            defender_id,
            defender_name,
            defender_hp,
            defender_is_ex,
            attacker_has_ability,
            weakness,
            resistance,
            attacker_tool_name,
            defender_tool_name,
            attacker_tool_effect_type,
            defender_tool_effect_type,
            attacker_tool_modifier,
            attacker_tool_modifier_timing,
            defender_tool_modifier,
            defender_tool_modifier_timing,
            attacker_tool_requires_poisoned,
            damage_before_weakness,
            applied_hp_modifier,
            effective_defender_hp,
            final_damage,
            match_type,
            CASE
                WHEN knockout_defender_tool_count =
                    applicable_defender_tool_count THEN 1
                ELSE 0
            END AS knocks_out_with_any_defender_tool
        FROM tool_outcomes
        WHERE defender_hp IS NOT NULL
            AND attacker_type IS NOT NULL
            AND final_damage >= effective_defender_hp
            AND COALESCE(prevents_knockout, 0) = 0
            AND (
                attacker_tool_name IS NULL
                OR damage_without_tools < effective_defender_hp
            )
        ORDER BY
            attacker_name COLLATE NOCASE ASC,
            move_name COLLATE NOCASE ASC,
            attacker_tool_name COLLATE NOCASE ASC,
            defender_tool_name COLLATE NOCASE ASC,
            attacker_set_code COLLATE NOCASE ASC,
            attacker_card_number COLLATE NOCASE ASC
    `);

    try {
        statement.bind([includeSurvivalBrace ? 1 : 0, defenderId]);

        const results = [];

        while (statement.step()) {
            results.push(statement.getAsObject());
        }

        return results;
    } finally {
        statement.free();
    }
}

/**
 * List all Pokémon cards so the UI can populate a selector.
 *
 * @returns {Promise<Array<object>>}
 */
async function getPokemonList() {
    const db = await loadDatabase();

    const result = db.exec(`
        SELECT
            id,
            name,
            hp,
            pokemon_type,
            set_code,
            card_number
        FROM pokemon
        ORDER BY
            name COLLATE NOCASE ASC,
            set_code COLLATE NOCASE ASC,
            card_number COLLATE NOCASE ASC
    `);

    if (result.length === 0) {
        return [];
    }

    const { columns, values } = result[0];

    return values.map(row =>
        Object.fromEntries(
            columns.map((column, index) => [column, row[index]])
        )
    );
}

/**
 * Get the information displayed in the defending Pokémon panel.
 *
 * @param {number} defenderId - ID from the pokemon table.
 * @returns {Promise<object|null>}
 */
async function getDefenderDetails(defenderId) {
    const db = await loadDatabase();

    const statement = db.prepare(`
        SELECT
            name,
            hp,
            pokemon_type,
            weakness,
            resistance,
            set_code,
            card_number
        FROM pokemon
        WHERE id = ?
    `);

    try {
        statement.bind([defenderId]);

        if (!statement.step()) {
            return null;
        }

        return statement.getAsObject();
    } finally {
        statement.free();
    }
}

// Expose functions for use by the website.
window.OneShotDatabase = {
    loadDatabase,
    getPokemonList,
    getDefenderDetails,
    findCandidateMoves
};