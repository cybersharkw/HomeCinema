"""Tests der Kodi-unabhängigen Logik. Ausführen: py -m unittest discover -s tests"""
import os
import re
import sqlite3
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script.homecinema", "resources", "lib"))

from homecinema import classify, episodes, kodifiles  # noqa: E402


class ParseEpisodeTest(unittest.TestCase):
    def test_common_patterns(self):
        cases = {
            "Breaking Bad/Breaking.Bad.S01E02.1080p.BluRay.x264.mkv": (1, 2),
            "Dark/Staffel 2/Dark - s02e10 - Ende.mkv": (2, 10),
            "Friends/Friends 3x07.avi": (3, 7),
            "Dark/Staffel 2/Folge 01.mkv": (2, 1),
            "Dark/Season 3/Episode 8 - Paradies.mp4": (3, 8),
            "Dark/Staffel 1/03 - Gestern und Heute.mkv": (1, 3),
            "Lost/S1/E04.mkv": (1, 4),
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify.parse_episode(path), expected)

    def test_movies_are_not_episodes(self):
        for path in [
            "Filme/Inception (2010).mkv",
            "Filme/The.Matrix.1999.1080p.BluRay.x264.mkv",
            "Filme/2012 (2009)/2012.mkv",
            "Filme/Blade Runner 2049.mkv",
            "Filme/Se7en (1995).mkv",
            "Filme/Ocean's Eleven.mkv",
        ]:
            with self.subTest(path=path):
                self.assertIsNone(classify.parse_episode(path))

    def test_is_video(self):
        self.assertTrue(classify.is_video("Film.MKV"))
        self.assertFalse(classify.is_video("cover.jpg"))
        self.assertFalse(classify.is_video("film-sample.mkv"))
        self.assertFalse(classify.is_video("Inception Trailer.mp4"))


class PlanLibraryTest(unittest.TestCase):
    def test_mixed_folder(self):
        plan = classify.plan_library([
            "Inception (2010).mkv",
            "Filme/Matrix/The.Matrix.1999.mkv",
            "Serien/Dark/Staffel 1/Folge 01.mkv",
            "Serien/Dark/Staffel 1/Folge 02.mkv",
            "Serien/Dark/Staffel 2/Folge 01.mkv",
            "Breaking Bad/Breaking.Bad.S01E01.mkv",
            "Breaking Bad/Making of.mkv",
            "S01E01.mkv",
            "notes.txt",
        ])
        self.assertEqual(plan["movies"], ["Filme/Matrix/The.Matrix.1999.mkv", "Inception (2010).mkv"])
        self.assertEqual(plan["shows"], {"Breaking Bad": 1, "Serien/Dark": 3})
        self.assertEqual(plan["unassigned"], ["S01E01.mkv"])

    def test_show_names_from_season_packs(self):
        self.assertEqual(classify.show_names([
            "Serien/Californication.S01.1080p.BluRay.x265-RARBG",
            "Serien/Californication.S02.1080p.BluRay.x265-RARBG",
            "Serien/Westworld Season 1  (2160p BD x265 10bit S86 Joy)",
            "Serien/Dark",
            "Breaking Bad (2008)",
            "The.Office.US.Complete.720p",
        ]), ["Californication", "Westworld", "Dark", "Breaking Bad (2008)", "The Office US"])

    def test_windows_separators(self):
        plan = classify.plan_library(["Serien\\Dark\\Staffel 1\\Folge 01.mkv"])
        self.assertEqual(plan["shows"], {"Serien/Dark": 1})


def ep(eid, season, episode, playcount=0, lastplayed="", position=0):
    return {"episodeid": eid, "season": season, "episode": episode, "playcount": playcount,
            "lastplayed": lastplayed, "resume": {"position": position, "total": 2400}}


class EpisodeOrderTest(unittest.TestCase):
    def setUp(self):
        # absichtlich durcheinander, inkl. Special
        self.eps = [ep(5, 2, 1), ep(2, 1, 2), ep(9, 0, 1), ep(3, 1, 10), ep(1, 1, 1), ep(6, 2, 2)]

    def test_order(self):
        self.assertEqual([e["episodeid"] for e in episodes.ordered(self.eps)], [1, 2, 3, 5, 6])

    def test_next_within_season(self):
        self.assertEqual(episodes.next_episode(self.eps, 1)["episodeid"], 2)
        self.assertEqual(episodes.next_episode(self.eps, 2)["episodeid"], 3)  # E02 -> E10, nicht alphabetisch

    def test_next_across_seasons(self):
        self.assertEqual(episodes.next_episode(self.eps, 3)["episodeid"], 5)

    def test_end_of_series_and_specials(self):
        self.assertIsNone(episodes.next_episode(self.eps, 6))
        self.assertIsNone(episodes.next_episode(self.eps, 9))
        self.assertIsNone(episodes.next_episode(self.eps, 404))

    def test_episode_code(self):
        self.assertEqual(episodes.episode_code(2, 5), "S02E05")


class ContinueEpisodeTest(unittest.TestCase):
    def test_nothing_watched_starts_at_first(self):
        self.assertEqual(episodes.continue_episode([ep(2, 1, 2), ep(1, 1, 1)])["episodeid"], 1)

    def test_resume_unfinished(self):
        eps = [ep(1, 1, 1, 1, "2026-09-01 20:00:00"), ep(2, 1, 2, 0, "2026-09-02 20:00:00", position=600)]
        self.assertEqual(episodes.continue_episode(eps)["episodeid"], 2)

    def test_next_after_finished_across_season(self):
        eps = [ep(1, 1, 1, 1, "2026-09-01 20:00:00"), ep(2, 2, 1)]
        self.assertEqual(episodes.continue_episode(eps)["episodeid"], 2)

    def test_skips_already_watched(self):
        eps = [ep(1, 1, 1, 1, "2026-09-03 20:00:00"), ep(2, 1, 2, 1, "2026-08-01 20:00:00"), ep(3, 1, 3)]
        self.assertEqual(episodes.continue_episode(eps)["episodeid"], 3)

    def test_all_watched(self):
        self.assertIsNone(episodes.continue_episode([ep(1, 1, 1, 1, "2026-09-01 20:00:00")]))


class KodiFilesTest(unittest.TestCase):
    def test_regexps_compile_and_match(self):
        tv = [re.compile(r, re.IGNORECASE) for r in kodifiles.TV_MATCHING]
        match = tv[0].search("/storage/videos/Dark/Staffel 2/Folge 03.mkv")
        self.assertEqual(match.group(1, 2), ("2", "03"))
        match = tv[1].search("/storage/videos/Dark/Staffel 1/07 - Titel.mkv")
        self.assertEqual(match.group(1, 2), ("1", "07"))
        self.assertIsNone(tv[0].search("/storage/videos/Sleepy Hollow/Staffel 1/Sleepy.Hollow.S01E01.mkv"))
        excludes = [re.compile(r, re.IGNORECASE) for r in kodifiles.MOVIE_EXCLUDES]
        for path in ["/m/Dark.S01E01.mkv", "/m/Friends 1x02.avi", "/m/Dark/Staffel 1/"]:
            self.assertTrue(any(r.search(path) for r in excludes), path)
        for path in ["/m/Inception (2010).mkv", "/m/Blade Runner 2049.mkv", "/m/Se7en.mkv"]:
            self.assertFalse(any(r.search(path) for r in excludes), path)

    def test_cleanstrings_cut_season_packs(self):
        def clean(name):  # wie Kodis CleanString: ab der ersten Fundstelle abschneiden
            for regexp in kodifiles.CLEAN_STRINGS:
                match = re.search(regexp, name, re.IGNORECASE)
                if match and match.start() > 0:
                    name = name[:match.start()]
            return name
        self.assertEqual(clean("Californication.S01.1080p.BluRay.x265-RARBG"), "Californication")
        self.assertEqual(clean("Westworld Season 1  (2160p BD x265 10bit S86 Joy)"), "Westworld")
        self.assertEqual(clean("Dark Staffel 2"), "Dark")
        for title in ["Season of the Witch (2011)", "S1m0ne (2002)", "Se7en", "Inception (2010)"]:
            self.assertEqual(clean(title), title)

    def test_merge_advancedsettings_keeps_existing_and_is_idempotent(self):
        existing = "<advancedsettings><cache><memorysize>1</memorysize></cache></advancedsettings>"
        once = kodifiles.merge_advancedsettings(existing)
        twice = kodifiles.merge_advancedsettings(once)
        self.assertEqual(once, twice)
        root = ET.fromstring(twice)
        self.assertEqual(root.findtext("cache/memorysize"), "1")
        self.assertEqual(len(root.findall("video/excludefromscan/regexp")), len(kodifiles.MOVIE_EXCLUDES))
        self.assertEqual(root.find("tvshowmatching").get("action"), "prepend")

    def test_merge_advancedsettings_from_nothing(self):
        root = ET.fromstring(kodifiles.merge_advancedsettings(""))
        self.assertEqual(root.tag, "advancedsettings")

    def test_merge_sources(self):
        xml = kodifiles.merge_sources("", "HomeCinema", "/storage/videos/")
        xml = kodifiles.merge_sources(xml, "HomeCinema", "/storage/videos/")  # doppelt -> nur einmal
        xml = kodifiles.merge_sources(xml, "HomeCinema", "smb://nas/filme/")
        root = ET.fromstring(xml)
        sources = root.findall("video/source")
        self.assertEqual([s.findtext("name") for s in sources], ["HomeCinema", "HomeCinema 2"])
        self.assertEqual(sources[1].findtext("path"), "smb://nas/filme/")
        self.assertIsNotNone(root.find("music/default"))

    def test_join_path(self):
        self.assertEqual(kodifiles.join_path("/storage/videos/", "Serien/Dark"), "/storage/videos/Serien/Dark/")
        self.assertEqual(kodifiles.join_path("/storage/videos", ""), "/storage/videos/")
        self.assertEqual(kodifiles.join_path("smb://nas/media/", "Dark"), "smb://nas/media/Dark/")
        self.assertEqual(kodifiles.join_path("D:\\Media\\", "Serien/Dark"), "D:\\Media\\Serien\\Dark\\")

    def test_register_library_with_kodi_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "MyVideos131.db")
            open(os.path.join(tmp, "MyVideos119.db"), "w").close()
            con = sqlite3.connect(db)
            con.execute(  # Schema wie in Kodi 21 (VideoDatabase.cpp)
                "CREATE TABLE path ( idPath integer primary key, strPath text, strContent text, strScraper "
                "text, strHash text, scanRecursive integer, useFolderNames bool, strSettings text, noUpdate "
                "bool, exclude bool, allAudio bool, dateAdded text, idParentPath integer)")
            con.execute("INSERT INTO path (strPath) VALUES ('/storage/videos/')")
            con.commit()
            con.close()
            self.assertEqual(kodifiles.find_video_db(tmp), db)

            shows = ["/storage/videos/Serien/Dark/", "/storage/videos/Breaking Bad/"]
            kodifiles.register_library(db, "/storage/videos/", shows)
            kodifiles.register_library(db, "/storage/videos/", shows)  # zweimal -> keine Duplikate

            con = sqlite3.connect(db)
            rows = {r[0]: r[1:] for r in con.execute(
                "SELECT strPath, strContent, strScraper, scanRecursive, useFolderNames FROM path")}
            settings = dict(con.execute("SELECT strPath, strSettings FROM path"))
            con.close()
            movie_settings = ET.fromstring(settings["/storage/videos/"])
            self.assertEqual(movie_settings.find("setting[@id='language']").text, "de-DE")
            tv_settings = ET.fromstring(settings["/storage/videos/Breaking Bad/"])
            self.assertEqual(tv_settings.find("setting[@id='languageDetails']").text, "de-DE")
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows["/storage/videos/"],
                             ("movies", kodifiles.MOVIE_SCRAPER, kodifiles.RECURSIVE, 0))
            self.assertEqual(rows["/storage/videos/Serien/Dark/"], ("tvshows", kodifiles.TV_SCRAPER, 0, 1))


if __name__ == "__main__":
    unittest.main()
