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
import gtk
import gobject
 
from xl import (
    event, 
    providers,
    settings
)

from xl.nls import gettext as _
from xlgui import guiutil
from xlgui.accelerators import Accelerator
from xlgui.widgets import menu, dialogs


plugin = None


def enable(exaile):
    '''Called on plugin enable'''
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)
        
def _enable(eventname, exaile, nothing):

    global plugin
    if plugin is None:
        plugin = BPMCounterPlugin()
    
    event.remove_callback(_enable, 'gui_loaded')
    
def disable(exaile):
    '''Called on plugin disable'''
    
    global plugin
    if plugin is not None:
        plugin.disable_plugin()
        plugin = None
   
    
class BPMCounterPlugin(object):
    """
        Implements logic for plugin
    """
    # Provider API requirement
    name = 'BPM'
    
    def __init__(self):
        providers.register('mainwindow-info-area-widget', self)
    
    def disable_plugin(self):
        """
            Called when the plugin is disabled
        """
        providers.unregister('mainwindow-info-area-widget', self)
        
    def create_widget(self, info_area):
        """
            mainwindow-info-area-widget provider API method
        """
        return BPMWidget(info_area.get_player())
        

class BPMWidget(gtk.Frame):

    def __init__(self, player):
        gtk.Frame.__init__(self, _('BPM Counter'))
        
        self.player = player
        self.taps = []
        
        # TODO: Add preferences to adjust these settings..
        
        # number of seconds to average taps over so it converges faster
        self.tap_history = settings.get_option('plugin/bpm/tap_history', 5.0)
        
        # if no tap received, then restart
        self.stale_time = settings.get_option('plugin/bpm/stale_period', 2.0)
        
        #info_label = gtk.Label(_('BPM Counter'))
        self.eventbox = gtk.EventBox()
        self.bpm_label = gtk.Label(_('Update'))
        self.apply_button = gtk.Button(_('Apply BPM'))
        
        vbox = gtk.VBox()
        w, h = self.bpm_label.size_request()
        self.eventbox.add(self.bpm_label)
        self.eventbox.props.can_focus = True
        vbox.pack_start(self.eventbox, False, False, padding=h/2) # add some space
        vbox.pack_start(self.apply_button, False, False)
        
        self.add(vbox)
        
        # attach events
        self.eventbox.connect('focus-out-event', self.on_focus_out)
        self.connect('destroy', self.on_destroy)
        self.connect('button-release-event', self.on_click )
        self.eventbox.connect('key-press-event', self.on_keydown )
        
        self.apply_button.connect('pressed', self.on_apply_button_pressed )
    
        # ok, register for some events
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
        
    @guiutil.idle_add()
    def playback_track_start(self, type, player, track):
        self.track = track
        self.bpm = self.track.get_tag_raw('bpm', True)
        self.taps = []
        
        self.update_ui(False)
    
    #
    # UI Events
    #
    
    def on_destroy(self, widget):
        # de-register the exaile events
        event.remove_callback(self.playback_track_start, 'playback_track_start', self.player)
    
    
    def on_apply_button_pressed(self, widget):
        self.set_bpm()
    
    
    def on_keydown(self, widget, event):
                
        if event.keyval == gtk.keysyms.Return:
            self.set_bpm()
            return False
                
        if widget == self.apply_button:
            return False
            
        if event.keyval == gtk.keysyms.Escape:
            self.taps = []
            
        self.add_bpm_tap()
        return True
    
    def on_click(self, widget, event):
        if widget == self.apply_button:
            return False
        
        self.eventbox.set_state(gtk.STATE_SELECTED)
        self.eventbox.grab_focus()
        
        self.add_bpm_tap()
        return True
        
    def on_focus_out(self, widget, event):
        self.eventbox.set_state(gtk.STATE_NORMAL)
        
            
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
        if self.track and self.bpm:
            
            msg = gtk.MessageDialog(self.get_toplevel(), gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
                _('Set BPM of %d on %s?') % (int(self.bpm), self.track.get_tag_display('title')))
            msg.set_default_response( gtk.RESPONSE_NO )
            result = msg.run()
            msg.destroy()
        
            if result == gtk.RESPONSE_YES:
                self.track.set_tag_raw('bpm', int(self.bpm))
                if not self.track.write_tags():
                    dialogs.error( None, "Error writing BPM to %s" % gobject.markup_escape_text(self.track.get_loc_for_io()) )
        
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
    
 
