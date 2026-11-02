#!/bin/zsh
set -euo pipefail
here="${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
phone_address="$("$here/venv/bin/python" "$here/scripts/remote_phone.py")"
if [[ "${1:-}" == "--check" ]]; then
  exit 0
fi
exec "$here/run.sh" agent.py --device "$phone_address" "$@"
