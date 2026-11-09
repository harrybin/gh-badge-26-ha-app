"""Hardware regression: recover lost RTC and Wi-Fi, then read HA without switching."""

import json
import os
import sys
import time

import machine

os.chdir("/system/apps/office")
sys.path.insert(0, "/system/apps/office")
from office_client import OfficeClient
from office_wifi import Connection


def wait_ready(connection):
    deadline = time.ticks_add(time.ticks_ms(), 120000)
    while not connection.poll():
        if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            raise RuntimeError(connection.message)
        time.sleep_ms(20)


def read_states(client):
    deadline = time.ticks_add(time.ticks_ms(), 45000)
    while not all(client.fresh(i) for i in range(len(client.values))):
        client.step()
        if any(client.errors):
            raise RuntimeError(str(client.errors))
        if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            raise RuntimeError("HTTPS state verification timed out")
        time.sleep_ms(10)
    print("Verified HTTPS states:", client.values)


machine.RTC().datetime((2021, 1, 1, 4, 0, 0, 0, 0))
print("Simulated power-loss clock:", time.gmtime()[:6])
connection = Connection()
with open("/system/office_ha.json") as handle:
    config = json.load(handle)
client = OfficeClient(config, "ha-ca.der")
del config
try:
    wait_ready(connection)
    print("Clock automatically restored:", time.gmtime()[:6])
    read_states(client)
    generation = connection.generation
    connection.radio.active(False)
    client.connection_lost()
    print("Simulated radio loss")
    wait_ready(connection)
    if connection.generation != generation + 1:
        raise RuntimeError("Connection recovery was not detected")
    read_states(client)
    print("PASS: lost RTC, verified HTTPS, radio recovery, fresh HA states")
finally:
    client.close()
    connection.close()
