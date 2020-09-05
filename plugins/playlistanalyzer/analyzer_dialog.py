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

from gi.repository import GObject
from gi.repository import Gtk

from os.path import basename, dirname, join
from glob import glob
from xlgui import guiutil

from xl import settings
from xl.nls import gettext as _
from xl.metadata.tags import get_default_tagdata, tag_data

from xlgui.widgets import dialogs

import json
import re

import logging

logger = logging.getLogger(__name__)

from .presets import DEFAULT_PRESETS


class AnalyzerDialog:
    """
    Provide super flexible interface to stuff. Hm.

    Need to define stuff before interface makes sense.
    """

    ui_filename = join(dirname(__file__), 'analyzer.ui')

    ui_widgets = [
        'window',
        'description_label',
        'info_bar',
        'playlists_list',
        'playlist_store',
        'preset_model',
        'tags_table',
        'template_list',
        'template_store',
        'title_entry',
    ]

    ui_signals = [
        'on_window_delete_event',
        'on_preset_combo_changed',
        'on_template_list_cursor_changed',
        'on_generate_clicked',
    ]

    def __init__(self, plugin, parent_window, selected_playlist=None):

        self.plugin = plugin

        guiutil.initialize_from_xml(self)

        self.info_bar = dialogs.MessageBar(
            self.info_bar, type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE
        )

        self.__build_template_list()
        self.__build_playlist_list(selected_playlist)
        self.__initialize_presets()

        self.__tag_widgets = []

        self.window.set_transient_for(parent_window)
        self.window.show_all()

        def tag_data_key(td):
            return td.translated_name

        # convenience
        td = [x for x in tag_data.values() if x is not None]

        # Add grouptagger to the list
        gt = get_default_tagdata('__grouptagger')
        gt.translated_name = _('GroupTagger')

        td.append(gt)

        self.__sorted_tags = sorted(td, key=tag_data_key)

        # setup the selected template
        guiutil.persist_selection(
            self.template_list, 0, 'plugin/playlistanalyzer/last_tmpl'
        )

    def __initialize_presets(self):

        presets = settings.get_option(
            'plugin/playlistanalyzer/presets', DEFAULT_PRESETS
        )

        for preset in presets:
            self.preset_model.append(preset)

    def __build_template_list(self):

        for fname in glob(join(dirname(__file__), 'templates', '*.html')):

            # let's not do a full DOM parse here, just scan the first few
            # lines and extract out the meta tags that match

            data = {
                'name': basename(fname),
                'fname': fname,
                'description': 'No description provided',
                'mintags': 1,
                'maxtags': 1,
            }

            # Open in non-binary mode, because we are reading strings
            # and not bytes
            with open(fname, 'r') as fp:
                for line in fp:
                    m = re.match(r'.*?<meta name="(.*?)" content="(.*?)"\s*/>.*?', line)
                    if m is not None:
                        data[m.group(1)] = m.group(2)

            try:
                data['mintags'] = int(data['mintags'])
                data['maxtags'] = int(data['maxtags'])

                self.template_store.append((data['name'], data))
            except Exception:
                logger.error("Invalid meta parameter in %s", fname)

    def __build_playlist_list(self, selected_playlist):

        self.playlists_list.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        manager = self.plugin.exaile.playlists
        for name in sorted(manager.list_playlists()):
            i = self.playlist_store.append((name, manager.get_playlist(name)))

            if selected_playlist and selected_playlist.name == name:
                self.playlists_list.get_selection().select_iter(i)
                self.playlists_list.scroll_to_cell(self.playlist_store.get_path(i))

    def __build_tag_combo(self, idx):

        model = Gtk.ListStore(
            GObject.TYPE_STRING, GObject.TYPE_PYOBJECT, GObject.TYPE_STRING
        )
        widget = Gtk.ComboBox.new_with_model(model)
        cell = Gtk.CellRendererText()
        widget.pack_start(cell, True)
        widget.add_attribute(cell, 'text', 0)

        for td in self.__sorted_tags:
            model.append((td.translated_name, td, td.tag_name))

        # show/hide the spin button when an integer is displayed
        def _on_changed(widget):
            if model[widget.get_active()][1].type == 'int':
                self.__tag_widgets[idx][1].show()
            else:
                self.__tag_widgets[idx][1].hide()

        widget.connect('changed', _on_changed)

        return widget

    def __build_spin(self, idx):

        # TODO: persist value

        spin = Gtk.SpinButton()
        spin.set_no_show_all(True)
        spin.hide()
        spin.set_tooltip_text(_('Modulus this number'))

        spin.set_range(0, 1000)
        spin.set_value(10)
        spin.set_increments(1, 5)
        spin.set_digits(0)

        return spin

    def __build_tag_table(self):

        self.__tag_widgets = []
        self.tags_table.foreach(self.tags_table.remove)

        tmpl = self._get_selected_template()
        if tmpl is None:
            return

        for i in range(0, tmpl['maxtags']):

            label = Gtk.Label(label=_('Tag %s') % (i + 1))
            combo = self.__build_tag_combo(i)
            spin = self.__build_spin(i)

            self.tags_table.attach(label, 0, i, 1, 1)
            self.tags_table.attach(combo, 1, i, 1, 1)
            self.tags_table.attach(spin, 2, i, 1, 1)

            self.__tag_widgets.append((combo, spin))

        # do this *after* the widgets are built
        for i, (cb, sp) in enumerate(self.__tag_widgets):
            guiutil.persist_selection(cb, 2, 'plugin/playlistanalyzer/tag%s' % i)

        self.tags_table.show_all()

    def __set_tag_combo_active(self, cb, tag_name):
        model = cb.get_model()
        for i in range(0, len(model)):
            if model[i][1].tag_name == tag_name:
                cb.set_active(i)
                return

    def _get_selected_playlists(self):
        model, paths = self.playlists_list.get_selection().get_selected_rows()

        return [model[path][1] for path in paths]

    def _get_selected_template(self):
        model, it = self.template_list.get_selection().get_selected()

        if it is None:
            return None

        return model.get(it, 1)[0]

    def _get_tag_data(self):
        td = []

        for cb, sp in self.__tag_widgets:
            if cb.get_active() < 0:
                td.append(None)
            else:
                data = cb.get_model()[cb.get_active()][1]
                if data.type == 'int':
                    td.append((data.tag_name, sp.get_value_as_int()))
                else:
                    td.append((data.tag_name, None))

        return td

    def _get_title(self):
        title = self.title_entry.get_text().strip()
        if title == '':
            playlists = self._get_selected_playlists()
            if len(playlists) == 1:
                title = playlists[0].name
            else:
                data = self._get_selected_template()
                title = data['name']

        return title

    def destroy(self):
        self.plugin.dialog = None
        self.window.destroy()

    def on_window_delete_event(self, widget, evt):
        self.plugin.dialog = None

    def on_preset_combo_changed(self, widget):

        if widget.get_active() < 0:
            return

        preset_name, tmpl, data = widget.get_model()[widget.get_active()]

        # cheat, just set the settings so when the template switches
        # it will automatically enable the right settings
        for i, td in enumerate(data):
            settings.set_option('plugin/playlistanalyzer/tag%s' % i, td)

        # switch the template
        for i in range(0, len(self.template_store)):
            if tmpl == basename(self.template_store[i][1]['fname']):
                self.template_list.set_cursor((i,))
                break

    def on_template_list_cursor_changed(self, widget):
        data = self._get_selected_template()

        if data:
            self.description_label.set_text(data['description'])
        else:
            self.description_label.set_text('')

        # setup the tags table
        self.__build_tag_table()

    def on_playlist_list_cursor_changed(self, widget):
        pass

    def on_generate_clicked(self, widget):

        output_fname = 'analysis'
        playlists = self._get_selected_playlists()

        # validate user selections

        tmpl_data = self._get_selected_template()
        if tmpl_data is None:
            self.info_bar.show_error("No template selected")
            return

        if len(playlists) < 1:
            self.info_bar.show_error("No playlist selected")
            return

        if len(playlists) == 1:
            pname = playlists[0].name
            output_fname = '%s%sanalysis.html' % (pname, ' ' if ' ' in pname else '-')

        # get output file
        output_uri = dialogs.save(
            self.window,
            output_fname,
            'plugin/playlistanalyzer/dlg_location',
            None,
            _("Save analysis"),
        )

        if output_uri is None:
            return

        # figure out the output track list
        # -> if the user selects more than one playlist, we separate the
        #    track list with a None so it can be detected if necessary
        tracks = []
        for pl in playlists:
            if len(tracks) > 0:
                tracks.append(None)
            tracks.extend(pl)

        tagdata = self._get_tag_data()

        # generate, write it out
        try:
            kwargs = {
                'tagdata': json.dumps(tagdata),
                'playlist_names': [pl.name for pl in playlists],
                'data': json.dumps(self.plugin.generate_data(tracks, tagdata)),
                'title': self._get_title(),
            }

            self.plugin.write_to_file(tmpl_data['fname'], output_uri, **kwargs)
        except Exception as e:
            logger.exception("Error generating analysis")
            self.info_bar.show_error("Error generating analysis", str(e))
        else:
            # and that's all folks
            self.destroy()
