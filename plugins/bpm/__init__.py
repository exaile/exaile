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


import os
import time
import gtk
import gobject
 
from xl import (
    event, 
    providers,
    player,
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
    plugin = BPMCounterPlugin(exaile)
    
def disable(exaile):
    '''Called on plugin disable'''
    
    global plugin
    if plugin is not None:
        plugin.disable_plugin()
        plugin = None
   
    
class BPMCounterPlugin(object):
    '''Implements logic for plugin'''

    def __init__(self, exaile):
    
        self.window = None
        self.taps = []
        
        self.MENU_ITEM = menu.simple_menu_item('bpm_counter', ['plugin-sep'], _('BPM Counter'),
            callback=lambda *x: self.enable(exaile))
        providers.register('menubar-tools-menu', self.MENU_ITEM)
        
        # TODO: Add preferences to adjust these settings..
        
        # number of seconds to average taps over so it converges faster
        self.tap_history = settings.get_option('plugin/bpm/tap_history', 5.0)
        
        # if no tap received, then restart
        self.stale_time = settings.get_option('plugin/bpm/stale_period', 2.0)
        
        self.accelerator = Accelerator('<Control>b', lambda *x: self.enable(exaile))
        providers.register('mainwindow-accelerators',self.accelerator)

        
        
    
    def disable_plugin(self):
        '''Called when the plugin is disabled'''
        
        if self.MENU_ITEM:
            providers.unregister('menubar-tools-menu', self.MENU_ITEM)
            self.MENU_ITEM = None
        
        if self.accelerator:
            providers.unregister('mainwindow-accelerator', self.accelerator)
        
        if self.window:
            self.window.hide()
            self.window.destroy()
        
    
    def enable(self, exaile):
        '''Called when the user selects the BPM counter from the menu'''
    
        if self.window is not None:
            self.window.present()
            return
    
        self.ui = gtk.Builder()
        self.ui.add_from_file(os.path.join( os.path.dirname(
                os.path.realpath(__file__)),'bpm.glade'))
        
        # get objects
        self.window = self.ui.get_object("BPMCounter")
        self.bpm_label = self.ui.get_object("bpm_label")
        self.apply_button = self.ui.get_object('apply_button')
        
        # attach events
        self.window.connect('destroy', self.on_destroy)
        self.window.connect('button-release-event', self.on_window_click )
        self.window.connect('key-press-event', self.on_window_keydown )
        
        self.apply_button.connect('pressed', self.on_apply_button_pressed )
    
        # ok, register for some events
        event.add_callback( self.playback_track_start, 'playback_track_start' )
        
        # get the main exaile window, and dock our window next to it if possible
        
        # trigger start event if exaile is currently playing something
        if player.PLAYER.is_playing():
            self.playback_track_start( None, player.PLAYER, player.PLAYER.current )
        else:
            self.track = None
            self.bpm = None
            self.taps = []
            self.update_ui()
        
        # and we're done
        self.window.show_all()
        
        
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
        
        if self.window is None:
            return
    
        # de-register the exaile events
        event.remove_callback( self.playback_track_start, 'playback_track_start' )
        
        # finish the GUI off
        self.window = None
    
    def on_apply_button_pressed(self, widget):
        self.set_bpm()
    
    
    def on_window_keydown(self, widget, event):
                
        if event.keyval == gtk.keysyms.Return:
            self.set_bpm()
            return False
                
        if widget == self.apply_button:
            return False
            
        self.add_bpm_tap()
        return True
    
    def on_window_click(self, widget, event):
        if widget == self.apply_button:
            return False
            
        self.add_bpm_tap()
        return True
        
            
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

        self.taps.append( current )
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
            
            msg = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
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
            self.bpm_label.set_label( '-' )
            self.apply_button.set_sensitive(False)
        else:
            self.bpm_label.set_label( self.bpm )
            
            if self.track is not None:
                self.apply_button.set_sensitive(apply_enabled)
                if apply_enabled:
                    self.window.set_default(self.apply_button)
            else:
                self.apply_button.set_sensitive(False)
    
 