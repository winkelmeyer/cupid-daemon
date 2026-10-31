# cupid-daemon

Drives the Hinge Android app over ADB: reads each profile, skips by hard rules, and sends likes with a comment written in your own voice.

## Setup
1. `brew install android-platform-tools scrcpy`
2. Phone: enable Developer options and USB debugging, plug in, accept the prompt.
3. `python3 -m venv venv && venv/bin/pip install uiautomator2 anthropic`
4. `cp persona.example.md persona.md` and fill it in with real facts about yourself.

## Scripts
- `swipe.py dump hinge` — save a screenshot and UI tree of the current Hinge screen.
- `swipe.py swipe hinge <n>` — go through n profiles; rule skips are automatic, you decide like/skip for the rest.
- `next_match.py` — skip rule-failing profiles until one passes, then print it.
- `reply.py` — suggest replies for the open chat; sends only after you confirm.
- `step.py` — tap/type helper that prints the visible UI labels.

Rules live at the top of `swipe.py` (`MAX_AGE`, `SKIP_IF_PRESENT`). Every action is logged to `swipe.log`.

Automating Hinge breaks its Terms of Service and can get the account and phone number banned.
