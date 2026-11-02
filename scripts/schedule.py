import argparse
import os
import plistlib
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
LABEL = "com.cupid-daemon.daily"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "enable", "disable"])
    args = parser.parse_args()
    domain = f"gui/{os.getuid()}"
    if args.action == "disable":
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=True)
        print("Daily job disabled")
        return
    with (HERE / f"{LABEL}.plist").open("rb") as source:
        config = plistlib.load(source)
    (HERE / "runs").mkdir(exist_ok=True)
    config["ProgramArguments"] = [str(HERE / "daily.sh")]
    config["WorkingDirectory"] = str(HERE)
    config["StandardOutPath"] = str(HERE / "runs" / "daily.log")
    config["StandardErrorPath"] = config["StandardOutPath"]
    prepared = HERE / "runs" / f"{LABEL}.plist"
    with prepared.open("wb") as target:
        plistlib.dump(config, target)
    if args.action == "prepare":
        print(f"Prepared {prepared}; job is not enabled")
        return
    subprocess.run([str(HERE / "run-remote.sh"), "--check"], check=True)
    target = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    target.parent.mkdir(parents=True, exist_ok=True)
    loaded = subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"], capture_output=True)
    if loaded.returncode == 0:
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=True)
    target.write_bytes(prepared.read_bytes())
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print("Daily job enabled: 18:00 local time plus up to three hours delay")


if __name__ == "__main__":
    main()
