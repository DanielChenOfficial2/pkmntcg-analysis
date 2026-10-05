#!/usr/bin/env python3
"""Convenience entry point for the Pokémon card scraper."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
WEBSCRAPER_DIR = REPO_ROOT / "data-building" / "webscraper"
if str(WEBSCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(WEBSCRAPER_DIR))

import webscraper


if __name__ == "__main__":
    webscraper.main()
