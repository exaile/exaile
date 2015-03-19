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

"""
    Collection of useful stock MenuItems for use with xlgui.widgets.menu
"""

# TODO: how should we document standardization of context's
# selected-(items|tracks) ?

import gio, glib, gtk

from xl import common, player, playlist, settings, trax
from xl.nls import gettext as _
from xlgui.widgets import dialogs, rating, menu
from xlgui import properties

### TRACKS ITEMS ###
# These items act on a set of Tracks, by default 'selected-tracks' from
# the parent's context, but custom accessors are allowed via the
# get_tracks_func kwarg

def generic_get_playlist_func(parent, context):
    return context.get('selected-playlist', None)

def generic_get_tracks_func(parent, context):
    return context.get('selected-tracks', [])

class RatingMenuItem(menu.MenuItem):
    """
        A menu item displaying rating images
        and allowing for selection of ratings
    """
    def __init__(self, name, after, get_tracks_func=generic_get_tracks_func):
        menu.MenuItem.__init__(self, name, self.factory, after)
        self.get_tracks_func = get_tracks_func
        self.rating_set = False

    def factory(self, menu, parent, context):
        item = rating.RatingMenuItem()
        item.connect('show', self.on_show, menu, parent, context)
        self._rating_changed_id = item.connect('rating-changed',
            self.on_rating_changed, menu, parent, context)

        return item

    @common.threaded
    def on_show(self, widget, menu, parent, context):
        """
            Updates the menu item on show
        """
        tracks = self.get_tracks_func(parent, context)
        rating = trax.util.get_rating_from_tracks(tracks)
        widget.disconnect(self._rating_changed_id)
        widget.props.rating = rating
        self._rating_changed_id = widget.connect('rating-changed',
            self.on_rating_changed, menu, parent, context)

    def on_rating_changed(self, widget, rating, menu, parent, context):
        """
            Passes the 'rating-changed' signal
        """
        rating_set = True
        tracks = self.get_tracks_func(parent, context)
        for track in tracks:
            track.set_rating(rating)

def _enqueue_cb(widget, name, parent, context, get_tracks_func):
    tracks = get_tracks_func(parent, context)
    player.QUEUE.extend(tracks)

def EnqueueMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return menu.simple_menu_item(name, after, _("Enqueue"), gtk.STOCK_ADD,
            _enqueue_cb, callback_args=[get_tracks_func])

# TODO: move logic into (GUI?) playlist
def _append_cb(widget, name, parent, context, get_tracks_func, replace=False):
    from xlgui import main
    page = main.get_selected_playlist()
    if not page:
        return
    pl = page.playlist
    if replace:
        pl.clear()
    offset = len(pl)
    tracks = get_tracks_func(parent, context)
    sort_by, reverse = page.view.get_sort_by()
    tracks = trax.sort_tracks(sort_by, tracks, reverse=reverse,
        artist_compilations=True)
    pl.extend(tracks)
    if settings.get_option( 'playlist/append_menu_starts_playback', False ):
        if not player.PLAYER.current:
            page.view.play_track_at(offset, tracks[0])

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
    return menu.simple_menu_item(name, after, None,
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

def generic_trash_tracks_func(parent, context, tracks):
    for track in tracks:
        gfile = gio.File(track.get_loc_for_io())
        gfile.trash()

def generic_delete_tracks_func(parent, context, tracks):
    for track in tracks:
        gfile = gio.File(track.get_loc_for_io())
        gfile.delete()

def _on_trash_tracks(widget, name, parent, context,
                     get_tracks_func, trash_tracks_func, delete_tracks_func):

    tracks = get_tracks_func(parent, context)

    try:
        trash_tracks_func(parent, context, tracks)
    except glib.GError:
        dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
            message_format=_('The files cannot be moved to the Trash. '
                             'Delete them permanently from the disk?'))
        dialog.add_buttons(
            gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_DELETE, gtk.RESPONSE_OK)
        dialog.set_alternative_button_order((gtk.RESPONSE_OK, gtk.RESPONSE_CANCEL))

        if dialog.run() == gtk.RESPONSE_OK:
            delete_tracks_func(parent, context, tracks)

        dialog.destroy()

def TrashMenuItem(name, after, get_tracks_func=generic_get_tracks_func,
                  trash_tracks_func=generic_trash_tracks_func,
                  delete_tracks_func=generic_delete_tracks_func):
    return menu.simple_menu_item(name, after, _('Move to Trash'), 'user-trash',
        _on_trash_tracks, callback_args=[get_tracks_func,
            trash_tracks_func, delete_tracks_func])

class ShowCurrentTrackMenuItem(menu.MenuItem):
    """
        A menu item for jumping to the currently
        playing track (given a callback and accelerator)
    """
    def __init__(self, name, after, callback=None, callback_args=[], accelerator=None):
        def factory(container, parent, context):
            item = gtk.ImageMenuItem(_("_Show Playing Track"))
            image = gtk.image_new_from_icon_name('gtk-jump-to-ltr',
                    size=gtk.ICON_SIZE_MENU)
            item.set_image(image)

            if accelerator is not None:
                key, mods = gtk.accelerator_parse(accelerator)
                item.add_accelerator('activate', menu.FAKEACCELGROUP, key, mods,
                        gtk.ACCEL_VISIBLE)

            if callback is not None:
                item.connect('activate', callback, name, parent, context, *callback_args)

            from xl import player;
            item.set_sensitive(player.PLAYER.get_state()!='stopped')

            return item
        menu.MenuItem.__init__(self, name, factory, after)

### END TRACKS ITEMS ###

### PLAYLIST ITEMS ###
# These items act on a playlist, by default 'selected-playlist' from
# the parent's context, but custom accessors are allowed via the
# get_pl_func kwarg

def RenamePlaylistMenuItem(name, after, get_pl_func=generic_get_playlist_func):
    return menu.simple_menu_item(name, after, _('Rename'), 'gtk-edit',
                          lambda w, n, o, c: o.rename_playlist(get_pl_func(o, c)),
                          condition_fn=lambda n, p, c: not isinstance(c['selected-playlist'], playlist.SmartPlaylist))
    
def EditPlaylistMenuItem(name, after, get_pl_func=generic_get_playlist_func):
    return menu.simple_menu_item(name, after, _('Edit'), 'gtk-edit',
                          lambda w, n, o, c: o.edit_smart_playlist(get_pl_func(o, c)),
                          condition_fn=lambda n, p, c: isinstance(c['selected-playlist'], playlist.SmartPlaylist))

def ExportPlaylistMenuItem(name, after, get_pl_func=generic_get_playlist_func):
    return menu.simple_menu_item(name, after, _('Export Playlist'), 'gtk-save',
                          lambda w, n, o, c: dialogs.export_playlist_dialog(get_pl_func(o, c)))

def ExportPlaylistFilesMenuItem(name, after, get_pl_func=generic_get_playlist_func):
    return menu.simple_menu_item(name, after, _('Export Files'), 'gtk-save',
                          lambda w, n, o, c: dialogs.export_playlist_files(get_pl_func(o, c)))

def DeletePlaylistMenuItem(name, after, get_pl_func=generic_get_playlist_func):
    return menu.simple_menu_item(name, after, _('Delete Playlist'), 'gtk-delete',
                          lambda w, n, o, c: o.remove_playlist(get_pl_func(o, c)))
    

### END PLAYLIST ITEMS ###


