"""Render real app frames on the badge without sending lamp commands."""

import os
import time


def capture(update):
    deadline = time.ticks_add(time.ticks_ms(), 90000)
    while True:
        update()
        badge.update()
        client = namespace["client"]
        if namespace["setup_error"]:
            raise RuntimeError(namespace["setup_error"])
        if namespace["network_ready"] and all(client.fresh(i) for i in range(len(client.values))):
            break
        if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            raise RuntimeError("Live render timed out")
        time.sleep_ms(20)
    update()
    print("Office rendered:", screen.width, screen.height)
    with open("/state/office-screen.rgb565", "wb") as handle:
        handle.write(screen.raw)
    print("Framebuffer bytes:", len(screen.raw), "stride:", screen.stride)


class ReadOnlyBadge:
    def pressed(self, button):
        return False

    def __getattr__(self, name):
        return getattr(badge, name)


namespace = {"__name__": "office_render_check", "run": capture, "badge": ReadOnlyBadge()}
with open("/system/apps/office/__init__.py") as handle:
    exec(handle.read(), namespace)
namespace["on_exit"]()
print("Configuration valid:", namespace["setup_error"] is None)
