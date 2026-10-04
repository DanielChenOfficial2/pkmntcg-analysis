#!/bin/bash
cd "$(dirname "$0")/.." || exit
python3 webscraper.py > webscraper_fileoutput.txt
