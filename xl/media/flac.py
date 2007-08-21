import mutagen.flac
from xl import xlmisc

TYPE = 'flac'

VALID_TAGS = xlmisc.VALID_TAGS

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
    f = mutagen.flac.FLAC(tr.io_loc)
    tr.length = int(f.info.length)

    for tag in VALID_TAGS:
        tr.tags[tag] = get_tag(f, tag)

def can_change(tag):
    """
        Can the tag in question be used in this file format?
    """
    return tag in VALID_TAGS

def write_tag(tr):
    f = mutagen.flac.FLAC(tr.io_loc)
    if f.vc is None: f.add_vorbiscomment()
    del(f.vc[:])

    for tag in VALID_TAGS:
        if tr.tags[tag]:
            f.vc[tag] = tr.tags[tag]

    #f.vc['artist'] = tr.artist
    #f.vc['album'] = tr.album
    #f.vc['title'] = tr.title
    #f.vc['discnumber'] = tr.disc_id
    #f.vc['genre'] = tr.genre
    #f.vc['tracknumber'] = str(tr.track)
    #f.vc['date'] = str(tr.date)
    #f.vc['version'] = tr.version
    #f.vc['performer'] = tr.performer
    #f.vc['copyright'] = tr.copyright
    #f.vc['organization'] = tr.org
    #f.vc['isrc'] = tr.isrc

    f.save()
