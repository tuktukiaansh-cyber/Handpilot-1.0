#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

echo "HandPilot macOS vision repair"
echo "Python: $PYTHON"

"$PYTHON" -m pip uninstall -y mediapipe >/dev/null 2>&1 || true
"$PYTHON" -m pip install --no-cache-dir "mediapipe==0.10.35"
"$PYTHON" -m pip check
"$PYTHON" tools/doctor.py

echo
echo "Repair complete. Launch with:"
echo "  $PYTHON main.py"
