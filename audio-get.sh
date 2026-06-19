#!/usr/bin/env bash
DIR="$(dirname "$(readlink -f "$0")")"
exec "$DIR/.venv/bin/python" "$DIR/main.py" "$@"
