import importlib.util
from pathlib import Path
import types
import unittest


spec = importlib.util.spec_from_file_location(
    "configure_autostart",
    Path(__file__).resolve().parents[1] / "tools" / "configure_autostart.py",
)
autostart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(autostart)


class AutostartTests(unittest.TestCase):
    source = '''import machine
watchdog = machine.WDT_RESET
app_to_launch = launch("/system/apps/menu")
launch(app_to_launch)
'''

    def test_cold_boot_opens_office(self):
        calls = []
        machine = types.ModuleType("machine")
        machine.WDT_RESET = 3
        machine.reset_cause = lambda: 1
        from unittest.mock import patch
        with patch.dict("sys.modules", {"machine": machine}):
            exec(autostart.patch_main(self.source), {"launch": calls.append})
        self.assertEqual(calls, ["/system/apps/office"])

    def test_watchdog_return_opens_menu(self):
        calls = []
        machine = types.ModuleType("machine")
        machine.WDT_RESET = 3
        machine.reset_cause = lambda: 3

        def launch(path):
            calls.append(path)
            return "/system/apps/settings"

        from unittest.mock import patch
        with patch.dict("sys.modules", {"machine": machine}):
            exec(autostart.patch_main(self.source), {"launch": launch})
        self.assertEqual(calls, ["/system/apps/menu", "/system/apps/settings"])

    def test_patch_is_idempotent(self):
        patched = autostart.patch_main(self.source)
        self.assertEqual(autostart.patch_main(patched), patched)

    def test_unknown_boot_file_is_rejected(self):
        with self.assertRaises(ValueError):
            autostart.patch_main("launch('/other')")
