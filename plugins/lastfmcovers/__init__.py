import md5, re, urllib
from xl.cover import *

def enable(exaile):
    exaile.covers.add_search_method(LastFMCoverSearch())

def disable(exaile):
    exaile.covers.remove_search_method('lastfm')

class LastFMCoverSearch(CoverSearchMethod):
    """
        Searches Last.FM for album art
    """
    name = 'lastfm'
    regex = re.compile(r'<coverart>.*?medium>([^<]*)</medium>.*?</coverart>', 
        re.IGNORECASE|re.DOTALL)
    url = "http://ws.audioscrobbler.com/1.0/album/%(artist)s/%(album)s/info.xml"

    def find_covers(self, track, limit=-1):
        """
            Searches last.fm for album covers
        """
        cache_dir = self.manager.cache_dir

        data = urllib.urlopen(self.url % 
        {
            'album': track['album'],
            'artist': track['artist']
        }).read()

        m = self.regex.search(data)
        if not m:
            raise CoverNotFoundException()

        h = urllib.urlopen(m.group(1))
        data = h.read()
        h.close()

        covername = os.path.join(cache_dir, md5.new(m.group(1)).hexdigest())
        covername += ".jpg"
        h = open(covername, 'w')
        h.write(data)
        h.close()

        return [covername]
