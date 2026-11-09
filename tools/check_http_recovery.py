"""Read-only hardware regression using the actual app's update loop."""

import time


namespace = {"__name__": "office_http_recovery"}
BAD_ADDRESS = (2, 1, 0, "", ("192.0.2.1", 8123))


class ReadOnlyBadge:
    def pressed(self, button):
        return False

    def __getattr__(self, name):
        return getattr(badge, name)


namespace["badge"] = ReadOnlyBadge()


def run_check(update):
    deadline = time.ticks_add(time.ticks_ms(), 150000)
    stage = "initial"
    generation = None
    host = None
    while True:
        update()
        badge.update()
        client = namespace["client"]
        connection = namespace["connection"]
        if namespace["setup_error"]:
            raise RuntimeError(namespace["setup_error"])
        fresh = namespace["network_ready"] and all(client.fresh(i) for i in range(len(client.values)))
        if stage == "initial" and fresh:
            print("Actual app HTTPS states:", client.values)
            client.http._addr_info = BAD_ADDRESS
            client.updated = [None] * len(client.values)
            client.refresh()
            stage = "cached"
        elif stage == "cached" and fresh:
            if client.http._addr_info == BAD_ADDRESS:
                raise RuntimeError("Obsolete DNS address was retained")
            print("PASS: obsolete DNS cache replaced without restarting Wi-Fi")
            generation = connection.generation

            host = client.http._host
            client.http._host = "192.0.2.1"
            client.updated = [None] * len(client.values)
            client.refresh()
            stage = "outage"
        elif stage == "outage" and connection.phase == "retry":
            if not connection.radio.isconnected():
                raise RuntimeError("Test did not retain Wi-Fi association")
            print("PASS: failed HTTPS detected despite associated Wi-Fi")
            client.http._host = host
            stage = "recovery"
        elif stage == "recovery" and fresh:
            if connection.generation != generation + 1:
                raise RuntimeError("Expected one automatic Wi-Fi restart")
            print("PASS: actual app reconnected and refreshed all states:", client.values)
            return
        if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            raise RuntimeError("App recovery timed out in " + stage)
        time.sleep_ms(20)


namespace["run"] = run_check
try:
    with open("/system/apps/office/__init__.py") as handle:
        exec(handle.read(), namespace)
finally:
    if "on_exit" in namespace:
        namespace["on_exit"]()
