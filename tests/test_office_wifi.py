import errno
import importlib.util
from pathlib import Path
import struct
import sys
import time
import types
import unittest
from unittest.mock import Mock, mock_open, patch


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.year = 2021
        self.radio = Mock()
        self.radio.isconnected.return_value = False
        self.radio.status.return_value = 1
        self.sock = Mock()
        self.sock.recvfrom.side_effect = OSError(errno.EAGAIN, "pending")
        self.socket = Mock()
        self.socket.getaddrinfo.return_value = [(2, 2, 0, "", ("192.0.2.1", 123))]
        self.socket.socket.return_value = self.sock
        self.machine = Mock()
        self.opened = mock_open(read_data="WIFI_SSID='test-network'\nWIFI_PASSWORD='test-password'\n")
        self.real_gmtime = time.gmtime
        patches = [
            patch("builtins.open", self.opened),
            patch.object(time, "ticks_ms", lambda: self.now, create=True),
            patch.object(time, "ticks_diff", lambda a, b: a - b, create=True),
            patch.object(time, "gmtime", lambda value=None: self.real_gmtime(value) if value is not None
                         else (self.year, 1, 1, 0, 0, 0, 0, 1)),
            patch.dict(sys.modules, {
                "network": types.SimpleNamespace(WLAN=lambda _: self.radio, STA_IF=0),
                "machine": self.machine, "socket": self.socket,
            }),
        ]
        for context in patches:
            context.start()
            self.addCleanup(context.stop)
        spec = importlib.util.spec_from_file_location(
            "office_wifi",
            Path(__file__).resolve().parents[1] / "badge" / "apps" / "office" / "office_wifi.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.connection = self.module.Connection()

    def associate(self):
        self.assertFalse(self.connection.poll())
        self.radio.active.assert_called_with(False)
        self.now += self.module.RADIO_OFF_MS
        self.assertFalse(self.connection.poll())
        self.radio.connect.assert_called_with("test-network", "test-password")
        self.radio.isconnected.return_value = True

    def test_reads_only_usb_configuration(self):
        self.opened.assert_called_once_with("/system/secrets.py", "r")

    def test_clock_is_required_before_https(self):
        self.associate()
        self.assertFalse(self.connection.poll())
        self.assertEqual(self.connection.phase, "clock")
        self.assertFalse(self.connection.poll())
        self.assertEqual(self.connection.generation, 0)

    def test_valid_ntp_response_sets_rtc(self):
        self.associate()
        self.connection.poll()
        reply = bytearray(48)
        reply[0], reply[1] = 0x24, 2
        reply[24:32] = self.connection.nonce
        reply[40:44] = struct.pack("!I", 4002825600)  # 2026-11-04 UTC
        self.sock.recvfrom.side_effect = None
        self.sock.recvfrom.return_value = (reply, ("192.0.2.1", 123))
        self.connection.poll()
        self.machine.RTC.return_value.datetime.assert_called_once()
        self.sock.close.assert_called_once()
        self.year = 2026
        self.assertTrue(self.connection.poll())

    def test_unsolicited_ntp_reply_is_not_accepted(self):
        self.associate()
        self.connection.poll()
        self.sock.recvfrom.side_effect = None
        self.sock.recvfrom.return_value = (bytes(48), ("192.0.2.2", 123))
        self.connection.poll()
        self.machine.RTC.return_value.datetime.assert_not_called()
        self.now += self.module.NTP_MS
        self.connection.poll()
        self.assertEqual(self.connection.phase, "clock-retry")

    def test_ntp_timeout_retries_alternate_server_without_radio_reset(self):
        self.associate()
        self.connection.poll()
        self.now += self.module.NTP_MS
        self.connection.poll()
        self.assertEqual(self.connection.phase, "clock-retry")
        self.now += self.connection.delay
        self.connection.poll()
        self.assertEqual(self.socket.getaddrinfo.call_args.args[0], "time.cloudflare.com")

    def test_micropython_errno_without_ewouldblock(self):
        self.module.errno = types.SimpleNamespace(EAGAIN=errno.EAGAIN)
        self.associate()
        self.connection.poll()
        self.assertFalse(self.connection.poll())
        self.assertEqual(self.connection.phase, "clock")

    def test_association_times_out_without_blocking_forever(self):
        self.connection.poll()
        self.now += self.module.RADIO_OFF_MS
        self.connection.poll()
        self.now += self.module.CONNECT_MS
        self.connection.poll()
        self.assertEqual(self.connection.phase, "retry")
        self.assertGreater(self.connection.delay, 0)

    def test_disconnection_resets_radio_with_bounded_backoff(self):
        self.year = 2026
        self.associate()
        self.assertTrue(self.connection.poll())
        self.assertEqual(self.connection.generation, 1)
        self.radio.isconnected.return_value = False
        self.connection.poll()
        self.assertEqual(self.connection.phase, "retry")
        self.assertIn("unterbrochen", self.connection.message)
        self.now += self.connection.delay
        self.connection.poll()
        self.assertEqual(self.connection.phase, "radio-off")
        self.now += self.module.RADIO_OFF_MS
        self.connection.poll()
        self.radio.isconnected.return_value = True
        self.assertTrue(self.connection.poll())
        self.assertEqual(self.connection.generation, 2)

    def test_connect_timeout_and_password_failure_are_visible(self):
        self.connection.poll()
        self.now += self.module.RADIO_OFF_MS
        self.connection.poll()
        self.radio.status.return_value = -3
        self.connection.poll()
        self.assertEqual(self.connection.message, "WLAN-Passwort pruefen")
        for _ in range(10):
            self.connection._retry("test")
        self.assertEqual(self.connection.delay, 30000)

    def test_valid_clock_does_not_need_ntp(self):
        self.year = 2026
        self.associate()
        self.assertTrue(self.connection.poll())
        self.socket.socket.assert_not_called()

    def test_bad_configuration_does_not_connect(self):
        for config in ("WIFI_SSID=''", "WIFI_SSID='test'", "WIFI_SSID=12"):
            with self.subTest(config=config), patch("builtins.open", mock_open(read_data=config)):
                with self.assertRaises(ValueError):
                    self.module.Connection()
        self.radio.connect.assert_not_called()
