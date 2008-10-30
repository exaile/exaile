import _ecs as ecs
import urllib, md5
from xl.cover import *
from xl import common, event

AMAZON_KEY = "15VDQG80MCS2K1W2VRR2" # Adam Olsen's key
def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    exaile.covers.add_search_method(
        AmazonCoverSearch(AMAZON_KEY) 
    )

def disable(exaile):
    exaile.covers.remove_search_method_by_name('amazon')

class AmazonCoverSearch(CoverSearchMethod):
    """
        Searches amazon for an album cover
    """
    name = 'amazon'
    type = 'remote' # fetches remotely as opposed to locally
    def __init__(self, amazon_key):
        ecs.setLicenseKey(amazon_key)

    def find_covers(self, track, limit=-1):
        """
            Searches amazon for album covers
        """
        return self.search_covers("%s - %s" % 
            ('/'.join(track['artist']), '/'.join(track['album'])),
            limit)

    def search_covers(self, search, limit=-1):
        cache_dir = self.manager.cache_dir
        try:
            albums = ecs.ItemSearch(Keywords=search,
                SearchIndex="Music",
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
