#!/usr/bin/env bash
# EPL-CDS one-shot setup for macOS.
# Installs OCR system deps (via Homebrew), a Python venv with the package, and
# the web deps. Safe to re-run. OCR is optional — the app still runs without it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!\033[0m %s\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

bold "EPL-CDS setup (macOS)"

# --- prerequisites --------------------------------------------------------
command -v python3 >/dev/null || die "python3 not found. Install with: brew install python@3.12"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' \
  || die "Python 3.10+ required (found $(python3 -V))."
ok "python3 $(python3 -V | awk '{print $2}')"

command -v node >/dev/null || die "node not found. Install with: brew install node"
NODE_MAJOR="$(node -v | sed 's/v//; s/\..*//')"
[ "$NODE_MAJOR" -ge 18 ] || die "Node.js 18+ required (found $(node -v))."
command -v npm >/dev/null || die "npm not found."
ok "node $(node -v)"

# --- OCR system deps (optional, via Homebrew) -----------------------------
if command -v tesseract >/dev/null; then
  ok "tesseract already installed"
elif command -v brew >/dev/null; then
  brew install tesseract poppler && ok "installed tesseract + poppler (OCR enabled)"
else
  warn "Homebrew not found — skipping OCR deps (scan/paper OCR off; app still works)."
  warn "Install Homebrew from https://brew.sh, then re-run for OCR."
fi

# --- Python venv + package ------------------------------------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ok "created virtualenv .venv"
fi
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/pip install -e ".[webapp,ocr]" -q
ok "installed Python package (.venv)"

# --- Web deps -------------------------------------------------------------
( cd web && npm install --no-audit --no-fund )
ok "installed web/ dependencies"

# --- Ollama hint ----------------------------------------------------------
echo
if command -v ollama >/dev/null; then
  MODELS="$(ollama list 2>/dev/null | awk 'NR>1{print $1}' | paste -sd, - || true)"
  ok "ollama found${MODELS:+ (models: $MODELS)}"
  RUN_API="EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=<your-model> .venv/bin/python -m webapp"
else
  warn "ollama not found — LLM extraction/chat will be disabled (manual entry still works)."
  warn "Install with: brew install ollama   (then: ollama pull <model>)"
  RUN_API=".venv/bin/python -m webapp"
fi

echo
bold "Setup complete. To run the demo (two terminals):"
echo "  1) API :5000   $RUN_API"
echo "  2) UI  :3000   cd web && npm run dev"
echo
echo "Then open http://localhost:3000"
