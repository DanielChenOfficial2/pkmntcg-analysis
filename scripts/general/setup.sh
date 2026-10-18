#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR/capacitor" || exit 1
sudo apt update
sudo apt install npm
sudo apt install python3
sudo apt install python3-pip
pip install requests
pip install bs4
pip install pandas
npm install
