console.log("Viewport:", window.innerWidth, window.innerHeight);
console.log("Screen:", window.screen.width, window.screen.height);
console.log("Device pixel ratio:", window.devicePixelRatio);

const defenderSelect = document.getElementById("defender");
const defenderInput = document.getElementById("defender-input");
const defenderOptions = document.getElementById("defender-options");

const searchForm = document.getElementById("search-form");
const searchButton = document.getElementById("search-button");

const defenderPanel = document.getElementById("defender-panel");
const defenderHeading = document.getElementById("defender-heading");
const defenderHp = document.getElementById("defender-hp");
const defenderType = document.getElementById("defender-type");
const defenderWeakness = document.getElementById("defender-weakness");
const defenderResistance = document.getElementById("defender-resistance");

const resultsBody = document.getElementById("results-body");
const resultCount = document.getElementById("result-count");
const statusElement = document.getElementById("status");

let allPokemon = [];
let filteredPokemon = [];
let activeSuggestionIndex = -1;


// ---------- Card labels and defender information ----------

function cardLabel(pokemon) {
    const details = [];

    if (pokemon.set_code && pokemon.card_number != null) {
        details.push(`${pokemon.set_code} #${pokemon.card_number}`);
    } else if (pokemon.set_code) {
        details.push(pokemon.set_code);
    } else if (pokemon.card_number != null) {
        details.push(`#${pokemon.card_number}`);
    }

    return details.length
        ? `${pokemon.name} (${details.join("")})`
        : pokemon.name;
}


function setStatus(message, isError = false) {
    statusElement.textContent = message;
    statusElement.classList.toggle("error", isError);
}


function displayDefenderInfo(pokemon) {
    defenderHeading.textContent = cardLabel(pokemon);
    defenderHp.textContent = pokemon.hp != null ? pokemon.hp : "None";

    renderPokemonType(pokemon.pokemon_type, defenderType);
    renderPokemonType(pokemon.weakness, defenderWeakness);
    renderPokemonType(pokemon.resistance, defenderResistance);

    defenderPanel.hidden = false;
}


// ---------- Autocomplete ----------

function closeSuggestions() {
    defenderOptions.hidden = true;
    defenderInput.setAttribute("aria-expanded", "false");
    defenderInput.removeAttribute("aria-activedescendant");
    activeSuggestionIndex = -1;
}


function renderSuggestions(query = "") {
    const normalizedQuery = query.trim().toLowerCase();

    filteredPokemon = normalizedQuery
        ? allPokemon.filter(pokemon => {
            const searchableText = [
                pokemon.name,
                pokemon.set_code,
                pokemon.card_number,
                cardLabel(pokemon)
            ]
                .filter(value => value != null)
                .join(" ")
                .toLowerCase();

            return searchableText.includes(normalizedQuery);
        })
        : allPokemon;

    activeSuggestionIndex = -1;
    defenderOptions.replaceChildren();

    if (filteredPokemon.length === 0) {
        const emptyMessage = document.createElement("div");
        emptyMessage.className = "autocomplete-empty";
        emptyMessage.textContent = "No matching Pokemon cards.";
        defenderOptions.appendChild(emptyMessage);
    } else {
        const fragment = document.createDocumentFragment();

        filteredPokemon.forEach(pokemon => {
            const option = document.createElement("button");

            option.type = "button";
            option.className = "autocomplete-option";
            option.id = `defender-option-${pokemon.id}`;
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", "false");
            option.textContent = cardLabel(pokemon);

            option.addEventListener("mousedown", event => {
                event.preventDefault();
            });

            option.addEventListener("click", () => {
                selectPokemon(pokemon);
            });

            fragment.appendChild(option);
        });

        defenderOptions.appendChild(fragment);
    }

    defenderOptions.hidden = false;
    defenderInput.setAttribute("aria-expanded", "true");
}


function selectPokemon(pokemon) {
    defenderSelect.value = pokemon.id;
    defenderInput.value = cardLabel(pokemon);

    closeSuggestions();
    setStatus("Pokemon selected. Press Search to continue.");
}


function highlightSuggestion(index) {
    const options =
        defenderOptions.querySelectorAll(".autocomplete-option");

    if (options.length === 0) {
        activeSuggestionIndex = -1;
        return;
    }

    activeSuggestionIndex =
        (index + options.length) % options.length;

    options.forEach((option, optionIndex) => {
        const isActive = optionIndex === activeSuggestionIndex;

        option.setAttribute("aria-selected", String(isActive));

        if (isActive) {
            defenderInput.setAttribute(
                "aria-activedescendant",
                option.id
            );

            option.scrollIntoView({ block: "nearest" });
        }
    });
}


defenderInput.addEventListener("focus", () => {
    renderSuggestions(defenderInput.value);
});


defenderInput.addEventListener("click", () => {
    if (defenderOptions.hidden) {
        renderSuggestions(defenderInput.value);
    }
});


defenderInput.addEventListener("input", () => {
    // Typing invalidates the previous selection.
    defenderSelect.value = "";
    renderSuggestions(defenderInput.value);
});


defenderInput.addEventListener("keydown", event => {
    if (event.key === "ArrowDown") {
        event.preventDefault();

        if (defenderOptions.hidden) {
            renderSuggestions(defenderInput.value);
        }

        highlightSuggestion(activeSuggestionIndex + 1);
    } else if (event.key === "ArrowUp") {
        event.preventDefault();

        if (defenderOptions.hidden) {
            renderSuggestions(defenderInput.value);
        }

        highlightSuggestion(
            activeSuggestionIndex === -1
                ? filteredPokemon.length - 1
                : activeSuggestionIndex - 1
        );
    } else if (event.key === "Enter" && !defenderOptions.hidden) {
        if (activeSuggestionIndex >= 0) {
            event.preventDefault();
            selectPokemon(filteredPokemon[activeSuggestionIndex]);
        } else {
            event.preventDefault();
        }
    } else if (event.key === "Escape") {
        closeSuggestions();
    }
});


document.addEventListener("click", event => {
    if (!event.target.closest(".autocomplete")) {
        closeSuggestions();
    }
});


// ---------- Pokémon and move table helpers ----------

function addPokemonCell(row, name, details) {
    const cell = document.createElement("td");

    const nameElement = document.createElement("span");
    nameElement.className = "pokemon-name";
    nameElement.textContent = name;
    cell.appendChild(nameElement);

    if (details !== null && details !== undefined && details !== "") {
        const detailsElement = document.createElement("span");
        detailsElement.className = "card-details";
        detailsElement.textContent = details;
        cell.appendChild(detailsElement);
    }

    row.appendChild(cell);
    return cell;
}


// Map recognized Energy names to local SVG filenames.
const ENERGY_ICON_FILES = {
    grass: "Grass-20px.png",
    fire: "Fire-20px.png",
    water: "Water-20px.png",
    lightning: "Lightning-20px.png",
    psychic: "Psychic-20px.png",
    fighting: "Fighting-20px.png",
    darkness: "Darkness-20px.png",
    metal: "Metal-20px.png",
    dragon: "Dragon-20px.png",
    colorless: "Colorless-20px.png",
};


function renderPokemonType(type, container) {
    container.replaceChildren();

    if (!type) {
        container.textContent = "None";
        return;
    }

    const normalizedType = String(type).trim().toLowerCase();
    const iconFile = ENERGY_ICON_FILES[normalizedType];

    if (!iconFile) {
        container.textContent = type;
        return;
    }

    const icon = document.createElement("img");
    icon.className = "energy-icon";
    icon.src = `./images/energy/${iconFile}`;
    icon.alt = type;
    icon.title = `${type} Type`;

    icon.addEventListener("error", () => {
        container.textContent = type;
    }, { once: true });

    container.appendChild(icon);
}


function renderEnergyCost(cost, container) {
    container.replaceChildren();

    if (cost === null || cost === undefined || cost === "") {
        return;
    }

    const costText = String(cost).trim();

    if (!costText || Number(costText) === 0) {
        const label = document.createElement("span");
        label.className = "cost-label";
        label.textContent = "Cost: ";

        const value = document.createElement("span");
        value.className = "cost-value";
        value.textContent = "No Energy";

        container.replaceChildren(label, value);
        return;
    }

    const energyCodes = {
        G: "grass",
        R: "fire",
        W: "water",
        L: "lightning",
        P: "psychic",
        F: "fighting",
        D: "darkness",
        M: "metal",
        C: "colorless"
    };

    const label = document.createElement("span");
    label.className = "cost-label";
    label.textContent = "Cost: ";
    container.appendChild(label);

    // Split compact codes such as MCCC or FCCC 2 into individual symbols.
    const match = costText.match(/^([A-Z]+)(?:\s+(\d+))?$/);

    if (!match) {
        const fallback = document.createElement("span");
        fallback.textContent = costText;
        container.appendChild(fallback);
        return;
    }

    const codes = match[1];
    const suffix = match[2];

    for (const code of codes) {
        const type = energyCodes[code];
        const iconFile = type ? ENERGY_ICON_FILES[type] : null;

        if (iconFile) {
            const icon = document.createElement("img");
            icon.className = "energy-icon";
            icon.src = `./images/energy/${iconFile}`;
            icon.alt = type;
            icon.title = `${type} Energy`;

            icon.addEventListener("error", () => {
                const fallback = document.createElement("span");
                fallback.textContent = code;
                icon.replaceWith(fallback);
            }, { once: true });

            container.appendChild(icon);
        } else {
            // Colorless and any unsupported symbols use a text fallback.
            const fallback = document.createElement("span");
            fallback.className = "energy-fallback";
            fallback.textContent = code;
            fallback.title = type
                ? `${type} Energy`
                : "Unknown Energy";
            container.appendChild(fallback);
        }
    }

    // Preserve trailing numeric text such as the "2" in "FCCC 2".
    if (suffix) {
        const extra = document.createElement("span");
        extra.textContent = ` ${suffix}`;
        container.appendChild(extra);
    }
}


// ---------- Damage calculations ----------

function formatDamage(move) {
    const hp = Number(move.defender_hp);
    const damage = Number(move.damage);

    switch (move.match_type) {
        case "weakness":
            return {
                type: "Weakness",
                firstLine: `${move.defender_name} has ${hp} HP.`,
                secondLine:
                    `${move.move_name} does ${damage} × 2 = ${damage * 2} damage.`
            };

        case "resistance":
            return {
                type: "Resistance",
                firstLine: `${move.defender_name} has ${hp} HP.`,
                secondLine:
                    `${move.move_name} does ${damage} − 30 = ${damage - 30} damage.`
            };

        default:
            return {
                type: "Neutral",
                firstLine: `${move.defender_name} has ${hp} HP.`,
                secondLine: `${move.move_name} does ${damage} damage.`
            };
    }
}


function showEmptyResults(message) {
    resultsBody.replaceChildren();

    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 3;
    cell.className = "empty-state";
    cell.textContent = message;

    row.appendChild(cell);
    resultsBody.appendChild(row);

    resultCount.textContent = "0 results";
}



function renderResults(moves) {
    resultsBody.replaceChildren();

    if (moves.length === 0) {
        showEmptyResults(
            "No moves met the current damage thresholds for this Pokemon."
        );
        return;
    }

    const fragment = document.createDocumentFragment();

    for (const move of moves) {
        const row = document.createElement("tr");
        const calculation = formatDamage(move);

        // Attacking Pokémon and its type.
        const attackerCell = addPokemonCell(
            row,
            cardLabel({
                name: move.attacker_name,
                set_code: move.attacker_set_code,
                card_number: move.attacker_card_number
            }),
            ""
        );

        const attackerType = document.createElement("span");
        attackerType.className = "card-details";
        attackerCell.appendChild(attackerType);

        const attackerTypeLabel = document.createElement("span");
        attackerTypeLabel.className = "cost-label";
        attackerTypeLabel.textContent = "Type: ";
        attackerType.appendChild(attackerTypeLabel);

        const typeIcon = document.createElement("span");
        attackerType.appendChild(typeIcon);

        renderPokemonType(move.attacker_type, typeIcon);

        // Attacking Pokémon's move and its Energy cost.
        const moveCell = addPokemonCell(
            row,
            move.move_name,
            " "
        );

        const costDetails = moveCell.querySelector(".card-details");

        if (costDetails) {
            renderEnergyCost(move.move_cost, costDetails);
        }

        // Damage calculation and interaction type.
        const damageCell = document.createElement("td");

        const typeLabel = document.createElement("div");
        typeLabel.className =
            `damage-type damage-type-${calculation.type.toLowerCase()}`;
        typeLabel.textContent = calculation.type;

        const firstLine = document.createElement("div");
        firstLine.textContent = calculation.firstLine;

        const secondLine = document.createElement("div");
        secondLine.textContent = calculation.secondLine;

        damageCell.append(typeLabel, firstLine, secondLine);
        row.appendChild(damageCell);

        fragment.appendChild(row);
    }

    resultsBody.appendChild(fragment);

    resultCount.textContent =
        `${moves.length} result${moves.length === 1 ? "" : "s"}`;
}


// ---------- Initialization ----------

async function initialize() {
    try {
        allPokemon = await OneShotDatabase.getPokemonList();

        searchButton.disabled = allPokemon.length === 0;

        setStatus(
            `Database ready. ${allPokemon.length} Pokemon cards loaded.`
        );
    } catch (error) {
        console.error(error);

        setStatus(
            `Could not load the database: ${error.message}`,
            true
        );

        defenderInput.disabled = true;
        searchButton.disabled = true;
    }
}


// ---------- Search submission ----------

searchForm.addEventListener("submit", async event => {
    event.preventDefault();

    const defenderId = Number(defenderSelect.value);

    if (!defenderId) {
        setStatus(
            "Please select a defending Pokemon from the suggestions.",
            true
        );
        defenderInput.focus();
        return;
    }

    searchButton.disabled = true;
    searchButton.textContent = "Searching...";
    setStatus("Loading defending Pokemon information...");

    try {
        const details =
            await OneShotDatabase.getDefenderDetails(defenderId);

        if (!details) {
            throw new Error("Defending Pokemon not found.");
        }

        displayDefenderInfo(details);

        setStatus("Searching for one-shot moves...");

        const moves =
            await OneShotDatabase.findCandidateMoves(defenderId);

        renderResults(moves);
        setStatus("Search complete.");
    } catch (error) {
        console.error(error);

        showEmptyResults("An error occurred while searching.");
        setStatus(`Search failed: ${error.message}`, true);
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = "Search";
    }
});


initialize();
