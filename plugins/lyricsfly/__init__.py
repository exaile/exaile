try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree
import cgi
import htmlentitydefs
import re
import urllib

from xl.lyrics import (
    LyricSearchMethod,
    LyricsNotFoundException
)
from xl import event

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


# really kinda surprised there isn't a standard lib implementation of
# this. :/
def html_un_entity(text):
    """
        lyricsfly returns lyrics with special characters encoded at html entities, this
        replaces the entities with their normal forms.
    """
    splitted = text.split("&")
    res = []
    for item in splitted:
        try:
            encoded, rest = item.split(";")
        except ValueError: # no ;, so its not encoded
            res.append("&" + item)
            continue
        if encoded[0] == "#" and encoded[1:].isdigit(): # raw codepoint encoding
            char = unichr(int(encoded[1:]))
        else:
            if not encoded.isalnum(): # all entity defs are alphanumeric
                res.append("&" + item)
                continue
            else:
                try:
                    char = unichr(htmlentitydefs.name2codepoint[encoded])
                except KeyError: # not a known entity
                    res.append("&" + item)
                    continue
        res.append(char + rest)
    return u"".join(res)[1:] # remove stray & at start

class LyricsFly(LyricSearchMethod):

    name= "lyricsfly"
    display_name = "Lyrics Fly"
    
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
        try:
            (lyrics, url) = self.parse_xml(xml)
        except SyntaxError: #happens if it gives us something wierd, like a 403
            raise LyricsNotFoundException

        return (lyrics, self.name, url)

    def parse_xml(self, xml):
        """
            Parses the xml into the lyrics and the URL
        """
        start = ETree.XML(xml)
        sg = start.find("sg")
        if sg:
            lyrics = sg.find("tx").text
            lyrics = lyrics.replace("\n", "")
            lyrics = lyrics.replace("[br]","\n")
            lyrics = html_un_entity(lyrics)
            cs = sg.find("cs").text
            id = sg.find("id").text
            url = "http://lyricsfly.com/search/view.php?%s&view=%s" % (
                urllib.quote_plus(cs),
                urllib.quote_plus(id))
            return (lyrics, url)
        else:
            raise LyricsNotFoundException
