"""Baut HomeCinema: erzeugt Playlists + Startseiten-Reihen, prüft alle XML-Dateien und packt die ZIP.

Ausführen: py tools/build.py
Ergebnis:  dist/script.homecinema-<version>.zip  (enthält den Skin, ein ZIP genügt für die Installation)
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape, quoteattr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIN = os.path.join(ROOT, "skin.homecinema")
ADDON = os.path.join(ROOT, "script.homecinema")
DIST = os.path.join(ROOT, "dist")

sys.path.insert(0, os.path.join(ADDON, "resources", "lib"))
from homecinema.genres import GENRE_ROWS  # noqa: E402

EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
EXCLUDE_EXT = {".pyc", ".pyo"}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# ------------------------------------------------------------------------- Smart-Playlists
def playlist(kind, name, rules, order, limit, match="all"):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
             '<smartplaylist type="{}">'.format(kind),
             "    <name>{}</name>".format(escape(name)),
             "    <match>{}</match>".format(match)]
    for field, operator, values in rules:
        if values:
            lines.append('    <rule field="{}" operator="{}">'.format(field, operator))
            lines.extend("        <value>{}</value>".format(escape(v)) for v in values)
            lines.append("    </rule>")
        else:
            lines.append('    <rule field="{}" operator="{}" />'.format(field, operator))
    lines.append("    <limit>{}</limit>".format(limit))
    lines.append('    <order direction="descending">{}</order>'.format(order))
    lines.append("</smartplaylist>")
    return "\n".join(lines) + "\n"


def generate_playlists():
    folder = os.path.join(SKIN, "playlists")
    for name in os.listdir(folder):
        if name.startswith("hc_"):
            os.remove(os.path.join(folder, name))
    write(os.path.join(folder, "hc_movies_recent.xsp"), playlist(
        "movies", "Zuletzt gesehen",
        [("inprogress", "true", []), ("playcount", "greaterthan", ["0"])],
        "lastplayed", 25, match="one"))
    for key, label, movie_genres, tv_genres in GENRE_ROWS:
        write(os.path.join(folder, "hc_movies_{}.xsp".format(key)),
              playlist("movies", label, [("genre", "is", movie_genres)], "dateadded", 40))
        write(os.path.join(folder, "hc_tvshows_{}.xsp".format(key)),
              playlist("tvshows", label, [("genre", "is", tv_genres)], "dateadded", 40))


# ------------------------------------------------------------------------- Startseiten-Reihen
def row(group_id, header, content, onclick=None, badge=False):
    params = [("group_id", str(group_id)), ("list_id", str(group_id + 1)),
              ("header", header), ("content", content)]
    if onclick:
        params.append(("onclick", onclick))
    if badge:
        params.append(("badge", "true"))
    body = "\n".join('\t\t\t<param name="{}" value={} />'.format(k, quoteattr(v)) for k, v in params)
    return '\t\t<include content="HCPosterRow">\n{}\n\t\t</include>'.format(body)


def header_variable(list_id, header):
    """Reihenüberschrift: golden, solange die Reihe den Fokus hat."""
    return ('\t<variable name="HCRowHeader{0}">\n'
            '\t\t<value condition="Control.HasFocus({0})">[COLOR hc_gold]{1}[/COLOR]</value>\n'
            "\t\t<value>{1}</value>\n"
            "\t</variable>").format(list_id, escape(header))


def generate_rows():
    headers = [(1171, "Filme"), (1181, "Serien")]  # Suche (Custom_1150_Search.xml)
    movies = [row(3100, "Zuletzt gesehen", "special://skin/playlists/hc_movies_recent.xsp")]
    series = [row(4100, "Zuletzt gesehen",
                  "plugin://script.homecinema/?action=continue_series&refresh=$INFO[Window(Home).Property(hc_refresh)]",
                  onclick="RunScript(script.homecinema,action=play_episode,episodeid=$INFO[ListItem.DBID])",
                  badge=True)]
    headers += [(3101, "Zuletzt gesehen"), (4101, "Zuletzt gesehen")]
    for index, (key, label, _, _) in enumerate(GENRE_ROWS, start=1):
        movies.append(row(3100 + index * 10, label, "special://skin/playlists/hc_movies_{}.xsp".format(key)))
        series.append(row(4100 + index * 10, label, "special://skin/playlists/hc_tvshows_{}.xsp".format(key)))
        headers += [(3101 + index * 10, label), (4101 + index * 10, label)]
    text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- Automatisch erzeugt von tools/build.py aus script.homecinema/resources/lib/homecinema/genres.py -->\n"
            "<includes>\n"
            '\t<include name="HCMovieRows">\n' + "\n".join(movies) + "\n\t</include>\n"
            '\t<include name="HCSeriesRows">\n' + "\n".join(series) + "\n\t</include>\n"
            + "\n".join(header_variable(list_id, header) for list_id, header in headers) + "\n"
            "</includes>\n")
    write(os.path.join(SKIN, "xml", "Includes_HomeCinemaRows.xml"), text)


# ------------------------------------------------------------------------- Prüfen & Packen
def validate_xml():
    errors = []
    for base in (SKIN, ADDON):
        for folder, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if name.endswith((".xml", ".xsp")):
                    path = os.path.join(folder, name)
                    try:
                        ET.parse(path)
                    except ET.ParseError as exc:
                        errors.append("{}: {}".format(os.path.relpath(path, ROOT), exc))
    return errors


def version_of(addon_dir):
    with open(os.path.join(addon_dir, "addon.xml"), encoding="utf-8") as handle:
        return re.search(r'<addon[^>]*\sversion="([^"]+)"', handle.read()).group(1)


def add_tree(archive, source, arc_prefix):
    for folder, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1] in EXCLUDE_EXT:
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, source).replace(os.sep, "/")
            archive.write(path, "{}/{}".format(arc_prefix, rel))


def package():
    os.makedirs(DIST, exist_ok=True)
    version = version_of(ADDON)
    target = os.path.join(DIST, "script.homecinema-{}.zip".format(version))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, ADDON, "script.homecinema")
        # Skin liegt im Add-on und wird beim Einrichten nach addons/ kopiert
        add_tree(archive, SKIN, "script.homecinema/resources/skin/skin.homecinema")
    skin_zip = os.path.join(DIST, "skin.homecinema-{}.zip".format(version_of(SKIN)))
    with zipfile.ZipFile(skin_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, SKIN, "skin.homecinema")
    return target, skin_zip


def main():
    generate_playlists()
    generate_rows()
    errors = validate_xml()
    if errors:
        print("XML-Fehler:")
        print("\n".join(errors))
        sys.exit(1)
    for path in package():
        print("{}  ({:.1f} MB)".format(os.path.relpath(path, ROOT), os.path.getsize(path) / 1e6))


if __name__ == "__main__":
    main()
