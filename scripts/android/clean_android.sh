#!/usr/bin/env bash
set -euo pipefail

# Resolve project directories relative to this script.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ANDROID_DIR="$PROJECT_ROOT/capacitor/android"

echo "==> Stopping Gradle daemons..."
cd "$ANDROID_DIR"
./gradlew --stop

echo "==> Cleaning Android build outputs..."
./gradlew clean

echo "==> Android clean complete!"
