from mutagen import id3
import traceback
"""
    In [27]: item = id['APIC:9eb3f9035a51833415404e5271a896d6.jpg']
In [32]: h = open('/home/synic/foo.jpg', 'w')
In [33]: h.write(item.data)
In [34]: h.close()
"""
from xl.cover import *
import os, os.path

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    exaile.covers.add_search_method(TagCoverSearch())

def disable(exaile):
    exaile.covers.remove_search_method_by_name('tagcover')

class TagCoverSearch(CoverSearchMethod):
    """
        Looks for album art in track tags
    """
    name = 'tagcover'
    type = 'local'

    def find_covers(self, track, limit=-1):
        """
            Searches track tags for album art
        """
        try:
            loc = track.get_loc()
        except AttributeError:
            raise NoCoverFoundException()

        (path, ext) = os.path.splitext(loc.lower())
        ext = ext[1:]

        if ext != 'mp3':
            # nothing but mp3 is supported at this time
            raise NoCoverFoundException()

        covers = []
        try:
            item = id3.ID3(loc)
            for value in item.values():
                if isinstance(value, id3.APIC):
                    covers.append(CoverData(value.data))
                    if limit != -1 and len(covers) >= limit:
                        return covers
        except:
            traceback.print_exc()

        if not covers:
            raise NoCoverFoundException()

        return covers
