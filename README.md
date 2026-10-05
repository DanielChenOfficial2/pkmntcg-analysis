# Pokemon TCG Analysis

Tools and a static website for analyzing Pokemon TCG cards and calculating
one-hit knockouts.

## Repository layout

- `data-building/` contains the card-data scraper and its launch scripts.
- `data-analysis/` contains the analysis calculator and related scripts.
- `capacitor/` contains the Capacitor Android and iOS projects and website build
  configuration.
- `website/` contains the static site served by GitHub Pages and packaged by
  Capacitor.

## Website and mobile builds

Install Node.js 22 or newer, then run:

```sh
npm install
npm run build
```

The build prepares generated HTML and compiles the local Tailwind stylesheet
into `website/tailwind.css`. See [CAPACITOR.md](CAPACITOR.md) for Android and
iOS setup and sync instructions.

## Pokémon card data

The data pipeline separates web extraction from storage:

1. `data-building/webscraper/webscraper.py` scrapes Pokémon cards from
   Limitless TCG and writes structured JSON to `data/raw/pokemon_cards.json`.
2. `database/build_database.py` reads that local JSON and builds or updates
   `data/pokemon.db`. It makes no web requests. Its relational schema is in
   `database/schema.sql`.

Install the scraper's Python dependencies with
`python -m pip install -r requirements.txt`. Scrape all configured expansions,
or use the original single-card test page / a specific card page:

```sh
python data-building/webscraper/webscraper.py
python data-building/webscraper/webscraper.py --test
python data-building/webscraper/webscraper.py --card-url "https://limitlesstcg.com/cards/30C/1"
```

Build the database separately from the saved file (no network access needed):

```sh
python database/build_database.py
```

The scraper accepts `--output`; the builder accepts `--input` and `--database`
to choose different file paths. Pokémon attacks, their energy costs, and their original
effect text are stored in related tables. Effect text and ability text remain
uninterpreted.

For example, retrieve cards and their attacks:

```sql
SELECT cards.name, attacks.name, attacks.damage, attacks.effect_text
FROM cards
JOIN attacks ON attacks.card_id = cards.id
WHERE cards.name = 'Bulbasaur';
```

Retrieve each attack's energy cost and effect text:

```sql
SELECT cards.name, attacks.name, attack_costs.energy_type,
       attack_costs.amount, attacks.effect_text
FROM cards
JOIN attacks ON attacks.card_id = cards.id
JOIN attack_costs ON attack_costs.attack_id = attacks.id
WHERE cards.name = 'Bulbasaur';
```

Run the local pipeline tests with `python -m unittest discover -s tests`.
The existing calculator remains under `data-analysis/calculator/`.
