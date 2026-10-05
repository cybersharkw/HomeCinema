# HomeCinema

Dein Heimkino für LibreELEC/Kodi: dunkler Kino-Look, komplett auf Deutsch und mit der Fernbedienung bedienbar.

- **Filme** und **Serien** als eigene Bereiche, oben rechts die **Suche** (Titel, Schauspieler, Regie)
- Erste Reihe **Zuletzt gesehen**, darunter **Genre-Reihen** (Action, Science-Fiction, Horror, Thriller, Komödie, …)
- Bilder, Beschreibungen, Darsteller und Regie kommen kostenlos von **TMDB** und werden nur **einmal** geladen (Kodi-Bibliothek)
- **Bewertung mit 1–5 Sternen** (Info-Ansicht → *Bewerten*)
- **Serien laufen automatisch weiter**: Nach Folge 1 startet Folge 2 – auch über Staffelgrenzen hinweg, mit Hinweis kurz vor dem Ende und „Schaust du noch?“-Abfrage
- Intro mit Kinovorhang, sanfte Animationen

Gebaut und getestet mit **Kodi 21.3 „Omega“** (= LibreELEC 12.2). Der Skin nutzt die GUI-Version 5.17,
die auch Kodi 22 noch unterstützt.

## Installation (einmalig, ca. 5 Minuten)

1. **ZIP auf den Laptop bringen**: `dist/script.homecinema-1.0.0.zip` auf einen USB-Stick kopieren
   (oder über das Netzwerk in die LibreELEC-Freigabe `\\LIBREELEC\Downloads` legen).
2. In Kodi: **Einstellungen → System → Add-ons → „Unbekannte Herkunft“ aktivieren** (Rückfrage mit *Ja* bestätigen).
3. **Einstellungen → Add-ons → Aus ZIP-Datei installieren** → USB-Stick bzw. *Downloads* →
   `script.homecinema-1.0.0.zip` wählen.
4. Der **Einrichtungsassistent startet automatisch**:
   - **Medienordner wählen** – z. B. die externe Festplatte oder `/storage/videos`.
     Netzlaufwerke (NAS) gehen auch: im Ordnerdialog *Netzwerkfreigabe hinzufügen*.
   - HomeCinema zeigt, wie viele Filme und Serien gefunden wurden → **Einrichten**.
   - Kodi lädt das **deutsche Sprachpaket** – Kodi fragt dabei noch auf Englisch
     *„Would you like to download this add-on?“* → **Yes**.
   - Kodi wechselt zum **HomeCinema-Skin** (falls Kodi fragt „Änderung beibehalten?“ → **Ja**).
   - Kodi startet neu und lädt danach alle Infos von TMDB. Neue Titel erscheinen nach und nach
     (rund 1 Minute für 25 Filme und 2 Serien).

Später neue Ordner hinzufügen: auf der Startseite oben rechts **Zahnrad → Medienordner hinzufügen**.

## So sollten die Dateien heißen

HomeCinema erkennt Serien an der Folgennummer. Alles andere wird als Film behandelt.

```
Medienordner/
├── Inception (2010).mkv
├── Filme/The Matrix (1999)/The.Matrix.1999.1080p.mkv
├── Serien/
│   ├── Dark/
│   │   ├── Staffel 1/Folge 01.mkv          ← "Staffel X/Folge Y" geht
│   │   └── Staffel 2/Dark.S02E01.mkv        ← S02E01 geht immer
│   └── Breaking Bad/Breaking.Bad.S01E01.mkv
```

- Release-Namen wie `Encanto (2021) [2160p] [4K] [WEB] [YTS.MX]/Encanto.2021.2160p….mkv` funktionieren.
- Jede Serie braucht einen **eigenen Ordner**. Staffel-Pakete wie
  `Californication.S01.1080p.BluRay.x265-RARBG` oder `Westworld Season 1 (2160p …)` gehen auch –
  mehrere Staffel-Ordner einer Serie werden automatisch zu einer Serie zusammengefasst.
- Folgen: `S01E02`, `1x02`, `Staffel 1/Folge 02` oder `Staffel 1/02 - Titel`.
- Bei mehrdeutigen Namen das Jahr in den Ordner schreiben: `Dark (2017)` statt `Dark`
  (sonst kann TMDB z. B. „Dark Shadows“ liefern).

**Falsch erkannt?** Titel öffnen → in der Info-Ansicht nach rechts zu **„Aktualisieren“** →
richtigen Titel auswählen.

## Fernbedienung

Jede USB-/Bluetooth-Fernbedienung, die Pfeiltasten, OK und Zurück sendet, funktioniert sofort.
Empfehlung (digitec.ch): **Xoro AMW 100 Airmouse** – USB-Empfänger einstecken, fertig.

| Taste | Wirkung |
|---|---|
| Pfeile | Navigieren |
| OK | Auswählen / Infos öffnen |
| Zurück | Zurück (auf der Startseite: zur Kopfzeile) |
| Home | Startseite |
| Menü | Kontextmenü (im Video: Bildschirmmenü) |

## Einstellungen

Zahnrad oben rechts auf der Startseite:

- **Medienordner hinzufügen / entfernen**
- **Bibliothek aktualisieren** (passiert auch bei jedem Start automatisch)
- **Wiedergabe & Autoplay**: nächste Folge automatisch (an/aus), Hinweis vor dem Ende,
  „Schaust du noch?“ nach 2/3/5 Folgen oder nie
- **Kodi-Einstellungen**, **Ausschalten / Neustart**

## Für Entwickler

```
script.homecinema/   Python-Add-on (Assistent, Autoplay-Dienst, Bewertung, "Weiter schauen"-Liste)
skin.homecinema/     Skin (Fork von Estuary): Home.xml, Startup.xml, Custom_1150_Search.xml,
                     Includes_HomeCinema.xml, DialogVideoInfo.xml (Bewerten/Weiter schauen)
tools/build.py       erzeugt Genre-Playlists + Reihen, prüft XML, baut dist/*.zip
tools/make_media.py  erzeugt Grafiken (Sterne, Vorhang, Verläufe, Icon)
tests/               Unit-Tests der Logik (Erkennung Film/Serie, Folgenreihenfolge, Kodi-Dateien)
```

```bash
py -m unittest discover -s tests
py tools/build.py
```

Fortgeschritten: Einrichtung ohne Ordnerdialog, z. B. per SSH auf LibreELEC:
`kodi-send --action="RunScript(script.homecinema,action=setup,path=/storage/videos/)"`

Genre-Reihen ändern: `script.homecinema/resources/lib/homecinema/genres.py` anpassen, dann `py tools/build.py`.

Lizenz: Skin basiert auf Estuary (CC BY-SA 4.0 / GPL-2.0), Schrift Bebas Neue (SIL OFL), Daten von TMDB
(„This product uses the TMDB API but is not endorsed or certified by TMDB.“).
