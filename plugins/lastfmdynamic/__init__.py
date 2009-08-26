# Copyright (C) 2009 Aren Olson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#
# The developers of the Exaile media player hereby grant permission 
# for non-GPL compatible GStreamer and Exaile plugins to be used and 
# distributed together with GStreamer and Exaile. This permission is 
# above and beyond the permissions granted by the GPL license by which 
# Exaile is covered. If you modify this code, you may extend this 
# exception to your version of the code, but you are not obligated to 
# do so. If you do not wish to do so, delete this exception statement 
# from your version.

try:
    import xml.etree.cElementTree as ETree
except:
    import xml.etree.ElementTree as ETree
import urllib
from xl.dynamic import DynamicSource
from xl import providers, common

LFMS = None

def enable(exaile):
    global LFMS
    LFMS = LastfmSource()
    providers.register("dynamic_playlists", LFMS)

def disable(exaile):
    global LFMS
    providers.unregister("dynamic_playlists", LFMS)
    LFMS = None


class LastfmSource(DynamicSource):
    name='lastfm'
    def __init__(self):
        DynamicSource.__init__(self)

    def get_results(self, artist):
        ar = urllib.quote(artist.encode('utf-8'))
        url = "http://ws.audioscrobbler.com/1.0/artist/%s/similar.xml"%ar
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
