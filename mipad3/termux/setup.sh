#!/usr/bin/env bash
# Run once in Termux:  bash mipad3/termux/setup.sh
set -e
pkg update -y
pkg install -y python git zip unzip curl
python3 --version
echo "Optional (only if the device tree is LZFSE-compressed): pip install lzfse"
