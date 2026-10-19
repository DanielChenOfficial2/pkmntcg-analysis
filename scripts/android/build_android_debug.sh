#!/usr/bin/env bash
set -euo pipefail

# Resolve project directories relative to this script.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
CAPACITOR_DIR="$PROJECT_ROOT/capacitor"

echo "==> Building web assets and syncing Android..."
cd "$CAPACITOR_DIR"
npm run cap:sync:android

echo "==> Configuring WSL Android SDK..."
export ANDROID_HOME="$HOME/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/platform-tools:$PATH"

printf 'sdk.dir=%s\n' "$ANDROID_HOME" \
    > "$CAPACITOR_DIR/android/local.properties"

echo "==> Compiling Android..."
cd "$CAPACITOR_DIR/android"
./gradlew assembleDebug

echo "==> Build complete!"
echo "APK: $CAPACITOR_DIR/android/app/build/outputs/apk/debug/app-debug.apk"

echo "==> Restoring Windows Android SDK path..."
printf '%s\n' 'sdk.dir=C\:\\Users\\Daniel\\AppData\\Local\\Android\\Sdk' \
    > "$CAPACITOR_DIR/android/local.properties"

echo "==> Windows SDK path restored."

