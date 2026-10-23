const defenderSelect = document.getElementById("defender");
const defenderInput = document.getElementById("defender-input");
const defenderOptions = document.getElementById("defender-options");

const searchForm = document.getElementById("search-form");
const searchButton = document.getElementById("search-button");
const clearButton = document.getElementById("clear-button");

const defenderPanel = document.getElementById("defender-panel");
const defenderHeading = document.getElementById("defender-heading");
const defenderHp = document.getElementById("defender-hp");
const defenderType = document.getElementById("defender-type");
const defenderWeakness = document.getElementById("defender-weakness");
const defenderResistance = document.getElementById("defender-resistance");

const resultsBody = document.getElementById("results-body");
const resultCount = document.getElementById("result-count");
const statusElement = document.getElementById("status");

const typeFilterOptions = document.getElementById("type-filter-options");
const clearTypeFilterButton = document.getElementById("clear-type-filter");

const pokemonFilterOptions = document.getElementById("pokemon-filter-options");
const clearPokemonFilterButton = document.getElementById("clear-pokemon-filter");

const evolutionFilterOptions =
    document.getElementById("evolution-filter-options");
const clearEvolutionFilterButton =
    document.getElementById("clear-evolution-filter");

const attackCostEnergyOptions =
    document.getElementById("attack-cost-energy-options");
const attackCostTypeComparison =
    document.getElementById("attack-cost-type-comparison");
const attackCostColorlessSubstitution =
    document.getElementById("attack-cost-colorless-substitution");
const attackCostTotalComparison =
    document.getElementById("attack-cost-total-comparison");
const attackCostTotalCount =
    document.getElementById("attack-cost-total-count");
const clearAttackCostFilterButton =
    document.getElementById("clear-attack-cost-filter");

let allPokemon = [];
let filteredPokemon = [];
let currentMoves = [];
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


function displayDefenderInfo(pokemon) {
    defenderHeading.textContent = cardLabel(pokemon);
    defenderHp.textContent = pokemon.hp != null ? pokemon.hp : "None";

    renderPokemonType(pokemon.pokemon_type, defenderType);
    renderPokemonType(pokemon.weakness, defenderWeakness);
    renderPokemonType(pokemon.resistance, defenderResistance);

    defenderPanel.hidden = false;
}


function setStatus(message, isError = false) {
    statusElement.classList.toggle("error", isError);

    const messageElement = document.getElementById("status-message");
    const breakElement = document.getElementById("status-break");
    const suffixElement = document.getElementById("status-suffix");

    const readyMessage =
        `Database ready. ${allPokemon.length} Pokemon cards loaded.`;
    const isReadyMessage = message === readyMessage;
    statusElement.classList.toggle("status-fit", isReadyMessage);

    if (isReadyMessage) {
        messageElement.textContent =
            `Database ready. ${allPokemon.length}`;
        suffixElement.textContent = "Pokemon cards loaded.";
        breakElement.textContent = "";
        breakElement.classList.add("status-responsive-break");
    } else {
        messageElement.textContent = message;
        suffixElement.textContent = "";
        breakElement.textContent = "";
        breakElement.classList.remove("status-responsive-break");
    }

    fitResponsiveText(statusElement);
}


const fitTextCanvas = document.createElement("canvas");
const fitTextContext = fitTextCanvas.getContext("2d");

function fitTextToWidth(element, text) {
    element.style.fontSize = "";

    const style = getComputedStyle(element);
    const availableWidth = element.clientWidth;
    const baseFontSize = parseFloat(style.fontSize);

    if (!text || !availableWidth || !baseFontSize || !fitTextContext) {
        return;
    }

    fitTextContext.font = style.font;
    const textWidth = fitTextContext.measureText(text).width;

    if (textWidth > 0) {
        element.style.fontSize =
            `${baseFontSize * Math.min(1, availableWidth / textWidth)}px`;
    }
}


function fitResponsiveText(element) {
    if (
        element === statusElement &&
        !element.classList.contains("status-fit")
    ) {
        element.style.fontSize = "";
        Array.from(element.children).forEach(
            child => { child.style.fontSize = ""; }
        );
        return;
    }

    const textLines = Array.from(element.children)
        .map(child => child.textContent.trim())
        .filter(Boolean);
    const text = textLines.join(" ");
    const lineElements = Array.from(element.children).filter(
        child => child.textContent.trim()
    );
    const hasSeparateLines = lineElements.some(
        line => getComputedStyle(line).display === "block"
    );

    if (hasSeparateLines) {
        element.style.fontSize = "";
        lineElements.forEach((line, index) => {
            fitTextToWidth(line, textLines[index]);
        });
    } else {
        lineElements.forEach(line => {
            line.style.fontSize = "";
        });
        fitTextToWidth(element, text);
    }
}


const responsiveTextObserver = new ResizeObserver(entries => {
    entries.forEach(({ target }) => fitResponsiveText(target));
});

responsiveTextObserver.observe(document.getElementById("defender-help"));
responsiveTextObserver.observe(statusElement);
fitResponsiveText(document.getElementById("defender-help"));


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

    searchButton.disabled = false;

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


defenderInput.addEventListener("keydown", event => {
    const options = defenderOptions.querySelectorAll(
        ".autocomplete-option"
    );
    const count = options.length;

    // Tab and Shift + Tab navigate autocomplete suggestions.
    if (event.key === "Tab") {
        if (defenderOptions.hidden || count === 0) {
            return;
        }

        event.preventDefault();

        if (event.shiftKey) {
            // Move backward, wrapping from the first to the last suggestion.
            const previousIndex =
                activeSuggestionIndex <= 0
                    ? count - 1
                    : activeSuggestionIndex - 1;

            highlightSuggestion(previousIndex);
        } else {
            // Move forward, wrapping from the last to the first suggestion.
            const nextIndex =
                activeSuggestionIndex === -1 ||
                activeSuggestionIndex === count - 1
                    ? 0
                    : activeSuggestionIndex + 1;

            highlightSuggestion(nextIndex);
        }

        return;
    }

    if (event.key === "ArrowDown") {
        event.preventDefault();

        if (defenderOptions.hidden) {
            renderSuggestions(defenderInput.value);
        }

        const optionCount = defenderOptions.querySelectorAll(
            ".autocomplete-option"
        ).length;

        if (optionCount > 0) {
            highlightSuggestion(activeSuggestionIndex + 1);
        }
    } else if (event.key === "ArrowUp") {
        event.preventDefault();

        if (defenderOptions.hidden) {
            renderSuggestions(defenderInput.value);
        }

        const optionCount = defenderOptions.querySelectorAll(
            ".autocomplete-option"
        ).length;

        if (optionCount > 0) {
            const previousIndex =
                activeSuggestionIndex === -1
                    ? optionCount - 1
                    : activeSuggestionIndex - 1;

            highlightSuggestion(previousIndex);
        }
    } else if (event.key === "Enter") {
        if (
            activeSuggestionIndex >= 0 &&
            filteredPokemon[activeSuggestionIndex]
        ) {
            event.preventDefault();
            selectPokemon(filteredPokemon[activeSuggestionIndex]);
        }
    } else if (event.key === "Escape") {
        if (!defenderOptions.hidden) {
            event.preventDefault();
            closeSuggestions();
        }
    }
});


defenderInput.addEventListener("blur", () => {
    closeSuggestions();
});


defenderInput.addEventListener("input", () => {
    // Typing invalidates the previous selection.
    defenderSelect.value = "";
    searchButton.disabled = true;

    renderSuggestions(defenderInput.value);
});


document.addEventListener("click", event => {
    if (!event.target.closest(".autocomplete")) {
        closeSuggestions();
    }
});


// ---------- Clear defending Pokemon ----------

clearButton.addEventListener("click", () => {
    defenderInput.value = "";
    defenderSelect.value = "";
    searchButton.disabled = true;

    closeSuggestions();
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


// Map recognized Energy names to local image filenames.
const ENERGY_ICON_FILES = {
    grass: "Grass-30px.png",
    fire: "Fire-30px.png",
    water: "Water-30px.png",
    lightning: "Lightning-30px.png",
    psychic: "Psychic-30px.png",
    fighting: "Fighting-30px.png",
    darkness: "Darkness-30px.png",
    metal: "Metal-30px.png",
    dragon: "Dragon-30px.png",
    colorless: "Colorless-30px.png",
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


// ---------- Empty results ----------


function showEmptyResults(message) {
    resultsBody.replaceChildren();

    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 3;
    cell.className = "empty-state";

    if (message === "No moves match the selected attacking types.") {
        cell.classList.add("empty-selected-types");

        cell.append(
            document.createTextNode("No moves match"),
            Object.assign(document.createElement("span"), {
                className: "line-break-450",
                textContent: " the selected"
            }),
            Object.assign(document.createElement("span"), {
                className: "line-break-277",
                textContent: " attacking types."
            })
        );
    } else if (
        message === "No moves met the current damage thresholds for this Pokemon."
    ) {
        cell.classList.add("empty-default");

        const layouts = [
            {
                className: "empty-layout-wide",
                lines: [
                    "No moves meet the current damage thresholds for this Pokemon."
                ]
            },
            {
                className: "empty-layout-medium",
                lines: [
                    "No moves meet the current",
                    "damage threshold for this Pokemon."
                ]
            },
            {
                className: "empty-layout-narrow",
                lines: [
                    "No moves meet",
                    "the current",
                    "damage thresholds",
                    "for this Pokemon"
                ]
            }
        ];

        for (const layout of layouts) {
            const layoutElement = document.createElement("span");
            layoutElement.className = layout.className;

            layout.lines.forEach((line, index) => {
                if (index > 0) {
                    layoutElement.appendChild(
                        document.createElement("br")
                    );
                }

                layoutElement.appendChild(
                    document.createTextNode(line)
                );
            });

            cell.appendChild(layoutElement);
        }
    } else {
        cell.textContent = message;
    }

    row.appendChild(cell);
    resultsBody.appendChild(row);

    resultCount.textContent = "0 results";
}


// ---------- Render results ----------

function renderResults(
    moves,
    emptyMessage = "No moves met the current damage thresholds for this Pokemon."
) {
    resultsBody.replaceChildren();

    if (moves.length === 0) {
        showEmptyResults(emptyMessage);
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


function renderFilteredResults() {
    const selectedTypes = new Set(
        [...typeFilterOptions.querySelectorAll(
            ".type-filter-option[aria-pressed='true']"
        )].map(button => button.dataset.type.toLowerCase())
    );

    const selectedMechanic =
        pokemonFilterOptions.querySelector(
            ".pokemon-filter-option[aria-pressed='true']"
        )?.dataset.mechanic || "all";

    const selectedStages = new Set(
        [...evolutionFilterOptions.querySelectorAll(
            ".pokemon-filter-option[aria-pressed='true']"
        )].map(button => button.dataset.stage.toLowerCase())
    );

    const energyCostCriteria = [
        ...attackCostEnergyOptions.querySelectorAll(
            ".attack-cost-energy-count"
        )
    ]
        .filter(input => input.value !== "")
        .map(input => ({
            code: input.dataset.energyCode,
            count: Number(input.value)
        }));
    const totalCostCount =
        attackCostTotalCount.value === ""
            ? null
            : Number(attackCostTotalCount.value);

    const filteredMoves = currentMoves.filter(move => {
        const matchesType =
            selectedTypes.size === 0 ||
            selectedTypes.has(
                (move.attacker_type || "").toLowerCase()
            );

        const isEx = Number(move.attacker_is_ex) === 1;
        const isMega = Number(move.attacker_is_mega) === 1;
        const isTera = Number(move.attacker_is_tera) === 1;

        let matchesMechanic;

        switch (selectedMechanic) {
            case "ex":
                matchesMechanic = isEx;
                break;

            case "mega":
                matchesMechanic = isMega;
                break;

            case "tera":
                matchesMechanic = isTera;
                break;

            case "nonex":
                matchesMechanic = !isEx;
                break;

            case "all":
            default:
                matchesMechanic = true;
                break;
        }

        const matchesStage =
            selectedStages.size === 0 ||
            selectedStages.has(
                (move.attacker_evolution_stage || "").toLowerCase()
            );

        const energyCounts = getAttackEnergyCounts(move.move_cost);
        const matchesEnergyTypes = energyCostCriteria.every(
            ({ code, count }) => {
                return matchesEnergyTypeCount(
                    energyCounts,
                    code,
                    attackCostTypeComparison.value,
                    count,
                    attackCostColorlessSubstitution.checked
                );
            }
        );
        const matchesTotalCost =
            totalCostCount === null ||
            compareEnergyCounts(
                energyCounts.total,
                attackCostTotalComparison.value,
                totalCostCount
            );

        return (
            matchesType &&
            matchesMechanic &&
            matchesStage &&
            matchesEnergyTypes &&
            matchesTotalCost
        );
    });

    if (filteredMoves.length === 0) {
        const activeFilters = [];

        if (selectedTypes.size > 0) {
            activeFilters.push("attacking types");
        }
        if (selectedMechanic !== "all") {
            activeFilters.push("attacking mechanic");
        }
        if (selectedStages.size > 0) {
            activeFilters.push("evolution stages");
        }
        if (energyCostCriteria.length > 0) {
            activeFilters.push("attack energy types");
        }
        if (totalCostCount !== null) {
            activeFilters.push("total attack energy cost");
        }

        let emptyMessage;
        if (activeFilters.length === 0) {
            emptyMessage =
                "No moves met the current damage thresholds for this Pokemon.";
        } else {
            const filterDescription = activeFilters.length < 2
                ? activeFilters[0]
                : `${activeFilters.slice(0, -1).join(", ")} and ${
                    activeFilters[activeFilters.length - 1]
                }`;
            emptyMessage =
                `No moves match the selected ${filterDescription}.`;
        }

        showEmptyResults(emptyMessage);
        return;
    }

    renderResults(filteredMoves);
}


function getAttackEnergyCounts(cost) {
    const counts = {
        G: 0,
        R: 0,
        W: 0,
        L: 0,
        P: 0,
        F: 0,
        D: 0,
        M: 0,
        C: 0,
        total: 0
    };

    for (const code of String(cost ?? "").toUpperCase()) {
        if (Object.hasOwn(counts, code) && code !== "total") {
            counts[code] += 1;
            counts.total += 1;
        }
    }

    return counts;
}


function compareEnergyCounts(actual, comparison, expected) {
    switch (comparison) {
        case "<":
            return actual < expected;
        case "<=":
            return actual <= expected;
        case "=":
            return actual === expected;
        case ">=":
            return actual >= expected;
        case ">":
            return actual > expected;
        default:
            return false;
    }
}


function matchesEnergyTypeCount(
    energyCounts,
    code,
    comparison,
    expected,
    colorlessSubstitution
) {
    let minimumCount = energyCounts[code];
    let maximumCount = minimumCount;

    if (colorlessSubstitution && code !== "C") {
        maximumCount += energyCounts.C;
    }

    switch (comparison) {
        case "<":
            return minimumCount < expected;
        case "<=":
            return minimumCount <= expected;
        case "=":
            return minimumCount <= expected && maximumCount >= expected;
        case ">=":
            return maximumCount >= expected;
        case ">":
            return maximumCount > expected;
        default:
            return false;
    }
}


// ---------- Attacking type filters ----------

typeFilterOptions.addEventListener("click", event => {
    const button = event.target.closest(".type-filter-option");

    if (!button) return;

    const isSelected = button.getAttribute("aria-pressed") === "true";
    button.setAttribute("aria-pressed", String(!isSelected));

    renderFilteredResults();
});


clearTypeFilterButton.addEventListener("click", () => {
    typeFilterOptions
        .querySelectorAll(".type-filter-option")
        .forEach(button => {
            button.setAttribute("aria-pressed", "false");
        });

    renderFilteredResults();
});


// ---------- Attacking Pokémon mechanic filters ----------

pokemonFilterOptions.addEventListener("click", event => {
    const button = event.target.closest(".pokemon-filter-option");

    if (!button) return;

    const isSelected = button.getAttribute("aria-pressed") === "true";

    pokemonFilterOptions
        .querySelectorAll(".pokemon-filter-option")
        .forEach(option => {
            option.setAttribute(
                "aria-pressed",
                String(option === button && !isSelected)
            );
        });

    renderFilteredResults();
});


clearPokemonFilterButton.addEventListener("click", () => {
    pokemonFilterOptions
        .querySelectorAll(".pokemon-filter-option")
        .forEach(button => {
            button.setAttribute("aria-pressed", "false");
        });

    renderFilteredResults();
});


// ---------- Evolution stage filters ----------

evolutionFilterOptions.addEventListener("click", event => {
    const button = event.target.closest(".pokemon-filter-option");

    if (!button) return;

    const isSelected = button.getAttribute("aria-pressed") === "true";
    button.setAttribute("aria-pressed", String(!isSelected));

    renderFilteredResults();
});


clearEvolutionFilterButton.addEventListener("click", () => {
    evolutionFilterOptions
        .querySelectorAll(".pokemon-filter-option")
        .forEach(button => {
            button.setAttribute("aria-pressed", "false");
        });

    renderFilteredResults();
});


[
    attackCostEnergyOptions,
    attackCostTypeComparison,
    attackCostColorlessSubstitution,
    attackCostTotalComparison,
    attackCostTotalCount
].forEach(control => {
    control.addEventListener("input", renderFilteredResults);
    control.addEventListener("change", renderFilteredResults);
});


clearAttackCostFilterButton.addEventListener("click", () => {
    attackCostEnergyOptions
        .querySelectorAll(".attack-cost-energy-count")
        .forEach(input => {
            input.value = "";
        });
    attackCostTypeComparison.value = "=";
    attackCostColorlessSubstitution.checked = true;
    attackCostTotalComparison.value = "=";
    attackCostTotalCount.value = "";

    renderFilteredResults();
});


// ---------- Initialization ----------

async function initialize() {
    searchButton.disabled = true;

    try {
        allPokemon = await OneShotDatabase.getPokemonList();

        // A card must be selected before Search is enabled.
        searchButton.disabled = true;

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

        currentMoves =
            await OneShotDatabase.findCandidateMoves(defenderId);

        renderFilteredResults();
        setStatus("Search complete.");
    } catch (error) {
        console.error(error);

        showEmptyResults("An error occurred while searching.");
        setStatus(`Search failed: ${error.message}`, true);
    } finally {
        searchButton.textContent = "Search";

        // Enable only if a valid selection still exists.
        searchButton.disabled = !defenderSelect.value;
    }
});


initialize();
