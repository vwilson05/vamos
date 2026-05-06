#!/usr/bin/env bash
# vamos launcher — single-command setup + run.
#
#   ./launch.sh                 # ensure venv, install deps, launch UI
#   ./launch.sh --install-crons # additionally install vamos-managed crons
#   ./launch.sh --no-ui         # setup only, don't launch UI
#   ./launch.sh --update        # re-run pip install -e '.[ui]' even if .venv exists
#   ./launch.sh --port 9000     # override UI port (default 8501)
#
# Cross-platform note: this is bash. Windows users: see launch.ps1.

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

# --- args ---
INSTALL_CRONS=0
NO_UI=0
UPDATE_DEPS=0
DO_PREP=0
PORT=8501
while [ $# -gt 0 ]; do
  case "$1" in
    --install-crons) INSTALL_CRONS=1; shift ;;
    --no-ui)         NO_UI=1; shift ;;
    --update)        UPDATE_DEPS=1; shift ;;
    --prep)          DO_PREP=1; shift ;;
    --port)          PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown flag: $1"; exit 64 ;;
  esac
done

PY="${PYTHON:-python3}"

# --- venv ---
if [ ! -d ".venv" ]; then
  echo "[launch] creating virtualenv .venv"
  "$PY" -m venv .venv
  UPDATE_DEPS=1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# --- deps ---
if [ "$UPDATE_DEPS" -eq 1 ] || ! command -v vamos >/dev/null 2>&1; then
  echo "[launch] installing vamos + Streamlit (this may take a minute on first run)"
  # --no-cache-dir avoids the noisy "Cache entry deserialization failed" warnings
  # that appear when pip's user cache is from a different Python version.
  pip install -q --no-cache-dir --upgrade pip
  pip install -q --no-cache-dir -e '.[ui]'
fi

# --- .env sanity ---
if [ ! -f ".env" ]; then
  echo "[launch] WARNING: .env not found. Copy .env.example to .env and fill in your ADO_PAT."
  echo "[launch]   cp .env.example .env"
fi

# --- auto-prep (read VAMOS_AUTO_PREP from .env if --prep wasn't passed) ---
if [ "$DO_PREP" -eq 0 ] && [ -f ".env" ]; then
  if grep -q '^VAMOS_AUTO_PREP=true' .env 2>/dev/null; then
    DO_PREP=1
  fi
fi
if [ "$DO_PREP" -eq 1 ]; then
  echo "[launch] running morning prep (sod + inbox + standup)"
  vamos prep || echo "[launch] WARNING: prep failed; continuing to UI launch"
fi

# --- crons (optional) ---
if [ "$INSTALL_CRONS" -eq 1 ]; then
  if [ ! -f "crons.yml" ]; then
    echo "[launch] crons.yml not found; copying from crons.yml.example"
    cp crons.yml.example crons.yml
  fi
  echo "[launch] installing crons (current ones first):"
  vamos cron-list
  vamos cron-install
fi

# --- UI ---
if [ "$NO_UI" -eq 1 ]; then
  echo "[launch] setup complete (UI launch skipped via --no-ui)"
  exit 0
fi

URL="http://localhost:${PORT}"
echo ""
echo "================================================================"
echo "  vamos UI starting at:  $URL"
echo "================================================================"
echo ""

# Belt-and-suspenders: open the browser ourselves a couple seconds in,
# in case Streamlit's auto-open doesn't fire (happens behind some VPNs).
case "$(uname -s)" in
  Darwin)  ( sleep 3 && open "$URL" 2>/dev/null ) & ;;
  Linux)   ( sleep 3 && xdg-open "$URL" 2>/dev/null ) & ;;
esac

exec vamos ui --port "$PORT"
