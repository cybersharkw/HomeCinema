"""Eigene Bewertung mit 1–5 Sternen (gespeichert als Kodi-"Meine Bewertung" 2–10)."""
import xbmcgui

from homecinema.kodi import addon, rpc

_DETAILS = {
    "movie": ("VideoLibrary.GetMovieDetails", "VideoLibrary.SetMovieDetails", "movieid", "moviedetails"),
    "tvshow": ("VideoLibrary.GetTVShowDetails", "VideoLibrary.SetTVShowDetails", "tvshowid", "tvshowdetails"),
    "episode": ("VideoLibrary.GetEpisodeDetails", "VideoLibrary.SetEpisodeDetails", "episodeid", "episodedetails"),
}
INFO_DIALOG_ID = 12003  # DialogVideoInfo
CHOICES = [
    (5, "5 Sterne  –  Meisterwerk"),
    (4, "4 Sterne  –  Sehr gut"),
    (3, "3 Sterne  –  Gut"),
    (2, "2 Sterne  –  Geht so"),
    (1, "1 Stern  –  Schlecht"),
    (0, "Bewertung entfernen"),
]


def stars_from_userrating(userrating):
    return int(round((userrating or 0) / 2.0))


def rate(dbtype, dbid):
    if dbtype not in _DETAILS or not dbid:
        return
    get_method, set_method, id_key, result_key = _DETAILS[dbtype]
    details = (rpc(get_method, {id_key: int(dbid), "properties": ["title", "userrating"]}) or {}).get(result_key, {})
    current = stars_from_userrating(details.get("userrating"))

    items = []
    for stars, label in CHOICES:
        item = xbmcgui.ListItem(label)
        item.setArt({"icon": "special://skin/media/hc/stars{}.png".format(stars * 2)})
        items.append(item)
    # Noch nicht bewertet -> "3 Sterne" vorauswählen, sonst die aktuelle Bewertung
    preselect = next((i for i, (stars, _) in enumerate(CHOICES) if stars == (current or 3)), 2)
    choice = xbmcgui.Dialog().select("{} bewerten".format(details.get("title", "")), items,
                                     preselect=preselect, useDetails=False)
    if choice < 0:
        return
    stars = CHOICES[choice][0]
    rpc(set_method, {id_key: int(dbid), "userrating": stars * 2})
    # Die offene Info-Ansicht zeigt sonst bis zum nächsten Öffnen die alte Bewertung
    xbmcgui.Window(INFO_DIALOG_ID).setProperty("hc_userrating", str(stars * 2))
    message = "Bewertung entfernt" if not stars else "{} von 5 Sternen".format(stars)
    xbmcgui.Dialog().notification("Bewertung gespeichert", message,
                                  addon().getAddonInfo("icon"), 3000, False)
