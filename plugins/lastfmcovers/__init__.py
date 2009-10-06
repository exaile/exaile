import hashlib, re, urllib
from xl.cover import *
from xl import event

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    exaile.covers.add_search_method(LastFMCoverSearch())

def disable(exaile):
    exaile.covers.remove_search_method_by_name('lastfm')

class LastFMCoverSearch(CoverSearchMethod):
    """
        Searches Last.fm for covers
    """
    name = 'lastfm'
    type = 'remote' # fetches remotely as opposed to locally
    regex = re.compile(r'<coverart>.*?<large>(.*)</large>.*?</coverart>', 
        re.IGNORECASE|re.DOTALL)
    url = "http://ws.audioscrobbler.com/1.0/album/%(artist)s/%(album)s/info.xml"

    # List of SHA1 (hex) signatures of covers to be ignored. It can be 
    # replaced by a [frozen]set if the number of elements becomes large.
    black_list = ["57b2c37343f711c94e83a37bd91bc4d18d2ed9d5"]

    def find_covers(self, track, limit=-1):
        """
            Searches last.fm for album covers
        """
        cache_dir = self.manager.cache_dir
        if not track['artist'] or not track['album']:
            raise NoCoverFoundException()
        (artist, album) = track['artist'][0], track['album'][0]

        data = urllib.urlopen(self.url % 
        {
            'album': urllib.quote_plus(album.encode("utf-8")),
            'artist': urllib.quote_plus(artist.encode("utf-8"))
        }).read()

        m = self.regex.search(data)
        if not m:
            raise NoCoverFoundException()

        image = m.group(1)
        if image.lower().endswith('.gif'):
            raise NoCoverFoundException()

        h = urllib.urlopen(image)
        data = h.read()
        h.close()

        if hashlib.sha1(data).hexdigest() in self.black_list:
            raise NoCoverFoundException()

        covername = os.path.join(cache_dir, hashlib.md5(m.group(1)).hexdigest())
        covername += ".jpg"
        h = open(covername, 'wb')
        h.write(data)
        h.close()

        return [covername]
