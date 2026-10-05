"""Serien-Autoplay: Nach dem Ende einer Folge startet automatisch die nächste – auch über Staffeln hinweg.

- Hinweis kurz vor dem Ende: "Gleich geht's weiter: S01E03 · Titel"
- "Schaust du noch?" nach N Folgen am Stück ohne Tastendruck (einstellbar)
"""
import time

import xbmc
import xbmcgui

from homecinema import episodes
from homecinema.kodi import addon, log, rpc, episodes_of_show, play_episode

NOTIFY_SECONDS_BEFORE_END = 20
AUTO_START_WINDOW = 15     # Start innerhalb von x s nach Folgenende = automatisch weitergeschaltet
ACTIVE_USER_SECONDS = 300  # Tastendruck in den letzten 5 Minuten = Zuschauer ist da


def _label(ep):
    code = episodes.episode_code(ep.get("season"), ep.get("episode"))
    return "{} · {}".format(code, ep["title"]) if ep.get("title") else code


class AutoplayPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.current = None        # laufende Episode (dict aus Player.GetItem)
        self.upcoming = None       # nächste Episode der laufenden
        self.notified = False
        self.ended = None          # (Episode, nächste, Zeitpunkt) – vom Service-Loop abgearbeitet
        self.last_end = 0.0
        self.auto_in_a_row = 0

    # --- Kodi-Callbacks (kurz halten, Arbeit passiert in tick()) -----------------------------
    def onAVStarted(self):
        item = self._playing_item()
        auto = time.time() - self.last_end < AUTO_START_WINDOW
        if not auto or xbmc.getGlobalIdleTime() < ACTIVE_USER_SECONDS:
            # selbst gestartet oder kürzlich eine Taste gedrückt -> Zähler "am Stück" zurücksetzen
            self.auto_in_a_row = 0
        if item and item.get("type") == "episode" and item.get("tvshowid", -1) > 0:
            self.current = item
            self.notified = False
            self.upcoming = episodes.next_episode(episodes_of_show(item["tvshowid"]), item["id"])
        else:
            self.current = self.upcoming = None
        _refresh_widgets()

    def onPlayBackEnded(self):
        if self.current:
            self.ended = (self.current, self.upcoming, time.time())
        self.last_end = time.time()
        self.current = None
        _refresh_widgets()

    def onPlayBackStopped(self):
        self.current = self.upcoming = self.ended = None
        self.auto_in_a_row = 0
        _refresh_widgets()

    # --- Service-Loop ------------------------------------------------------------------------
    def tick(self):
        self._notify_upcoming()
        if self.ended and time.time() - self.ended[2] > 1.5:
            finished, upcoming, _ = self.ended
            self.ended = None
            self._continue_after(finished, upcoming)

    def _playing_item(self):
        players = rpc("Player.GetActivePlayers") or []
        video = next((p for p in players if p.get("type") == "video"), None)
        if not video:
            return None
        result = rpc("Player.GetItem", {"playerid": video["playerid"],
                                         "properties": ["tvshowid", "season", "episode", "showtitle", "title"]})
        return (result or {}).get("item")

    def _notify_upcoming(self):
        if self.notified or not self.current or not self.upcoming:
            return
        if not addon().getSettingBool("autoplay") or not addon().getSettingBool("upnext_notify"):
            return
        try:
            remaining = self.getTotalTime() - self.getTime()
        except RuntimeError:
            return
        if 0 < remaining <= NOTIFY_SECONDS_BEFORE_END:
            self.notified = True
            xbmcgui.Dialog().notification("Gleich geht's weiter", _label(self.upcoming),
                                          addon().getAddonInfo("icon"), 8000, False)

    def _continue_after(self, finished, upcoming):
        if self.isPlayingVideo() or not addon().getSettingBool("autoplay"):
            return
        if upcoming is None:
            xbmcgui.Dialog().notification(finished.get("showtitle", "HomeCinema"),
                                          "Das war die letzte Folge.", addon().getAddonInfo("icon"), 5000, False)
            return
        limit = addon().getSettingInt("still_watching")
        if limit and self.auto_in_a_row + 1 >= limit and xbmc.getGlobalIdleTime() >= ACTIVE_USER_SECONDS:
            still_there = xbmcgui.Dialog().yesno(
                "Schaust du noch?",
                "Du hast {} Folgen am Stück geschaut.\nWeiter mit {}?".format(self.auto_in_a_row + 1, _label(upcoming)),
                nolabel="Beenden", yeslabel="Weiter schauen", autoclose=120000)
            if not still_there:
                self.auto_in_a_row = 0
                return
        log("Autoplay: {} -> {}".format(finished.get("id"), upcoming["episodeid"]))
        xbmcgui.Dialog().notification("Nächste Folge", _label(upcoming), addon().getAddonInfo("icon"), 5000, False)
        self.auto_in_a_row += 1
        self.last_end = time.time()
        play_episode(upcoming["episodeid"], resume=True)


def _refresh_widgets():
    """Plugin-Reihen ("Weiter schauen") auf der Startseite neu laden."""
    xbmcgui.Window(10000).setProperty("hc_refresh", str(int(time.time())))
