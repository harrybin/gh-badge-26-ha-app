import json
import os
import sys
import time

import missing_details

APP_DIR = "/system/apps/office"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
from office_client import ENTITIES, OfficeClient
from office_wifi import Connection

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
screen.font = missing_details.mona_sans()

BG = color.rgb(13, 23, 32)
PANEL = color.rgb(55, 39, 89)
INK = color.rgb(239, 247, 248)
MUTED = color.rgb(165, 187, 197)
CYAN = color.rgb(102, 222, 224)
AMBER = color.rgb(255, 202, 112)
DIM = color.rgb(51, 72, 83)
ALERT = color.rgb(255, 158, 143)
ON = color.rgb(66, 45, 115)
LAVENDER = color.rgb(224, 206, 255)
TEMP_BG = color.rgb(98, 43, 20)
TEMP_LABEL = color.rgb(255, 226, 194)
TEMP_VALUE = color.rgb(255, 215, 146)
HUMIDITY_BG = color.rgb(16, 63, 108)
HUMIDITY_LABEL = color.rgb(207, 234, 255)
HUMIDITY_VALUE = color.rgb(158, 231, 255)
LED_BG = color.rgb(28, 66, 49)
LED_ON = color.rgb(37, 88, 59)
LED_INK = color.rgb(196, 246, 188)
CAT = image.load("cat.png")
TEMPERATURE_EMOJI = image.load("temperature.png")
HUMIDITY_EMOJI = image.load("humidity.png")

client = None
setup_error = None
try:
    with open("/system/office_ha.json", "r") as handle:
        config = json.load(handle)
    if not isinstance(config.get("token"), str) or not config["token"]:
        raise ValueError("Token fehlt")
    client = OfficeClient(config, "ha-ca.der")
    connection = Connection()
    del config
except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
    print("Office configuration failed:", type(error).__name__)
    setup_error = "HA-Konfiguration / secrets.py pruefen"
    connection = None

connection_generation = 0
network_ready = False


def box(x, y, width, height, radius, pen):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, width, height, radius))


def text(value, x, y, size=14, pen=INK, max_width=None):
    value = str(value)
    if max_width is not None:
        width, _ = screen.measure_text(value, font_size=size)
        if width > max_width:
            size *= max_width / width
    screen.pen = pen
    screen.text(value, x, y, size)


def dot(x, y, pen, radius=3):
    screen.pen = pen
    screen.shape(shape.circle(x, y, radius))


def sensor(index, y, label, background, foreground, accent, emoji, now):
    x = 12
    value = client.values[index] if client else None
    fresh = client.fresh(index, now) if client else False
    box(x, y, 143, 80, 10, background)
    screen.blit(emoji, vec2(x + 8, y + 6))
    text(label, x + 37, y + 10, 12, foreground, 98)
    if value is None:
        text("--", x + 12, y + 31, 32, foreground)
    else:
        formatted = ("%.1f" % value).replace(".", ",") if index == 0 else "%.0f" % value
        text(formatted, x + 12, y + 31, 32, accent if fresh else foreground, 98)
    unit = client.units[index] if client else ("\u00b0C" if index == 0 else "%")
    if unit == "C":
        unit = "\u00b0C"
    text(unit, x + 112, y + 48, 14, foreground, 25)
    if value is not None and not fresh:
        text("veraltet", x + 12, y + 66, 9, foreground)


def led_icon(x, y, background):
    strip = color.rgb(242, 247, 235)
    dot(x + 21, y + 19, strip, 17)
    dot(x + 21, y + 19, background, 7)
    box(x - 2, y + 12, 23, 14, 0, background)
    box(x - 2, y + 2, 24, 10, 3, strip)
    box(x - 2, y + 26, 24, 10, 3, strip)
    for dx, dy, rgb in (
        (3, 7, (235, 65, 92)),
        (15, 7, (238, 164, 24)),
        (28, 9, (51, 178, 69)),
        (33, 19, (0, 164, 198)),
        (28, 29, (56, 103, 238)),
        (15, 31, (166, 70, 220)),
        (3, 31, (232, 70, 156)),
    ):
        box(x + dx - 3, y + dy - 3, 6, 6, 1, color.rgb(*rgb))


def lamp(index, y, label, button, connected, now):
    light = client.values[index] if client else None
    fresh = client.fresh(index, now) if client else False
    enabled = connected and fresh and light in ("on", "off")
    lit = light == "on" and enabled
    pending = (client.command or client.expected) if client else None
    busy = pending is not None and pending[0] == index
    ink = LED_INK if index == 3 else LAVENDER
    background = (LED_ON if lit else LED_BG) if index == 3 else (ON if lit else PANEL)
    box(165, y, 143, 80, 10, background)
    text(label, 175, y + 7, 14, ink, 123)
    if index == 2:
        screen.blit(CAT, vec2(172, y + 26))
    else:
        led_icon(181, y + 30, background)
    text("AN" if lit else ("AUS" if enabled else "--"), 236, y + 29, 22, ink)
    subtitle = "Schaltet..." if busy else (
        ("Ausschalten" if lit else "Einschalten") if enabled else "Unbekannt"
    )
    text(subtitle, 226, y + 55, 10, ink, 76)
    text(button, 226, y + 68, 9, ink, 76)


def draw(now, connected):
    screen.pen = BG
    screen.rectangle(screen.clip)
    text("HA-Office", 16, 8, 24, max_width=205)
    ready = client and connected and all(client.fresh(i, now) for i in range(len(ENTITIES)))
    dot(239, 23, CYAN if ready else AMBER)
    text("LIVE" if ready else "WARTEN", 249, 15, 11, CYAN if ready else AMBER)
    sensor(0, 46, "Temperatur", TEMP_BG, TEMP_LABEL, TEMP_VALUE, TEMPERATURE_EMOJI, now)
    sensor(1, 134, "Luftfeuchte", HUMIDITY_BG, HUMIDITY_LABEL, HUMIDITY_VALUE, HUMIDITY_EMOJI, now)
    lamp(3, 46, "LED-Lampe", "HOCH", connected, now)
    lamp(2, 134, "OctoCat-Lamp", "RUNTER", connected, now)

    message = setup_error
    if message is None and not connected:
        message = connection.message or "Verbindung wird aufgebaut..."
    if message is None and client:
        message = client.message
        if message is None:
            message = next((error for error in client.errors if error), None)
    if message:
        text(message, 17, 219, 12, ALERT if connected or setup_error else AMBER, 286)
    else:
        text("L / R: Laden", 17, 220, 11, MUTED)
        text("SELECT: Home", 207, 220, 11, MUTED, 97)
    if client and client.active is not None:
        width = 32
        position = int((now % 1800) / 1800 * (288 - width))
        box(16 + position, 237, width, 2, 0, CYAN)


def update():
    global connection_generation, network_ready
    if badge.pressed(BUTTON_SELECT):
        on_exit()
        return "/system/apps/menu"
    now = time.ticks_ms()
    connected = False
    if client and not setup_error:
        connected = connection.poll()
        if network_ready and not connected:
            client.connection_lost()
        network_ready = connected
        if connected and connection_generation != connection.generation:
            connection_generation = connection.generation
            client.refresh()
        if any(badge.pressed(button) for button in (
            BUTTON_LEFT, BUTTON_RIGHT, BUTTON_MENU, BUTTON_BACK
        )):
            client.refresh()
        if connected:
            if badge.pressed(BUTTON_DOWN):
                client.set_light()
            elif badge.pressed(BUTTON_UP):
                client.set_light(index=3)
            client.step()
            if client.needs_reconnect:
                connection.reconnect()
                client.connection_lost()
                network_ready = False
                connected = False
    draw(now, connected)


def on_exit():
    if client:
        client.close()
    if connection:
        connection.close()


run(update)
