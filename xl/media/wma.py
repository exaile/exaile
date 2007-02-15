import lib.wmainfo

def get_tag(inf, name):
    if inf.tags.has_key(name):
        return inf.tags[name]
    else:
        return ''

def fill_tag_from_path(tr):
    inf = lib.wmainfo.WmaInfo(tr.io_loc)

    tr.length = inf.info["playtime_seconds"]
    tr.bitrate = inf.info["max_bitrate"]
    tr.artist = get_tag(inf, 'Author')
    tr.album = get_tag(inf, 'AlbumTitle')
    tr.title = get_tag(inf, 'Title') 
    tr.genre = ""
    tr.track = get_tag(inf, 'TrackNumber')
    tr.year = get_tag(inf, 'Year')
