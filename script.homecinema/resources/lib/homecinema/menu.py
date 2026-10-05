"""Einstellungsmenü der Startseite (Zahnrad oben rechts)."""
import sqlite3

import xbmc
import xbmcgui
import xbmcvfs

from homecinema import kodifiles, wizard
from homecinema.kodi import addon, log


def _remove_root():
    roots = [r for r in addon().getSettingString("media_roots").split("|") if r]
    if not roots:
        xbmcgui.Dialog().ok("HomeCinema", "Es ist noch kein Medienordner eingerichtet.")
        return
    choice = xbmcgui.Dialog().select("Welchen Medienordner entfernen?", roots)
    if choice < 0:
        return
    root = roots[choice]
    if not xbmcgui.Dialog().yesno("Medienordner entfernen",
                                  "{}\n\nFilme und Serien aus diesem Ordner verschwinden aus HomeCinema. "
                                  "Die Dateien selbst bleiben erhalten.".format(root),
                                  nolabel="Abbrechen", yeslabel="Entfernen"):
        return
    db = kodifiles.find_video_db(xbmcvfs.translatePath("special://database/"))
    con = sqlite3.connect(db, timeout=30)
    try:
        con.execute("UPDATE path SET strContent='', strScraper='', strSettings='' WHERE strPath LIKE ?",
                    (root.replace("%", "\\%") + "%",))
        con.commit()
    finally:
        con.close()
    roots.pop(choice)
    addon().setSettingString("media_roots", "|".join(roots))
    log("Medienordner entfernt: " + root)
    xbmc.executebuiltin("CleanLibrary(video)")


def _update_library():
    # UpdateLibrary während eines laufenden Scans würde ihn abbrechen
    if xbmc.getCondVisibility("Library.IsScanningVideo"):
        xbmcgui.Dialog().notification("HomeCinema", "Die Bibliothek wird bereits aktualisiert.")
    else:
        xbmc.executebuiltin("UpdateLibrary(video)")


ENTRIES = [
    ("Medienordner hinzufügen", lambda: wizard.run()),
    ("Medienordner entfernen", _remove_root),
    ("Bibliothek jetzt aktualisieren", _update_library),
    ("Bibliothek bereinigen", lambda: xbmc.executebuiltin("CleanLibrary(video)")),
    ("Wiedergabe & Autoplay", lambda: addon().openSettings()),
    ("Kodi-Einstellungen", lambda: xbmc.executebuiltin("ActivateWindow(Settings)")),
    ("Dateien & Netzwerkfreigaben", lambda: xbmc.executebuiltin("ActivateWindow(Videos,sources://video/,return)")),
    ("Ausschalten / Neustart", lambda: xbmc.executebuiltin("ActivateWindow(ShutdownMenu)")),
]


def run():
    choice = xbmcgui.Dialog().select("Einstellungen", [label for label, _ in ENTRIES])
    if choice >= 0:
        ENTRIES[choice][1]()
