"""Render real app frames on the badge without sending lamp commands."""

import os
import time


def capture(update):
    for _ in range(12):
        update()
        badge.update()
        time.sleep_ms(20)
    update()
    print("Office rendered:", screen.width, screen.height)
    with open("/state/office-screen.rgb565", "wb") as handle:
        handle.write(screen.raw)
    print("Framebuffer bytes:", len(screen.raw), "stride:", screen.stride)


namespace = {"__name__": "office_render_check", "run": capture}
with open("/system/apps/office/__init__.py") as handle:
    exec(handle.read(), namespace)
namespace["on_exit"]()
print("Configuration valid:", namespace["setup_error"] is None)
