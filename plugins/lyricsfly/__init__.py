from xl.lyrics import LyricSearchMethod
from xl.lyrics import LyricsNotFoundException
import cgi, re
from xl import event

try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree

import urllib

## Notice.  Please request your own key from lyricswiki.com/api.
## DO NOT USE THIS KEY FOR YOUR OWN SOFTWARE.
LYRICSFLY_KEY = "46102e76dde1a145b-exaile.org"

def enable(exaile):
    """
        Enables the lyric wiki plugin that fetches track lyrics
        from lyricwiki.org
    """
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    exaile.lyrics.add_search_method(LyricsFly())


def disable(exaile):
    exaile.lyrics.remove_search_method_by_name("lyricsfly")

def rep(m):
    """
        LyricsFly api says to replace all foreign and special characters with
        just %.  Yeah, doesn't make sense, but that's what it says
    """
    return re.sub(r"[^a-zA-Z _-]", '%', m).replace('%%', '%')

class LyricsFly(LyricSearchMethod):

    name= "lyricsfly"
    def find_lyrics(self, track):
        try:
            artist = track.get_tag_raw("artist")[0]
            title = track.get_tag_raw("title")[0]
        except TypeError:
            raise LyricsNotFoundException
        search = "http://lyricsfly.com/api/api.php?i=%s&a=%s&t=%s" % (
            LYRICSFLY_KEY, rep(artist), rep(title))
        try:
            xml = urllib.urlopen(search).read()
        except IOError:
            raise LyricsNotFoundException

        # Lyrics fly uses xml so we must parse it
        (lyrics, url) = self.parse_xml(xml)

        return (lyrics, "Lyrics Fly", url)

    def parse_xml(self, xml):
        """
            Parses the xml into the lyrics and the URL
        """
        start = ETree.XML(xml)
        sg = start.find("sg")
        if sg:
            lyrics = sg.find("tx").text
            lyrics = lyrics.replace("[br]","")
            cs = sg.find("cs").text
            id = sg.find("id").text
            url = "http://lyricsfly.com/search/view.php?%s&view=%s" % (
                urllib.quote_plus(cs),
                urllib.quote_plus(id))
            return (lyrics, url)
        else:
            raise LyricsNotFoundException
