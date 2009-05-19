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


name = 'Notify'
basedir = os.path.dirname(os.path.realpath(__file__))
glade = os.path.join(basedir, "notifyprefs_pane.glade")


class ResizeCovers(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notify/resize'


class AttachToTray(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/notify/attach_tray'


class BodyArtistAlbum(widgets.TextViewPrefsItem):
    default = _("by %(artist)s\nfrom <i>%(album)s</i>")
    name = 'plugin/notify/body_artistalbum'


class BodyArtist(widgets.TextViewPrefsItem):
    default = _("by %(artist)s")
    name = 'plugin/notify/body_artist'


class BodyAlbum(widgets.TextViewPrefsItem):
    default = _("by %(album)s")
    name = 'plugin/notify/body_album'


class Summary(widgets.TextViewPrefsItem):
    default = _("%(title)s")
    name = 'plugin/notify/summary'

