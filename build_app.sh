#!/bin/bash
# Build a standalone .app (macOS) or .exe (Windows)
# Run this ONCE; distribute the output in dist/

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "──────────────────────────────────────"
echo "  ShareData — Build"
echo "──────────────────────────────────────"

source .venv/bin/activate 2>/dev/null || true
pip install -q pyinstaller

# Detect arch and download cloudflared for bundling
SYSTEM="$(uname -s)"
ARCH="$(uname -m)"

if [ "$SYSTEM" = "Darwin" ]; then
  if [ "$ARCH" = "arm64" ]; then
    CF_FILE="cloudflared-darwin-arm64"
  else
    CF_FILE="cloudflared-darwin-amd64"
  fi
else
  CF_FILE="cloudflared-linux-amd64"
fi

if [ ! -f "$CF_FILE" ]; then
  echo "Downloading cloudflared for bundling..."
  curl -L -o "$CF_FILE" \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/$CF_FILE"
  chmod +x "$CF_FILE"
fi

echo "Building..."
pyinstaller build.spec --clean --noconfirm

echo ""
echo "✅  Build complete!  Output:"
ls -lh dist/
