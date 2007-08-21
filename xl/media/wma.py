import lib.wmainfo

TYPE = 'wma'

TAG_TRANSLATION = {
    "Author":       "artist",
    "AlbumTitle":   "album",
    "Title":        "title",
    "Genre":        "genre",
    "TrackNumber":  "tracknumber",
    "Year":         "date"
}

def get_tag(inf, name):
    if inf.tags.has_key(name):
        return [inf.tags[name]]
    else:
        return []

def can_change(tag):
    return False

def is_multi():
    # FIXME: is this true?
    return False

def fill_tag_from_path(tr):
    inf = lib.wmainfo.WmaInfo(tr.io_loc)

    tr.length = inf.info["playtime_seconds"]
    tr.bitrate = inf.info["max_bitrate"]

    for wma_tag, tag in TAG_TRANSLATION:
        tr.tags[tag] = get_tag(inf, wma_tag)

