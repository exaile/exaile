import mutagen.flac

TYPE = 'flac'

def get_tag(flac, tag):
    try:    
        return unicode(flac[tag][0])
    except KeyError:
        return ''

def fill_tag_from_path(tr):
    """
        Reads all tags from the file
    """
    f = mutagen.flac.FLAC(tr.io_loc)
    tr.length = int(f.info.length)

    tr.artist = get_tag(f, "artist")
    tr.album = get_tag(f, "album")
    tr.track = get_tag(f, "tracknumber")
    tr.disc_id = get_tag(f, 'tracktotal')
    tr.title = get_tag(f, "title")
    tr.genre = get_tag(f, "genre")
    tr.year = get_tag(f, "date")


def write_tag(tr):
    f = mutagen.flac.FLAC(tr.io_loc)
    if f.vc is None: f.add_vorbiscomment()
    del(f.vc[:])
    f.vc['artist'] = tr.artist
    f.vc['album'] = tr.album
    f.vc['title'] = tr.title
    f.vc['tracktotal'] = tr.disc_id
    f.vc['genre'] = tr.genre
    f.vc['tracknumber'] = str(tr.track)
    f.vc['date'] = str(tr.year)
    f.save()
