#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CAPACITOR_DIR="$REPO_ROOT/capacitor"

cd "$CAPACITOR_DIR"

echo "Syncing web assets to Android..."
npx cap sync android

echo "Android sync complete."
