#!/bin/bash
cd "$(dirname "$0")/../webscraper" || exit
python3 webscraper.py > ../scripts_return/webscraper_fileoutput.txt
