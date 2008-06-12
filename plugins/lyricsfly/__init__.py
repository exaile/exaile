from xl.lyrics import LyricSearchMethod
from xl.lyrics import LyricsNotFoundException

try:
    import xml.etree.cElementTree as cETree
except:
    import cElementTree as cETree

import urllib

search_method = None
# lyricsfly does weekly license keys for software in dev.
# for permintent key please see
# http://lyricsfly.com/api/
license_key = "4a4bf5d237cfac72b"

def enable(exaile):
    """
        Enables the lyric wiki plugin that fetches track lyrics
        from lyricwiki.org
    """
    search_method = LyricsFly()
    exaile.lyrics.add_search_method(search_method)


def disable(exaile):
    if search_method:
        exaile.lyrics.remove_search_method(search_method)

class LyricsFly(LyricSearchMethod):
    
    name= "lyricsfly"
    def find_lyrics(self, track):
        search = "http://lyricsfly.com/api/api.php?i=%s&a=%s&t=%s" % (
            urllib.quote_plus(license_key),
            urllib.quote_plus(track["artist"]), 
            urllib.quote_plus(track["title"]))
        sock = urllib.urlopen(search)
        xml = sock.read()
        sock.close()
        try:
            # Lyrics fly uses xml so we must parse it
            (lyrics, url) = self.parse_xml(xml)
        except:
            raise LyricsNotFoundException
        if lyrics == "Not found":
            raise LyricsNotFoundException
        return (lyrics, "Lyrics Fly", url)

    def parse_xml(self, xml):
        """
            Parses the xml into the lyrics and the URL
        """
        start = cETree.XML(xml)
        sg = start.find("sg")
        #TODO determine whether we found a song or not
        if sg.text == None:
            lyrics = sg.find("tx").text
            cs = sg.find("cs").text
            id = sg.find("id")
            url = "http://lyricsfly.com/search/view.php?%s&view=%s" % (
                urllib.quote_plus(cs),
                urllib.quote_plus(id)) 
            return (lyrics, url)
        else:
            raise LyricsNotFoundException