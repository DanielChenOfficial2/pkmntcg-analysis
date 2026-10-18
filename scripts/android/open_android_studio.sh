mkdir -p ../scripts

cat > ../scripts/open-android-studio.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CAPACITOR_DIR="$REPO_ROOT/capacitor"

export CAPACITOR_ANDROID_STUDIO_PATH="/mnt/c/Program Files/Android/Android Studio/bin/studio.exe"

if [[ ! -f "$CAPACITOR_ANDROID_STUDIO_PATH" ]]; then
    echo "Error: Android Studio not found at: $CAPACITOR_ANDROID_STUDIO_PATH" >&2
    exit 1
fi

cd "$CAPACITOR_DIR"
npm run cap:open:android
EOF

chmod +x ../scripts/open-android-studio.sh