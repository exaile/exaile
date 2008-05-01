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
        com = mutagen.oggvorbis.OggVorbis(tr.io_loc)
    except mutagen.oggvorbis.OggVorbisHeaderError:
        # FIXME: No use, this fails at the save() call.
        com = mutagen.oggvorbis.OggVorbis()
    com.clear()

    for tag in VALID_TAGS:
        if tr.tags[tag]:
            com[tag] = tr.tags[tag]
            
    com.save(tr.io_loc)

def can_change(tag):
    return tag in VALID_TAGS

def is_multi():
    return True

def fill_tag_from_path(tr):
    """
        Fills the passed in media.Track with tags from the file
    """
    try:
        f = mutagen.oggvorbis.OggVorbis(tr.io_loc)
    except mutagen.oggvorbis.OggVorbisHeaderError:
        return

    tr.length = int(f.info.length)
    
    tr.bitrate = (f.info.bitrate // 33554431) * 1000

    for tag in VALID_TAGS:
        tr.tags[tag] = get_tag(f, tag)
