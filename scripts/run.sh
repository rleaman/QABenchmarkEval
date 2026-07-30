#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}" python "${PWD}/src/main.py" update "${1:-configs/config.yaml}"
