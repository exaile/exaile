# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xlgui.prefs import widgets
from xl import xdg
from xlgui import osd

name = 'Notification'
glade = xdg.get_data_path('glade/osd_prefs_pane.glade')

def page_enter(prefs):
    global OSD
    OSD = osd.OSDWindow(draggable=True)
    OSD.show(None, timeout=0)

def page_leave(prefs):
    global OSD
    if OSD:
        OSD.destroy()
        OSD = None

def apply(prefs):
    prefs.main.main.osd.setup_osd()

class OSDItem(object):
    """
        This basically just assures that every single osd preference does the
        same thing: resets up the osd window
    """
    def change(self, *e):
        self.apply()
        if OSD:
            OSD.destroy()
            OSD.setup_osd()
            OSD.show(None, timeout=0)

class OsdPreference(widgets.CheckPrefsItem, OSDItem):
    default = True
    name = 'osd/enabled'

class OsdHoverTrayPreference(widgets.CheckPrefsItem, OSDItem):
    default = True
    name = 'osd/hover_tray'

class OsdProgressPreference(widgets.CheckPrefsItem, OSDItem):
    default = True
    name = 'osd/show_progress'

class OsdTextFontPreference(widgets.FontButtonPrefsItem, OSDItem):
    default = 'Sans 11'
    name = 'osd/text_font'

class OsdTextColorPreference(widgets.ColorButtonPrefsItem, OSDItem):
    default = '#ffffff'
    name = 'osd/text_color'

class OsdBGColorPreference(widgets.ColorButtonPrefsItem, OSDItem):
    default = '#567ea2'
    name = 'osd/bg_color'

class OsdOpacityPreference(widgets.SpinPrefsItem, OSDItem):
    default = 75
    name = 'osd/opacity'

class OsdWidthPreference(widgets.IntPrefsItem, OSDItem):
    default = 400
    name = 'osd/w'

class OsdHeightPreference(widgets.IntPrefsItem, OSDItem):
    default = 95
    name = 'osd/h'

class OsdTextPreference(widgets.TextViewPrefsItem, OSDItem):
    default = """<b>{title}</b>
{artist}
on {album} - {length}"""
    name = 'osd/display_text'
