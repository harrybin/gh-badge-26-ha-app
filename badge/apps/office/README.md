# HA-Office

Zeigt Temperatur und Luftfeuchtigkeit im Buero und schaltet zwei Lampen ueber Home Assistant.

SELECT kehrt zum Home-Launcher zurueck. RUNTER schaltet die OctoCat-Lamp um.
HOCH schaltet die zweite LED-Lampe (Hintergrund-Licht).
LINKS und RECHTS aktualisieren alle vier Werte.
MENU und BACK aktualisieren ebenfalls; HOME bleibt die Launcher-Taste.
Beim Oeffnen und danach alle 5 Minuten werden die Messwerte automatisch geladen.
Beide Lampenzustaende werden unabhaengig davon alle 5 Sekunden aus Home Assistant
abgefragt, damit externe Aenderungen sichtbar werden.
Nach 5 Minuten und 45 Sekunden werden Messwerte als veraltet markiert.
Der Lampenstatus gilt bereits nach 20 Sekunden ohne erfolgreiche Abfrage als
veraltet; die Lampe ist dann nicht schaltbar und zeigt keinen AUS-Status an.
Unbekannte oder nicht verfuegbare Zustaende werden niemals als AUS interpretiert.
Nach jedem Schaltbefehl wird der tatsaechliche Zustand erneut abgefragt.
Schaltbefehle werden bei einem Verbindungsfehler nicht automatisch wiederholt.
Waehrend ein Schaltbefehl laeuft, wird kein weiterer angenommen.

## Einrichtung

WLAN verwendet ausdruecklich WIFI_SSID und WIFI_PASSWORD aus
/system/secrets.py (secrets.py im Stamm des BADGER-USB-Laufwerks).
Eine eventuell vorhandene /secrets.py im internen Root-Dateisystem wird nicht
verwendet: die Firmware kann beim normalen Import sonst alte Daten laden.
Die App verwaltet das Funkmodul direkt statt ueber das zwischengespeicherte
Firmware-wifi-Modul. Beim Start und nach Ausfaellen wird das Radio fuer eine
Sekunde abgeschaltet und anschliessend neu verbunden. Verbindungsversuche
sind auf 20 Sekunden begrenzt; weitere Versuche erfolgen mit wachsender Pause
von 1 bis maximal 30 Sekunden, ohne die Bedienung zu blockieren.
Die separate Datei /system/office_ha.json enthaelt url und token.
Sie gehoert nicht in das App-Verzeichnis oder die Versionsverwaltung.
Das lokale Werkzeug tools/prepare_badge.py liest das bereits vorhandene
ha_token aus einer explizit angegebenen .env-Datei und schreibt die separate
Badge-Konfiguration, ohne das Token auszugeben.

Es werden ausschliesslich diese bestaetigten Entities verwendet:

- sensor.gewachshaus_temperatur (Anzeigename: Buero Temperatur)
- sensor.gewachshaus_luftfeuchtigkeit (Anzeigename: Buero Luftfeuchtigkeit)
- light.wled (OctoCat)
- switch.hintergrundlicht_socket_1 (Hintergrund-Licht, Anzeige LED-Lampe)

Schalten verwendet den passenden HA-Dienst: light fuer OctoCat,
switch fuer die zweite LED. Bestaetigungen und Fehler gehoeren immer zur
jeweils geschalteten Lampe; eine Antwort der anderen Lampe bestaetigt sie nicht.

HTTPS prueft Zertifikat und Hostnamen mit der oeffentlichen CA in ha-ca.der.
Nach voelligem Stromverlust synchronisiert die App eine zurueckgesetzte Uhr
automatisch ueber NTP, bevor sie HTTPS-Anfragen erlaubt. Sie verwendet abwechselnd
pool.ntp.org und time.cloudflare.com (UDP 123). Bleiben Zeitserver unerreichbar,
zeigt sie das an und versucht es erneut; SELECT/HOME bleiben bedienbar.
Bei Verbindungsabbruch werden HTTP-Verbindungen und ausstehende Schaltbefehle
verworfen. Nach Wiederverbindung werden alle vier Zustaende sofort neu geladen.
HTTPS loest den Servernamen bei jeder Verbindung erneut auf. Nach drei
aufeinanderfolgenden Transportfehlern oder Zeitlimits startet die App WLAN neu,
auch wenn das Radio weiterhin verbunden meldet. HTTP- und Datenfehler
(z.B. ein ungueltiges Token) starten das Funkmodul nicht neu.
Die App schaltet die Zertifikatspruefung niemals stillschweigend ab.
Ein dedizierter, nicht-administrativer HA-Benutzer fuer das Badge wird empfohlen.
Das Token liegt wie die WLAN-Konfiguration lesbar auf dem physischen Badge:
Badge nicht mit aktiven Zugangsdaten weitergeben; Token bei Verlust widerrufen.

## Darstellung und Hardware

320x240-HIRES, Mona Sans aus der vorhandenen Firmware, orange Temperatur-
und blaue Feuchtigkeitsflaechen mit farbigen Thermometer-/Tropfen-Emojis sowie
ein 2x2-Raster: links Temperatur ueber Luftfeuchte, rechts die gruene LED-Lampe
mit geschwungenem, hellem LED-Streifen und einzelnen bunten RGB-Lichtpunkten
ueber der violetten OctoCat-Lamp. Die Icon-Farben sind dekorativ und zeigen
nicht die aktuelle Lichtfarbe an; AN/AUS zeigt den bestaetigten HA-Zustand.
Das vom Benutzer bereitgestellte Octocat-Bild
wird fuer Lampe und Menue-Icon verwendet; nur der aeussere weisse Rand wird
entfernt. Quelle: https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQjZTF0k_xjswerB0jHPXqtM2JFeQFVX3L7iV5_H_XOvw&s=10

tools/build_visual_assets.py erzeugt die PNGs aus tools/assets/octocat-source.jpg
und den lokalen Segoe-UI-Emoji-Glyphen. Emojis sind eingebettete PNG-Bilder,
damit sie auch ohne Emoji-Font auf dem Badge farbig erscheinen.
Die Badge-App selbst benoetigt keine Desktop-Schriften oder Pillow.
Benoetigt Universe-2026-Firmware mit
fetch.AsyncFetch, TLS-Zertifikatspruefung und WLAN. Der Browser-Simulator kann
die Netzwerkverbindung und die Hardware-Steuerung nicht nachweisen.
