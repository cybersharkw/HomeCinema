"""Hintergrunddienst: Ersteinrichtung, Bibliotheks-Scan nach dem Neustart und Serien-Autoplay."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmc  # noqa: E402

from homecinema import skin, wizard  # noqa: E402
from homecinema.autoplay import AutoplayPlayer  # noqa: E402
from homecinema.kodi import addon, log  # noqa: E402


def _wait_for_gui(monitor, timeout=300):
    """Warten, bis Kodi gestartet ist und kein Dialog/Video läuft (auch direkt nach der Installation)."""
    for _ in range(timeout * 2):
        if xbmc.getCondVisibility("!System.HasActiveModalDialog + !Window.IsActive(startup) + !Player.HasVideo"):
            return not monitor.waitForAbort(2)
        if monitor.waitForAbort(0.5):
            return False
    return False


def main():
    monitor = xbmc.Monitor()
    player = AutoplayPlayer()
    log("Dienst gestartet")

    try:
        skin.update_if_needed()
    except Exception as exc:
        log("Skin-Update fehlgeschlagen: {}".format(exc), xbmc.LOGERROR)

    if _wait_for_gui(monitor):
        if addon().getSettingBool("pending_scan"):
            addon().setSettingBool("pending_scan", False)
            # Läuft der Scan beim Start schon (videolibrary.updateonstartup), würde UpdateLibrary ihn abbrechen
            if not xbmc.getCondVisibility("Library.IsScanningVideo"):
                xbmc.executebuiltin("UpdateLibrary(video)")
        elif not addon().getSettingBool("setup_done"):
            wizard.run(first_run=True)

    while not monitor.abortRequested():
        if monitor.waitForAbort(0.5):
            break
        player.tick()
    log("Dienst beendet")


main()
