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
 * Weakness match: damage >= half of defender HP.
 * Resistance match: damage >= defender HP + 30.
 * Neither match: damage >= defender HP.
 *
 * @param {number} defenderId - ID from the pokemon table.
 * @returns {Promise<Array<object>>}
 */
async function findCandidateMoves(defenderId) {
    const db = await loadDatabase();

    const statement = db.prepare(`
        SELECT
            attacker.id AS attacker_id,
            attacker.name AS attacker_name,
            attacker.is_ex AS attacker_is_ex,
            attacker.is_mega AS attacker_is_mega,
            attacker.is_tera AS attacker_is_tera,
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
            defender.weakness,
            defender.resistance,
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
        WHERE defender.hp IS NOT NULL
            AND attacker.pokemon_type IS NOT NULL
            AND (
                (
                    attacker.pokemon_type = defender.weakness
                    AND defender.weakness IS NOT NULL
                    AND moves.damage >= defender.hp / 2.0
                )
                OR (
                    attacker.pokemon_type = defender.resistance
                    AND defender.resistance IS NOT NULL
                    AND moves.damage >= defender.hp + 30
                )
                OR (
                    attacker.pokemon_type IS NOT defender.weakness
                    AND attacker.pokemon_type IS NOT defender.resistance
                    AND moves.damage >= defender.hp
                )
            )
        ORDER BY
            attacker.name COLLATE NOCASE ASC,
            moves.name COLLATE NOCASE ASC,
            attacker.set_code COLLATE NOCASE ASC,
            attacker.card_number COLLATE NOCASE ASC
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