import ast
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "office"


class HTTPException(Exception):
    pass


class Transport:
    DONE, ERROR, FETCHING = 2, 3, 1

    def __init__(self):
        self.calls = []
        self.result = None
        self.http_status = 200
        self.failure = None
        self.resets = 0

    def reset(self):
        self.resets += 1

    def fetch(self, path, **kwargs):
        self.calls.append((path, kwargs))

    def update(self):
        if self.failure:
            raise self.failure
        return self.DONE if self.result is not None else self.FETCHING

    def to_json(self):
        return self.result


FETCH = types.SimpleNamespace(AsyncFetch=Transport, HTTPException=HTTPException)
with patch.dict(sys.modules, {"fetch": FETCH, "tls": types.ModuleType("tls")}):
    spec = importlib.util.spec_from_file_location("office_client", APP / "office_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.clock = patch.object(time, "ticks_ms", lambda: self.now, create=True)
        self.diff = patch.object(time, "ticks_diff", lambda a, b: a - b, create=True)
        self.clock.start()
        self.diff.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.diff.stop)
        self.http = Transport()
        self.client = module.OfficeClient(
            {"url": "https://example.test:8123", "token": "test-not-a-real-token"},
            "unused.pem", self.http
        )

    def response(self, index, state):
        self.http.result = {"entity_id": module.ENTITIES[index], "state": state, "attributes": {}}
        self.client.step()
        self.http.result = None

    def load(self):
        for index, value in enumerate(("24.0", "36", "off")):
            self.response(index, value)

    def test_reads_only_three_entities(self):
        self.load()
        self.assertEqual(self.client.values, [24.0, 36.0, "off"])
        self.assertEqual(len(self.http.calls), 3)
        self.assertTrue(all(self.client.fresh(i) for i in range(3)))

    def test_toggle_uses_service_then_confirms(self):
        self.load()
        self.assertTrue(self.client.set_light())
        self.http.result = []
        self.client.step()
        path, options = self.http.calls[-1]
        self.assertEqual(path, "/api/services/light/turn_on")
        self.assertEqual(options["method"], "POST")
        self.assertEqual(json.loads(options["data"]), {"entity_id": "light.wled"})
        self.assertEqual(self.client.values[2], "off")
        self.assertTrue(self.client.busy)
        self.response(2, "on")
        self.assertFalse(self.client.busy)
        self.assertEqual(self.client.message, "OctoCat-Lamp ist an")

    def test_stale_and_unavailable_disable_control(self):
        self.load()
        self.now += module.STALE_MS
        self.assertFalse(self.client.set_light())
        self.client.queue = [2]
        self.response(2, "unavailable")
        self.assertIsNone(self.client.values[2])
        self.assertFalse(self.client.set_light())

    def test_post_failure_never_replays_command(self):
        self.load()
        self.client.set_light()
        self.http.failure = OSError("timeout")
        self.client.step()
        self.assertIsNone(self.client.expected)
        self.assertIsNone(self.client.command)
        self.assertFalse(self.client.fresh(2))
        self.http.failure = None
        self.response(2, "on")
        posts = [call for call in self.http.calls if call[1]["method"] == "POST"]
        self.assertEqual(len(posts), 1)

    def test_unauthorized_is_explicit(self):
        self.http.http_status = 401
        self.http.failure = HTTPException()
        self.client.step()
        self.assertEqual(self.client.errors[0], "Token ungueltig")

    def test_confirmation_mismatch_not_success(self):
        self.load()
        self.client.set_light()
        self.http.result = []
        self.client.step()
        self.response(2, "off")
        self.assertEqual(self.client.message, "Nicht bestaetigt - neu laden")

    def test_invalid_sensor_does_not_replace_last_reading(self):
        self.load()
        self.client.queue = [0]
        self.response(0, "nan")
        self.assertEqual(self.client.values[0], 24.0)
        self.assertFalse(self.client.fresh(0))

    def test_request_deadline_and_refresh_dedup(self):
        self.client.step()
        self.client.refresh()
        self.client.refresh()
        self.assertEqual(self.client.queue, [1, 2])
        self.now += 12001
        self.client.step()
        self.assertIn("Zeitlimit", self.client.errors[0])

    def test_repeated_press_does_not_double_send(self):
        self.load()
        self.assertTrue(self.client.set_light())
        self.assertFalse(self.client.set_light())
        self.assertFalse(self.client.set_light("off"))

    def test_rejects_plain_http(self):
        with self.assertRaises(ValueError):
            module.OfficeClient({"url": "http://example.test", "token": "x"}, "", self.http)

    def test_refresh_starts_at_exactly_five_minutes(self):
        self.load()
        self.now += 299999
        self.client.step()
        self.assertEqual(self.http.calls[-1][0], "/api/states/light.wled")
        self.response(2, "off")
        self.assertTrue(self.client.fresh(2))
        self.now += 1
        self.client.step()
        self.assertEqual(len(self.http.calls), 5)
        self.assertEqual(self.http.calls[-1][0], "/api/states/" + module.ENTITIES[0])
        self.assertEqual(self.client.queue, [1, 2])

    def test_stale_grace_covers_scheduled_refresh(self):
        self.load()
        self.now += 344999
        self.assertTrue(self.client.fresh(0))
        self.assertTrue(self.client.fresh(1))
        self.now += 1
        self.assertFalse(self.client.fresh(0))
        self.assertFalse(self.client.fresh(1))

    def test_external_light_changes_are_polled_every_five_seconds(self):
        self.load()
        self.now += 4999
        self.client.step()
        self.assertEqual(len(self.http.calls), 3)
        self.now += 1
        self.response(2, "on")
        self.assertEqual(self.http.calls[-1][0], "/api/states/light.wled")
        self.assertEqual(self.client.values[2], "on")
        self.now += 5000
        self.response(2, "off")
        self.assertEqual(self.client.values[2], "off")
        self.assertEqual(len(self.http.calls), 5)
        self.assertTrue(all(call[1]["method"] == "GET" for call in self.http.calls))

    def test_light_becomes_stale_before_sensor_values(self):
        self.load()
        self.now += module.LIGHT_STALE_MS - 1
        self.assertTrue(self.client.fresh(2))
        self.now += 1
        self.assertFalse(self.client.fresh(2))
        self.assertFalse(self.client.set_light())
        self.assertTrue(self.client.fresh(0))

    def test_light_poll_does_not_duplicate_active_request(self):
        self.load()
        self.now += module.LIGHT_POLL_MS
        self.client.step()
        self.now += module.LIGHT_POLL_MS
        self.client.step()
        self.assertEqual(self.client.active, 2)
        self.assertEqual(self.client.queue, [])


class ButtonTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((APP / "__init__.py").read_text())
        update = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "update")
        self.client = Mock()
        self.pressed = set()
        self.env = {
            "badge": types.SimpleNamespace(pressed=lambda key: key in self.pressed),
            "time": types.SimpleNamespace(ticks_ms=lambda: 1000),
            "wifi": types.SimpleNamespace(is_connected=lambda: True, connect=lambda **kw: True),
            "client": self.client, "setup_error": None, "wifi_started": True,
            "on_exit": Mock(), "draw": Mock(),
        }
        for key in ("SELECT", "LEFT", "RIGHT", "UP", "DOWN", "MENU", "BACK"):
            self.env["BUTTON_" + key] = key
        exec(compile(ast.Module(body=[update], type_ignores=[]), "<update>", "exec"), self.env)

    def test_select_returns_home_and_closes_requests(self):
        self.pressed.add("SELECT")
        self.env["setup_error"] = "offline"
        self.assertEqual(self.env["update"](), "/system/apps/menu")
        self.env["on_exit"].assert_called_once()
        self.client.set_light.assert_not_called()
        self.client.step.assert_not_called()

    def test_down_toggles_light(self):
        self.pressed.add("DOWN")
        self.env["update"]()
        self.client.set_light.assert_called_once_with()
        self.client.refresh.assert_not_called()

    def test_other_buttons_refresh_without_switching(self):
        for key in ("LEFT", "RIGHT", "UP", "MENU", "BACK"):
            with self.subTest(key=key):
                self.client.reset_mock()
                self.pressed.clear()
                self.pressed.add(key)
                self.env["update"]()
                self.client.refresh.assert_called_once_with()
                self.client.set_light.assert_not_called()


if __name__ == "__main__":
    unittest.main()
