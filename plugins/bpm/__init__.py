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


import os
import time

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
 
from xl import (
    event, 
    providers,
    settings
)

from xl.nls import gettext as _
from xlgui.guiutil import idle_add, GtkTemplate
from xlgui.accelerators import Accelerator
from xlgui.widgets import menu, dialogs

import bpmdetect
autodetect_enabled = bpmdetect.autodetect_supported()

menu_providers = [
    'track-panel-menu',
    'playlist-context-menu',
]
    
class BPMCounterPlugin(object):
    """
        Implements logic for plugin
    """
    # Provider API requirement
    name = 'BPM'
    menuitem = None
    
    def enable(self, exaile):
        pass
    
    def on_gui_loaded(self):
        providers.register('mainwindow-info-area-widget', self)
        
        if autodetect_enabled:
            self.menuitem = menu.simple_menu_item('_bpm', ['enqueue'],
                _('Autodetect BPM'), callback=self.on_auto_menuitem,
                condition_fn=lambda n, p, c: not c['selection-empty'])
            
            for p in menu_providers:
                providers.register(p, self.menuitem)
    
    def disable(self, exaile):
        """
            Called when the plugin is disabled
        """
        providers.unregister('mainwindow-info-area-widget', self)
        
        if self.menuitem is not None:
            for p in menu_providers:
                providers.unregister(p, self.menuitem)
        
    def create_widget(self, info_area):
        """
            mainwindow-info-area-widget provider API method
        """
        return BPMWidget(info_area.get_player(), self)

    def on_auto_menuitem(self, menu, display_name, playlist_view, context):
        tracks = context['selected-tracks']
        if len(tracks) > 0:
            self.autodetect_bpm(tracks[0])
            
    def autodetect_bpm(self, track):
        
        def _on_complete(bpm, err):
            if err is not None:
                dialogs.error(None, err)
            else:
                self.set_bpm(track, bpm)
        
        bpmdetect.detect_bpm(track.get_loc_for_io(), _on_complete)
    
    def set_bpm(self, track, bpm):
        '''Make sure we don't accidentally set BPM on things'''
        
        if track and bpm:
            
            bpm = int(bpm)
            
            msg = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, 
                _('Set BPM of %d on %s?') % (bpm, track.get_tag_display('title')))
            msg.set_default_response(Gtk.ResponseType.NO)
            result = msg.run()
            msg.destroy()
        
            if result == Gtk.ResponseType.YES:
                track.set_tag_raw('bpm', bpm)
                if not track.write_tags():
                    dialogs.error(None, "Error writing BPM to %s" % GObject.markup_escape_text(track.get_loc_for_io()))

plugin_class = BPMCounterPlugin


@GtkTemplate('bpm.ui', relto=__file__)
class BPMWidget(Gtk.Frame):

    __gtype_name__ = 'BPMWidget'
    
    eventbox,       \
    bpm_label,      \
    apply_button    = GtkTemplate.Child.widgets(3)

    def __init__(self, player, plugin):
        Gtk.Frame.__init__(self, label=_('BPM Counter'))
        self.init_template()
        
        self.player = player
        self.plugin = plugin
        self.taps = []
        
        # TODO: Add preferences to adjust these settings..
        
        # number of seconds to average taps over so it converges faster
        self.tap_history = settings.get_option('plugin/bpm/tap_history', 5.0)
        
        # if no tap received, then restart
        self.stale_time = settings.get_option('plugin/bpm/stale_period', 2.0)
        
        # Autodetect plugin
        
        self.menu = None
        if autodetect_enabled:
            self.menu = menu.Menu(None)
            
            item = menu.simple_menu_item('_bpm', [], _('Autodetect BPM'),
                                         callback=self.on_auto_menuitem)
            self.menu.add_item(item)
        
        # Be notified when a new track is playing
        event.add_callback(self.playback_track_start, 'playback_track_start', self.player)
        
        # get the main exaile window, and dock our window next to it if possible
        
        # trigger start event if exaile is currently playing something
        if self.player.is_playing():
            self.playback_track_start(None, self.player, self.player.current)
        else:
            self.track = None
            self.bpm = None
            self.taps = []
            self.update_ui()
        
    #
    # Exaile events
    #
        
    @idle_add()
    def playback_track_start(self, type, player, track):
        self.track = track
        self.bpm = self.track.get_tag_raw('bpm', True)
        self.taps = []
        
        self.update_ui(False)
    
    #
    # UI Events
    #
    
    @GtkTemplate.Callback
    def on_destroy(self, widget):
        # de-register the exaile events
        event.remove_callback(self.playback_track_start, 'playback_track_start', self.player)
    
    @GtkTemplate.Callback
    def on_apply_button_clicked(self, widget):
        self.set_bpm()
        
    @GtkTemplate.Callback
    def on_eventbox_key_press_event(self, widget, event):
        
        if event.keyval == Gdk.KEY_Return:
            self.set_bpm()
            return False
             
        if widget == self.apply_button:
            return False
        
        if event.keyval == Gdk.KEY_Escape:
            self.taps = []
        
        self.add_bpm_tap()
        return True
    
    @GtkTemplate.Callback
    def on_eventbox_button_press_event(self, widget, event):
        
        if event.button == 3:
            if self.menu is not None and self.track is not None:
                self.menu.popup(event)
            return
        
        self.eventbox.set_state(Gtk.StateType.SELECTED)
        self.eventbox.grab_focus()
        
        self.add_bpm_tap()
        return True
    
    @GtkTemplate.Callback
    def on_eventbox_focus_out_event(self, widget, event):
        self.eventbox.set_state(Gtk.StateType.NORMAL)
    
    def on_auto_menuitem(self, *args):
        if self.track is not None:
            self.plugin.autodetect_bpm(self.track)
            
    #
    # BPM Logic
    #
        
    def add_bpm_tap(self):
        '''Recalculates the BPM each time an event occurs'''
        
        current = time.time()
        
        if len(self.taps) > 0:
            # reset counter if its stale
            if current - self.taps[-1] > self.stale_time:
                self.taps = []

        self.taps.append(current)
        self.trim_taps()
        
        if len(self.taps) > 1:
            self.bpm = str(int(round(((len(self.taps)-1) * 60.0) / ( self.taps[-1] - self.taps[0] ))))
        else:
            self.bpm = None
        
        self.update_ui()    
            
    def trim_taps(self):
        '''Remove old taps so the BPM value converges faster'''
        while len(self.taps) != 0 and self.taps[-1] - self.taps[0] > self.tap_history:
            self.taps.pop(0)
        
    def set_bpm(self):
        '''Make sure we don't accidentally set BPM on things'''
        self.plugin.set_bpm(self.track, self.bpm)
        self.update_ui()
    
    
    def update_ui(self, apply_enabled=True):
        '''Updates the current UI display'''
        
        if self.bpm is None:
            self.bpm_label.set_label(_('Update'))
            self.apply_button.set_sensitive(False)
        else:
            self.bpm_label.set_label(self.bpm)
            
            if self.track is not None:
                self.apply_button.set_sensitive(apply_enabled)
            else:
                self.apply_button.set_sensitive(False)
    
 
