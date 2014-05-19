# Copyright (C) 2014 Dustin Spicuzza
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

import gtk

from os.path import join, dirname

from xl.nls import gettext as _

from xlgui.guiutil import initialize_from_xml
from xlgui.widgets import dialogs

import gt_common

class GtMassRename(object):

    ui_filename = join(dirname(__file__), 'gt_mass.ui')
    
    ui_widgets = [
        'window',
        'found_label',
        'playlists',
        'replace',
        'replace_entry',
        'search_entry',
        'tracks_list'
    ]
    
    ui_signals = [
        'on_find_clicked',
        'on_replace_clicked'
    ]
    
    def __init__(self, exaile):
        
        self.exaile = exaile
        
        initialize_from_xml(self)
        
        self.tracks_list.get_model().set_sort_column_id(1, gtk.SORT_ASCENDING)
        
        # initialize playlist list
        model = self.playlists.get_model()
        
        for pl in exaile.smart_playlists.list_playlists():
            model.append((True, pl))
            
        for pl in exaile.playlists.list_playlists():
            model.append((False, pl))
        
        self.window.show_all()
        
    def reset(self):
        self.tracks_list.get_model().clear()
        self.replace.set_sensitive(False)

    def on_find_clicked(self, widget):
        
        self.search_str = self.search_entry.get_text().strip()
        self.replace_str = self.replace_entry.get_text().strip()
        self.tagname = gt_common.get_tagname()
        
        # freeze update
        model = self.tracks_list.get_model()
        self.tracks_list.freeze_child_notify()
        self.tracks_list.set_model(None)
            
        model.clear()
        
        idx = self.playlists.get_active() 
        if idx != -1 and (self.search_str != '' or self.replace_str != ''):
        
            smart, name = self.playlists.get_model()[idx]
            if smart:
                pl = self.exaile.smart_playlists.get_playlist(name)
            else:
                pl = self.exaile.playlists.get_playlist(name)
            
            if hasattr(pl, 'get_playlist'):
                pl = pl.get_playlist(self.exaile.collection)
                
            for track in pl:
                
                groups = gt_common._get_track_groups(track, self.tagname)
                
                if self.search_str != '' and self.search_str not in groups:
                    continue
                
                name = ' - '.join([ track.get_tag_display('artist'),
                                    track.get_tag_display('album'),
                                    track.get_tag_display('title')])
                model.append((True, name, track))
        
        # unfreeze, draw it up
        self.tracks_list.set_model(model)
        self.tracks_list.thaw_child_notify()
        
        self.found_label = _('%s tracks found') % len(model)
        
        self.replace.set_sensitive(len(model) != 0)
        
    def on_replace_clicked(self, widget):
        
        tracks = [row[2] for row in self.tracks_list.get_model() if row[1]]
        
        query = _("Replace '%s' with '%s' on %s tracks?") % (self.search_str, self.replace_str, len(tracks))
        if dialogs.yesno(self.window, query) != gtk.RESPONSE_YES:
            return 

        for track in tracks:
            
            groups = gt_common._get_track_groups(track, self.tagname)
            
            if self.search_str != '':
                groups.discard(self.search_str)
            
            if self.replace_str != '':
                groups.add(self.replace_str)
            
            if not gt_common.set_track_groups(track, groups):
                return
        
        dialogs.info(self.window, "Tags successfully renamed!")
        self.reset()

def mass_rename(exaile):
    
    if dialogs.yesno(None, _("You should rescan your collection before using mass tag rename to ensure that all tags are up to date. Rescan now?")) == gtk.RESPONSE_YES:
        exaile.gui.on_rescan_collection()
    
    GtMassRename(exaile)
