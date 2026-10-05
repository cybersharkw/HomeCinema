"""Reihenfolge von Episoden und Ermittlung der nächsten Folge (ohne Kodi-Abhängigkeit).

Episoden sind dicts wie sie Kodi per JSON-RPC liefert:
{"episodeid": 7, "season": 1, "episode": 3, "playcount": 0, "lastplayed": "2026-09-30 21:14:02",
 "resume": {"position": 0, "total": 0}, "title": "..."}
"""


def episode_code(season, episode):
    return "S{:02d}E{:02d}".format(int(season or 0), int(episode or 0))


def _order_key(ep):
    return (int(ep.get("season") or 0), int(ep.get("episode") or 0), int(ep.get("episodeid") or 0))


def ordered(episodes, include_specials=False):
    """Episoden in Abspielreihenfolge: Staffel für Staffel, Folge für Folge.

    Specials (Staffel 0) sind standardmässig ausgeschlossen.
    """
    eps = [e for e in episodes if include_specials or int(e.get("season") or 0) > 0]
    return sorted(eps, key=_order_key)


def next_episode(episodes, current_id):
    """Die Folge nach current_id – auch über Staffelgrenzen hinweg. None am Serienende.

    Läuft gerade ein Special (Staffel 0), wird nicht automatisch weitergespielt.
    """
    current = next((e for e in episodes if e.get("episodeid") == current_id), None)
    if current is None or int(current.get("season") or 0) == 0:
        return None
    eps = ordered(episodes)
    for index, ep in enumerate(eps):
        if ep.get("episodeid") == current_id:
            return eps[index + 1] if index + 1 < len(eps) else None
    return None


def _is_in_progress(ep):
    resume = ep.get("resume") or {}
    return float(resume.get("position") or 0) > 0


def continue_episode(episodes):
    """Die Folge, mit der es bei "Weiter schauen" weitergeht.

    - Zuletzt gespielte Folge noch nicht fertig -> genau diese (mit Fortsetzen).
    - Sonst die nächste Folge danach.
    - Noch nichts gesehen -> erste Folge.
    - Serie komplett gesehen -> None.
    """
    eps = ordered(episodes)
    if not eps:
        return None
    played = [e for e in eps if e.get("lastplayed")]
    if not played:
        return eps[0]
    last = max(played, key=lambda e: (e.get("lastplayed") or "", _order_key(e)))
    if _is_in_progress(last) or not int(last.get("playcount") or 0):
        return last
    following = next_episode(eps, last.get("episodeid"))
    # Folgen, die später schon gesehen wurden (z.B. vorgespult), überspringen
    while following is not None and int(following.get("playcount") or 0) and not _is_in_progress(following):
        following = next_episode(eps, following.get("episodeid"))
    return following
