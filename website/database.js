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
 * @returns {Promise<Array<object>>}
 */
async function findCandidateMoves(defenderId) {
    const db = await loadDatabase();

    const statement = db.prepare(`
        WITH attacker_tools AS (
            SELECT DISTINCT
                card_name,
                classification,
                damage_modifier,
                requires_attached_no_rule_box,
                requires_opponent_ex
            FROM tools
            WHERE supported = 1
                AND effect_type = 'damage_modifier'
                AND classification IN ('offensive', 'both')
            UNION ALL
            SELECT NULL, NULL, 0, NULL, NULL
        ),
        defender_tools AS (
            SELECT DISTINCT
                card_name,
                classification,
                damage_modifier,
                requires_attached_no_rule_box,
                requires_opponent_ex
            FROM tools
            WHERE supported = 1
                AND effect_type = 'damage_modifier'
                AND classification IN ('defensive', 'both')
            UNION ALL
            SELECT NULL, NULL, 0, NULL, NULL
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
                attacking_tool.card_name AS attacker_tool_name,
                defending_tool.card_name AS defender_tool_name,
                CASE
                    WHEN attacking_tool.card_name IS NOT NULL
                        AND (
                            attacking_tool.requires_attached_no_rule_box IS NULL
                            OR attacker.has_rule_box = 0
                        )
                        AND (
                            attacking_tool.requires_opponent_ex IS NULL
                            OR defender.is_ex =
                                attacking_tool.requires_opponent_ex
                        )
                        THEN attacking_tool.damage_modifier
                    ELSE 0
                END AS attacker_damage_modifier,
                CASE
                    WHEN defending_tool.card_name IS NOT NULL
                        AND (
                            defending_tool.requires_attached_no_rule_box IS NULL
                            OR defender.has_rule_box = 0
                        )
                        AND (
                            defending_tool.requires_opponent_ex IS NULL
                            OR attacker.is_ex =
                                defending_tool.requires_opponent_ex
                        )
                        THEN defending_tool.damage_modifier
                    ELSE 0
                END AS defender_damage_modifier,
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
        calculated_damage AS (
            SELECT
                *,
                CASE match_type
                    WHEN 'weakness'
                        THEN (damage + attacker_damage_modifier) * 2
                    WHEN 'resistance'
                        THEN damage + attacker_damage_modifier - 30
                    ELSE damage + attacker_damage_modifier
                END + defender_damage_modifier AS final_damage,
                CASE match_type
                    WHEN 'weakness' THEN damage * 2
                    WHEN 'resistance' THEN damage - 30
                    ELSE damage
                END + defender_damage_modifier AS damage_without_attacker_tool
            FROM move_data
        )
        SELECT
            attacker_id,
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
            weakness,
            resistance,
            attacker_tool_name,
            defender_tool_name,
            attacker_damage_modifier,
            defender_damage_modifier,
            final_damage,
            match_type
        FROM calculated_damage
        WHERE defender_hp IS NOT NULL
            AND attacker_type IS NOT NULL
            AND final_damage >= defender_hp
            AND (
                attacker_tool_name IS NULL
                OR attacker_damage_modifier <> 0
            )
            AND (
                defender_tool_name IS NULL
                OR defender_damage_modifier <> 0
            )
            AND (
                attacker_tool_name IS NULL
                OR damage_without_attacker_tool < defender_hp
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
        statement.bind([defenderId]);

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