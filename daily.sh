#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
source ./.env

sleep $(( RANDOM % 10800 ))

export ANTHROPIC_API_KEY="$(security find-generic-password -s anthropic-api-key -w)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

adb connect "$PHONE_ADB"
if [[ "$(adb -s "$PHONE_ADB" get-state)" != "device" ]]; then
  echo "phone not reachable at $PHONE_ADB" >&2
  exit 1
fi

caffeinate -i venv/bin/python agent.py
