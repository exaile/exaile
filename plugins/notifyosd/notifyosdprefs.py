# Copyright (C) 2009 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
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

import os
from xlgui.prefs import widgets
from xl import xdg
from xl.nls import gettext as _

name = _('Notify-osd notifications')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "notifyosdprefs_pane.ui")

class ShowCovers(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notifyosd/covers'

class NotifyPlay(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notifyosd/notify_play'

class NotifyPause(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notifyosd/notify_pause'

class UseMediaIcons(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notifyosd/media_icons'

class TrayHover(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/notifyosd/tray_hover'

class Summary(widgets.PrefsItem):
    default = _("%(title)s")
    name = 'plugin/notifyosd/summary'

class BodyArtist(widgets.PrefsItem):
    default = _("by %(artist)s")
    name = 'plugin/notifyosd/bodyartist'

class BodyAlbum(widgets.PrefsItem):
    default = _("from %(album)s")
    name = 'plugin/notifyosd/bodyalbum'

class ShowWhenFocused(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notifyosd/show_when_focused'
