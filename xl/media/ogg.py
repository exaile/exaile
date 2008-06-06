import mutagen.oggvorbis
from xl import common 

TYPE = 'ogg'
VALID_TAGS = common.VALID_TAGS

def get_tag(f, tag):
    """
        Gets a specific tag, or if the tag does not exist, it returns an empty
        list
    """
    try:
        return [unicode(t) for t in f[tag]]
    except:
        return [] 

def write_tag(tr):
    try:
        com = mutagen.oggvorbis.OggVorbis(tr.get_loc_for_io())
    except mutagen.oggvorbis.OggVorbisHeaderError:
        # FIXME: No use, this fails at the save() call.
        com = mutagen.oggvorbis.OggVorbis()
    com.clear()

    for tag in VALID_TAGS:
        if tr[tag]:
            com[tag] = tr[tag]
            
    com.save(tr.get_loc_for_io())

def can_change(tag):
    return tag in VALID_TAGS

def is_multi():
    return True

def fill_tag_from_path(tr):
    """
        Fills the passed in media.Track with tags from the file
    """
    try:
        f = mutagen.oggvorbis.OggVorbis(tr.get_loc_for_io())
    except mutagen.oggvorbis.OggVorbisHeaderError:
        return

    tr['length'] = int(f.info.length)
    
    tr['bitrate'] = (f.info.bitrate // 33554431) * 1000

    for tag in VALID_TAGS:
        tr[tag] = get_tag(f, tag)
