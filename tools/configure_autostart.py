"""Enable HA-Office on cold boot while preserving the watchdog launcher path."""

import argparse
from datetime import datetime
from pathlib import Path
import shutil


ORIGINAL = 'app_to_launch = launch("/system/apps/menu")'
AUTOSTART = '''# Cold boot opens HA-Office; HOME/SELECT watchdog resets still open the menu.
if machine.reset_cause() != machine.WDT_RESET:
    app_to_launch = "/system/apps/office"
else:
    app_to_launch = launch("/system/apps/menu")'''


def patch_main(source):
    if AUTOSTART in source:
        return source
    if source.count(ORIGINAL) != 1:
        raise ValueError("Unrecognized main.py; refusing to change the boot sequence")
    if "machine.WDT_RESET" not in source or "launch(app_to_launch)" not in source:
        raise ValueError("Expected Universe 2026 boot and launcher lifecycle")
    return source.replace(ORIGINAL, AUTOSTART)


def configure(mount, write=False):
    root = mount / "system" if (mount / "system" / "main.py").is_file() else mount
    main = root / "main.py"
    if not (root / "apps" / "office" / "__init__.py").is_file():
        raise ValueError("Install HA-Office before enabling autostart")
    source = main.read_bytes().decode("utf-8")
    updated = patch_main(source)
    if updated == source:
        print("HA-Office autostart is already enabled.")
        return
    compile(updated, str(main), "exec")
    if not write:
        print("Would enable HA-Office on cold boot in", main)
        print("Dry run only. Add --write to apply with a backup.")
        return
    backups = mount / ".badge-app-backups"
    backups.mkdir(exist_ok=True)
    backup = backups / ("main.py-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    shutil.copy2(main, backup)
    main.write_bytes(updated.encode("utf-8"))
    if main.read_bytes().decode("utf-8") != updated:
        raise OSError("Boot configuration verification failed")
    print("HA-Office autostart enabled. Original boot file:", backup)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mount", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    configure(args.mount, args.write)
