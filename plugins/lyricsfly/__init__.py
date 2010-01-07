from xl.lyrics import LyricSearchMethod
from xl.lyrics import LyricsNotFoundException
import cgi, re
from xl import event

try:
    import xml.etree.cElementTree as cETree
except:
    import xml.etree.ElementTree as cETree

import urllib

##
## Notice.  Please request your own key from lyricswiki.com/api.  DO NOT USE
## THIS KEY FOR YOUR OWN SOFTWARE.
##
## Yeah, key is encoded.  No, it's not a good way to protect it, but there's
## not really a great way to do it.
license_key = "AQLkZQWyAmMxMTHkLGR0AJVgMKuunJkyYz9lMj=="

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
            license_key.decode('rot13').decode('base64'),
            rep(artist), rep(title))
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
            # Take out the [br]
            lyrics = lyrics.replace("[br]","")
            return (lyrics, url)
        else:
            raise LyricsNotFoundException
