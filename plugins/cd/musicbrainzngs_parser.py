"""
    This module is a parser for audio CDs based on musicbrainzngs and discid.

    It uses the online database provided by musicbrainzngs.

    musicbrainz documentation:
    * Wiki: https://wiki.musicbrainz.org/
    * Web API: https://musicbrainz.org/doc/Development/XML%20Web%20Service/Version%202
    * Web API format: https://github.com/metabrainz/mmd-schema/blob/master/schema/musicbrainz_mmd-2.0.rng
    * Database schema: https://wiki.musicbrainz.org/MusicBrainz_Database/Schema

    musicbrainzngs documentation:
    * https://python-musicbrainzngs.readthedocs.io/

    Note: All the "priority" values are arbitrary/random choices and may need improvement

    TODO: Room for improvement:
    * fetch composers (especially interesting for classical music)
    * test text-representation for non-latin languages
    * get more data with secondary query, e.g. genre ("medium_tags")
        see https://wiki.musicbrainz.org/Genre
"""


from __future__ import division

import logging

import musicbrainzngs

from xl import main

from xl.covers import MANAGER as CoverManager


logger = logging.getLogger(__name__)


def fetch_with_disc_id(disc_id):
    """
    I/O operation to fetch data from musicbrainz over the internet.
    This must happen async because it may take quite some time.

    @param disc_id: A musicbrainz disc ID
    @return: Metadata for the parse() function
    """
    musicbrainzngs.set_useragent(
        'Exaile_Cd_Import', main.__version__, 'https://exaile.org/'
    )
    logger.debug('Querying Musicbrainz web servers with disc id %s', disc_id)
    try:
        musicbrainz_data = musicbrainzngs.get_releases_by_discid(
            disc_id.id,
            toc=disc_id.toc_string,
            includes=['artists', 'recordings', 'isrcs', 'artist-credits'],
        )
        logger.debug('Received data from musicbrainzngs')
    except musicbrainzngs.WebServiceError:
        # This is expected to fail if user is offline or behind an
        # aggressive firewall.
        logger.info('Failed to fetch data from musicbrainz database.', exc_info=True)
        musicbrainz_data = None
    return musicbrainz_data


def parse(musicbrainz_data, disc_id, tracks):
    """
    Parses the given musicbrainz data into existing tracks.
    This function must be run on the main thread because it modifies
    tracks, which may be in use by the main thread!

    @param musicbrainz_data: The data from fetch_with_disc_id()
    @param disc_id: The disc ID from read_disc_id()
    @param device: Name of the CD device
    @return: An array of xl.trax.Track with more information
    """
    # TODO: This parser is very slow, especially before creating tracks.
    # Put some of the parser (which does not modify tracks) into separate thread
    if musicbrainz_data is None:
        return None
    disc_tracks = None
    try:
        if musicbrainz_data.get('disc') is not None:  # preferred: good quality
            disc_tracks = __parse_musicbrainz_disc_data(
                musicbrainz_data['disc'], disc_id, tracks
            )
            if disc_tracks is not None:
                logger.debug('Parsed disc data: %s', disc_tracks)
        if disc_tracks is None:
            if (
                musicbrainz_data.get('cdstub') is not None
            ):  # bad quality, use as fallback
                disc_tracks = __parse_musicbrainz_cdstub_data(
                    musicbrainz_data['cdstub'], tracks
                )
                if disc_tracks is not None:
                    logger.debug('Parsed cdstub data: %s', disc_tracks)
        if disc_tracks is None:
            logger.info('Musicbrainz returned no useful data: %s', musicbrainz_data)
    except Exception:
        logger.warn('Failed to parse data from musicbrainz database.', exc_info=True)
    return disc_tracks


def __parse_musicbrainz_cdstub_data(cdstub_data, tracks):
    """
    Parses cdstub data into xl.trax.Track
    See "def_cdstub"
    Unused: disambiguation, def_cdstub-attribute_extension, def_cdstub-element_extension
    """
    track_count = cdstub_data.get('track-count')
    if track_count is not None:
        if len(tracks) is not track_count:
            logger.debug(
                'Track count mismatch: real disc has %i, musicbrainz says %i. '
                'Ignoring all data.',
                len(tracks),
                track_count,
            )
            return None

    album_tags = dict()

    if cdstub_data.get('id') is not None:
        album_tags['__musicbrainz_cdstub_id'] = cdstub_data['id']

    album_title = cdstub_data['title']
    album_tags['album'] = album_title

    artist = cdstub_data.get('artist')
    if artist is not None:
        album_tags['albumartist'] = artist
        album_tags['artist'] = artist

    barcode = cdstub_data.get('barcode')
    if barcode is not None:
        album_tags['barcode'] = barcode

    track_list = cdstub_data.get('track-list')
    if track_list is not None:
        for i in range(0, len(tracks)):
            # See "def_nonmb-track"
            # unused: length
            track = tracks[i]
            track_tags = album_tags.copy()
            track_tags['title'] = track_list[i]['title']

            track_artist = track_list[i].get('artist')
            if track_artist is not None:
                track_tags['artist'] = track_artist

            track.set_tags(**track_tags)
    return tracks, album_title


def __parse_musicbrainz_disc_data(disc_data, disc_id, tracks):
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
    return __parse_medium_from_disc_data(release, medium, tracks)


def __choose_release_and_medium(suitable_releases):
    """
    find the most suitable release
    """
    chosen_prio = -10  # this is a threshold
    chosen_release = None
    chosen_release_media = None
    for prio, release_media, release in suitable_releases:
        if prio > chosen_prio:
            chosen_prio = prio
            chosen_release_media = release_media
            chosen_release = release

    # find the most suitable medium
    chosen_prio = -50  # this is a threshold
    chosen_medium = None
    for prio, medium in chosen_release_media:
        if prio > chosen_prio:
            chosen_prio = prio
            chosen_medium = medium

    return (chosen_release, chosen_medium)


def __check_single_release(single_release, disc_id):
    """
    Documentation: https://wiki.musicbrainz.org/Recording
    """

    priority = 0
    # See https://wiki.musicbrainz.org/Barcode
    mb_barcode = single_release.get('barcode')
    if mb_barcode is not None and disc_id.mcn is not None:
        mb_barcode = mb_barcode.lstrip('0')
        disc_barcode = disc_id.mcn.lstrip('0')

        if len(disc_barcode) > 5:  # empty string indicates missing barcode
            if mb_barcode == disc_barcode:
                logger.debug('Found exact barcode match: %s', disc_barcode)
                priority = 100
            else:  # could be a different barcode format or a weak match
                logger.debug(
                    'Barcode mismatch: real disc has %s, musicbrainz says %s.',
                    disc_barcode,
                    mb_barcode,
                )
                priority = -19

    medium_list = single_release.get('medium-list')
    if medium_list is None:
        logger.debug('Release contains no `medium-list`. This sounds fishy, ignoring.')
        return None

    suitable_media = []
    for single_medium in medium_list:
        medium_priority = __check_single_medium(single_medium, disc_id)
        if medium_priority is not None:
            suitable_media.append((medium_priority, single_medium))
            priority = priority + medium_priority / 20

    if len(suitable_media) == 0:
        return None
    else:
        return (priority, suitable_media, single_release)


def __check_single_medium(single_medium, disc_id):
    """
    Documentation: https://wiki.musicbrainz.org/Medium
    """
    priority = 0
    mb_format = single_medium.get('format')
    if mb_format is not None:
        if not mb_format == 'CD':
            logger.debug(
                'Medium format mismatch: real disc is CD, musicbrainz says %s. Ignoring.',
                mb_format,
            )
            return None
        priority = priority + 7

    track_count = single_medium.get('track-count')
    if track_count is not None:
        if not track_count == len(disc_id.tracks):
            logger.debug(
                'Track count mismatch: real disc has %i, musicbrainz says %i. Ignoring.',
                len(disc_id.tracks),
                track_count,
            )
            return None
        priority = priority + 2

    track_list = single_medium.get('track-list')
    if track_list is None:
        logger.debug('Medium contains no `track-list`. This sounds fishy, ignoring.')
    if not len(track_list) == len(disc_id.tracks):
        logger.debug(
            'Track number mismatch: real disc has %i, musicbrainz says %i. Ignoring.',
            len(disc_id.tracks),
            track_list,
        )
        return None

    # disc-list does not seem to contain important information.

    priority = 0
    for i in range(0, len(track_list)):
        single_mb_track = track_list[i]
        single_disc_track = disc_id.tracks[i]
        track_prio = __check_single_track(single_mb_track, single_disc_track)
        if not track_prio:
            logger.debug('Track mismatch, ignoring this disk.')
            return None
        priority = priority + track_prio
    return priority


def __check_single_track(single_mb_track, single_disc_track):
    """
    See "def_track-data"
    """
    priority = 0

    # TODO: position or number?
    position = single_mb_track.get('position')
    if position is not None:
        mb_position = int(position)
        if mb_position == single_disc_track.number:
            priority = priority + 9
        else:
            logger.info(
                'Track position mismatch: real disc has %i, musicbrainz says %i.',
                single_disc_track.number,
                mb_position,
            )
            return None

    if single_mb_track.get('number') is not None:
        mb_number = int(single_mb_track['number'])
        if mb_number == single_disc_track.number:
            priority = priority + 9
        else:
            logger.info(
                'Track number mismatch: real disc has %i, musicbrainz says %i.',
                single_disc_track.number,
                mb_number,
            )
            return None

    # compare length
    if single_mb_track.get('length') is not None:
        mb_length_ms = int(single_mb_track['length'])
        real_length_ms = single_disc_track.sectors * 1000 / 75
        len_diff = abs(real_length_ms - mb_length_ms)
        if len_diff > 10000:  # up to 5 seconds fade in / fade out time at start and end
            logger.debug(
                'Massive track length mismatch: real disc has %ims, musicbrainz says %ims.',
                real_length_ms,
                mb_length_ms,
            )
            return None
        elif len_diff < 20:  # sector length = 1000ms/75 = (13+1/3)ms
            priority = priority + 50  # priority bonus for "exact" length match
        else:
            priority = priority - len_diff / 100
            logger.debug(
                'Slight track length mismatch: real disc has %i, musicbrainz says %i.',
                real_length_ms,
                mb_length_ms,
            )

    if single_mb_track.get('recording') is not None:
        resource_priority = __check_single_track_as_recording(
            single_mb_track.get('recording'), single_disc_track
        )
        if resource_priority is None:
            return None
        else:
            priority = priority + resource_priority

    return priority


def __check_single_track_as_recording(mb_recording, disc_track):
    """
    See "def_recording-element"
    """

    priority = 0
    if hasattr(disc_track, 'isrc') and disc_track.isrc is not None:
        mb_isrc_list = mb_recording.get('isrc-list')
        if mb_isrc_list is not None:
            if disc_track.isrc in mb_isrc_list:
                priority = +1000
            else:
                priority = -100
    return priority


def __parse_medium_from_disc_data(release, medium, tracks):
    medium_tags = dict()

    disc_number = __get_disc_number(medium, release)
    if disc_number is not None:
        medium_tags['discnumber'] = disc_number

    if release.get('id') is not None:
        medium_tags['__release_id'] = release['id']

    if release.get('date') is not None:
        medium_tags['date'] = release['date']

    # TODO difference of medium.title vs. release.title?
    album_title = medium.get('title')
    if album_title is not None:
        medium_tags['album'] = album_title
    else:
        album_title = release.get('title')
        if album_title is not None:
            medium_tags['album'] = album_title

    artist = release.get('artist-credit-phrase')
    if artist is not None:
        medium_tags['albumartist'] = artist
        medium_tags['artist'] = artist

    if release.get('barcode') is not None:
        medium_tags['barcode'] = release.get('barcode')

    mb_tracks = medium['track-list']
    for track_index in range(0, len(mb_tracks)):
        __parse_track_from_disc_data(
            medium_tags.copy(), tracks[track_index], mb_tracks[track_index]
        )

    # needs the 'musicbrainz_albumid' tag to be set, thus this happens after writing track tags
    __get_cover_image(release, tracks)

    return (tracks, album_title)


def __get_cover_image(release, tracks):
    """
    Fetch a cover using musicbrainzcover's cover provider.
    Requires the 'musicbrainz_albumid' tag to be set on the tracks.

    Documentation:
    * https://musicbrainz.org/doc/Cover_Art_Archive/API
    """
    if release.get('id') is None:
        return None

    try:
        import plugins.musicbrainzcovers as musicbrainzcovers
    except ImportError:
        logger.warn('Cannot load musicbrainzcovers, will not fetch covers.')
        return None

    cover_searcher = musicbrainzcovers.MusicBrainzCoverSearch(main.exaile())
    cover_data = None
    for resolution in ['500', '1200', '250']:
        try:
            db_string = '%s:%s' % (release['id'], resolution)
            cover_data = cover_searcher.get_cover_data(db_string)
            break
        except Exception:
            logger.debug(
                'Cannot fetch cover for %s in resolution %s', release['id'], resolution
            )

    if cover_data is not None:
        for track in tracks:
            # TODO: This is a hack: set_cover() expects a db_string to start with this, but why?
            # We could use CoverManager.get_cover(track) but this does not work because
            # CoverManager.get_db_string(track) fails to get the right string.
            db_string = 'musicbrainz: '
            CoverManager.set_cover(track, db_string, cover_data)


def __parse_track_from_disc_data(track_tags, xl_track, mb_track):
    """
    See "def_track-data" in
    https://github.com/metabrainz/mmd-schema/blob/master/schema/musicbrainz_mmd-2.0.rng
    unused and populated from discid: position, number, length
    """
    if mb_track.get('id') is not None:
        track_tags['__musicbrainz_track_id'] = mb_track['id']

    if mb_track.get('title') is not None:
        track_tags['title'] = mb_track['title']

    track_artist = mb_track.get('artist-credit-phrase')
    if track_artist is not None:
        track_tags['artist'] = track_artist

    if mb_track.get('recording') is not None:
        mb_recording = mb_track['recording']
        # see "def_recording-element"
        # unused fields: length, annotation, disambiguation, ...

        recording_title = mb_recording.get('title')
        if recording_title is not None and track_tags.get('title') is None:
            track_tags['title'] = recording_title

    xl_track.set_tags(**track_tags)


def __get_disc_number(medium, release):
    """
    Helper function to extract disc number string, e.g. 1/2 for the first of 2 CDs
    """
    # We may also be able to use the 'disc-count' field of "medium"
    medium_position = medium.get('position')
    medium_count = release.get('medium-count')
    if medium_count is None:
        medium_count = len(release['medium-list'])
    if medium_position is not None:
        if medium_count is not None:
            return '{0}/{1}'.format(medium_position, medium_count)
        else:
            return medium_position
    elif medium_count is not None and medium_count == 1:
        return '1/1'
    return None
