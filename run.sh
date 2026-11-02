#!/bin/zsh
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
here="${0:A:h}"
clera_repo="${CLERA_REPO:-$HOME/Clera/clera-platform}"
script="${1:?Usage: ./run.sh <script.py> [args...]}"
shift
set -a
source "$here/.env"
set +a
cd "$clera_repo"
exec pnpm secrets:run:prod -- "$here/venv/bin/python" "$here/$script" "$@"
