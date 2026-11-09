import errno
import json
import socket
import time
import tls

import fetch


ENTITIES = (
    "sensor.gewachshaus_temperatur",
    "sensor.gewachshaus_luftfeuchtigkeit",
    "light.wled",
    "switch.hintergrundlicht_socket_1",
)
LIGHTS = (2, 3)
LIGHT_NAMES = ("OctoCat-Lamp", "LED-Lampe")
POLL_MS = 300000
STALE_MS = POLL_MS + 45000
LIGHT_POLL_MS = 5000
LIGHT_STALE_MS = 20000
REQUEST_FAILURE_LIMIT = 3


class VerifiedFetch(fetch.AsyncFetch):
    # Firmware's default fetch disables certificate verification. Keep its
    # incremental HTTP engine, but require our public CA and hostname check.
    def __init__(self, host, port, ca_file):
        super().__init__(host, port, use_tls=True, max_bytes=8192, timeout=8)
        self.context = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
        self.context.verify_mode = tls.CERT_REQUIRED
        with open(ca_file, "rb") as handle:
            self.context.load_verify_locations(handle.read())

    def _connect(self):
        self._phase = "dns"
        # Firmware reset() keeps its DNS cache, even after a failed connection.
        self._addr_info = None
        self._addr_info = socket.getaddrinfo(
            self._host, self._port, 0, socket.SOCK_STREAM
        )[0]
        family, kind, protocol, _, address = self._addr_info
        sock = socket.socket(family, kind, protocol)
        sock.setblocking(False)
        self._phase = "connect"
        try:
            try:
                sock.connect(address)
            except OSError as error:
                if error.errno != errno.EINPROGRESS:
                    raise
            sock = self.context.wrap_socket(
                sock, server_hostname=self._host, do_handshake_on_connect=False
            )
        except OSError:
            sock.close()
            self._addr_info = None
            raise
        self._sock = sock
        yield


class OfficeClient:
    def __init__(self, config, ca_file, transport=None):
        url = config["url"].rstrip("/")
        if not url.startswith("https://"):
            raise ValueError("Home Assistant braucht HTTPS")
        address = url[8:]
        if "/" in address:
            raise ValueError("Home Assistant URL ohne Pfad angeben")
        host, _, port = address.partition(":")
        self.http = transport or VerifiedFetch(host, int(port or 443), ca_file)
        self.headers = {
            "Authorization": "Bearer " + config["token"],
            "Content-Type": "application/json",
        }
        self.values = [None] * len(ENTITIES)
        self.units = ["C", "%", "", ""]
        self.updated = [None] * len(ENTITIES)
        self.errors = [None] * len(ENTITIES)
        self.queue = list(range(len(ENTITIES)))
        self.active = None
        self.started = None
        self.last_poll = time.ticks_ms()
        self.last_light_poll = self.last_poll
        self.command = None
        self.expected = None
        self.message = None
        self.message_at = None
        self.network_failures = 0

    @property
    def needs_reconnect(self):
        return self.network_failures >= REQUEST_FAILURE_LIMIT

    @property
    def busy(self):
        return self.command is not None or self.expected is not None

    def fresh(self, index, now=None):
        now = time.ticks_ms() if now is None else now
        stamp = self.updated[index]
        return (
            stamp is not None
            and time.ticks_diff(now, stamp) < (LIGHT_STALE_MS if index in LIGHTS else STALE_MS)
            and self.errors[index] is None
        )

    def refresh(self):
        for index in range(len(ENTITIES)):
            if index not in self.queue and self.active != index:
                self.queue.append(index)

    def set_light(self, target=None, index=2):
        if index not in LIGHTS:
            raise ValueError("Ungueltige Lampe")
        if self.busy or not self.fresh(index) or self.values[index] not in ("on", "off"):
            return False
        if target is None:
            target = "off" if self.values[index] == "on" else "on"
        if target not in ("on", "off"):
            raise ValueError("Ungueltiger Lampenzustand")
        if target == self.values[index]:
            return False
        self.command = (index, target)
        self.message = None
        return True

    def _notice(self, message):
        self.message = message
        self.message_at = time.ticks_ms()

    def _start(self, job):
        self.active = job
        self.started = time.ticks_ms()
        self.http.reset()
        if job == "command":
            self.expected = self.command
            self.command = None
            index, target = self.expected
            domain = ENTITIES[index].split(".")[0]
            self.http.fetch(
                "/api/services/" + domain + "/turn_" + target,
                headers=self.headers,
                data=json.dumps({"entity_id": ENTITIES[index]}).encode(),
                method="POST",
            )
        else:
            self.http.fetch(
                "/api/states/" + ENTITIES[job],
                headers=self.headers,
                method="GET",
            )

    def _confirm(self, index):
        self.queue = [index] + [queued for queued in self.queue if queued != index]

    def _fail(self, message, network=False):
        job = self.active
        self.network_failures = self.network_failures + 1 if network else 0
        self.http.reset()
        self.active = None
        self._notice(message)
        if job == "command":
            # A timed-out POST may have reached HA. Never replay it blindly.
            index = self.expected[0]
            self.updated[index] = None
            self.expected = None
            self._confirm(index)
        elif isinstance(job, int):
            self.errors[job] = message
            if self.expected is not None and job == self.expected[0]:
                self.expected = None

    def step(self):
        now = time.ticks_ms()
        if self.message_at is not None and time.ticks_diff(now, self.message_at) > 8000:
            self.message = None
        if time.ticks_diff(now, self.last_poll) >= POLL_MS:
            self.refresh()
            self.last_poll = now
        if time.ticks_diff(now, self.last_light_poll) >= LIGHT_POLL_MS:
            for index in LIGHTS:
                if self.active != index and index not in self.queue:
                    self.queue.append(index)
            self.last_light_poll = now
        try:
            if self.active is None:
                if self.command is not None:
                    self._start("command")
                elif self.queue:
                    self._start(self.queue.pop(0))
                else:
                    return
            if time.ticks_diff(now, self.started) > 12000:
                self._fail("Zeitlimit - neuer Versuch", network=True)
                return
            status = self.http.update()
            if status == fetch.AsyncFetch.DONE:
                self.network_failures = 0
                job = self.active
                if job == "command":
                    self._confirm(self.expected[0])
                else:
                    data = self.http.to_json()
                    if not isinstance(data, dict) or data.get("entity_id") != ENTITIES[job]:
                        raise ValueError("Unerwartete Entity")
                    state = data.get("state")
                    if job < 2:
                        if state in ("unknown", "unavailable", None):
                            self.values[job] = None
                        else:
                            value = float(state)
                            if value != value or abs(value) == float("inf"):
                                raise ValueError("Ungueltiger Messwert")
                            self.values[job] = value
                        unit = data.get("attributes", {}).get("unit_of_measurement")
                        self.units[job] = unit or ("C" if job == 0 else "%")
                    else:
                        self.values[job] = state if state in ("on", "off") else None
                        if self.expected is not None and job == self.expected[0]:
                            if state == self.expected[1]:
                                self._notice(LIGHT_NAMES[job - 2] + " ist " + ("an" if state == "on" else "aus"))
                            else:
                                self._notice("Nicht bestaetigt - neu laden")
                            self.expected = None
                    self.updated[job] = now
                    self.errors[job] = None
                self.active = None
            elif status == fetch.AsyncFetch.ERROR:
                self._fail("Home Assistant antwortet nicht", network=True)
        except fetch.HTTPException:
            code = self.http.http_status
            message = {
                401: "Token ungueltig",
                403: "Zugriff verweigert",
                404: "Entity nicht gefunden",
            }.get(code, "Home Assistant: HTTP " + str(code))
            self._fail(message)
        except OSError as error:
            print("Office request network error:", error.errno)
            self._fail("Verbindung unterbrochen - neuer Versuch", network=True)
        except (ValueError, KeyError, TypeError) as error:
            print("Office request failed:", type(error).__name__)
            self._fail("Verbindung / Daten pruefen")

    def close(self):
        self.http.reset()

    def connection_lost(self):
        # A POST may already have reached HA. Drop it; never replay on reconnect.
        if self.busy or self.active == "command":
            self._notice("Verbindung weg - Lampenstatus pruefen")
        self.command = None
        self.expected = None
        self.active = None
        self.network_failures = 0
        self.updated = [None] * len(ENTITIES)
        self.http.reset()
        self.queue = list(range(len(ENTITIES)))
