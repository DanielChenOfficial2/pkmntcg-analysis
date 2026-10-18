#!/usr/bin/env bash
set -euo pipefail

# Resolve project directories relative to this script.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CAPACITOR_DIR="$PROJECT_ROOT/capacitor"

echo "==> Building web assets and syncing Android..."
cd "$CAPACITOR_DIR"
npm run cap:sync:android

echo "==> Compiling Android..."
cd "$CAPACITOR_DIR/android"
./gradlew assembleDebug

echo "==> Build complete!"
echo "APK: $CAPACITOR_DIR/android/app/build/outputs/apk/debug/app-debug.apk"
