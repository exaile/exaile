try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree
import urllib
from xl.dynamic import DynamicSource

def enable(exaile):
    exaile.dynamic.add_search_method(LastfmSource())

def disable(exaile):
    exaile.dynamic.remove_search_method('lastfm')


class LastfmSource(DynamicSource):
    name='lastfm'
    def __init__(self):
        DynamicSource.__init__(self)

    def get_results(self, artist):
        url = "http://ws.audioscrobbler.com/1.0/artist/%s/similar.xml"%urllib.quote(artist)
        try:
            f = urllib.urlopen(url)
        except:
            common.log_exception()
            return []
        try:
            tree = ETree.ElementTree(file=f)
        except SyntaxError:
            #XML syntax was bad, meaning artist not found
            return []
        artists = tree.findall('artist')
        retlist = []
        for ar in artists:
            name = ar.find('name').text
            match = float(ar.find('match').text)
            retlist.append((match, name))

        return retlist
