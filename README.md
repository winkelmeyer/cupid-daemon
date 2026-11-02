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

## LLM gateway

The agent, comment writer, and reply suggestions call an Anthropic-compatible gateway through the Anthropic SDK. Set two values in `.env`: `LLM_BASE_URL` (the gateway URL) and `LLM_KEY_VAR` (the name of the environment variable that holds the key). `run.sh` injects the key from the secrets manager at runtime without writing it to disk. Set `CLERA_REPO` if the checkout that provides the secrets command is somewhere other than `~/Clera/clera-platform`.

```sh
./run.sh scripts/test_llm.py
./run.sh agent.py
./run.sh agent.py --no-likes --device "$(adb -d get-serialno)"
```

The first command tests live inference and a synthetic tool round trip; it does not connect to the phone or send messages. The second starts the real session, including likes and the email approval flow for replies. The third uses the USB phone and exposes only chat-reading and reply-proposal tools, so it cannot like or skip profiles. The daily script uses the same launcher. Run manually only when you intend those actions; this change does not install or update the scheduled launch agent.

## Remote access over cellular

Install Tailscale on the Mac and Android phone, sign both into the same account, and connect both. Allow the OS VPN/network extension prompts. The Mac app is expected at `/Applications/Tailscale.app`. No router port forwarding is needed.

Keep the phone attached by USB for the one-time setup:

```sh
venv/bin/python scripts/remote_phone.py --setup
./run-remote.sh --check
```

Setup discovers the phone's Tailscale address (preferring IPv6) from its VPN interface, verifies that it belongs to the Mac's tailnet, enables ADB TCP port 5555, and verifies a remote shell before saving `.phone-address` locally. It never stores the old `100.x.y.z` placeholder. Every remote run checks the tunnel and ADB before starting the agent. On the tested Pixel/cellular setup, IPv6 reached ADB while IPv4 timed out. Accept the Android debugging authorization prompt when it appears.

After setup, disconnect USB and leave the phone on cellular, with Tailscale connected:

```sh
./run-remote.sh --check
./run-remote.sh --no-likes
```

The first command only verifies connectivity. The second checks chats and uses the existing email approval flow. Omit `--no-likes` only for a full session with automatic likes. The phone must be unlocked for UI automation. If Android restarts and the ADB port disappears, reconnect USB and rerun setup. ADB TCP can also listen on local network interfaces; do not forward port 5555 through a router. To turn network ADB off, reconnect USB and run `adb -d usb`.

## Daily job

Use the generator instead of installing the template plist directly; it puts the current checkout's absolute paths into the job:

```sh
venv/bin/python scripts/schedule.py prepare
venv/bin/python scripts/schedule.py enable
venv/bin/python scripts/schedule.py disable
```

`prepare` writes a reviewable plist under `runs/` without enabling it. `enable` requires a passing remote connection check before installing the job. The job starts at 18:00 local time, waits up to three hours, then runs a full Hinge session followed by a full Tinder session. A failure in one app does not stop the other; the job exits non-zero if either failed. It keeps the Mac awake during the delay and run. The Mac must be logged in, awake and online at the scheduled time; this does not configure a system wake timer. Infisical access and the mail app password in the login Keychain must remain available. Output goes to `runs/daily.log`.

## Tinder

```sh
./run-remote.sh --app tinder
./run-remote.sh --app tinder --max-profiles 5
```

`tinder.py` reads the opened profile (only the detail view, not the cards stacked behind it), then likes or passes with the gamepad buttons and checks that the next card appeared. The same hard rules apply; Tinder's values are `Long-term partner` and family plans starting with `I have children`. Free Tinder likes carry no comment, so the agent logs a reason instead. Only the top card of the real swipe deck counts; Tinder's own Preview Profile and Profile tab do not. A card with no age or with ad wording (Sponsored, Learn more, Install, …) is treated as an ad: it is passed, screenshotted to `runs/`, and never shown to the agent. Promo sheets are dismissed before each profile and screenshotted to `runs/`. A match pop-up is screenshotted and dismissed. The session stops on Tinder's out-of-likes screen, an empty deck, or `--max-profiles` (default 40, the daily job uses 150).

Not automated on Tinder yet: the Likes tab (needs Tinder Gold) and chat replies (mapped once there is a first match).
