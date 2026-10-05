"""Plugin-Einstieg: plugin://script.homecinema/?action=... (Listen für die Startseite)."""
import os
import sys
from urllib.parse import parse_qsl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmcplugin  # noqa: E402

from homecinema import widgets  # noqa: E402
from homecinema.kodi import play_episode  # noqa: E402


def main():
    handle = int(sys.argv[1])
    params = dict(parse_qsl(sys.argv[2].lstrip("?")))
    action = params.get("action")
    if action == "continue_series":
        widgets.continue_series(handle)
    elif action == "play_episode" and params.get("episodeid"):
        play_episode(params["episodeid"], resume=True)
    else:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


main()
