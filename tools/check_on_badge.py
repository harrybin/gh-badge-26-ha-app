"""Read-only hardware check; run with mpremote, never changes lamp state."""

import json
import os
import sys
import time

import wifi

os.chdir("/system/apps/office")
sys.path.insert(0, "/system/apps/office")
from office_client import OfficeClient

with open("/system/office_ha.json") as handle:
    config = json.load(handle)
client = OfficeClient(config, "ha-ca.der")
del config
deadline = time.ticks_add(time.ticks_ms(), 45000)
while not wifi.connect(timeout=10, retries=100000):
    if time.ticks_diff(time.ticks_ms(), deadline) > 0:
        raise RuntimeError("Wi-Fi connection timed out")
    time.sleep_ms(50)
print("Wi-Fi connected")
while not all(client.fresh(i) for i in range(3)):
    client.step()
    if any(client.errors):
        raise RuntimeError(str(client.errors))
    if time.ticks_diff(time.ticks_ms(), deadline) > 0:
        raise RuntimeError("Home Assistant read timed out")
    time.sleep_ms(10)
print("Verified HTTPS readings:", client.values, client.units)
client.close()
print("Screen capture methods:", [name for name in dir(screen) if name in ("save", "to_png", "to_bytes", "buffer")])
