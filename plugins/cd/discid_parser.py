'''
Created on 03.05.2019

@author: christian
'''



try:  # allow both python-discid and python-libdiscid
    from libdiscid.compat import discid
except ImportError:
    import discid

from xl.trax import Track



def parse_disc(device):
    disc_id = discid.read(device)
    
    xl_tracks = []
    for discid_track in disc_id.tracks:
        track_uri = "cdda://%d/#%s" % (discid_track.number, device)
        track = Track(uri=track_uri, scan=False)
        track.set_tags(
            title="Track %d" % discid_track.number,
            tracknumber=discid_track.number,
            __length=discid_track.seconds
        )
        xl_tracks.append(track)
    return xl_tracks
