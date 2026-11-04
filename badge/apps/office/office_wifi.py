import errno
import os
import socket
import struct
import time

import machine
import network


CONNECT_MS = 20000
RADIO_OFF_MS = 1000
NTP_MS = 5000
NTP_HOSTS = ("pool.ntp.org", "time.cloudflare.com")


def load_config():
    # Never let a cached/frozen `secrets` import select the old root file.
    config = {}
    with open("/system/secrets.py", "r") as handle:
        exec(handle.read(), config)
    ssid = config.get("WIFI_SSID")
    password = config.get("WIFI_PASSWORD")
    if not isinstance(ssid, str) or not ssid:
        raise ValueError("WIFI_SSID fehlt in /system/secrets.py")
    if not isinstance(password, str):
        raise ValueError("WIFI_PASSWORD fehlt in /system/secrets.py")
    return ssid, password


class Connection:
    def __init__(self):
        self.ssid, self.password = load_config()
        self.radio = network.WLAN(network.STA_IF)
        self.phase = "retry"
        self.since = time.ticks_ms()
        self.delay = 0
        self.failures = 0
        self.message = "WLAN wird gestartet..."
        self.ntp = None
        self.ntp_index = 0
        self.was_ready = False
        self.generation = 0

    def close(self):
        if self.ntp is not None:
            self.ntp.close()
            self.ntp = None

    def _retry(self, message, radio=True):
        self.close()
        self.was_ready = False
        self.message = message
        self.failures += 1
        self.delay = min(30000, 1000 * (2 ** min(self.failures - 1, 5)))
        self.since = time.ticks_ms()
        self.phase = "retry" if radio else "clock-retry"
        print("Office connection:", message)

    def _start_clock(self, now):
        self.message = "Uhrzeit wird synchronisiert..."
        host = NTP_HOSTS[self.ntp_index % len(NTP_HOSTS)]
        self.ntp_index += 1
        address = socket.getaddrinfo(host, 123, 0, socket.SOCK_DGRAM)[0][-1]
        self.ntp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ntp.setblocking(False)
        packet = bytearray(48)
        packet[0] = 0x23
        self.nonce = os.urandom(8)
        packet[40:48] = self.nonce
        self.ntp_address = address
        self.ntp.sendto(packet, address)
        self.since = now
        self.phase = "clock"

    def _read_clock(self, now):
        if time.ticks_diff(now, self.since) >= NTP_MS:
            self._retry("Zeitserver nicht erreichbar", radio=False)
            return
        try:
            packet, address = self.ntp.recvfrom(512)
        except OSError as error:
            if error.errno in (errno.EAGAIN, getattr(errno, "EWOULDBLOCK", errno.EAGAIN)):
                return
            raise
        if (
            address != self.ntp_address or len(packet) < 48
            or packet[0] >> 6 == 3 or packet[0] & 7 != 4
            or not 1 <= packet[1] <= 15 or packet[24:32] != self.nonce
        ):
            return
        seconds = struct.unpack("!I", packet[40:44])[0]
        # NTP epoch 1900; MicroPython ports use either 1970 or 2000.
        epoch = 3155673600 if time.gmtime(0)[0] == 2000 else 2208988800
        utc = time.gmtime(seconds - epoch)
        if not 2026 <= utc[0] <= 2099:
            raise ValueError("Ungueltige Zeitserver-Antwort")
        machine.RTC().datetime((utc[0], utc[1], utc[2], utc[6], utc[3], utc[4], utc[5], 0))
        self.close()
        self.phase = "connected"

    def poll(self):
        now = time.ticks_ms()
        try:
            if self.phase == "retry":
                if time.ticks_diff(now, self.since) < self.delay:
                    return False
                self.radio.active(False)
                self.since = now
                self.phase = "radio-off"
                return False
            if self.phase == "radio-off":
                if time.ticks_diff(now, self.since) < RADIO_OFF_MS:
                    return False
                self.radio.active(True)
                self.radio.connect(self.ssid, self.password)
                self.since = now
                self.phase = "connecting"
                self.message = "WLAN verbindet..."
                return False
            if not self.radio.isconnected():
                status = self.radio.status()
                if self.phase != "connecting" or status < 0 or time.ticks_diff(now, self.since) >= CONNECT_MS:
                    message = {
                        -3: "WLAN-Passwort pruefen",
                        -2: "WLAN nicht gefunden - neuer Versuch",
                    }.get(status, "WLAN unterbrochen - neuer Versuch")
                    self._retry(message)
                return False
            if self.phase == "clock-retry":
                if time.ticks_diff(now, self.since) < self.delay:
                    return False
                self._start_clock(now)
            elif self.phase == "clock":
                self._read_clock(now)
            elif time.gmtime()[0] < 2026:
                self._start_clock(now)
            else:
                if not self.was_ready:
                    self.generation += 1
                self.was_ready = True
                self.failures = 0
                self.phase = "connected"
                self.message = None
                return True
        except OSError as error:
            print("Office network error:", error.errno)
            self._retry("WLAN / Zeitserver: neuer Versuch", radio=not self.radio.isconnected())
        except ValueError:
            self._retry("Uhrzeit ungueltig - neuer Versuch", radio=False)
        return False
