"""
    This module is a parser for audio CDs based on discid.
    It is compatible with both python-discid and python-libdiscid.
"""


try:  # allow both python-discid and python-libdiscid
    from libdiscid.compat import discid
except ImportError:
    import discid

from xl.trax import Track


def read_disc_id(device):
    try:  # retry with reduced features if it fails
        # Note: reading additional features like isrc will take some time.
        disc_id = discid.read(device, features=discid.FEATURES)
    except discid.DiscError:
        disc_id = discid.read(device)
    return disc_id

def parse_disc(disc_id, device):
    """
        Retrieves data from the disc using discid only.
        As a result, the data will only contain track numbers and lengths.
        
        @param device: Name of the CD device
        @return: An array of xl.trax.Track with minimal information
    """
    xl_tracks = []
    for discid_track in disc_id.tracks:
        track_uri = "cdda://%d/#%s" % (discid_track.number, device)
        track = Track(uri=track_uri, scan=False)
        
        track_number = '{0}/{1}'.format(discid_track.number, len(disc_id.tracks))
        track.set_tags(
            title="Track %d" % discid_track.number,
            tracknumber=track_number,
            __length=discid_track.seconds,
            musicbrainz_disc_id=disc_id.id,
            freedb_disc_id=disc_id.freedb_id,
        )

        if discid_track.isrc:
            track.set_tags(isrc=discid_track.isrc)

        if disc_id.mcn and '0000000000000' not in disc_id.mcn:
            track.set_tags(mcn=disc_id.mcn)
        xl_tracks.append(track)
    return xl_tracks
