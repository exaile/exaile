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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import _ecs as ecs
import amazonprefs
import urllib, hashlib, time
from xl.cover import *
from xl import common, event, metadata, providers
from xl import settings
from xl.nls import gettext as _
import logging

logger = logging.getLogger(__name__)

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    providers.register('covers', AmazonCoverSearch())

def disable(exaile):
    providers.unregister('covers', AmazonCoverSearch())

def get_prefs_pane():
    return amazonprefs

joiner = lambda x: " ".join(x)

class AmazonCoverSearch(CoverSearchMethod):
    """
        Searches amazon for an album cover
    """
    name = 'amazon'
    def __init__(self):
        self.starttime = 0

    def find_covers(self, track, limit=-1):
        """
            Searches amazon for album covers
        """
        try:
            artist = track.get_tag_raw('artist')[0]
            album = track.get_tag_raw('album')[0]
        except AttributeError:
            pass
        return self.search_covers("%s - %s" %
            (artist, album), limit)

    def search_covers(self, search, limit=-1):

        # wait at least 1 second until the next attempt
        waittime = 1 - (time.time() - self.starttime)
        if waittime > 0: time.sleep(waittime)

        self.starttime = time.time()

        # get the settings for amazon key and secret key
        api_key = settings.get_option(
            'plugin/amazoncovers/api_key', '')
        secret_key = settings.get_option(
            'plugin/amazoncovers/secret_key', '')

        if not api_key or not secret_key:
            logger.warning('Please enter your Amazon API and secret '
                'keys in the Amazon Covers preferences')

        try:
            albums = ecs.search_covers(search, api_key, secret_key)
        except ecs.AmazonSearchError, e:
            return []
        return albums

    def get_cover_data(self, url):
        h = urllib.urlopen(url)
        data = h.read()
        h.close()
        return data
