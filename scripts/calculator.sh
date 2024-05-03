#!/bin/bash
cd ../calculator
python3 calculator.py > data.txt
cd ..
cp calculator/pkmn_data.json website/pkmn_data.json