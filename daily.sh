#!/bin/zsh
set -euo pipefail
here="${0:A:h}"
exec caffeinate -i /bin/zsh -c '
  sleep "$1"
  failed=0
  "$2/run-remote.sh" --app hinge || failed=1
  "$2/run-remote.sh" --app tinder --max-profiles 150 || failed=1
  exit $failed
' daily "$(( RANDOM % 10800 ))" "$here"
