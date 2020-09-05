# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import logging
import time

from xl import common, covers, event, providers, settings

from . import _ecs as ecs
from . import amazonprefs

logger = logging.getLogger(__name__)

AMAZON = None
USER_AGENT = None


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, nothing):
    global AMAZON, USER_AGENT
    USER_AGENT = exaile.get_user_agent_string('amazoncovers')
    AMAZON = AmazonCoverSearch()
    providers.register('covers', AMAZON)


def disable(exaile):
    providers.unregister('covers', AMAZON)


def get_preferences_pane():
    return amazonprefs


class AmazonCoverSearch(covers.CoverSearchMethod):
    """
    Searches amazon for an album cover
    """

    name = 'amazon'
    title = 'Amazon'

    def __init__(self):
        self.starttime = 0

    def find_covers(self, track, limit=-1):
        """
        Searches amazon for album covers
        """
        try:
            artist = track.get_tag_raw('artist')[0]
            album = track.get_tag_raw('album')[0]
        except (AttributeError, TypeError):
            return []

        # get the settings for amazon key and secret key
        api_key = settings.get_option('plugin/amazoncovers/api_key', '')
        secret_key = settings.get_option('plugin/amazoncovers/secret_key', '')
        if not api_key or not secret_key:
            logger.warning(
                'Please enter your Amazon API and secret '
                'keys in the Amazon Covers preferences'
            )
            return []

        # wait at least 1 second until the next attempt
        waittime = 1 - (time.time() - self.starttime)
        if waittime > 0:
            time.sleep(waittime)
        self.starttime = time.time()

        search = "%s - %s" % (artist, album)
        try:
            albums = ecs.search_covers(search, api_key, secret_key, USER_AGENT)
        except ecs.AmazonSearchError:
            return []
        return albums

    def get_cover_data(self, url):
        return common.get_url_contents(url, USER_AGENT)
