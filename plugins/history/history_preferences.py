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


from xlgui.preferences import widgets


from xl.nls import gettext as _
import os

name = _('History')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'history_preferences.ui')
icon = 'document-open-recent'


# defaults
save_on_exit_default = False
history_length_default = 1000


class SaveOnExitPreference(widgets.CheckPreference):
    default = save_on_exit_default
    name = 'plugin/history/save_on_exit'


class HistoryLengthPreference(widgets.SpinPreference):
    default = history_length_default
    name = 'plugin/history/history_length'
