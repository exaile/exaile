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

import gtk, gio

from xl import common, player, trax
from xl.nls import gettext as _
from xlgui.widgets import rating, menu
from xlgui import properties

### TRACKS ITEMS ###
# These items act on a set of Tracks, by default 'selected-tracks' from
# the parent's context, but custom accessors are allowed via the
# get_tracks_func kwarg

def generic_get_tracks_func(parent_obj, parent_context):
    return parent_context.get('selected-tracks', [])

class RatingMenuItem(menu.MenuItem):
    """
        A menu item displaying rating images
        and allowing for selection of ratings
    """
    def __init__(self, name, after, get_tracks_func=generic_get_tracks_func):
        menu.MenuItem.__init__(self, name, self.factory, after)
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

def _enqueue_cb(widget, name, parent, context, get_tracks_func):
    tracks = get_tracks_func(parent, context)
    player.QUEUE.extend(tracks)
    if not player.PLAYER.current:
        player.QUEUE.play()

def EnqueueMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return menu.simple_menu_item(name, after, _("Enqueue"), gtk.STOCK_ADD,
            _enqueue_cb, callback_args=[get_tracks_func])

# TODO: move logic into (GUI?) playlist
def _append_cb(widget, name, parent, context, get_tracks_func, replace=False):
    from xlgui import main
    page = main.get_current_playlist()
    if not page:
        return
    pl = page.playlist
    if replace:
        pl.clear()
    offset = len(pl)
    tracks = get_tracks_func(parent, context)
    sort_by, reverse = page.view.get_sort_by()
    tracks = trax.sort_tracks(sort_by, tracks, reverse=reverse)
    pl.extend(tracks)
    if not player.PLAYER.current:
        pl.current_position = offset
        player.QUEUE.set_current_playlist(pl)
        player.QUEUE.play(track=pl.current)

def ReplaceCurrentMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return menu.simple_menu_item(name, after, _("Replace Current"), None,
            _append_cb, callback_args=[get_tracks_func, True])

def AppendMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return menu.simple_menu_item(name, after, _("Append to Current"),
            'gtk-add', _append_cb, callback_args=[get_tracks_func])

def _properties_cb(widget, name, parent, context, get_tracks_func, dialog_parent):
    tracks = get_tracks_func(parent, context)
    if tracks:
        dialog = properties.TrackPropertiesDialog(dialog_parent, tracks)

def PropertiesMenuItem(name, after, get_tracks_func=generic_get_tracks_func,
        dialog_parent=None):
    return menu.simple_menu_item(name, after, _("Properties"),
            'gtk-properties', _properties_cb,
            callback_args=[get_tracks_func, dialog_parent])


def _open_directory_cb(widget, name, parent, context, get_tracks_func):
    try:
        track = get_tracks_func(parent, context)[0]
    except IndexError:
        return
    common.open_file_directory(track.get_loc_for_io())

def OpenDirectoryMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return menu.simple_menu_item(name, after, _("Open Directory"),
            'gtk-open', _open_directory_cb, callback_args=[get_tracks_func])


def generic_delete_tracks_func(parent, context, tracks):
    for tr in tracks:
        f = gio.File(tr.get_loc_for_io())
        f.delete()

def _delete_tracks_cb(widget, name, parent, context,
        get_tracks_func, delete_tracks_func):
    dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=_("This will permanantly delete the selected "
                    "tracks from your disk, are you sure you wish to continue?")
                )
    res = dialog.run()
    if res == gtk.RESPONSE_YES:
        delete_tracks_func(parent, context, get_tracks_func(parent, context))
    dialog.destroy()


def DeleteTracksMenuItem(name, after, get_tracks_func=generic_get_tracks_func,
        delete_tracks_func=generic_delete_tracks_func):
    return menu.simple_menu_item(name, after, _("Delete Tracks From Storage"),
            'gtk-delete', _delete_tracks_cb,
            callback_args=[get_tracks_func, delete_tracks_func])

### END TRACKS ITEMS ###

