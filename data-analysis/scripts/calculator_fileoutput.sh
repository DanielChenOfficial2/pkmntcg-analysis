#!/bin/bash
cd "$(dirname "$0")/../data-analysis/calculator" || exit
python3 calculator.py > calculator_fileoutput.txt