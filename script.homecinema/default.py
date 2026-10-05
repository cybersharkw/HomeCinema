"""Einstiegspunkt für RunScript(script.homecinema,action=...) aus dem Skin."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmcgui  # noqa: E402

from homecinema import episodes, menu, rating, search, wizard  # noqa: E402
from homecinema.kodi import episodes_of_show, play_episode  # noqa: E402


def _args():
    params = {}
    for arg in sys.argv[1:]:
        key, _, value = arg.partition("=")
        params[key.strip()] = value.strip()
    return params


def continue_show(tvshowid):
    ep = episodes.continue_episode(episodes_of_show(tvshowid))
    if ep is None:
        xbmcgui.Dialog().notification("HomeCinema", "Alle Folgen gesehen – starte mit Folge 1.")
        all_eps = episodes.ordered(episodes_of_show(tvshowid))
        if not all_eps:
            return
        ep = all_eps[0]
    play_episode(ep["episodeid"], resume=True)


def main():
    params = _args()
    action = params.get("action", "menu")
    if action == "setup":
        wizard.run(path=params.get("path"))
    elif action == "rate":
        rating.rate(params.get("dbtype"), params.get("dbid"))
    elif action == "play_episode" and params.get("episodeid"):
        play_episode(params["episodeid"], resume=True)
    elif action == "continue_show" and params.get("tvshowid"):
        continue_show(params["tvshowid"])
    elif action == "search":
        search.ask()
    else:
        menu.run()


main()
