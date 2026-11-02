import json
import os
import sys
import time

import missing_details
import wifi

APP_DIR = "/system/apps/office"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
from office_client import OfficeClient

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
    del config
except (OSError, ValueError, KeyError, TypeError) as error:
    print("Office configuration failed:", type(error).__name__)
    setup_error = "office_ha.json pruefen"

wifi_started = False


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


def sensor(index, x, label, background, foreground, accent, emoji, now):
    value = client.values[index] if client else None
    fresh = client.fresh(index, now) if client else False
    box(x, 46, 143, 88, 12, background)
    screen.blit(emoji, vec2(x + 8, 52))
    text(label, x + 37, 57, 12, foreground, 98)
    if value is None:
        text("--", x + 12, 81, 35, foreground)
    else:
        formatted = ("%.1f" % value).replace(".", ",") if index == 0 else "%.0f" % value
        text(formatted, x + 12, 81, 35, accent if fresh else foreground, 98)
    unit = client.units[index] if client else ("\u00b0C" if index == 0 else "%")
    if unit == "C":
        unit = "\u00b0C"
    text(unit, x + 112, 101, 14, foreground, 25)
    if value is not None and not fresh:
        text("veraltet", x + 12, 119, 9, foreground)


def draw(now, connected):
    screen.pen = BG
    screen.rectangle(screen.clip)
    text("HA-Office", 16, 8, 24, max_width=205)
    ready = client and connected and all(client.fresh(i, now) for i in range(3))
    dot(239, 23, CYAN if ready else AMBER)
    text("LIVE" if ready else "WARTEN", 249, 15, 11, CYAN if ready else AMBER)
    sensor(0, 12, "Temperatur", TEMP_BG, TEMP_LABEL, TEMP_VALUE, TEMPERATURE_EMOJI, now)
    sensor(1, 165, "Luftfeuchte", HUMIDITY_BG, HUMIDITY_LABEL, HUMIDITY_VALUE, HUMIDITY_EMOJI, now)

    light = client.values[2] if client else None
    fresh = client.fresh(2, now) if client else False
    enabled = connected and fresh and light in ("on", "off")
    lit = light == "on" and enabled
    busy = client.busy if client else False
    box(12, 144, 296, 64, 12, ON if lit else PANEL)
    screen.blit(CAT, vec2(22, 152))
    text("OctoCat-Lamp", 82, 152, 19, max_width=158)
    subtitle = "Wird geschaltet..." if busy else (
        ("RUNTER: ausschalten" if lit else "RUNTER: einschalten") if enabled
        else "Status nicht verfuegbar"
    )
    text(subtitle, 82, 180, 11, LAVENDER, 158)
    box(251, 160, 43, 23, 11, CYAN if lit else DIM)
    dot(282 if lit else 263, 171, BG if lit else MUTED, 7)
    text("AN" if lit else ("AUS" if enabled else "--"), 260, 188, 9, CYAN if lit else LAVENDER)

    message = setup_error
    if message is None and not connected:
        message = "WLAN verbindet..." if wifi_started else "WLAN wird gestartet..."
    if message is None and client:
        message = client.message
        if message is None:
            message = next((error for error in client.errors if error), None)
    if message:
        text(message, 17, 219, 12, ALERT if connected or setup_error else AMBER, 286)
    else:
        text("L / R / HOCH: Laden", 17, 220, 11, MUTED)
        text("SELECT: Home", 207, 220, 11, MUTED, 97)
    if client and client.active is not None:
        width = 32
        position = int((now % 1800) / 1800 * (288 - width))
        box(16 + position, 237, width, 2, 0, CYAN)


def update():
    global wifi_started
    if badge.pressed(BUTTON_SELECT):
        on_exit()
        return "/system/apps/menu"
    now = time.ticks_ms()
    connected = wifi.is_connected()
    if client and not setup_error:
        if not wifi_started:
            wifi.connect(timeout=10, retries=100000)
            wifi_started = True
        connected = wifi.connect()
        if any(badge.pressed(button) for button in (
            BUTTON_LEFT, BUTTON_RIGHT, BUTTON_UP, BUTTON_MENU, BUTTON_BACK
        )):
            client.refresh()
        if connected:
            if badge.pressed(BUTTON_DOWN):
                client.set_light()
            client.step()
    draw(now, connected)


def on_exit():
    if client:
        client.close()


run(update)
