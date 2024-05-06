#!/bin/bash
cd ../calculator
cp template/tfindex_template.html ../website/tf/index.html
python3 calculator.py > output.txt