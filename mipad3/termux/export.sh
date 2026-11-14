#!/usr/bin/env bash
# Pack the results into Downloads so you can copy them to the PC over USB.
# First time only: run  termux-setup-storage  and allow access.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DEST="$HOME/storage/downloads"
[ -d "$DEST" ] || { echo "run termux-setup-storage first"; exit 1; }
[ -d "$ROOT/research/ipsw-ipad7" ] || { echo "nothing to export, run fetch.sh first"; exit 1; }
cd "$ROOT"
zip -r "$DEST/ipad7_parts.zip" research/ipsw-ipad7
echo "ready: $DEST/ipad7_parts.zip  ->  unpack into the repo root on the PC (it recreates research/ipsw-ipad7/)"
