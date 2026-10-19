#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CAPACITOR_DIR="$REPO_ROOT/capacitor"
ANDROID_DIR="$CAPACITOR_DIR/android"

export CAPACITOR_ANDROID_STUDIO_PATH="/mnt/c/Program Files/Android/Android Studio/bin/studio.exe"

if [[ ! -f "$CAPACITOR_ANDROID_STUDIO_PATH" ]]; then
    echo "Error: Android Studio not found at: $CAPACITOR_ANDROID_STUDIO_PATH" >&2
    exit 1
fi

if [[ ! -f "$ANDROID_DIR/settings.gradle" && ! -f "$ANDROID_DIR/settings.gradle.kts" ]]; then
    echo "Error: Android project not found at: $ANDROID_DIR" >&2
    echo "Expected settings.gradle or settings.gradle.kts" >&2
    exit 1
fi

echo "Opening Android project:"
echo "$ANDROID_DIR"

WIN_ANDROID_DIR="$(wslpath -w "$ANDROID_DIR")"

nohup "$CAPACITOR_ANDROID_STUDIO_PATH" "$WIN_ANDROID_DIR" \
    >/dev/null 2>&1 </dev/null &
disown
