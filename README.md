# Pokemon TCG Analysis

Tools and a static website for analyzing Pokemon TCG cards and calculating
one-hit knockouts.

## License and Commercial Use

This project is licensed under the [PolyForm Noncommercial License 1.0.0](./LICENSE.md).

You may use, modify, and redistribute this project for permitted noncommercial purposes, subject to the license terms.

**Commercial use requires prior written permission from the copyright holder.** This includes, but is not limited to:

- Selling this software or charging users to access it.
- Monetizing it through advertisements, sponsorships, or other commercial revenue.
- Incorporating its code or substantial portions of it into a commercial application, product, or service.
- Distributing it as part of a paid product or service.

If you wish to use this project commercially, please contact the copyright holder to discuss obtaining a separate commercial license.

Third-party components are governed by their respective licenses. This project's license does not override or restrict permissions independently granted by those licenses.

## Pokémon Intellectual Property and Disclaimer

Pokémon, Pokémon Trading Card Game, and all related names, characters, images, card artwork, logos, and other Pokémon-related assets are the property of their respective rights holders, including Nintendo, Creatures Inc., GAME FREAK inc., and The Pokémon Company, as applicable.

These assets are not owned by the author of this project and are not licensed under this project's PolyForm Noncommercial License. All rights to such assets remain with their respective owners.

This project is an unofficial fan-made tool and is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Creatures Inc., or GAME FREAK inc.

Use of Pokémon-related intellectual property in this project does not imply permission to reproduce, redistribute, or commercially use those assets beyond what is permitted by applicable law or the relevant rights holders.

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

## Energy icon assets

`data-building/scripts/process_energy_icons.py` extracts configured Energy
symbols from the PNG card images in `data-building/data/raw` and writes
32×32 transparent masters at the source symbol's native resolution to
`website/images/energy`. The existing
`*-20px.png` assets and website references are left unchanged.

Install the Python dependencies and run the workflow from the repository root:

```sh
python -m pip install -r requirements.txt
python data-building/scripts/process_energy_icons.py
```

The per-image crop box, symbol center, mask radius, and optional mask inset are
in `data-building/scripts/energy_icons.json`; coordinates are source-image
pixels from the top-left, and `crop_box` is `[left, top, right, bottom]`.
`output_size` and `padding` are configurable at the top of that file, while
`mask_inset` trims the circular mask inward without changing pixel colors.
Adjust an entry and regenerate only that image with, for example:

```sh
python data-building/scripts/process_energy_icons.py --only fire.png --overwrite
```

The script creates `energy-contact-sheet.png` with light and dark previews,
reports skipped or unconfigured inputs, and skips existing master files unless
`--overwrite` is supplied. The current raw images are 460×640 card images and their printed symbols are
about 25 pixels across. The default 29px circular mask is centered at x=419.5
in each 460px-wide source image, with 1px of transparent padding in the 30×30
output. Review the contact sheet and adjust crop settings if needed.

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
