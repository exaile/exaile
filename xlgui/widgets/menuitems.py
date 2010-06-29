# Copyright (C) 2008-2010 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

"""
    Collection of useful stock MenuItems for use with xlgui.widgets.menu
"""

# TODO: how should we document standardization of context's
# selected-(items|tracks) ?

from xl.nls import gettext as _
from xl import event, settings, trax

from xlgui.widgets import rating
from xlgui.widgets.menu import MenuItem, simple_menu_item


### TRACKS ITEMS ###
# These items act on a set of Tracks, by default 'selected-tracks' from
# the parent's context, but custom accessors are allowed via the
# get_tracks_func kwarg

def generic_get_tracks_func(parent_obj, parent_context):
    return parent_context.get('selected-tracks', [])

class RatingMenuItem(MenuItem):
    """
        A menu item displaying rating images
        and allowing for selection of ratings
    """
    def __init__(self, name, after, get_tracks_func=generic_get_tracks_func):
        MenuItem.__init__(self, name, self.factory, after)
        self.get_tracks_func = get_tracks_func

    def factory(self, menu, parent_obj, parent_context):
        item = rating.RatingMenuItem(auto_update=False)
        item.connect('show', self.on_show, menu, parent_obj, parent_context)
        self._rating_changed_id = item.connect('rating-changed',
            self.on_rating_changed, menu, parent_obj, parent_context)

        return item

    def on_show(self, widget, menu, parent_obj, context):
        """
            Updates the menu item on show
        """
        widget.disconnect(self._rating_changed_id)
        tracks = self.get_tracks_func(parent_obj, context)
        rating = trax.util.get_rating_from_tracks(tracks)
        widget.props.rating = rating
        self._rating_changed_id = widget.connect('rating-changed',
            self.on_rating_changed, menu, parent_obj, context)

    def on_rating_changed(self, widget, rating, menu, parent_obj, context):
        """
            Passes the 'rating-changed' signal
        """
        tracks = self.get_tracks_func(parent_obj, context)

        for track in tracks:
            track.set_rating(rating)

        maximum = settings.get_option('rating/maximum', 5)
        event.log_event('rating_changed', self, rating / maximum * 100)

def _enqueue_cb(widget, name, parent, context, get_tracks_func):
    from xlgui import actions
    tracks = get_tracks_func(parent, context)
    actions.playback.enqueue(tracks)

def EnqueueMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return simple_menu_item(name, after, _("Enqueue"), 'gtk-add',
            _enqueue_cb, callback_args=[get_tracks_func])

### END TRACKS ITEMS ###
