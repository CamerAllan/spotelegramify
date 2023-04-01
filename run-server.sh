#!/usr/bin/env bash
set -Eeuo pipefail

pip install -r requirements.txt
nohup npx nodemon src/main.py prod > ./output 2>&1 &
