import argparse
import ipaddress
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ADDRESS_FILE = HERE / ".phone-address"
TAILSCALE = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
TAILNETS = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{args[0]} failed")
    return result.stdout.strip()


def validate_address(address):
    host, port = address.rsplit(":", 1)
    ip = ipaddress.ip_address(host.strip("[]"))
    if not any(ip in network for network in TAILNETS) or port != "5555":
        raise ValueError("Expected a Tailscale IP address with port 5555")
    if ip.version == 6 and host != f"[{ip}]":
        raise ValueError("IPv6 addresses require brackets: [address]:5555")
    return str(ip)


def connect(address):
    host = validate_address(address)
    status = json.loads(run(TAILSCALE, "status", "--json"))
    if status.get("BackendState") != "Running":
        raise RuntimeError("Sign in and connect Tailscale on the Mac first")
    peers = (status.get("Peer") or {}).values()
    if not any(host in peer.get("TailscaleIPs", []) for peer in peers):
        raise RuntimeError("Phone is not in this Mac's tailnet; sign both into the same account")
    run(TAILSCALE, "ping", "--c=3", "--until-direct=false", host)
    result = run("adb", "connect", address)
    if "connected to" not in result:
        raise RuntimeError(f"{result}. Reconnect USB and run scripts/remote_phone.py --setup")
    if run("adb", "-s", address, "get-state") != "device":
        raise RuntimeError("Remote ADB is not ready; check the phone's authorization prompt")
    if run("adb", "-s", address, "shell", "echo", "CUPID_REMOTE_OK") != "CUPID_REMOTE_OK":
        raise RuntimeError("Remote shell check failed")
    print("PASS remote ADB shell over Tailscale", file=sys.stderr)
    return address


def setup():
    status = json.loads(run(TAILSCALE, "status", "--json"))
    if status.get("BackendState") != "Running":
        raise RuntimeError("Sign in and connect Tailscale on the Mac first")
    serial = run("adb", "-d", "get-serialno")
    interfaces = json.loads(run("adb", "-s", serial, "shell", "ip", "-j", "addr"))
    addresses = [
        item["local"]
        for interface in interfaces
        if interface["ifname"].startswith("tun")
        for item in interface.get("addr_info", [])
        if any(ipaddress.ip_address(item["local"]) in network for network in TAILNETS)
    ]
    if not addresses:
        raise RuntimeError("Connect Tailscale on the USB phone first; no tailnet address found")
    host = max(addresses, key=lambda address: ipaddress.ip_address(address).version)
    if not any(host in peer.get("TailscaleIPs", []) for peer in (status.get("Peer") or {}).values()):
        raise RuntimeError("USB phone is not in the Mac's tailnet")
    run(TAILSCALE, "ping", "--c=3", "--until-direct=false", host)
    if run("adb", "-s", serial, "shell", "getprop", "service.adb.tcp.port") != "5555":
        run("adb", "-s", serial, "tcpip", "5555")
        time.sleep(3)
    endpoint = f"[{host}]:5555" if ipaddress.ip_address(host).version == 6 else f"{host}:5555"
    address = connect(endpoint)
    ADDRESS_FILE.write_text(address + "\n")
    ADDRESS_FILE.chmod(0o600)
    return address


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    args = parser.parse_args()
    try:
        if args.setup:
            address = setup()
        else:
            address = ADDRESS_FILE.read_text().strip() if ADDRESS_FILE.exists() else os.environ.get("PHONE_ADB", "")
            if not address:
                raise RuntimeError("Remote address missing; connect USB and run scripts/remote_phone.py --setup")
            address = connect(address)
        print(address)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Remote phone: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
