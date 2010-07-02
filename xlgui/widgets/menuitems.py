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

import gtk

from xl.nls import gettext as _
from xl import event, settings, trax, player, playlist

from xlgui.widgets import rating
from xlgui.widgets.menu import (
        radio_menu_item,
        simple_menu_item,
        simple_separator,
        MenuItem,
        Menu,
        ProviderMenu
    )


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
    tracks = get_tracks_func(parent, context)
    player.QUEUE.extend(tracks)

def EnqueueMenuItem(name, after, get_tracks_func=generic_get_tracks_func):
    return simple_menu_item(name, after, _("Enqueue"), 'gtk-add',
            _enqueue_cb, callback_args=[get_tracks_func])

### END TRACKS ITEMS ###

### PLAYBACK MENU ITEMS ###


# TODO: figure out somehwere more generic to put this
def _play_pause_cb(widget, name, parent_obj, parent_context):
    if player.PLAYER.get_state() in ('playing', 'paused'):
        player.PLAYER.toggle_pause()
    else:
        from xlgui import main
        page = main.get_current_playlist()
        if page:
            pl = page.playlist
            if len(pl) == 0:
                return
            try:
                idx = page.view.get_selected_paths()[0][0]
            except IndexError:
                idx = 0
            player.QUEUE.set_current_playlist(pl)
            pl.current_position = idx
            player.QUEUE.play(track=pl.current)


def PlayPauseMenuItem(name, after):
    def factory(menu, parent_obj, parent_context):
        if player.PLAYER.is_playing():
            icon = 'gtk-media-pause'
            display = _("Pause")
        else:
            icon = 'gtk-media-play-ltr'
            display = _("Play")
        item = gtk.ImageMenuItem(display)
        image = gtk.image_new_from_icon_name(icon,
                size=gtk.ICON_SIZE_MENU)
        item.set_image(image)
        item.connect('activate', _play_pause_cb, name, parent_obj, parent_context)
        return item
    return MenuItem(name, factory, after=after)

def _next_cb(widget, name, parent_obj, parent_context):
    player.QUEUE.next()

def NextMenuItem(name, after):
    return simple_menu_item(name, after, _("Next"),
            'gtk-media-next-ltr', _next_cb)

def _prev_cb(widget, name, parent_obj, parent_context):
    player.QUEUE.prev()

def PrevMenuItem(name, after):
    return simple_menu_item(name, after, _("Previous"),
            'gtk-media-previous-ltr', _prev_cb)

def _stop_cb(widget, name, parent_obj, parent_context):
    player.PLAYER.stop()

def StopMenuItem(name, after):
    return simple_menu_item(name, after, _("Stop"),
            'gtk-media-stop', _stop_cb)

### END PLAYBACK ###

### CURRENT PLAYLIST ITEMS ###

def default_get_playlist_func(parent, parent_context):
    return player.QUEUE.current_playlist

class ModesMenuItem(MenuItem):
    """
        A menu item having a submenu containing entries for shuffle modes.

        Defaults to adjusting the currently-playing playlist.
    """
    modetype = ''
    display_name = ""
    def __init__(self, name, after, get_playlist_func=default_get_playlist_func):
        MenuItem.__init__(self, name, None, after)
        self.get_playlist_func = get_playlist_func

    def factory(self, menu, parent_obj, parent_context):
        item = gtk.ImageMenuItem(self.display_name)
        image = gtk.image_new_from_icon_name('media-playlist-'+self.modetype,
                size=gtk.ICON_SIZE_MENU)
        item.set_image(image)
        submenu = self.create_mode_submenu(item)
        item.set_submenu(submenu)
        pl = self.get_playlist_func(parent_obj, parent_context)
        item.set_sensitive(pl != None)
        return item

    def create_mode_submenu(self, parent_item):
        names = getattr(playlist.Playlist, "%s_modes"%self.modetype)
        displays = getattr(playlist.Playlist, "%s_mode_names"%self.modetype)
        items = []
        previous = None
        for name, display in zip(names, displays):
            after = [previous] if previous else []
            item = radio_menu_item(name, after, display,
                    '%s_modes'%self.modetype, self.mode_is_selected,
                    self.on_mode_activated)
            items.append(item)
            if previous is None:
                items.append(simple_separator("sep", [items[-1].name]))
            previous = items[-1].name
        menu = Menu(parent_item)
        for item in items:
            menu.add_item(item)
        return menu

    def mode_is_selected(self, name, parent_obj, parent_context):
        pl = self.get_playlist_func(parent_obj, parent_context)
        if pl is None:
            return False
        return getattr(pl, "%s_mode"%self.modetype) == name

    def on_mode_activated(self, widget, name, parent_obj, parent_context):
        pl = self.get_playlist_func(parent_obj, parent_context)
        if pl is None:
            return False
        setattr(pl, "%s_mode"%self.modetype, name)

class ShuffleModesMenuItem(ModesMenuItem):
    modetype = 'shuffle'
    display_name = _("Shuffle")

class RepeatModesMenuItem(ModesMenuItem):
    modetype = 'repeat'
    display_name = _("Repeat")

class DynamicModesMenuItem(ModesMenuItem):
    modetype = 'dynamic'
    display_name = _("Dynamic")


### END PLAYLIST ###
