"""Installiert den mitgelieferten HomeCinema-Skin bzw. hält ihn aktuell."""
import os
import re
import shutil

import xbmc
import xbmcvfs

from homecinema.kodi import addon, log, rpc

SKIN_ID = "skin.homecinema"


def _version(addon_dir):
    try:
        with open(os.path.join(addon_dir, "addon.xml"), "r", encoding="utf-8") as handle:
            match = re.search(r'<addon[^>]*\sversion="([^"]+)"', handle.read())
            return match.group(1) if match else None
    except OSError:
        return None


def bundled_dir():
    return os.path.join(xbmcvfs.translatePath(addon().getAddonInfo("path")), "resources", "skin", SKIN_ID)


def installed_dir():
    return os.path.join(xbmcvfs.translatePath("special://home/addons/"), SKIN_ID)


def needs_update():
    """True, wenn der Skin installiert ist, aber eine andere Version als die mitgelieferte hat."""
    current = _version(installed_dir())
    return current is not None and current != _version(bundled_dir())


def install():
    """Kopiert den Skin nach addons/ und aktiviert ihn. True bei Erfolg."""
    source = bundled_dir()
    if not os.path.isdir(source):
        log("Mitgelieferter Skin fehlt: " + source, xbmc.LOGERROR)
        return False
    target = installed_dir()
    if _version(target) != _version(source):
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(source, target)
        xbmc.executebuiltin("UpdateLocalAddons", True)
        xbmc.Monitor().waitForAbort(3)
    rpc("Addons.SetAddonEnabled", {"addonid": SKIN_ID, "enabled": True})
    return xbmc.getCondVisibility("System.HasAddon({})".format(SKIN_ID))


def update_if_needed():
    """Nach einem Update des Add-ons: neuen Skin übernehmen und neu laden."""
    if not needs_update():
        return
    log("Aktualisiere Skin auf Version {}".format(_version(bundled_dir())))
    if install() and xbmc.getSkinDir() == SKIN_ID:
        xbmc.executebuiltin("ReloadSkin()")
