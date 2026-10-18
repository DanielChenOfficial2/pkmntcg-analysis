#!/usr/bin/env bash
set -euo pipefail

# Install and configure the Android SDK for WSL/Linux.
# Run from any directory; paths are resolved relative to this script.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
CMDLINE_TOOLS_DIR="$ANDROID_HOME/cmdline-tools/latest"
TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip"

echo "==> Installing prerequisites..."
sudo apt-get update
sudo apt-get install -y wget unzip

echo "==> Preparing Android SDK directory..."
mkdir -p "$ANDROID_HOME/cmdline-tools"

if [[ ! -x "$CMDLINE_TOOLS_DIR/bin/sdkmanager" ]]; then
    echo "==> Downloading Android command-line tools..."
    TEMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TEMP_DIR"' EXIT

    wget -q --show-progress "$TOOLS_URL" \
        -O "$TEMP_DIR/commandlinetools.zip"

    echo "==> Extracting command-line tools..."
    unzip -q "$TEMP_DIR/commandlinetools.zip" -d "$TEMP_DIR"

    if [[ -d "$CMDLINE_TOOLS_DIR" ]]; then
        mv "$CMDLINE_TOOLS_DIR" "$TEMP_DIR/old-latest"
    fi

    mv "$TEMP_DIR/cmdline-tools" "$CMDLINE_TOOLS_DIR"
fi

export ANDROID_HOME
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$CMDLINE_TOOLS_DIR/bin:$ANDROID_HOME/platform-tools:$PATH"

echo "==> Accepting Android SDK licenses..."
sdkmanager --sdk_root="$ANDROID_HOME" --licenses

echo "==> Installing Android SDK packages..."
sdkmanager --sdk_root="$ANDROID_HOME" \
    "platform-tools" \
    "platforms;android-36" \
    "build-tools;35.0.0"

echo "==> Configuring Gradle SDK path..."
printf 'sdk.dir=%s\n' "$ANDROID_HOME" \
    > "$PROJECT_ROOT/capacitor/android/local.properties"

echo "==> Setup complete!"
echo "Android SDK: $ANDROID_HOME"
echo "Gradle config: $PROJECT_ROOT/capacitor/android/local.properties"
echo
echo "Add these lines to ~/.bashrc if they aren't already present:"
echo "export ANDROID_HOME=\"$ANDROID_HOME\""
echo 'export ANDROID_SDK_ROOT="$ANDROID_HOME"'
echo 'export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"'
