set -euo pipefail

# Install Java and required utilities.
sudo apt-get update
sudo apt-get install -y openjdk-21-jdk curl unzip

# Define the Linux Android SDK location.
export ANDROID_HOME="$HOME/Android/Sdk"
mkdir -p "$ANDROID_HOME/cmdline-tools"

# Download Google's Linux command-line tools.
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

curl -fL \
    "https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip" \
    -o "$TEMP_DIR/cmdline-tools.zip"

# Install into the required cmdline-tools/latest layout.
unzip -q "$TEMP_DIR/cmdline-tools.zip" -d "$TEMP_DIR"

rm -rf "$ANDROID_HOME/cmdline-tools/latest"
mv "$TEMP_DIR/cmdline-tools" \
    "$ANDROID_HOME/cmdline-tools/latest"

# Configure the SDK for this terminal.
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# Accept SDK licenses.
yes | sdkmanager --sdk_root="$ANDROID_HOME" --licenses

# Install the Linux SDK components.
sdkmanager --sdk_root="$ANDROID_HOME" \
    "platform-tools" \
    "platforms;android-35" \
    "build-tools;35.0.0"

echo "Android SDK installation complete."
