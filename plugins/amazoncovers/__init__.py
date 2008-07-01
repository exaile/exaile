import _ecs as ecs
import urllib, md5
from xl.cover import *
from xl import common

AMAZON_KEY = "15VDQG80MCS2K1W2VRR2" # Adam Olsen's key
def enable(exaile):
    exaile.covers.add_search_method(
        AmazonCoverSearch(AMAZON_KEY) 
    )

def disable(exaile):
    exaile.covers.remove_search_method('amazon')

class AmazonCoverSearch(CoverSearchMethod):
    """
        Searches amazon for an album cover
    """
    name = 'amazon'
    def __init__(self, amazon_key):
        ecs.setLicenseKey(amazon_key)

    def find_covers(self, track, limit=-1):
        """
            Searches amazon for album covers
        """
        cache_dir = self.manager.cache_dir
        try:
            albums = ecs.ItemSearch(Keywords="%s - %s" %
                (track['artist'], track['album']), SearchIndex="Music",
                ResponseGroup="ItemAttributes,Images")
        except ecs.NoExactMatches:
            raise NoCoverFoundException()

        covers = []
        for album in albums:
            try:
                h = urllib.urlopen(album.LargeImage.URL)
                data = h.read()
                h.close()

                covername = os.path.join(cache_dir,
                    md5.new(album.LargeImage.URL).hexdigest())
                covername += ".jpg"
                h = open(covername, 'w')
                h.write(data)
                h.close()

                covers.append(covername)
                if limit != -1 and len(covers) == limit:
                    return covers
            except AttributeError: continue
            except:
                traceback.print_exc()
                common.log_exception()

        if not covers:
            raise NoCoverFoundException()

        return covers
