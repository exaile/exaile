# Copyright (C) 2009-2010 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
# Copyright (C) 2017 Christian Stadelmann
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _('Notify')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "notifyprefs_pane.ui")


class ResizeCovers(widgets.CheckPreference, widgets.CheckConditional):
    default = False
    name = 'plugin/notify/resize'
    condition_preference_name = 'plugin/notify/show_covers'


class ShowCovers(widgets.CheckPreference):
    default = True
    name = 'plugin/notify/show_covers'
    pre_migration_name = 'plugin/notifyosd/covers'


class NotifyPause(widgets.CheckPreference):
    default = True
    name = 'plugin/notify/notify_pause'
    pre_migration_name = 'plugin/notifyosd/notify_pause'


class UseMediaIcons(widgets.CheckPreference):
    default = True
    name = 'plugin/notify/use_media_icons'
    pre_migration_name = 'plugin/notifyosd/media_icons'


class TrayHover(widgets.CheckPreference, widgets.CheckConditional):
    default = False
    name = 'plugin/notify/tray_hover'
    pre_migration_name = 'plugin/notifyosd/tray_hover'
    condition_preference_name = 'gui/use_tray'


class ShowWhenFocused(widgets.CheckPreference):
    default = False
    name = 'plugin/notify/show_when_focused'
    pre_migration_name = 'plugin/notifyosd/show_when_focused'
