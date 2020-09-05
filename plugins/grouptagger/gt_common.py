# Copyright (C) 2011 Dustin Spicuzza
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

#
# Grouping field utility functions
#


from gi.repository import Gtk
from gi.repository import GObject

import re

from xl import playlist, settings

from xl.nls import gettext as _
from xl.trax import search

from xlgui import main
from xlgui.widgets import dialogs

from . import gt_widgets


group_categories_option = 'plugin/grouptagger/group_categories'
migrated_option = 'plugin/grouptagger/0.2_migration'
tagname_option = 'plugin/grouptagger/tagname'


def migrate_settings():
    '''Automatically migrate group tagger 0.1 settings to 0.2'''

    if settings.get_option(migrated_option, False):

        default_groups = settings.get_option('plugin/grouptagger/default_groups', None)
        if default_groups is not None:
            group_categories = {_('Uncategorized'): [True, default_groups]}
            set_group_categories(group_categories)
            # settings.remove_option( 'plugin/grouptagger/default_groups' )

        settings.set_option(migrated_option, True)


def get_tagname():
    return settings.get_option(tagname_option, 'grouping')


def get_track_groups(track):
    """
    Returns a set() of groups present in this track
    """
    return _get_track_groups(track, get_tagname())


def _get_track_groups(track, tagname):
    grouping = track.get_tag_raw(tagname, True)

    if grouping is not None:
        return {group.replace('_', ' ') for group in grouping.split()}

    return set()


def set_track_groups(track, groups):
    """
    Given an array of groups, sets them on a track

    Returns true if successful, false if there was an error
    """

    grouping = ' '.join(sorted('_'.join(group.split()) for group in groups))
    track.set_tag_raw(get_tagname(), grouping)

    if not track.write_tags():
        dialogs.error(
            None,
            "Error writing tags to %s"
            % GObject.markup_escape_text(track.get_loc_for_io()),
        )
        return False

    return True


def get_group_categories():
    """
    Returns a dictionary that contains a mapping of default groups
    to categories.

    Structure: { category: [expanded, [group, ... ]], ... }
    """

    return settings.get_option(group_categories_option, dict())


def get_groups_from_categories():

    groups = set()
    categories = get_group_categories()
    for category, (expanded, cgroups) in categories.items():
        for group in cgroups:
            groups.add(group)
    return groups


def set_group_categories(group_categories):
    """
    Set the mapping of default groups to categories
    """
    settings.set_option(group_categories_option, group_categories)


def get_all_collection_groups(collection):
    """
    For a given collection of tracks, return all groups
    used within that collection
    """
    groups = set()
    for track in collection:
        groups |= get_track_groups(track)

    return groups


def _create_search_playlist(name, search_string, exaile):
    '''Create a playlist based on a search string'''
    tracks = [
        x.track
        for x in search.search_tracks_from_string(exaile.collection, search_string)
    ]

    # create the playlist
    pl = playlist.Playlist(name, tracks)
    main.get_playlist_notebook().create_tab_from_playlist(pl)


def create_all_search_playlist(groups, exaile):
    '''Create a playlist of tracks that have all groups selected'''

    tagname = get_tagname()

    name = '%s: %s' % (tagname.title(), ' and '.join(groups))
    search_string = ' '.join(
        [
            '%s~"\\b%s\\b"' % (tagname, re.escape(group.replace(' ', '_')))
            for group in groups
        ]
    )

    _create_search_playlist(name, search_string, exaile)


def create_custom_search_playlist(groups, exaile):
    '''Create a playlist based on groups, and user input in a shiny dialog'''

    dialog = gt_widgets.GroupTaggerQueryDialog(groups)
    if dialog.run() == Gtk.ResponseType.OK:
        name, search_string = dialog.get_search_params()
        _create_search_playlist(name, search_string, exaile)

    dialog.destroy()
