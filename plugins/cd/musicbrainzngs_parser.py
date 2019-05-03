"""
    This module is a parser for audio CDs based on musicbrainzngs and discid.
    
    It uses the online database provided by musicbrainzngs.
    
    musicbrainz documentation:
    * Web API: https://musicbrainz.org/doc/Development/XML%20Web%20Service/Version%202
    * Web API format: https://github.com/metabrainz/mmd-schema/blob/master/schema/musicbrainz_mmd-2.0.rng
    
    Note: All the "priority" values are arbitrary/random choices and may need improvement
"""


from __future__ import division

import logging

import musicbrainzngs

from xl import main
from xl.trax import Track
from plugins.cd import discid_parser


logger = logging.getLogger(__name__)


MUSICBRAINZNGS_INITIALIZED = False

# TODO which fields are optional?
# TODO test
# TODO adapt log levels


def fetch_with_disc_id(disc_id, device):
    global MUSICBRAINZNGS_INITIALIZED
    if not MUSICBRAINZNGS_INITIALIZED:
        version = main.exaile().get_user_agent_for_musicbrainz()
        musicbrainzngs.set_useragent(*version)
        MUSICBRAINZNGS_INITIALIZED = True

    musicbrainz_data = musicbrainzngs.get_releases_by_discid(
        disc_id.id, toc=disc_id.toc_string, includes=["artists", "recordings"])
    
    if musicbrainz_data.get('disc') is not None:  # preferred: good quality
        disc_tracks = __parse_musicbrainz_disc_data(musicbrainz_data['disc'], disc_id, device)
        if disc_tracks is not None:
            return disc_tracks

    if musicbrainz_data.get('cdstub') is not None:  # bad quality, use as fallback
        disc_tracks = __parse_musicbrainz_cdstub_data(musicbrainz_data['cdstub'], disc_id, device)
        if disc_tracks is not None:
            return disc_tracks
    
    # no useful data returned
    logger.info('Musicbrainz returned not useful data: %s', musicbrainz_data)
    return None


def __parse_musicbrainz_cdstub_data(cdstub_data, disc_id, device):
    # prepopulate from disc_id parser
    tracks = discid_parser.parse_disc(disc_id, device)
    
    if cdstub_data['track-count']:
        track_count = cdstub_data['track-count']
        if len(tracks) is not track_count:
            logger.info('Track count mismatch: real disc has %i, musicbrainz says %i. Ignoring all data.',
                  len(tracks), track_count)
            return None
    
    album_title = cdstub_data['title']
    
    artist = cdstub_data.get('artist')
    barcode = cdstub_data.get('barcode')
    
    track_list = cdstub_data.get('track-list')
    if track_list is not None:
        for i in range(0, len(tracks)):
            track = tracks[i]
            new_tags = dict()
            new_tags['album'] = album_title
            
            if barcode is not None:
                new_tags['barcode'] = barcode
                
            if artist is not None:
                new_tags['artist'] = artist
            track_title = track_list[i].get('title')
            if track_title is not None:
                new_tags['title'] = track_title
            
            if artist is not None:
                new_tags['artist'] = artist
                new_tags['albumartist'] = artist
            
            track.set_tags(**new_tags)
    return tracks, album_title


def __parse_musicbrainz_disc_data(disc_data, disc_id, device):
    
    # get list of potential candidates, throw away the rest
    release_list = disc_data['release-list']
    suitable_releases = []
    for single_release in release_list:
        release = __check_single_release(single_release, disc_id)
        if release is not None:
            suitable_releases.append(release)
    
    if len(suitable_releases) < 1:
        return None
    
    (release, medium) = __choose_release_and_medium(suitable_releases)
    
    return __parse_from_disc_data(release, medium, device, disc_id)


def __choose_release_and_medium(suitable_releases):
    # find the most suitable release
    chosen_prio = -10  # this is a threshold
    chosen_release = None
    chosen_release_media = None
    for (prio, release_media, release) in suitable_releases:
        if prio > chosen_prio:
            chosen_prio = prio
            chosen_release_media = release_media
            chosen_release = release
    
    # find the most suitable medium
    chosen_prio = -50  # this is a threshold
    chosen_medium = None
    for (prio, medium) in chosen_release_media:
        if prio > chosen_prio:
            chosen_prio = prio
            chosen_medium = medium
    
    return (chosen_release, chosen_medium)


def __check_single_release(single_release, disc_id):
    # https://wiki.musicbrainz.org/Recording
    
    priority = 0
    
    # See https://wiki.musicbrainz.org/Barcode
    if single_release.get('barcode') is not None and disc_id.mcn is not None:
        mb_barcode = single_release['barcode'].lstrip('0')
        disc_barcode = disc_id.mcn.lstrip('0')
        
        if len(disc_barcode) > 5:  # empty string indicates missing barcode
            if mb_barcode == disc_barcode:
                logger.info('Found exact barcode match: %s', disc_barcode)
                priority = 100
            else:  # could be a different barcode format or a weak match
                logger.info('Barcode mismatch: real disc has %s, musicbrainz says %s.',
                            disc_barcode, mb_barcode)
                priority = -19
    
    medium_list = single_release['medium-list']
    suitable_media = []
    for single_medium in medium_list:
        medium_priority = __check_single_medium(single_medium, disc_id)
        if medium_priority is not None:
            suitable_media.append((medium_priority, single_medium))
            priority = priority + medium_priority/20

    if len(suitable_media) == 0:
        return None
    else:
        return (priority, suitable_media, single_release)


def __check_single_medium(single_medium, disc_id):
    # https://wiki.musicbrainz.org/Medium
    priority = 0
    if single_medium.get('format') is not None:
        if not 'CD' == single_medium['format']:
            logger.info('Medium format mismatch: real disc is CD, musicbrainz says %s. Ignoring.',
                  single_medium['format'])
            return None
        priority = priority + 7
    
    if single_medium.get('track-count') is not None:
        if not single_medium['track-count'] == len(disc_id.tracks):
            logger.info('Track count mismatch: real disc has %i, musicbrainz says %i. Ignoring.',
                  len(disc_id.tracks), single_medium['track-count'])
            return None
        priority = priority + 2
    
    if not len(single_medium['track-list']) == len(disc_id.tracks):
        logger.info('Track number mismatch: real disc has %i, musicbrainz says %i. Ignoring.',
                  len(disc_id.tracks), single_medium['track-count'])
        return None

    # disc-list does not seem to contain important information.

    priority = 0
    for i in range(0, len(single_medium['track-list'])):
        single_mb_track = single_medium['track-list'][i]
        single_disc_track = disc_id.tracks[i]
        track_prio = __check_single_track(single_mb_track, single_disc_track)
        if not track_prio:
            logger.info('Track mismatch, ignoring this disk.')
            return None
        priority = priority + track_prio
    return priority


def __check_single_track(single_mb_track, single_disc_track):
    priority = 0
    
    # TODO: position or number?
    if single_mb_track.get('position') is not None:
        mb_position = int(single_mb_track['position'])
        if mb_position == single_disc_track.number:
            priority = priority + 9
        else:
            logger.info('Track position mismatch: real disc has %i, musicbrainz says %i.',
                        single_disc_track.number, mb_position)
            return None
    
    if single_mb_track.get('number') is not None:
        mb_number = int(single_mb_track['number'])
        if mb_number == single_disc_track.number:
            priority = priority + 9
        else:
            logger.info('Track number mismatch: real disc has %i, musicbrainz says %i.',
                        single_disc_track.number, mb_number)
            return None
    
    # compare length
    if single_mb_track.get('length') is not None:
        mb_length_ms = int(single_mb_track['length'])
        real_length_ms = single_disc_track.sectors * 1000 / 75
        len_diff = abs(real_length_ms - mb_length_ms)
        if len_diff > 10000:  # up to 5 seconds fade in / fade out time at start and end
            logger.info('Massive track length mismatch: real disc has %ims, musicbrainz says %ims.',
                        real_length_ms, mb_length_ms)
            return None
        elif len_diff < 20:  # sector length = 1000ms/75 = 13+1/3
            # exact track length match!
            priority = priority + 50
        else:
            print(len_diff)
            priority = priority - len_diff/100
            logger.info('Slight track length mismatch: real disc has %i, musicbrainz says %i.',
                        real_length_ms, mb_length_ms)
    
    # TODO read and compare isrc? Musicbrainz does not seem to support that.
    
    return priority


def __parse_from_disc_data(release, medium, device, disk_id):
    # prepopulate from disc_id parser
    tracks = discid_parser.parse_disc(disc_id, device)
    
    artist = release['artist-credit-phrase']
    album_title = release['title']
    date = release['date']
    track_list = medium['track-list']
    disc_number = '{0}/{1}'.format(medium['position'], 1)  # TODO calculate disc number?
    
    track_count = medium['track-count']
    for track_index in range(0, track_count):
        track = tracks[track_index]
        #track_number = '{0}/{1}'.format(
        #    track_list[track_index]['number'],  # TODO or position?
        #    medium['track-count'])
        track.set_tags(
            artist=artist,
            title=track_list[track_index]['recording']['title'],
            albumartist=artist,
            album=album_title,
            #tracknumber=track_number,
            discnumber=disc_number,
            date=date,
            #__length=int(track_list[track_index]['length']) / 1000,
            # or track_list[track_index]['recording']['length']
            # or track_list[track_index]['track_or_recording_length']
            # TODO Get more data with secondary query, e.g. genre ("tags")? 
            # https://wiki.musicbrainz.org/Genre
            )
        tracks.append(track)
    
    return (tracks, album_title)

