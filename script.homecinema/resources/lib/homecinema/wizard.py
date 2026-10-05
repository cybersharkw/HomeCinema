"""Einrichtungsassistent: Medienordner wählen, Filme/Serien erkennen, Kodi passend einstellen."""
import os
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from homecinema import classify, kodifiles, skin
from homecinema.kodi import addon, log, get_setting_value, set_setting_value

HEADING = "HomeCinema"
GERMAN = "resource.language.de_de"
SKIP_DIRS = {"@eadir", "$recycle.bin", "system volume information", "lost+found", ".trash", "extrafanart"}
MAX_DEPTH = 10


def _walk(root, progress):
    """Alle Videodateien unter root (relativ, mit '/')."""
    found = []
    stack = [("", 0)]
    scanned = 0
    while stack:
        if progress.iscanceled():
            return None
        rel, depth = stack.pop()
        full = kodifiles.join_path(root, rel)
        try:
            dirs, files = xbmcvfs.listdir(full)
        except Exception as exc:  # unlesbarer Ordner -> überspringen
            log("Ordner nicht lesbar: {} ({})".format(full, exc), xbmc.LOGWARNING)
            continue
        scanned += 1
        progress.update(scanned % 100, "Durchsuche: {}\n{} Videos gefunden".format(rel or "/", len(found)))
        for name in files:
            if classify.is_video(name):
                found.append("{}/{}".format(rel, name).lstrip("/"))
        if depth < MAX_DEPTH:
            for name in dirs:
                if not name.startswith(".") and name.lower() not in SKIP_DIRS:
                    stack.append(("{}/{}".format(rel, name).lstrip("/"), depth + 1))
    return found


def _summary(plan):
    shows = classify.show_names(plan["shows"])
    lines = ["[B]{}[/B] Filme und [B]{}[/B] Serien gefunden.".format(len(plan["movies"]), len(shows))]
    if shows:
        names = ", ".join(shows[:6])
        if len(shows) > 6:
            names += " und {} weitere".format(len(shows) - 6)
        lines.append("Serien: " + names)
    if plan["unassigned"]:
        lines.append("[COLOR FFE5B04A]{} Folgen liegen direkt im Medienordner und brauchen einen eigenen "
                     "Serienordner.[/COLOR]".format(len(plan["unassigned"])))
    return "\n".join(lines)


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _wait_for(condition, timeout):
    monitor = xbmc.Monitor()
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        if monitor.waitForAbort(0.5):
            return False
    return condition()


def _ensure_addon(addon_id, timeout=90):
    if xbmc.getCondVisibility("System.HasAddon({})".format(addon_id)):
        return True
    xbmc.executebuiltin("InstallAddon({})".format(addon_id), True)
    return _wait_for(lambda: xbmc.getCondVisibility("System.HasAddon({})".format(addon_id)), timeout)


def _configure_scrapers():
    """Auch die globalen Scraper-Einstellungen auf Deutsch (z.B. für "Informationen aktualisieren")."""
    for scraper_id, values in kodifiles.SCRAPER_SETTINGS.items():
        if not _ensure_addon(scraper_id):
            log("Scraper fehlt: " + scraper_id, xbmc.LOGERROR)
            continue
        scraper = xbmcaddon.Addon(scraper_id)
        for key, value in values.items():
            try:
                scraper.setSetting(key, value)
            except Exception as exc:
                log("Scraper-Einstellung {}={} nicht gesetzt: {}".format(key, value, exc), xbmc.LOGWARNING)


def _clear_scraper_cache():
    """Der Serien-Scraper cached Serien nach ID – unabhängig von der Sprache. Alte (englische) Einträge löschen."""
    cache = xbmcvfs.translatePath("special://temp/scrapers/{}/".format(kodifiles.TV_SCRAPER))
    if os.path.isdir(cache):
        for name in os.listdir(cache):
            if name.endswith(".pickle"):
                try:
                    os.remove(os.path.join(cache, name))
                except OSError:
                    pass


def _configure_kodi():
    set_setting_value("videolibrary.updateonstartup", True)
    # Kodis eigenes "nächstes Element abspielen" aus – das Serien-Autoplay von HomeCinema übernimmt
    set_setting_value("videoplayer.autoplaynextitem", [])
    set_setting_value("locale.keyboardlayouts", ["German QWERTZ"])
    set_setting_value("lookandfeel.enablerssfeeds", False)
    set_setting_value("filelists.showparentdiritems", False)  # keine ".."-Einträge, "Zurück" genügt


def remember_root(path):
    roots = [r for r in addon().getSettingString("media_roots").split("|") if r]
    if path not in roots:
        roots.append(path)
    addon().setSettingString("media_roots", "|".join(roots))


def apply_setup(path, plan):
    """Richtet den Ordner ein. Liefert True, wenn Kodi neu starten muss (neue Scan-Regeln)."""
    profile = xbmcvfs.translatePath("special://profile/")
    adv = os.path.join(profile, "advancedsettings.xml")
    old_adv = _read(adv)
    new_adv = kodifiles.merge_advancedsettings(old_adv)
    if new_adv != old_adv:
        _write(adv, new_adv)
    src = os.path.join(profile, "sources.xml")
    _write(src, kodifiles.merge_sources(_read(src), "HomeCinema", path))
    _write(os.path.join(profile, "keymaps", "homecinema.xml"), kodifiles.KEYMAP)

    db = kodifiles.find_video_db(xbmcvfs.translatePath("special://database/"))
    if not db:
        raise RuntimeError("Kodi-Videodatenbank nicht gefunden")
    show_paths = [kodifiles.join_path(path, folder) for folder in plan["shows"]]
    kodifiles.register_library(db, kodifiles.join_path(path, ""), show_paths)

    _configure_scrapers()
    _clear_scraper_cache()
    _configure_kodi()
    remember_root(path)
    addon().setSettingBool("setup_done", True)
    # advancedsettings.xml liest Kodi nur beim Start – dann nach dem Neustart scannen
    needs_restart = new_adv != old_adv
    addon().setSettingBool("pending_scan", needs_restart)
    return needs_restart


def _switch_language_and_skin():
    """Deutsch + HomeCinema-Skin aktivieren."""
    if get_setting_value("locale.language") != GERMAN:
        if not xbmc.getCondVisibility("System.HasAddon({})".format(GERMAN)):
            xbmcgui.Dialog().ok(HEADING, "Jetzt wird das deutsche Sprachpaket geladen.\n"
                                         "Kodi fragt dazu auf Englisch [I]„Would you like to download this "
                                         "add-on?“[/I] – bitte mit [B]Yes[/B] bestätigen.")
        if _ensure_addon(GERMAN):
            set_setting_value("locale.language", GERMAN)
            xbmc.Monitor().waitForAbort(3)
    if xbmc.getSkinDir() != skin.SKIN_ID:
        if not skin.install():
            xbmcgui.Dialog().ok(HEADING, "Der HomeCinema-Skin konnte nicht installiert werden.")
            return
        xbmcgui.Dialog().ok(HEADING, "Gleich wechselt die Oberfläche zu HomeCinema.\n"
                                     "Bitte bestätige die Rückfrage mit [B]Ja[/B].")
        set_setting_value("lookandfeel.skin", skin.SKIN_ID)
        _wait_for(lambda: xbmc.getSkinDir() == skin.SKIN_ID, 30)


def _ask(heading, text, nolabel, yeslabel):
    """Ja/Nein-Frage, bei der die Ja-Taste vorausgewählt ist (bequemer mit der Fernbedienung)."""
    try:
        return xbmcgui.Dialog().yesno(heading, text, nolabel=nolabel, yeslabel=yeslabel,
                                      defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
    except (AttributeError, TypeError):  # Kodi < 20
        return xbmcgui.Dialog().yesno(heading, text, nolabel=nolabel, yeslabel=yeslabel)


def run(first_run=False, path=None):
    dialog = xbmcgui.Dialog()
    if first_run and not _ask(
            HEADING,
            "[B]Willkommen bei HomeCinema![/B]\nWähle den Ordner mit deinen Filmen und Serien – "
            "Bilder, Beschreibungen und Darsteller kommen dann automatisch.",
            nolabel="Später", yeslabel="Einrichten"):
        return

    path = path or dialog.browse(0, "Medienordner wählen", "files")
    if not path:
        return

    progress = xbmcgui.DialogProgress()
    progress.create(HEADING, "Medienordner wird durchsucht…")
    try:
        files = _walk(path, progress)
    finally:
        progress.close()
    if files is None:
        return
    if not files:
        dialog.ok(HEADING, "In diesem Ordner wurden keine Videos gefunden.")
        return

    plan = classify.plan_library(files)
    if not _ask(HEADING, _summary(plan), nolabel="Abbrechen", yeslabel="Einrichten"):
        return

    try:
        needs_restart = apply_setup(path, plan)
    except Exception as exc:
        log("Einrichtung fehlgeschlagen: {}".format(exc), xbmc.LOGERROR)
        dialog.ok(HEADING, "Die Einrichtung ist fehlgeschlagen:\n{}".format(exc))
        return

    _switch_language_and_skin()
    if needs_restart:
        dialog.ok(HEADING, "Fertig! Kodi startet jetzt neu und lädt danach deine Filme und Serien.\n"
                           "Beim ersten Mal kann das je nach Grösse der Sammlung einige Minuten dauern.")
        xbmc.executebuiltin("RestartApp")
        return
    if xbmc.getCondVisibility("Library.IsScanningVideo"):
        # Ein laufender Scan würde durch UpdateLibrary abgebrochen – danach erneut scannen
        xbmc.executebuiltin("StopScanning(video)")
        _wait_for(lambda: not xbmc.getCondVisibility("Library.IsScanningVideo"), 30)
    xbmc.executebuiltin("UpdateLibrary(video)")
    dialog.notification(HEADING, "Fertig! Neue Titel erscheinen in wenigen Augenblicken.",
                        addon().getAddonInfo("icon"), 6000, False)
