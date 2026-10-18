#!/usr/bin/env bash
set -euo pipefail

# Resolve the repository root relative to this script.
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Build the SQLite database.
python3 data-analysis/calculator/build_damage_database.py

# Copy the database for the website.
mkdir -p website/data
cp data-analysis/datasets/damage_calculator.sqlite3 \
   website/data/damage_calculator.sqlite3

echo "Database copied to website/data/damage_calculator.sqlite3"
