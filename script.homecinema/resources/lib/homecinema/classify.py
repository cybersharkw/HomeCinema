"""Erkennt in einem Medienordner, was Film und was Serie ist.

Reine Logik ohne Kodi-Abhängigkeit, damit sie getestet werden kann.
Pfade werden intern immer mit '/' getrennt verarbeitet.
"""
import re

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".mpg", ".mpeg", ".ts", ".m2ts",
    ".webm", ".flv", ".vob", ".iso", ".divx", ".ogm", ".3gp", ".mts",
}

# Episodenmuster im Dateinamen: S01E02, s1e2, S01.E02, 1x02
_EPISODE_IN_NAME = [
    re.compile(r"(?:^|[ ._\-\[(])s(\d{1,2})[ ._-]*e(\d{1,3})", re.IGNORECASE),
    re.compile(r"(?:^|[ ._\-\[(])(\d{1,2})x(\d{2,3})(?!\d)", re.IGNORECASE),
]
# Staffel-Ordner: "Staffel 1", "Season 02", "S1"
_SEASON_FOLDER = re.compile(r"^(?:staffel|season|s)[ ._-]*(\d{1,2})$", re.IGNORECASE)
# Folgennummer im Dateinamen, wenn die Staffel aus dem Ordner kommt
_EPISODE_NUMBER = [
    re.compile(r"(?:^|[ ._-])(?:folge|episode|ep|e)[ ._-]*(\d{1,3})", re.IGNORECASE),
    re.compile(r"^(\d{1,3})(?:[ ._-]|$)"),
]
_IGNORED_NAMES = re.compile(r"(?:^|[ ._-])(sample|trailer)(?:[ ._-]|$)", re.IGNORECASE)


def is_video(name):
    """True, wenn der Dateiname eine Videoendung hat (keine Samples/Trailer)."""
    dot = name.rfind(".")
    if dot < 0:
        return False
    if _IGNORED_NAMES.search(name[:dot]):
        return False
    return name[dot:].lower() in VIDEO_EXTENSIONS


def _strip_ext(name):
    dot = name.rfind(".")
    return name[:dot] if dot > 0 else name


def parse_episode(rel_path):
    """Liefert (staffel, folge) für einen relativen Pfad oder None, wenn es kein Episodenname ist."""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    if not parts:
        return None
    stem = _strip_ext(parts[-1])
    for pattern in _EPISODE_IN_NAME:
        match = pattern.search(stem)
        if match:
            return int(match.group(1)), int(match.group(2))
    if len(parts) >= 2:
        season_match = _SEASON_FOLDER.match(parts[-2])
        if season_match:
            for pattern in _EPISODE_NUMBER:
                match = pattern.search(stem)
                if match:
                    return int(season_match.group(1)), int(match.group(1))
    return None


def is_season_folder(name):
    return bool(_SEASON_FOLDER.match(name))


def show_folder_of(rel_path):
    """Relativer Serienordner einer Episode ('' = direkt im Medienordner)."""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p][:-1]
    if parts and is_season_folder(parts[-1]):
        parts = parts[:-1]
    return "/".join(parts)


def plan_library(rel_files):
    """Ordnet alle gefundenen Videodateien zu.

    rel_files: Pfade relativ zum Medienordner (z.B. "Serien/Dark/Staffel 1/Folge 01.mkv").
    Rückgabe: dict mit
      movies     – Liste der Filmdateien
      shows      – {Serienordner: Anzahl Episoden}
      unassigned – Episoden direkt im Medienordner (Kodi kann sie keiner Serie zuordnen)
    """
    movies, unassigned = [], []
    shows = {}
    for rel in rel_files:
        rel = rel.replace("\\", "/").strip("/")
        name = rel.rsplit("/", 1)[-1]
        if not is_video(name):
            continue
        if parse_episode(rel) is None:
            movies.append(rel)
            continue
        folder = show_folder_of(rel)
        if not folder:
            unassigned.append(rel)
        else:
            shows[folder] = shows.get(folder, 0) + 1
    # Ein "Film", der in einem Serienordner liegt (z.B. ein Extra ohne Episodennummer),
    # gehört nicht in die Filmliste – Kodi scannt den Ordner ohnehin als Serie.
    show_prefixes = tuple(folder + "/" for folder in shows)
    movies = [m for m in movies if not m.startswith(show_prefixes)]
    return {"movies": sorted(movies), "shows": dict(sorted(shows.items())), "unassigned": sorted(unassigned)}


# Ab hier ist ein Ordnername nur noch Technik: Staffel-Angabe, Auflösung, Quelle, Codec, Klammern
_NAME_CUT = re.compile(
    r"[ ._\-\[(](?:s\d{1,2}(?:e\d{1,3})?|season[ ._-]*\d{1,2}|staffel[ ._-]*\d{1,2}|complete|\d{3,4}p|"
    r"bluray|blu-ray|bdrip|brrip|web(?:-?dl|rip)?|hdtv|dvdrip|x26[45]|h\.?26[45]|hevc|\[|\()(?:[ ._\-\])]|$)",
    re.IGNORECASE)


def show_display_name(folder):
    """Lesbarer Serienname aus dem Ordnerpfad, z.B. "Californication.S01.1080p.BluRay" -> "Californication"."""
    name = folder.rstrip("/").rsplit("/", 1)[-1]
    match = _NAME_CUT.search(name)
    if match and match.start() > 0:
        name = name[:match.start()]
    if " " not in name:
        name = name.replace(".", " ").replace("_", " ")
    return re.sub(r"\s+", " ", name).strip(" -")


def show_names(shows):
    """Eindeutige, lesbare Seriennamen (mehrere Staffel-Ordner einer Serie zählen einmal)."""
    names = []
    for folder in shows:
        name = show_display_name(folder)
        if name.lower() not in (n.lower() for n in names):
            names.append(name)
    return names
