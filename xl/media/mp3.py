import mutagen, mutagen.id3, mutagen.mp3
from xl import xlmisc

IDS = { "TIT2": "title",
        "TPE1": "artist",
        "TALB": "album",
        "TRCK": "track",
        "TDRC": "year",
        "TCON": "genre"
        }

SDI = dict([(v, k) for k, v in IDS.iteritems()])

def get_tag(id3, t):
    """
        Reads a specific id3 tag from the file
    """
    if not id3.has_key(t): return ""
    text = unicode(id3[t])

    text = text.replace('\n', ' ').replace('\r', ' ')
    return text

def write_tag(tr):
    try:
        id3 = mutagen.id3.ID3(tr.loc)
    except mutagen.id3.ID3NoHeaderError:
        id3 = mutagen.id3.ID3()

    for key, id3name in SDI.items():
        id3.delall(id3name)

    for k, v in IDS.iteritems():
        if k == 'TRCK': continue

        try:
            frame = mutagen.id3.Frames[k](encoding=3,
                text = unicode(getattr(tr, v)))
            id3.loaded_frame(frame)
        except:
            xlmisc.log_exception()

        if tr.track > -1:
            track = str(tr.track)
            if tr.disc_id > -1:
                track = "%s/%s" % (track, tr.disc_id)

            frame = mutagen.id3.Frames['TRCK'](encoding=3,
                text=track)

            id3.loaded_frame(frame)

        id3.save(tr.loc)    

def fill_tag_from_path(tr):
    info = mutagen.mp3.MP3(tr.loc)
    tr.length = info.info.length
    tr.bitrate = info.info.bitrate

    try:    
        id3 = mutagen.id3.ID3(tr.loc)
        tr.title = get_tag(id3, 'TIT2')
        tr.artist = get_tag(id3, 'TPE1')
        tr.album = get_tag(id3, 'TALB')
        tr.genre = get_tag(id3, 'TCON')

        trackinfo = get_tag(id3, 'TRCK')
        if trackinfo.find('/') > -1:
            tr.track, tr.disc_id = trackinfo.split('/')

            try:
                tr.track = int(tr.track)
            except ValueError: tr.track = -1

            try:
                tr.disc_id = int(tr.disc_id)
            except ValueError: tr.disc_id = -1
        else:
            try:
                tr.track = int(trackinfo)
            except ValueError:
                tr.track = -1

        tr.year = get_tag(id3, 'TRDC')

    except OverflowError:
        pass
    except mutagen.id3.ID3NoHeaderError:
        pass
    except IOError:
        pass
    except:
        xlmisc.log_exception()
