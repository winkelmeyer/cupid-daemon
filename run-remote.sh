#!/bin/zsh
set -euo pipefail
here="${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
phone_address="$("$here/venv/bin/python" "$here/scripts/remote_phone.py")"
if [[ "${1:-}" == "--check" ]]; then
  exit 0
fi
phone() { adb -s "$phone_address" shell "$@"; }
screen_timeout="$(phone settings get system screen_off_timeout | tr -d '\r')"
phone settings put system screen_off_timeout 10800000
trap 'phone settings put system screen_off_timeout "$screen_timeout"' EXIT
"$here/run.sh" agent.py --device "$phone_address" "$@"
