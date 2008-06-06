import mutagen.wavpack

def get_tag(wv, tag):
    try:
        return unicode(wv[tag][0])
    except:
        return ""

def fill_tag_from_path(tr):
    """
        Reads all tags from the file
    """
    f = mutagen.wavpack.WavPack(tr.get_loc_for_io())

    tr['length'] = int(f.info.length)

    tr['artist'] = get_tag(f, "artist")
    tr['album'] = get_tag(f, "album")
    tr['title'] = get_tag(f, "title")
    tr['genre'] = get_tag(f, "genre")
    tr['year'] = get_tag(f, "year")
    track = get_tag(f, "track")
    
    if track.find('/') > -1:
        (tr['track'], tr['disc_id']) = get_tag(f, "track").split('/')
    else:
        tr['track'] = get_tag(f, "track")
        tr['disc_id'] = ""
    
def write_tag(tr):
    """
        Writes all tags to the file
    """
    f = mutagen.wavpack.WavPack(tr.get_loc_for_io())

    f['artist'] = tr['artist']
    f['album'] = tr['album']
    f['title'] = tr['title']
    f['genre'] = tr['genre']
    f['year'] = tr['year']

    if tr['disc_id']:
        f['track'] = str(tr['track']) + '/' + tr['disc_id']
    else:
        f['track'] = str(tr['track'])
    f.save()
