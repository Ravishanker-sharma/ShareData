#!/bin/bash
# One-command setup for macOS / Linux
# Usage:  bash install_and_run.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "──────────────────────────────────────"
echo "  ShareData — Setup"
echo "──────────────────────────────────────"

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not installed. Download it from https://python.org"
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(sys.version_info.major * 10 + sys.version_info.minor)")
if [ "$PY_VER" -lt 310 ]; then
  echo "ERROR: Python 3.10 or newer required. Found $(python3 --version)"
  exit 1
fi

# Create venv if not present
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✅  Ready! Launching ShareData..."
echo ""
python main.py
