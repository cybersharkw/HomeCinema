"""Plugin-Listen für die Startseite: "Zuletzt gesehen" bei Serien zeigt direkt die nächste Folge."""
import xbmcgui
import xbmcplugin

from homecinema import episodes
from homecinema.kodi import rpc, episodes_of_show

MAX_SHOWS = 25


def continue_series(handle):
    result = rpc("VideoLibrary.GetTVShows", {
        "properties": ["title", "art", "lastplayed", "genre", "year", "rating", "userrating", "plot"],
        "sort": {"method": "lastplayed", "order": "descending"},
        "limits": {"start": 0, "end": MAX_SHOWS * 2},
    }) or {}
    items = []
    for show in result.get("tvshows", []):
        if not show.get("lastplayed") or len(items) >= MAX_SHOWS:
            continue  # noch nie geschaut
        ep = episodes.continue_episode(episodes_of_show(show["tvshowid"]))
        if ep is None:
            continue  # Serie komplett gesehen
        items.append(_episode_item(show, ep))
    xbmcplugin.setContent(handle, "episodes")
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _episode_item(show, ep):
    code = episodes.episode_code(ep["season"], ep["episode"])
    resume = ep.get("resume") or {}
    prefix = "Fortsetzen" if float(resume.get("position") or 0) > 0 else "Weiter"
    item = xbmcgui.ListItem(show["title"], "{}: {}".format(prefix, code), offscreen=True)
    show_art = show.get("art", {})
    item.setArt({
        "poster": show_art.get("poster", ""),
        "fanart": show_art.get("fanart", ""),
        "landscape": show_art.get("landscape", ""),
        "clearlogo": show_art.get("clearlogo", ""),
        "thumb": (ep.get("art") or {}).get("thumb", ""),
    })
    tag = item.getVideoInfoTag()
    tag.setMediaType("episode")
    tag.setDbId(int(ep["episodeid"]))
    tag.setTitle(ep.get("title", ""))
    tag.setTvShowTitle(show["title"])
    tag.setSeason(int(ep["season"]))
    tag.setEpisode(int(ep["episode"]))
    tag.setPlot(ep.get("plot") or show.get("plot", ""))
    tag.setGenres(show.get("genre", []))
    tag.setYear(int(show.get("year") or 0))
    tag.setRating(float(show.get("rating") or 0))
    tag.setUserRating(int(show.get("userrating") or 0))
    if resume.get("total"):
        tag.setResumePoint(float(resume.get("position") or 0), float(resume["total"]))
    item.setProperty("hc_code", code)
    item.setProperty("hc_episode_title", ep.get("title", ""))
    item.setProperty("hc_tvshowid", str(show["tvshowid"]))
    url = "plugin://script.homecinema/?action=play_episode&episodeid={}".format(ep["episodeid"])
    return url, item, False
