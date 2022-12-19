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
    """
    I/O operation to read an ID from the disc.
    This must happen async because it may take quite some time.

    @param device: Name of the CD device
    @return: The disc ID as understood by musicbrainz and parse_disc()
    """
    try:  # retry with reduced features if it fails
        # Note: reading additional features like isrc will take some time.
        disc_id = discid.read(device, features=discid.FEATURES)
    except discid.DiscError:
        disc_id = discid.read(device)
    return disc_id


def parse_disc(disc_id, device):
    """
    Parses the given disc ID into tracks.
    As a result, the data will only contain track numbers and lengths but
    no sophisticated metadata.

    @param disc_id: The disc ID from read_disc_id()
    @param device: Name of the CD device
    @return: An array of xl.trax.Track with minimal information
    """
    xl_tracks = []
    disc_tags = dict()
    # The tag name is chosen for compatibility with the cover manager!
    disc_tags['musicbrainz_albumid'] = disc_id.id
    disc_tags['__freedb_disc_id'] = disc_id.freedb_id
    if disc_id.mcn and '0000000000000' not in disc_id.mcn:
        disc_tags['__mcn'] = disc_id.mcn

    for discid_track in disc_id.tracks:
        track_tags = disc_tags.copy()
        track_tags['tracknumber'] = '{0}/{1}'.format(
            discid_track.number, len(disc_id.tracks)
        )
        track_tags['title'] = "Track %d" % discid_track.number
        track_tags['__length'] = discid_track.seconds
        if discid_track.isrc:
            track_tags['isrc'] = discid_track.isrc

        track_uri = "cdda://%d/#%s" % (discid_track.number, device)
        track = Track(uri=track_uri, scan=False)
        track.set_tags(**track_tags)
        xl_tracks.append(track)
    return xl_tracks
