import mutagen.flac
from xl import common

TYPE = 'flac'

VALID_TAGS = common.VALID_TAGS

def get_tag(flac, tag):
    try:    
        return [unicode(t) for t in flac[tag]]
    except KeyError:
        return [] 

def is_multi():
    return True

def fill_tag_from_path(tr):
    """
        Reads all tags from the file
    """
    try:
        f = mutagen.flac.FLAC(tr.get_loc_for_io())
    except:
        common.log("Couldn't read tags from file: " + tr.get_loc())
        return
    tr.info['length'] = int(f.info.length)

    for tag in VALID_TAGS:
        tr[tag] = get_tag(f, tag)

def can_change(tag):
    """
        Can the tag in question be used in this file format?
    """
    return tag in VALID_TAGS

def write_tag(tr):
    f = mutagen.flac.FLAC(tr.get_loc_for_io())
    if f.vc is None: f.add_vorbiscomment()
    del(f.vc[:])

    for tag in VALID_TAGS:
        if tr.tags[tag]:
            f.vc[tag] = tr[tag]

    f.save()
