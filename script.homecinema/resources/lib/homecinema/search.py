"""Suchbegriff über die Bildschirmtastatur abfragen und an den Skin (Custom_1150_Search.xml) übergeben."""
import xbmc
import xbmcgui

SKIN_STRING = "HC.Search"


def ask():
    current = xbmc.getInfoLabel("Skin.String({})".format(SKIN_STRING))
    term = xbmcgui.Dialog().input("Suche: Titel, Schauspieler oder Regie", defaultt=current).strip()
    if not term and not current:
        return
    # Anführungszeichen würden die Suchabfrage des Skins zerbrechen
    term = term.replace('"', "").replace("\\", "")
    xbmc.executebuiltin('Skin.SetString({},"{}")'.format(SKIN_STRING, term))
