"""Schreibt Kodis Konfiguration: advancedsettings.xml, sources.xml, Keymap und Bibliothekspfade.

Ohne Kodi-Abhängigkeit (Dateipfade werden übergeben), damit alles testbar ist.
"""
import glob
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

MOVIE_SCRAPER = "metadata.themoviedb.org.python"
TV_SCRAPER = "metadata.tvshows.themoviedb.org.python"
RECURSIVE = 2147483647  # So speichert Kodi "rekursiv scannen"

# Deutsche TMDB-Daten. Kodi nimmt für einen Bibliothekspfad die Scraper-Standardwerte (Englisch),
# wenn strSettings leer ist – deshalb werden die Einstellungen pro Pfad gespeichert.
SCRAPER_SETTINGS = {
    MOVIE_SCRAPER: {"language": "de-DE", "searchlanguage": "de-DE", "tmdbcertcountry": "de",
                    "certprefix": "FSK ", "fanarttv_language": "de"},
    TV_SCRAPER: {"languageDetails": "de-DE", "tmdbcertcountry": "de", "usecertprefix": "true",
                 "certprefix": "FSK "},
}


def scraper_settings_xml(scraper_id):
    root = ET.Element("settings", {"version": "2"})
    for key, value in SCRAPER_SETTINGS[scraper_id].items():
        ET.SubElement(root, "setting", {"id": key}).text = value
    return ET.tostring(root, encoding="unicode")

# Kodi-Regex: (Staffel)(Folge)(Rest). Ergänzt "Staffel 1/Folge 01.mkv" und "Staffel 1/01 - Titel.mkv".
TV_MATCHING = [
    r"(?:staffel|season)[ ._-]*([0-9]+)[\\/](?:[^\\/]*[ ._-])?(?:folge|episode|ep)[ ._-]*([0-9]+)([^\\/]*)$",
    r"(?:staffel|season)[ ._-]*([0-9]+)[\\/]([0-9]{1,3})([ ._-][^\\/]*)$",
]
# Staffel-Pakete: "Westworld Season 1 (2160p …)" oder "Californication.S01.1080p…" -> Suche nach "Westworld".
# Kodi schneidet Namen ab der ersten Fundstelle eines cleanstrings-Ausdrucks ab.
CLEAN_STRINGS = [
    r"[ _\,\.\(\)\[\]\-](?:s[0-9]{1,2}|season[ ._-]*[0-9]{1,2}|staffel[ ._-]*[0-9]{1,2})(?:[ _\,\.\(\)\[\]\-]|$)",
]
# Episoden dürfen beim Film-Scan nicht als Film erkannt werden.
MOVIE_EXCLUDES = [
    r"[\\/._ -]s[0-9]{1,2}[ ._-]*e[0-9]{1,3}",
    r"[\\/._ \[(-][0-9]{1,2}x[0-9]{2,3}(?![0-9])",
    r"[\\/](?:staffel|season)[ ._-]*[0-9]+[\\/]",
]

KEYMAP = """<?xml version="1.0" encoding="UTF-8"?>
<!-- HomeCinema: Tasten typischer Air-Mouse-/Media-Fernbedienungen -->
<keymap>
  <global>
    <keyboard>
      <browser_back>Back</browser_back>
      <homepage>ActivateWindow(Home)</homepage>
      <browser_home>ActivateWindow(Home)</browser_home>
      <menu>ContextMenu</menu>
      <browser_search>ActivateWindow(1150)</browser_search>
    </keyboard>
  </global>
  <FullscreenVideo>
    <keyboard>
      <menu>OSD</menu>
    </keyboard>
  </FullscreenVideo>
</keymap>
"""


def _indent(elem, level=0):
    pad = "\n" + "  " * level
    if len(elem):
        if not (elem.text or "").strip():
            elem.text = pad + "  "
        for child in elem:
            _indent(child, level + 1)
        if not (child.tail or "").strip():
            child.tail = pad
    if level and not (elem.tail or "").strip():
        elem.tail = pad


def _to_xml(root):
    _indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _parse_or_new(xml_text, root_tag):
    if xml_text and xml_text.strip():
        try:
            root = ET.fromstring(xml_text)
            if root.tag == root_tag:
                return root
        except ET.ParseError:
            pass
    return ET.Element(root_tag)


def _ensure_regexps(parent, tag, action, regexps):
    elem = parent.find(tag)
    if elem is None:
        elem = ET.SubElement(parent, tag)
        elem.set("action", action)
    existing = {(r.text or "") for r in elem.findall("regexp")}
    for regexp in regexps:
        if regexp not in existing:
            ET.SubElement(elem, "regexp").text = regexp


def merge_advancedsettings(xml_text):
    """Ergänzt eine (evtl. vorhandene) advancedsettings.xml um die HomeCinema-Regeln. Idempotent."""
    root = _parse_or_new(xml_text, "advancedsettings")
    video = root.find("video")
    if video is None:
        video = ET.SubElement(root, "video")
    _ensure_regexps(video, "excludefromscan", "append", MOVIE_EXCLUDES)
    _ensure_regexps(video, "cleanstrings", "append", CLEAN_STRINGS)
    _ensure_regexps(root, "tvshowmatching", "prepend", TV_MATCHING)
    return _to_xml(root)


def merge_sources(xml_text, name, path):
    """Fügt den Medienordner als Video-Quelle in sources.xml ein (falls noch nicht vorhanden)."""
    root = _parse_or_new(xml_text, "sources")
    for section in ("programs", "video", "music", "pictures", "files", "games"):
        if root.find(section) is None:
            sec = ET.SubElement(root, section)
            ET.SubElement(sec, "default").set("pathversion", "1")
    video = root.find("video")
    for source in video.findall("source"):
        if any((p.text or "") == path for p in source.findall("path")):
            return _to_xml(root)
    names = {(s.findtext("name") or "") for s in video.findall("source")}
    unique, counter = name, 2
    while unique in names:
        unique = "{} {}".format(name, counter)
        counter += 1
    source = ET.SubElement(video, "source")
    ET.SubElement(source, "name").text = unique
    path_elem = ET.SubElement(source, "path")
    path_elem.set("pathversion", "1")
    path_elem.text = path
    ET.SubElement(source, "allowsharing").text = "true"
    return _to_xml(root)


def find_video_db(database_dir):
    """Neueste MyVideosNNN.db im Kodi-Datenbankordner."""
    candidates = []
    for path in glob.glob(os.path.join(database_dir, "MyVideos*.db")):
        match = re.search(r"MyVideos(\d+)\.db$", path)
        if match:
            candidates.append((int(match.group(1)), path))
    return max(candidates)[1] if candidates else None


def join_path(base, rel):
    """Hängt einen relativen '/'-Pfad an einen Kodi-Pfad an (Ergebnis mit Schlussstrich)."""
    sep = "\\" if ("\\" in base and "://" not in base) else "/"
    base = base if base.endswith(("/", "\\")) else base + sep
    rel = rel.strip("/")
    if not rel:
        return base
    return base + rel.replace("/", sep) + sep


def _parent_path(path):
    sep = "\\" if ("\\" in path and "://" not in path) else "/"
    trimmed = path.rstrip(sep)
    cut = trimmed.rfind(sep)
    return trimmed[:cut + 1] if cut >= 0 else ""


def _path_id(cur, path):
    row = cur.execute("SELECT idPath FROM path WHERE strPath = ?", (path,)).fetchone()
    return row[0] if row else None


def _add_path(cur, path):
    """Wie CVideoDatabase::AddPath: Pfad anlegen (falls neu), mit Elternpfad-Verknüpfung."""
    existing = _path_id(cur, path)
    if existing is not None:
        return existing
    parent_id = _path_id(cur, _parent_path(path))
    cur.execute("INSERT INTO path (idPath, strPath, idParentPath) VALUES (NULL, ?, ?)", (path, parent_id))
    return cur.lastrowid


def register_library(db_path, movies_root, show_paths):
    """Legt fest, wie Kodi scannt: Medienordner = Filme (rekursiv), jeder Serienordner = eine Serie.

    Entspricht in Kodi "Inhalt festlegen" mit dem TMDB-Scraper auf Deutsch.
    """
    con = sqlite3.connect(db_path, timeout=30)
    try:
        cur = con.cursor()
        root_id = _add_path(cur, movies_root)
        cur.execute(
            "UPDATE path SET strContent='movies', strScraper=?, scanRecursive=?, useFolderNames=0, "
            "strSettings=?, noUpdate=0, exclude=0 WHERE idPath=?",
            (MOVIE_SCRAPER, RECURSIVE, scraper_settings_xml(MOVIE_SCRAPER), root_id),
        )
        for show_path in show_paths:
            show_id = _add_path(cur, show_path)
            # useFolderNames=1 bei Serien = "Ordner enthält eine einzelne Serie"
            cur.execute(
                "UPDATE path SET strContent='tvshows', strScraper=?, scanRecursive=0, useFolderNames=1, "
                "strSettings=?, noUpdate=0, exclude=0 WHERE idPath=?",
                (TV_SCRAPER, scraper_settings_xml(TV_SCRAPER), show_id),
            )
        con.commit()
    finally:
        con.close()
