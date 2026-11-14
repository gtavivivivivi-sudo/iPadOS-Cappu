#!/usr/bin/env bash
# Pull the iPad7,11 device tree + image list from the IPSW without downloading it.
# Run from anywhere:  bash mipad3/termux/fetch.sh [ipsw-url]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/../tools/fetch_j171ap.py" "$@"
