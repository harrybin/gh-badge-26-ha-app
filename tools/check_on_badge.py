"""Read-only hardware check; run with mpremote, never changes lamp state."""

import json
import os
import sys
import time


os.chdir("/system/apps/office")
sys.path.insert(0, "/system/apps/office")
from office_client import OfficeClient
from office_wifi import Connection

with open("/system/office_ha.json") as handle:
    config = json.load(handle)
client = OfficeClient(config, "ha-ca.der")
del config
deadline = time.ticks_add(time.ticks_ms(), 90000)
connection = Connection()
while not connection.poll():
    if time.ticks_diff(time.ticks_ms(), deadline) > 0:
        raise RuntimeError("Wi-Fi connection timed out")
    time.sleep_ms(50)
print("Wi-Fi and clock ready:", time.gmtime()[:6])
while not all(client.fresh(i) for i in range(len(client.values))):
    client.step()
    if any(client.errors):
        raise RuntimeError(str(client.errors))
    if time.ticks_diff(time.ticks_ms(), deadline) > 0:
        raise RuntimeError("Home Assistant read timed out")
    time.sleep_ms(10)
print("Verified HTTPS readings:", client.values, client.units)
previous = client.updated[2:]
deadline = time.ticks_add(time.ticks_ms(), 15000)
while any(client.updated[i + 2] == stamp for i, stamp in enumerate(previous)):
    client.step()
    if any(client.errors[2:]):
        raise RuntimeError(str(client.errors[2:]))
    if time.ticks_diff(time.ticks_ms(), deadline) > 0:
        raise RuntimeError("Independent lamp status poll timed out")
    time.sleep_ms(10)
print("Independent lamp refresh:", client.values[2:])
client.close()
connection.close()
print("Screen capture methods:", [name for name in dir(screen) if name in ("save", "to_png", "to_bytes", "buffer")])
