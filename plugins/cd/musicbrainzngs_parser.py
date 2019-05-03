'''
Created on 03.05.2019

@author: christian
'''




import musicbrainzngs


from xl import main
from xl.trax import Track


MUSICBRAINZNGS_INITIALIZED = False



def parse_disc_id(disc_id, device):
    if not MUSICBRAINZNGS_INITIALIZED:
        version = main.exaile().get_user_agent_for_musicbrainz()
        musicbrainzngs.set_useragent(*version)

    musicbrainz_data = musicbrainzngs.get_releases_by_discid(
        disc_id.id, toc=disc_id.toc_string, includes=["artists", "recordings"])
    
    if musicbrainz_data.get('disc'):  # preferred: good quality
        return __parse_musicbrainz_disc(musicbrainz_data['disc'], device)
    elif musicbrainz_data.get('cdstub'):  # not so nice
        raise NotImplementedError


def __parse_musicbrainz_disc(disc_data, device):
    # arbitrarily choose first release. There may be more!
    release = disc_data['release-list'][0]
    artist = release['artist-credit-phrase']
    album_title = release['title']
    date = release['date']
    if release['medium-count'] > 1 or release['medium-list'][0]['disc-count'] > 1:
        raise NotImplementedError
    track_list = release['medium-list'][0]['track-list']
    disc_number = '{0}/{1}'.format(
        release['medium-list'][0]['position'],
        1)  # TODO calculate disk number?
    
    track_count = release['medium-list'][0]['track-count']
    tracks = []
    for track_index in range(0, track_count):
        # TODO put this into a new musicbrainz parser in xl/metadata
        track_uri = "cdda://%d/#%s" % (track_index+1, device)
        track = Track(uri=track_uri, scan=False)
        track_number = '{0}/{1}'.format(
            track_list[track_index]['number'],  # TODO or position?
            release['medium-list'][0]['track-count'])
        track.set_tags(
            artist=artist,
            title=track_list[track_index]['recording']['title'],
            albumartist=artist,
            album=album_title,
            tracknumber=track_number,
            discnumber=disc_number,
            date=date,
            __length=int(track_list[track_index]['length']) / 1000,
            # or track_list[track_index]['recording']['length']
            # or track_list[track_index]['track_or_recording_length']
            # TODO Get more data with secondary query, e.g. genre ("tags")? 
            )
        tracks.append(track)
    
    return (tracks, album_title)
