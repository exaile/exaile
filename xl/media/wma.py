import lib.wmainfo
from xl import common
import logging

logger = loggin.getLogger(__name__)

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
    try:
        inf = lib.wmainfo.WmaInfo(tr.get_loc_for_io())
    except:
        logger.warning("Couldn't read tags from file: " + tr.get_loc_for_io())
        return

    tr['length'] = inf.info["playtime_seconds"]
    tr['bitrate'] = inf.info["max_bitrate"]

    for wma_tag, tag in TAG_TRANSLATION.iteritems():
        tr.tags[tag] = get_tag(inf, wma_tag)
# vim: et sts=4 sw=4

