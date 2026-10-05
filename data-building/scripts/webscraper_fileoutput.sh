#!/bin/bash
cd "$(dirname "$0")/../webscraper" || exit
mkdir -p ../scripts_return || exit 1
python3 webscraper.py > ../scripts_return/webscraper_fileoutput.txt 2>&1
