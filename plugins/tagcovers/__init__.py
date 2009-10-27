from mutagen import id3
import traceback, time
from xl.cover import *
import os, os.path, hashlib

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
        Looks for covers in track tags
    """
    name = 'tagcover'
    type = 'local'

    def find_covers(self, track, limit=-1):
        """
            Searches track tags for covers
        """
        cache_dir = self.manager.cache_dir
        try:
            loc = track.get_loc()
        except AttributeError:
            raise NoCoverFoundException()
        if loc.startswith("file://"):
            loc = loc[7:]

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
                    m = hashlib.sha1()
                    m.update(value.data)
                    covername = os.path.join(cache_dir, m.hexdigest())
                    covername += '.jpg'
                    h = open(covername, 'w')
                    h.write(value.data)
                    h.close()
                    covers.append(covername)
                    if limit != -1 and len(covers) >= limit:
                        return covers
        except:
            traceback.print_exc()

        if not covers:
            raise NoCoverFoundException()

        return covers

if __name__ == '__main__':
    from mutagen import id3
    from xl import cover, settings, xdg, settings

    settings = settings.SettingsManager(os.path.join(
        xdg.get_config_dir(), 'settings.ini'))

    from xl import collection
    collection = collection.Collection('Collection',
        os.path.join(xdg.get_data_dirs()[0], 'music.db'))
    covers = cover.CoverManager(settings, cache_dir=os.path.join(
        xdg.get_data_dirs()[0], 'covers'))

    tracks = collection.search('')
    for track in tracks:
        if not track.get_loc().endswith('.mp3'):
            continue

        try:
            try:
                c = covers.get_cover(track)
                if not c: continue
            except cover.NoCoverFoundException:
                continue

            a = id3.ID3(track.get_loc())
            done = False
            for v in a.values():
                if isinstance(v, id3.APIC):
                    if v.desc == '__exaile_cover__':
                        done = True
                        break
                    done = True
                    break
            if done: continue

            data = open(c).read()

            i = id3.APIC(type=3, desc='__exaile_cover__', data=data,
                encoding=3, mime='image/jpg')
            a.add(i)
            a.save()
        except:
            traceback.print_exc()

    covers.save_cover_db()

