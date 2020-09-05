# Copyright (C) 2009-2010 Aren Olson
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

from xl import settings, transcoder
from xl.nls import gettext as _
from xlgui.preferences import widgets

name = _("CD")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "cdprefs_pane.ui")

FORMAT_WIDGET = None

# TODO: allow setting cddb server?


class OutputFormatPreference(widgets.ComboPreference):
    name = 'cd_import/format'


class OutputQualityPreference(widgets.ComboPreference, widgets.Conditional):
    name = 'cd_import/quality'
    condition_preference_name = 'cd_import/format'

    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)
        self.format = settings.get_option("cd_import/format", None)
        self.default = settings.get_option("cd_import/quality", None)

    def on_check_condition(self):
        """
        Specifies the condition to meet

        :returns: Whether the condition is met or not
        :rtype: bool
        """
        model = self.widget.get_model()
        if not model:  # happens if preferences window is shut down on close
            return False

        curiter = self.condition_widget.get_active_iter()
        format = self.condition_widget.get_model().get_value(curiter, 0)
        formatinfo = transcoder.FORMATS[format]
        if self.format != format:
            self.format = format
            default = formatinfo['default']

            if self.default != default:
                self.default = default  # raw value

        default_title = formatinfo['kbs_steps'][
            formatinfo['raw_steps'].index(self.default)
        ]
        active_iter = self.widget.get_active_iter()

        if active_iter is not None:
            active_title = float(model.get_value(active_iter, 1))
        else:
            active_title = default_title

        self.widget.set_model(None)
        model.clear()

        steps = zip(formatinfo['raw_steps'], formatinfo['kbs_steps'])

        for item, title in steps:
            model.append([item, str(title)])

        self.widget.set_model(model)

        if active_title not in formatinfo['kbs_steps']:
            active_title = default_title

        index = formatinfo['kbs_steps'].index(active_title)
        self.widget.set_active(index)

        return True


class OutputPathPreference(widgets.ComboEntryPreference):
    name = 'cd_import/outpath'
    completion_items = {
        '$tracknumber': _('Track number'),
        '$title': _('Title'),
        '$artist': _('Artist'),
        '$composer': _('Composer'),
        '$album': _('Album'),
        '$__length': _('Length'),
        '$discnumber': _('Disc number'),
        '$__rating': _('Rating'),
        '$date': _('Date'),
        '$genre': _('Genre'),
        '$bitrate': _('Bitrate'),
        '$__loc': _('Location'),
        '$filename': _('Filename'),
        '$__playcount': _('Play count'),
        '$__last_played': _('Last played'),
        '$bpm': _('BPM'),
    }
    preset_items = ["%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME")]
    default = "%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME")


# vim: et sts=4 sw=4
