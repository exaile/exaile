# Copyright (C) 2017 Dustin Spicuzza
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import json
import time

from gi.repository import Gio

from xl.common import GioFileOutputStream
from xl.nls import gettext as _
from xl.trax import search

from xlgui.widgets import dialogs

from .gt_common import get_track_groups

import logging

logger = logging.getLogger(__name__)


def export_tags(exaile):
    """
    Exports all tags to a user specified JSON file
    """

    uri = dialogs.save(
        parent=exaile.gui.main.window,
        output_fname='tags.json',
        output_setting='plugin/grouptagger/export_dir',
        title=_('Export tags to JSON'),
        extensions={'.json': 'grouptagger JSON export'},
    )

    if uri is not None:

        # collect the data
        trackdata = {}
        for strack in search.search_tracks_from_string(exaile.collection, ''):
            track = strack.track
            tags = list(sorted(get_track_groups(track)))
            if tags:
                trackdata[track.get_loc_for_io()] = tags

        data = {
            '_meta': {
                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'exporter': 'Exaile/%s' % exaile.get_version(),
                'version': 1,
            },
            'tracks': trackdata,
        }

        # save it
        with GioFileOutputStream(Gio.File.new_for_uri(uri), 'w') as fp:
            json.dump(data, fp, sort_keys=True, indent=4, separators=(',', ': '))

        logger.info("Exported tags of %s tracks to %s", len(trackdata), uri)
