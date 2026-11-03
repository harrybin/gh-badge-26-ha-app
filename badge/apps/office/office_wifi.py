import wifi


def start_wifi():
    # The frozen firmware's `import secrets` can resolve to /secrets.py instead
    # of the file edited on the BADGER USB volume.
    config = {}
    with open("/system/secrets.py", "r") as handle:
        exec(handle.read(), config)
    ssid = config.get("WIFI_SSID")
    password = config.get("WIFI_PASSWORD")
    if not isinstance(ssid, str) or not ssid:
        raise ValueError("WIFI_SSID fehlt in /system/secrets.py")
    if not isinstance(password, str):
        raise ValueError("WIFI_PASSWORD fehlt in /system/secrets.py")
    wifi.disconnect()
    return wifi.connect(ssid=ssid, psk=password, timeout=10, retries=100000)
