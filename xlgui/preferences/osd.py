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

from xlgui.preferences import widgets
from xl import xdg
from xl.nls import gettext as _
from xlgui import osd

name = _('On Screen Display')
ui = xdg.get_data_path('ui', 'preferences', 'osd.ui')

def page_enter(preferences):
    global OSD
    OSD = osd.OSDWindow(draggable=True)
    OSD.show(None, timeout=0)

def page_leave(preferences):
    global OSD
    if OSD:
        OSD.destroy()
        OSD = None

def apply(preferences):
    preferences.main.main.osd.setup_osd()

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

class OsdPreference(widgets.CheckPreference, OSDItem):
    default = True
    name = 'osd/enabled'

class OsdProgressPreference(widgets.CheckPreference, OSDItem):
    default = True
    name = 'osd/show_progress'

class OsdDurationPreference(widgets.SpinPreference, OSDItem):
    default = 4000
    name = 'osd/duration'

class OsdTextFontPreference(widgets.FontButtonPreference, OSDItem):
    default = 'Sans 11'
    name = 'osd/text_font'

class OsdTextColorPreference(widgets.ColorButtonPreference, OSDItem):
    default = '#ffffff'
    name = 'osd/text_color'

class OsdBGColorPreference(widgets.ColorButtonPreference, OSDItem):
    default = '#567ea2'
    name = 'osd/bg_color'

class OsdOpacityPreference(widgets.SpinPreference, OSDItem):
    default = 75
    name = 'osd/opacity'

class OsdWidthPreference(widgets.IntPreference, OSDItem):
    default = 400
    name = 'osd/w'

class OsdHeightPreference(widgets.IntPreference, OSDItem):
    default = 95
    name = 'osd/h'

class OsdTextPreference(widgets.TextViewPreference, OSDItem):
    default = """<b>{title}</b>
{artist}
on {album} - {length}"""
    name = 'osd/display_text'
