# Copyright (C) 2010 Aren Olson
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

from xl.nls import gettext as _
import os, gtk, gobject
from xlgui.preferences import widgets
from xl import event, transcoder, settings
import warnings 

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
        self._changed_id=None

    def _setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        pass

    def on_check_condition(self):
        """
            Specifies the condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        model = self.widget.get_model()
        format = self.condition_widget.get_active_text()
        formatinfo = transcoder.FORMATS[format]
        if self.format != format:
            self.format=format
            default=formatinfo['default']
            if self.default != default:
                self.default = default # raw value

        default_title = formatinfo['kbs_steps'][
            formatinfo['raw_steps'].index(self.default)]
        active_iter = self.widget.get_active_iter()

        if active_iter is not None:
            active_title = int(model.get_value(active_iter, 1))
        else:
            active_title = default_title
        
        if self._changed_id:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self.widget.disconnect(self._changed_id)
                self._changed_id=None
        model.clear()
        
        if not self._changed_id:
            self._changed_id=self.widget.connect('changed', self.change)

        steps = zip(formatinfo['raw_steps'], formatinfo['kbs_steps'])

        for item, title in steps:
            iter = model.append([item, title])

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
        '$length': _('Length'),
        '$discnumber': _('Disc number'),
        '$rating': _('Rating'),
        '$date': _('Date'),
        '$genre': _('Genre'),
        '$bitrate': _('Bitrate'),
        '$location': _('Location'),
        '$filename': _('Filename'),
        '$playcount': _('Play count'),
        '$bpm': _('BPM'),
    }
    preset_items = [
        "%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME")
    ]
    default = "%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME")

# vim: et sts=4 sw=4
