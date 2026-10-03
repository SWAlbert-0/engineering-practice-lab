#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Explicit --manager venv should not require a working Conda installation.
use_conda=true
for ((i=1; i<=$#; i++)); do
  if [[ "${!i}" == "--manager=venv" ]]; then use_conda=false; fi
  if [[ "${!i}" == "--manager" ]]; then
    j=$((i+1)); if [[ "${!j-}" == "venv" ]]; then use_conda=false; fi
  fi
done
conda_command="${CONDA_EXE:-}"
if [[ -z "$conda_command" || ! -f "$conda_command" ]]; then
  conda_command="$(command -v conda || true)"
fi
if $use_conda && [[ -n "$conda_command" ]]; then
  export CONDA_EXE="$conda_command"
  exec "$conda_command" run --no-capture-output -n base python "$project_root/launch.py" "$@"
fi
for python_command in python3.12 python3 python; do
  if command -v "$python_command" >/dev/null 2>&1; then
    exec "$python_command" "$project_root/launch.py" "$@"
  fi
done
echo 'Python was not found. Install Miniconda/Anaconda, or Python 3.12 with venv, then retry.' >&2
exit 1
