# Pokemon TCG Analysis

Tools and a static website for analyzing Pokemon TCG cards and calculating
one-hit knockouts.

## Repository layout

- `webscraping/` contains the card-data scraper, generated-data inputs, analysis
  calculator, and related scripts.
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

## Data analysis

The scraper is `webscraping/webscraper.py`. Its CSV data is stored in
`webscraping/data-analysis/data/`. The calculator and its HTML templates are in
`webscraping/data-analysis/calculator/`. Shell launchers are in
`webscraping/scripts/`.
