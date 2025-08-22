#!/usr/bin/env bash
set -euo pipefail

python --version
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "Build step completed."
