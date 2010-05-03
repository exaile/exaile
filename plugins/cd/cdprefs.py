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
from xl import event, transcoder

name = _("CD")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "cdprefs_pane.ui")

FORMAT_WIDGET = None

# TODO: allow setting cddb server?

class OutputFormatPreference(widgets.ComboPreference):
    name = 'cd_import/format'
    map = ["Ogg Vorbis", "FLAC", "AAC", "MP3 (VBR)", "MP3 (CBR)", "WavPack"]
    default = "Ogg Vorbis"
    def __init__(self, *args):
        widgets.ComboPreference.__init__(self, *args)
        global FORMAT_WIDGET
        FORMAT_WIDGET = self.widget


class OutputQualityPreference(widgets.ComboPreference):
    name = 'cd_import/quality'
    def __init__(self, prefs, widget):
        store = gtk.ListStore(gobject.TYPE_STRING)
        widget.set_model(store)
        cell = gtk.CellRendererText()
        widget.pack_start(cell, True)
        widget.add_attribute(cell, 'text', 0)
        widget.show_all()

        self._update_list(None, widget, prefs)
        widgets.ComboPreference.__init__(self, prefs, widget,
                use_map=True)

        global FORMAT_WIDGET
        FORMAT_WIDGET.connect('changed', self._update_list, widget, prefs)

    def _update_list(self, other, widget, prefs):
        oldindex = widget.get_active()
        oldval = widget.get_active_text()

        if other is not None:
            format = other.get_active_text()
        else:
            format = prefs.settings.get_option("cd_import/format",
                    OutputFormatPreference.default)
        fmt_dict = transcoder.FORMATS[format]
        self.default = fmt_dict["default"]
        widget.get_model().clear()

        for kbs in fmt_dict["kbs_steps"]:
            widget.append_text(str(kbs))

        self.map = list(fmt_dict["raw_steps"])
        self.use_map = True

        if oldval in self.map:
            widget.set_active(self.map.index(oldval))
        else:
            widget.set_active(fmt_dict["raw_steps"].index(
                fmt_dict["default"]))


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
