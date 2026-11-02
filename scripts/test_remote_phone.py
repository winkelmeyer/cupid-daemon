import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import remote_phone


class RemotePhoneTests(unittest.TestCase):
    def test_rejects_non_tailnet_addresses_before_connecting(self):
        for address in ["100.x.y.z:5555", "192.168.1.2:5555", "8.8.8.8:5555", "100.64.0.1:22"]:
            with self.subTest(address=address), patch.object(remote_phone, "run") as run:
                with self.assertRaises(ValueError):
                    remote_phone.connect(address)
                run.assert_not_called()

    def test_signed_out_does_not_enable_network_adb(self):
        with patch.object(remote_phone, "run", return_value='{"BackendState":"NeedsLogin"}') as run:
            with self.assertRaisesRegex(RuntimeError, "Sign in"):
                remote_phone.setup()
            self.assertEqual(run.call_count, 1)

    def test_only_accepts_a_peer_in_this_tailnet(self):
        status = {"BackendState": "Running", "Peer": None}
        with patch.object(remote_phone, "run", return_value=json.dumps(status)) as run:
            with self.assertRaisesRegex(RuntimeError, "not in this Mac's tailnet"):
                remote_phone.connect("100.64.0.1:5555")
            self.assertEqual(run.call_count, 1)

    def test_connect_requires_a_working_remote_shell(self):
        status = {"BackendState": "Running", "Peer": {"phone": {"TailscaleIPs": ["100.64.0.1"]}}}
        replies = [json.dumps(status), "pong", "connected to 100.64.0.1:5555", "device", "CUPID_REMOTE_OK"]
        with patch.object(remote_phone, "run", side_effect=replies) as run:
            self.assertEqual(remote_phone.connect("100.64.0.1:5555"), "100.64.0.1:5555")
            self.assertEqual(run.call_args.args, ("adb", "-s", "100.64.0.1:5555", "shell", "echo", "CUPID_REMOTE_OK"))

    def test_ipv6_requires_brackets_and_tailnet_prefix(self):
        self.assertEqual(remote_phone.validate_address("[fd7a:115c:a1e0::1]:5555"), "fd7a:115c:a1e0::1")
        for address in ["fd7a:115c:a1e0::1:5555", "[2001:db8::1]:5555"]:
            with self.assertRaises(ValueError):
                remote_phone.validate_address(address)

    def test_setup_prefers_ipv6_and_saves_verified_endpoint(self):
        host = "fd7a:115c:a1e0::1"
        endpoint = f"[{host}]:5555"
        status = {"BackendState": "Running", "Peer": {"phone": {"TailscaleIPs": ["100.64.0.1", host]}}}
        interfaces = [{"ifname": "tun0", "addr_info": [{"local": "100.64.0.1"}, {"local": host}]}]
        replies = [json.dumps(status), "test-device", json.dumps(interfaces), "pong", "5555"]
        with tempfile.TemporaryDirectory() as directory:
            address_file = Path(directory) / ".phone-address"
            with (
                patch.object(remote_phone, "ADDRESS_FILE", address_file),
                patch.object(remote_phone, "run", side_effect=replies),
                patch.object(remote_phone.time, "sleep"),
                patch.object(remote_phone, "connect", return_value=endpoint) as connect,
            ):
                self.assertEqual(remote_phone.setup(), endpoint)
                connect.assert_called_once_with(endpoint)
                self.assertEqual(address_file.read_text().strip(), endpoint)

    def test_failed_setup_does_not_save_address(self):
        status = {"BackendState": "Running", "Peer": {"phone": {"TailscaleIPs": ["100.64.0.1"]}}}
        interfaces = [{"ifname": "tun0", "addr_info": [{"local": "100.64.0.1"}]}]
        replies = [json.dumps(status), "test-device", json.dumps(interfaces), "pong", "5555"]
        with tempfile.TemporaryDirectory() as directory:
            address_file = Path(directory) / ".phone-address"
            with (
                patch.object(remote_phone, "ADDRESS_FILE", address_file),
                patch.object(remote_phone, "run", side_effect=replies),
                patch.object(remote_phone.time, "sleep"),
                patch.object(remote_phone, "connect", side_effect=RuntimeError("unreachable")),
            ):
                with self.assertRaisesRegex(RuntimeError, "unreachable"):
                    remote_phone.setup()
                self.assertFalse(address_file.exists())


if __name__ == "__main__":
    unittest.main()
