"""Generate public assets and explicitly provision separate badge credentials."""

import argparse
import json
from pathlib import Path
import socket
import ssl
from urllib.parse import urlsplit

from build_visual_assets import build_assets


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "office"


def public_assets(url):
    APP.mkdir(parents=True, exist_ok=True)
    build_assets()
    parsed = urlsplit(url)
    context = ssl.create_default_context()
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=12) as raw:
        with context.wrap_socket(raw, server_hostname=parsed.hostname) as secure:
            # Only public CA material from a successfully verified chain is saved.
            chain = secure._sslobj.get_verified_chain()
            root = chain[-1].public_bytes()
    (APP / "ha-ca.der").write_bytes(ssl.PEM_cert_to_DER_cert(root))
    print("Generated cat.png, icon.png and verified public CA.")


def provision(env_file, mount, url):
    values = {}
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    token = values.get("ha_token")
    if not token:
        raise ValueError("No ha_token in the selected .env file")
    if not (mount / "apps" / "menu" / "app.py").is_file():
        raise ValueError("Expected mounted BADGER application volume")
    destination = mount / "office_ha.json"
    if destination.exists():
        raise FileExistsError("office_ha.json already exists; preserve/review it before updating")
    destination.write_text(json.dumps({"url": url, "token": token}), encoding="utf-8")
    print("Separate office_ha.json provisioned; credential value not displayed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--env", type=Path)
    parser.add_argument("--mount", type=Path)
    args = parser.parse_args()
    if not args.url.startswith("https://"):
        parser.error("HTTPS is required")
    public_assets(args.url)
    if args.env:
        if not args.mount:
            parser.error("--env requires --mount")
        provision(args.env, args.mount, args.url)
