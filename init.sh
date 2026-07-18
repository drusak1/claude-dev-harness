#!/usr/bin/env bash
# Standard startup path: every session begins here. Idempotent, offline.
set -euo pipefail
cd "$(dirname "$0")"

echo "== init: $(pwd)"

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "ERROR: python is not installed."
    echo "  WHY: the ledger, the project registry and the session hooks are Python."
    echo "  FIX: install Python 3.9+ (https://www.python.org/downloads/)."
    exit 1
fi

if [ ! -f projects.json ]; then
    echo "NOTE: projects.json not found -- creating one from projects.example.json."
    echo "  Edit it to point at your repos, then re-run ./init.sh"
    cp projects.example.json projects.json
fi

make check
echo "== baseline OK -- ready to work"
echo
make projects-list
