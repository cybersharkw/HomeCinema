"""Kleine Helfer rund um Kodi (JSON-RPC, Einstellungen, Logging)."""
import json

import xbmc
import xbmcaddon

ADDON_ID = "script.homecinema"


def addon():
    return xbmcaddon.Addon(ADDON_ID)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[HomeCinema] {}".format(message), level)


def rpc(method, params=None):
    """JSON-RPC-Aufruf; liefert 'result' oder None (Fehler werden geloggt)."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        request["params"] = params
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        log("JSON-RPC {} fehlgeschlagen: {}".format(method, response["error"]), xbmc.LOGWARNING)
        return None
    return response.get("result")


def get_setting_value(setting):
    result = rpc("Settings.GetSettingValue", {"setting": setting})
    return result.get("value") if result else None


def set_setting_value(setting, value):
    return rpc("Settings.SetSettingValue", {"setting": setting, "value": value}) is not None


def setting_bool(key):
    return addon().getSettingBool(key)


def setting_int(key):
    return addon().getSettingInt(key)


def episodes_of_show(tvshowid):
    result = rpc("VideoLibrary.GetEpisodes", {
        "tvshowid": int(tvshowid),
        "properties": ["season", "episode", "title", "showtitle", "playcount", "lastplayed",
                       "resume", "art", "plot", "runtime", "file"],
    }) or {}
    return result.get("episodes", [])


def play_episode(episodeid, resume=True):
    """Startet eine Episode über die Bibliothek (Gesehen-Status und Fortsetzen funktionieren)."""
    return rpc("Player.Open", {"item": {"episodeid": int(episodeid)}, "options": {"resume": bool(resume)}})
