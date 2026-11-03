import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, mock_open, patch


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.wifi = Mock()
        spec = importlib.util.spec_from_file_location(
            "office_wifi",
            Path(__file__).resolve().parents[1] / "badge" / "apps" / "office" / "office_wifi.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"wifi": self.wifi}):
            spec.loader.exec_module(self.module)

    def test_explicitly_uses_usb_configuration_not_imported_secrets(self):
        opened = mock_open(read_data="WIFI_SSID = 'test-network'\nWIFI_PASSWORD = 'test-password'\n")
        stale = Mock(WIFI_SSID="old-network", WIFI_PASSWORD="old-password")
        with patch("builtins.open", opened), patch.dict(sys.modules, {"secrets": stale}):
            self.module.start_wifi()
        opened.assert_called_once_with("/system/secrets.py", "r")
        self.wifi.disconnect.assert_called_once()
        self.wifi.connect.assert_called_once_with(
            ssid="test-network", psk="test-password", timeout=10, retries=100000
        )
        self.assertEqual(self.wifi.method_calls[0][0], "disconnect")

    def test_invalid_configuration_does_not_connect(self):
        for config in ("WIFI_SSID = ''", "WIFI_SSID = 'test'", "WIFI_SSID = 12"):
            with self.subTest(config=config), patch("builtins.open", mock_open(read_data=config)):
                with self.assertRaises(ValueError):
                    self.module.start_wifi()
        self.wifi.connect.assert_not_called()
        self.wifi.disconnect.assert_not_called()

    def test_missing_usb_config_does_not_fall_back_to_old_credentials(self):
        with patch("builtins.open", side_effect=OSError("missing")):
            with self.assertRaises(OSError):
                self.module.start_wifi()
        self.wifi.connect.assert_not_called()
