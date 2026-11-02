# HA-Office

Zeigt Temperatur und Luftfeuchtigkeit im Buero und schaltet die WLED-OctoCat-Lampe ueber Home Assistant.

SELECT kehrt zum Home-Launcher zurueck. RUNTER schaltet die OctoCat-Lamp um.
LINKS, RECHTS und HOCH aktualisieren alle drei Werte.
MENU und BACK aktualisieren ebenfalls; HOME bleibt die Launcher-Taste.
Beim Oeffnen und danach alle 5 Minuten werden die Werte automatisch geladen.
Nach 5 Minuten und 45 Sekunden ohne erfolgreiche
Aktualisierung werden sie als veraltet markiert; die Lampe ist dann nicht schaltbar.
Unbekannte oder nicht verfuegbare Zustaende werden niemals als AUS interpretiert.
Nach jedem Schaltbefehl wird der tatsaechliche Zustand erneut abgefragt.
Schaltbefehle werden bei einem Verbindungsfehler nicht automatisch wiederholt.

## Einrichtung

WLAN verwendet die vorhandenen WIFI_SSID und WIFI_PASSWORD in der badge-eigenen
secrets.py. Die separate Datei /system/office_ha.json enthaelt url und token.
Sie gehoert nicht in das App-Verzeichnis oder die Versionsverwaltung.
Das lokale Werkzeug tools/prepare_badge.py liest das bereits vorhandene
ha_token aus einer explizit angegebenen .env-Datei und schreibt die separate
Badge-Konfiguration, ohne das Token auszugeben.

Es werden ausschliesslich diese bestaetigten Entities verwendet:

- sensor.gewachshaus_temperatur (Anzeigename: Buero Temperatur)
- sensor.gewachshaus_luftfeuchtigkeit (Anzeigename: Buero Luftfeuchtigkeit)
- light.wled (OctoCat)

HTTPS prueft Zertifikat und Hostnamen mit der oeffentlichen CA in ha-ca.der.
Die Badge-Uhr muss stimmen; das Deployment setzt sie ueber USB auf die PC-Zeit.
Nach voelligem Stromverlust die Uhr erneut per mpremote rtc --set stellen.
Die App schaltet die Zertifikatspruefung niemals stillschweigend ab.
Ein dedizierter, nicht-administrativer HA-Benutzer fuer das Badge wird empfohlen.
Das Token liegt wie die WLAN-Konfiguration lesbar auf dem physischen Badge:
Badge nicht mit aktiven Zugangsdaten weitergeben; Token bei Verlust widerrufen.

## Darstellung und Hardware

320x240-HIRES, Mona Sans aus der vorhandenen Firmware, orange Temperatur-
und blaue Feuchtigkeitsflaechen mit farbigen Thermometer-/Tropfen-Emojis sowie
eine violette Lampenflaeche. Das vom Benutzer bereitgestellte Octocat-Bild
wird fuer Lampe und Menue-Icon verwendet; nur der aeussere weisse Rand wird
entfernt. Quelle: https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQjZTF0k_xjswerB0jHPXqtM2JFeQFVX3L7iV5_H_XOvw&s=10

tools/build_visual_assets.py erzeugt die PNGs aus tools/assets/octocat-source.jpg
und den lokalen Segoe-UI-Emoji-Glyphen. Emojis sind eingebettete PNG-Bilder,
damit sie auch ohne Emoji-Font auf dem Badge farbig erscheinen.
Die Badge-App selbst benoetigt keine Desktop-Schriften oder Pillow.
Benoetigt Universe-2026-Firmware mit
fetch.AsyncFetch, TLS-Zertifikatspruefung und WLAN. Der Browser-Simulator kann
die Netzwerkverbindung und die Hardware-Steuerung nicht nachweisen.
