#!/usr/bin/env bash
# verify.sh — repository-local release checks. Exit code is the answer.
set -euo pipefail

python -m pytest -q
ruff check .

artifact_dir="${1:-dist}"
python -m build --outdir "$artifact_dir"
python -m twine check "$artifact_dir"/*

echo "verify: OK"
