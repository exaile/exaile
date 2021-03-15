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

from collections import OrderedDict
import datetime
import io
import os
import string
import re
from typing import Iterable, Sequence

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from xl.nls import gettext as _
from xl.metadata import CoverImage
from xl import common, settings, trax, xdg

from xlgui.widgets import dialogs
from xlgui.guiutil import GtkTemplate
from xl.metadata.tags import tag_data, get_default_tagdata

import logging

logger = logging.getLogger(__name__)


class TrackPropertiesDialog(GObject.GObject):
    def __init__(
        self,
        parent: Gtk.Window,
        tracks: Sequence[trax.Track],
        current_position: int = 0,
    ):
        """
        :param parent: the parent window for modal operation
        :param tracks: the tracks to process
        :param current_position: the position of the currently
            selected track in the list
        """
        GObject.GObject.__init__(self)

        self.builder = Gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui', 'trackproperties_dialog.ui'))
        self.builder.connect_signals(self)
        self.dialog = self.builder.get_object('TrackPropertiesDialog')
        self.dialog.set_transient_for(parent)

        self.__default_attributes = Pango.AttrList()
        self.__changed_attributes = Pango.AttrList()

        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('main_content'),
            buttons=Gtk.ButtonsType.CLOSE,
        )

        self.remove_tag_button = self.builder.get_object('remove_tag_button')
        self.cur_track_label = self.builder.get_object('current_track_label')
        self.apply_button = self.builder.get_object('apply_button')
        self.prev_button = self.builder.get_object('prev_track_button')
        self.next_button = self.builder.get_object('next_track_button')

        self.tags_grid = self.builder.get_object('tags_grid')
        self.properties_grid = self.builder.get_object('properties_grid')
        self.rows = []

        self.new_tag_combo = self.builder.get_object('new_tag_combo')
        self.new_tag_combo_list = Gtk.ListStore(str, str)
        for tag, tag_info in tag_data.items():
            if tag_info is not None and tag_info.editable:
                self.new_tag_combo_list.append((tag, tag_info.translated_name))
        self.new_tag_combo_list.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.new_tag_combo.set_model(self.new_tag_combo_list)
        self.add_tag_button = self.builder.get_object('add_tag_button')
        self.add_tag_button.set_sensitive(False)

        # Show these tags for all tracks, no matter what
        def_tags = [
            'tracknumber',
            'title',
            'artist',
            'albumartist',
            'album',
            'discnumber',
            'date',
            'genre',
            'cover',
            'comment',
            '__startoffset',
            '__stopoffset',
            'lyrics',
        ]

        self.def_tags = OrderedDict([(tag, tag_data[tag]) for tag in def_tags])

        # Store the tracks and a working copy
        self.tracks = tracks
        self.trackdata = self._tags_copy(tracks)
        self.trackdata_original = self._tags_copy(tracks)
        self.current_position = current_position

        self._build_from_track(self.current_position)

        self._setup_position()
        self.dialog.show()

        self.rows[0].field.grab_focus()

    def _get_field_widget(self, tag_info, ab):
        tag_type = tag_info.type

        if tag_type == 'int':
            field = TagNumField(tag_info.min, tag_info.max, all_button=ab)
        elif tag_type == 'dblnum':
            field = TagDblNumField(tag_info.min, tag_info.max, all_button=ab)
        elif tag_type == 'time':
            field = TagNumField(tag_info.min, tag_info.max, all_button=ab)
        elif tag_type == 'image':
            field = TagImageField()
        elif tag_type == 'multiline':
            field = TagTextField(all_button=ab)
        else:
            field = TagField(all_button=ab)

        return field

    def _tags_copy(self, tracks: Iterable[trax.Track]):
        l = []
        for track in tracks:
            t = {}
            for tag, tag_info in self.def_tags.items():
                if tag_info.use_disk:
                    tagval = track.get_tag_disk(tag)
                else:
                    tagval = track.get_tag_raw(tag)

                if tagval:
                    if isinstance(tagval, list):
                        t[tag] = tagval[:]
                    else:
                        t[tag] = [tagval]
                else:
                    t[tag] = ['']

                if tag_info.type == 'dblnum':
                    for i, entry in enumerate(t[tag]):
                        if len(entry.split('/')) < 2:
                            t[tag][i] += '/0'

            for tag in track.list_tags():
                if tag not in self.def_tags:
                    tag_info = tag_data.get(tag)
                    if not tag_info or not tag_info.use_disk:
                        tagval = track.get_tag_raw(tag)
                    else:
                        tagval = track.get_tag_disk(tag)
                    if isinstance(tagval, list):
                        t[tag] = tagval[:]
                    else:
                        t[tag] = [tagval]

            l.append(t)

        return l

    def _write_tag(self, track, tag, value):
        tag_info = tag_data.get(tag)
        if not tag_info or not tag_info.use_disk:
            track.set_tag_raw(tag, value)
        else:
            track.set_tag_disk(tag, value)

    def _tags_write(self, data):
        errors = []
        dialog = SavingProgressWindow(self.dialog, len(data))
        for n, trackdata in data:
            track = self.tracks[n]
            poplist = []

            try:
                for tag in trackdata:
                    if not tag.startswith("__"):
                        if tag in ("tracknumber", "discnumber") and trackdata[tag] == [
                            "0/0"
                        ]:
                            poplist.append(tag)
                            continue
                        self._write_tag(track, tag, trackdata[tag])
                    elif tag in ('__startoffset', '__stopoffset'):
                        try:
                            offset = int(trackdata[tag][0])
                        except ValueError:
                            poplist.append(tag)
                        else:
                            track.set_tag_raw(tag, offset)

                # In case a tag has been removed..
                for tag in track.list_tags():
                    if tag in tag_data:
                        if tag_data[tag] is not None:
                            try:
                                trackdata[tag]
                            except KeyError:
                                poplist.append(tag)
                    else:
                        try:
                            trackdata[tag]
                        except KeyError:
                            poplist.append(tag)

                for tag in poplist:
                    self._write_tag(track, tag, None)

                if not track.write_tags():
                    errors.append(track.get_loc_for_io())
            except Exception:
                logger.warning("Error saving track", exc_info=True)
                errors.append(track.get_loc_for_io())

            trax.track._CACHER.remove(track)
            dialog.step()
        dialog.destroy()

        if len(errors) > 0:
            self.message.clear_buttons()
            self.message.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            self.message.show_error(
                _('Writing of tags failed'),
                _(
                    'Tags could not be written to the following files:\n' '{files}'
                ).format(files='\n'.join(errors)),
            )

    def _build_from_track(self, position):
        self._clear_grids()

        self.rows = []

        # Previous, next and current track label
        self.prev_button.set_sensitive(True)
        self.next_button.set_sensitive(True)

        if position == 0:
            self.prev_button.set_sensitive(False)

        if position == (len(self.trackdata) - 1):
            self.next_button.set_sensitive(False)

        self.cur_track_label.set_text(
            _("Editing track %(current)d of %(total)d")
            % {'current': self.current_position + 1, 'total': len(self.tracks)}
        )

        trackdata = self.trackdata[position]

        if len(self.trackdata) == 1:
            ab = False
        else:
            ab = True

        for tag, tag_info in self.def_tags.items():

            for i, entry in enumerate(trackdata.get(tag, [''])):

                field = self._get_field_widget(tag_info, ab)

                row = TagRow(self, self.tags_grid, field, tag, entry, i)
                self.rows.append(row)

                try:
                    if (
                        self.trackdata[self.current_position][tag]
                        != self.trackdata_original[self.current_position][tag]
                    ):
                        row.label.set_attributes(self.__changed_attributes)
                except KeyError:
                    row.label.set_attributes(self.__changed_attributes)

        for tag in trackdata:
            if tag in self.def_tags:
                continue

            try:
                tag_info = tag_data[tag]
            except KeyError:
                tag_info = get_default_tagdata(tag)

            if tag_info is None:
                continue

            for i, entry in enumerate(trackdata[tag]):
                if tag_info.editable:
                    field = self._get_field_widget(tag_info, ab)
                    self.rows.append(TagRow(self, self.tags_grid, field, tag, entry, i))
                else:
                    field = PropertyField(tag_info.type)
                    self.rows.append(
                        TagRow(self, self.properties_grid, field, tag, entry, i)
                    )

        self._check_for_changes()
        self._build_grids_from_rows()

    def _build_grids_from_rows(self):
        self._clear_grids()
        grids = [self.tags_grid, self.properties_grid]
        cur_row = {grids[0]: 0, grids[1]: 0}

        for row in self.rows:
            row.grid.insert_row(cur_row[row.grid] + 1)
            row.grid.attach(Gtk.Separator(), 0, cur_row[row.grid], 2, 1)
            cur_row[row.grid] += 1

            row.grid.insert_row(cur_row[row.grid] + 1)
            row.grid.attach(row.label, 0, cur_row[row.grid], 1, 1)
            row.grid.attach(row.field, 1, cur_row[row.grid], 1, 1)
            cur_row[row.grid] += 1

        for grid in grids:
            grid.show_all()

        self.remove_tag_button.toggled()

    def _clear_grids(self):
        """Careful, we need to delete exactly as many rows as we inserted"""
        grids = [self.tags_grid, self.properties_grid]

        for grid in grids:
            row_count = len(grid.get_children())
            for child in grid.get_children():
                grid.remove(child)

            for i in range((row_count // 3) * 2, 0, -1):
                grid.remove_row(i)

    def _save_position(self):
        (width, height) = self.dialog.get_size()
        if [width, height] != [
            settings.get_option('gui/trackprop_' + key, -1)
            for key in ['width', 'height']
        ]:
            settings.set_option('gui/trackprop_height', height, save=False)
            settings.set_option('gui/trackprop_width', width, save=False)
        (x, y) = self.dialog.get_position()
        if [x, y] != [
            settings.get_option('gui/trackprop_' + key, -1) for key in ['x', 'y']
        ]:
            settings.set_option('gui/trackprop_x', x, save=False)
            settings.set_option('gui/trackprop_y', y, save=False)

    def _setup_position(self):
        width = settings.get_option('gui/trackprop_width', 600)
        height = settings.get_option('gui/trackprop_height', 350)
        x = settings.get_option('gui/trackprop_x', 100)
        y = settings.get_option('gui/trackprop_y', 100)

        self.dialog.move(x, y)
        self.dialog.resize(width, height)

    def on_apply_button_clicked(self, w):
        modified = []
        for n, trackdata in enumerate(self.trackdata):
            if trackdata != self.trackdata_original[n]:
                modified.append((n, trackdata))

        if modified:
            if len(modified) != 1:
                dialog = Gtk.MessageDialog(
                    buttons=Gtk.ButtonsType.YES_NO,
                    message_type=Gtk.MessageType.QUESTION,
                    modal=True,
                    text=_('Are you sure you want to apply the changes to all tracks?'),
                    transient_for=self.dialog,
                )
                response = dialog.run()
                dialog.destroy()

                if response != Gtk.ResponseType.YES:
                    return

            self._tags_write(modified)

            del self.trackdata
            del self.trackdata_original
            self.trackdata = self._tags_copy(self.tracks)
            self.trackdata_original = self._tags_copy(self.tracks)

            self.apply_button.set_sensitive(False)
            for row in self.rows:
                if row.multi_id == 0:
                    row.label.set_attributes(self.__default_attributes)

        # Hide close confirmation if necessary
        if self.message.get_message_type() == Gtk.MessageType.QUESTION:
            self.message.hide()

    def _check_for_save(self):
        if self.trackdata != self.trackdata_original:

            def on_response(message, response):
                """
                Applies changes before closing if requested
                """
                if response == Gtk.ResponseType.APPLY:
                    self.apply_button.clicked()

                self._save_position()
                self.dialog.destroy()

            self.message.connect('response', on_response)
            self.message.clear_buttons()
            self.message.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            self.message.add_button(Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY)
            self.message.show_question(
                _('Apply changes before closing?'),
                _('Your changes will be lost if you do not apply them now.'),
            )
        else:
            self._save_position()
            self.dialog.destroy()

    def on_close_button_clicked(self, w):
        self._check_for_save()

    def on_delete_event(self, widget, data=None):
        self._check_for_save()
        return True

    def on_prev_track_button_clicked(self, widget):
        self.current_position -= 1
        self._build_from_track(self.current_position)

    def on_next_track_button_clicked(self, widget):
        self.current_position += 1
        self._build_from_track(self.current_position)

    def on_title_case_button_clicked(self, w):
        for row in self.rows:
            if isinstance(row.field, TagField) or isinstance(row.field, TagTextField):
                val = row.field.get_value()
                val = string.capwords(val, ' ')
                row.field.set_value(val)

        self._check_for_changes()

    def on_new_tag_entry_changed(self, entry):
        """
        Enables or disables the button for adding tags,
        effectively preventing empty tag names
        """
        self.add_tag_button.set_sensitive(len(entry.get_text()) > 0)

    def on_add_tag_button_clicked(self, w):
        tag = None

        index = self.new_tag_combo.get_active()

        if index != -1:
            tag = self.new_tag_combo_list[index][0]
        else:
            tag = self.new_tag_combo.get_child().get_text()

        if not tag:
            return

        trackdata = self.trackdata[self.current_position]

        try:
            trackdata[tag].append('')
        except KeyError:
            trackdata[tag] = ['']

        self._build_from_track(self.current_position)

    def on_remove_tag_button_toggled(self, widget):
        for row in self.rows:
            row.set_remove_mode(widget.get_active())

    def _check_for_changes(self):
        apply_flag = False
        for i, trackdata in enumerate(self.trackdata):
            for tag in trackdata:
                try:
                    if trackdata[tag] != self.trackdata_original[i][tag]:
                        apply_flag = True
                except KeyError:
                    apply_flag = True

            if len(trackdata) != len(self.trackdata_original[i]):
                apply_flag = True

        if apply_flag:
            if not self.apply_button.get_property("sensitive"):
                self.apply_button.set_sensitive(True)
        else:
            self.apply_button.set_sensitive(False)

    def update_tag(self, widget, tag, multi_id, val):

        trackdata = self.trackdata[self.current_position]
        original_trackdata = self.trackdata_original[self.current_position]
        trackdata[tag][multi_id] = val()

        for row in self.rows:
            if row.tag == tag and row.multi_id == 0:
                try:
                    if trackdata[tag] != original_trackdata[tag]:
                        row.label.set_attributes(self.__changed_attributes)
                    else:
                        row.label.set_attributes(self.__default_attributes)
                except KeyError:
                    row.label.set_attributes(self.__changed_attributes)

            if row.tag == tag and row.multi_id == multi_id:
                all_vals = []
                for trackdata in self.trackdata:
                    try:
                        all_vals.append(trackdata[tag][multi_id])
                    except (KeyError, IndexError):
                        all_vals.append('')

                row.field.set_value(val(), all_vals, doupdate=False)

        self._check_for_changes()

    def apply_all(self, field, multi_id, val, split_num=0):
        value = val()

        if tag_data[field].type == 'dblnum':
            original_values = value.split("/")
            for i, trackdata in enumerate(self.trackdata):
                values = trackdata[field][multi_id].split("/")
                values[split_num] = original_values[split_num]
                try:
                    trackdata[field][multi_id] = values[0] + "/" + values[1]
                except KeyError:
                    trackdata[field] = [values[0] + "/" + values[1]]
                except IndexError:
                    trackdata[field].append(values[0] + "/" + values[1])

        else:
            for i, trackdata in enumerate(self.trackdata):
                try:
                    trackdata[field][multi_id] = value
                except KeyError:
                    trackdata[field] = [value]
                except IndexError:
                    trackdata[field].append(value)

        self._check_for_changes()

    def remove_row(self, w, tag, multi_id):
        for row in self.rows:
            if row.tag == tag and row.multi_id == multi_id:
                self.trackdata[self.current_position][tag].pop(multi_id)
                if len(self.trackdata[self.current_position][tag]) == 0:
                    self.trackdata[self.current_position].pop(tag)

        self._build_from_track(self.current_position)

    def run(self):
        return self.dialog.run()

    def hide(self):
        self.dialog.hide()


class TagRow:
    def __init__(self, parent, parent_grid, field, tag_name, value, multi_id):
        self.parent = parent
        self.grid = parent_grid
        self.tag = tag_name
        self.field = field
        self.field.register_parent_row(self)
        self.multi_id = multi_id
        all_vals = []
        for track in parent.trackdata:
            try:
                all_vals.append(track[tag_name][multi_id])
            except (KeyError, IndexError):
                all_vals.append(None)

        self.field.set_value(value, all_vals)

        try:
            name = tag_data[self.tag].translated_name
        except KeyError:
            if self.tag.startswith('__'):
                name = self.tag[2:]
            else:
                name = self.tag
            name = name.capitalize()

        self.name = name
        self.label = Gtk.Label(halign=Gtk.Align.START, margin_top=5)

        if multi_id == 0:
            # TRANSLATORS: Label for a tag on the Track Properties dialog
            self.label.set_text(_('%s:') % name)
            self.label.create_pango_context()

        self.clear_button = Gtk.Button(
            image=Gtk.Image.new_from_icon_name('edit-clear', Gtk.IconSize.BUTTON),
            relief=Gtk.ReliefStyle.NONE,
            # TRANSLATORS: Remove tag value
            tooltip_text=_("Clear"),
        )
        self.clear_button.connect("clicked", self.clear)

        if not isinstance(field, PropertyField):
            self.field.pack_start(self.clear_button, False, False, 0)

        self.field.show_all()

        # Remove mode settings
        self.remove_mode = False
        self.remove_button = Gtk.Button()
        self.remove_button.set_image(
            Gtk.Image.new_from_icon_name('list-remove', Gtk.IconSize.BUTTON)
        )
        self.remove_button.connect(
            "clicked", parent.remove_row, self.tag, self.multi_id
        )

        self.field.register_update_func(parent.update_tag)
        self.field.register_all_func(parent.apply_all)

    def set_remove_mode(self, val):
        if not self.tag.startswith('__') or self.multi_id != 0:
            if val and not self.remove_mode:
                self.field.remove(self.clear_button)
                self.field.pack_start(self.remove_button, False, False, 0)
                self.field.show_all()
                self.remove_mode = True

            if not val and self.remove_mode:
                self.field.remove(self.remove_button)
                self.remove_mode = False
                self.field.pack_start(self.clear_button, False, False, 0)
                self.field.show_all()

    def clear(self, w):
        self.field.set_value('')


class TagField(Gtk.Box):
    def __init__(self, all_button=True):
        Gtk.Box.__init__(self, homogeneous=False, spacing=5)

        # Create the widgets
        self.field = Gtk.Entry()
        self.all_func = None
        self.parent_row = None

        self.pack_start(self.field, True, True, 0)

        self.all_button = None
        if all_button:
            self.all_button = AllButton(self)
            self.pack_start(self.all_button, False, False, 0)

    def grab_focus(self):
        """
        Gives focus to the internal widget
        """
        self.field.grab_focus()

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def set_value(self, val, all_vals=None, doupdate=True):
        if doupdate:
            self.field.set_text(val)

        if all_vals is not None and self.all_button is not None:
            # Set the value of the all button
            self.all_button.set_active(all(val == v for v in all_vals))

    def get_value(self):
        return self.field.get_text()

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.field.connect("changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f


def dummy_scroll_handler(widget, _):
    """scroll-event handler that just disables the default handler.

    Tag field widgets should use this to prevent the user from accidentally
    modifying tags by scrolling.
    """
    GObject.signal_stop_emission_by_name(widget, 'scroll-event')
    return False


class TagTextField(Gtk.Box):
    def __init__(self, all_button=True):
        Gtk.Box.__init__(self, homogeneous=False, spacing=5)

        self.buffer = Gtk.TextBuffer()
        self.field = Gtk.TextView.new_with_buffer(self.buffer)
        self.field.set_size_request(200, 150)  # XXX
        self.field.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scrollwindow = Gtk.ScrolledWindow()
        scrollwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollwindow.set_shadow_type(Gtk.ShadowType.IN)
        scrollwindow.add(self.field)
        self.all_func = None
        self.parent_row = None

        self.pack_start(scrollwindow, True, True, 0)

        self.all_button = None
        if all_button:
            self.all_button = AllButton(self)
            self.pack_start(self.all_button, False, False, 0)

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def set_value(self, val, all_vals=None, doupdate=True):
        if doupdate:
            self.buffer.set_text(val)

        if all_vals is not None and self.all_button is not None:
            # Set the value of the all button
            flag = True
            for v in all_vals:
                if val != v:
                    flag = False

            if flag:
                self.all_button.set_active(True)
            else:
                self.all_button.set_active(False)

    def get_value(self):
        return self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), True
        )

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.buffer.connect("changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f


class TagNumField(Gtk.Box):
    def __init__(self, min=0, max=10000, step=1, page=10, all_button=True):
        Gtk.Box.__init__(self, homogeneous=False, spacing=5)

        # Create the widgets
        self.field = Gtk.SpinButton()
        self.field.set_range(min, max)
        self.field.set_increments(step, page)
        self.field.connect('scroll-event', dummy_scroll_handler)
        self.all_func = None
        self.parent_row = None

        self.pack_start(self.field, True, True, 0)

        self.all_button = None
        if all_button:
            self.all_button = AllButton(self)
            self.pack_start(self.all_button, False, False, 0)

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def set_value(self, val, all_vals=None, doupdate=True):
        if doupdate:
            field_val = 0
            if val != '':
                try:
                    field_val = float(val)
                except ValueError:
                    digits = re.search(r'\d+\.?\d*', val)
                    if digits:
                        field_val = float(digits.group())
            self.field.set_value(field_val)

        if all_vals is not None and self.all_button is not None:
            # Set the value of the all button
            flag = True
            for v in all_vals:
                if val != v:
                    flag = False

            if flag:
                self.all_button.set_active(True)
            else:
                self.all_button.set_active(False)

    def get_value(self):
        return str(int(self.field.get_value()))

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.field.connect("value-changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f


class TagDblNumField(Gtk.Box):
    def __init__(self, min=0, max=10000, step=1, page=10, all_button=True):
        Gtk.Box.__init__(self, homogeneous=False, spacing=5)

        self.field = [Gtk.SpinButton(), Gtk.SpinButton()]
        self.all_func = None
        self.parent_row = None
        for f in self.field:
            f.set_range(min, max)
            f.set_increments(step, page)
            f.connect('scroll-event', dummy_scroll_handler)

        # TRANSLATORS: This is the 'of' between numbers in fields like
        # tracknumber, discnumber, etc. in the tagger.
        lbl = Gtk.Label(label=_('of:'))
        self.all_button = [None, None]
        if all_button:
            self.all_button = [AllButton(self), AllButton(self, 1)]

        self.pack_start(self.field[0], True, True, 0)
        if all_button and self.all_button[0] is not None:
            self.pack_start(self.all_button[0], False, False, 0)
        self.pack_start(lbl, True, True, 0)
        self.pack_start(self.field[1], True, True, 0)
        if all_button:
            self.pack_start(self.all_button[1], False, False, 0)

    def grab_focus(self):
        """
        Gives focus to the internal widget
        """
        self.field[0].grab_focus()

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def register_all_func(self, f):
        self.all_func = f

    def set_value(self, val, all_val=None, doupdate=True):
        if len(val.split('/')) < 2:
            val += '/'

        vals = val.split('/')

        if doupdate:
            for x in range(2):
                field_val = 0
                if vals[x] != '':
                    try:
                        field_val = float(vals[x])
                    except ValueError:
                        digits = re.search(r'\d+\.?\d*', val)
                        if digits:
                            field_val = float(digits.group())
                self.field[x].set_value(field_val)

        if all_val is not None:
            all_vals = []
            for v in all_val:
                if v is not None:
                    if len(v.split('/')) < 2:
                        v += '/'
                    all_vals.append(v.split('/'))
                else:
                    all_vals.append(None)

            # Set the value of the all button
            flags = [True, True]
            for i in range(2):
                for v in all_vals:
                    if v is None or vals[i] != v[i]:
                        flags[i] = False

                if self.all_button[i] is not None:
                    if flags[i]:
                        self.all_button[i].set_active(True)
                    else:
                        self.all_button[i].set_active(False)

    def get_value(self):
        return '%d/%d' % (self.field[0].get_value(), self.field[1].get_value())

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.field[0].connect("value-changed", f, tag, multi_id, self.get_value)
        self.field[1].connect("value-changed", f, tag, multi_id, self.get_value)


@GtkTemplate('ui', 'trackproperties_dialog_cover_row.ui')
class TagImageField(Gtk.Box):

    __gtype_name__ = 'TagImageField'

    (
        button,
        image,
        type_model,
        description_entry,
        type_selection,
        info_label,
    ) = GtkTemplate.Child.widgets(6)

    def __init__(self, all_button=True):
        Gtk.Box.__init__(self)
        self.init_template()

        self.parent_row = None
        self.all_func = None
        self.update_func = None
        # Prevents the update function from being called, make
        # sure you do that manually after the batch update
        self.batch_update = False

        self.pixbuf = None
        self.info = CoverImage(None, None, None, None)
        self.default_type = 3
        self.mime_info = {
            'image/jpeg': {
                # Title for display
                'title': _('JPEG image'),
                # Type and options for GDK Pixbuf saving
                'type': 'jpeg',
                'options': {'quality': '90'},
            },
            'image/png': {'title': _('PNG image'), 'type': 'png', 'options': {}},
            'image/': {
                'title': _('Image'),
                # Store unknown images as JPEG
                'type': 'jpeg',
                'options': {'quality': '90'},
            },
            # TODO: Handle linked images
            '-->': {'title': _('Linked image')},
        }

        self.button.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.button.drag_dest_add_uri_targets()

        self.type_selection.connect('scroll-event', dummy_scroll_handler)

        self.all_button = None
        if all_button:
            self.all_button = AllButton(self)
            self.pack_start(self.all_button, False, False, 0)

    def grab_focus(self):
        """
        Gives focus to the internal widget
        """
        self.image.grab_focus()

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def register_update_func(self, func):
        self.update_func = func

    def register_all_func(self, function):
        self.all_func = function

    def set_value(self, val, all_vals=None, doupdate=True):
        if doupdate:
            if val:
                loader = GdkPixbuf.PixbufLoader()

                try:
                    loader.write(val.data)
                    loader.close()
                except GLib.GError:
                    pass
                else:
                    self.batch_update = True
                    self.set_pixbuf(loader.get_pixbuf(), val.mime)

                    # some file types do not support multiple cover types
                    if val.type is not None:
                        self.type_selection.set_active(val.type)
                        self.type_selection.set_sensitive(True)
                    else:
                        self.type_selection.set_active(-1)
                        self.type_selection.set_sensitive(False)

                    if val.desc is not None:
                        self.description_entry.set_text(val.desc)
                        self.description_entry.set_sensitive(True)
                    else:
                        self.description_entry.set_text('')
                        self.description_entry.set_sensitive(False)

                    self.batch_update = False
            else:
                self.batch_update = True
                self.set_pixbuf(None)
                self.type_selection.set_active(-1)
                self.type_selection.set_sensitive(False)
                self.description_entry.set_text('')
                self.description_entry.set_sensitive(False)
                self.batch_update = False
                self.call_update_func()

        if None not in (all_vals, self.all_button):
            self.all_button.set_active(all(val == v for v in all_vals))

    def get_value(self):
        if not self.pixbuf:
            return None

        mime = self.mime_info[self.info.mime]
        # Retrieve proper image data
        writer = io.BytesIO()

        def gdk_pixbuf_save_func(buf, count, user_data):
            if writer.write(buf) == count:
                return True
            return False

        # workaround for some undocumented changes in GdkPixbuf API
        # see https://bugzilla.gnome.org/show_bug.cgi?id=670372
        # see https://github.com/mypaint/mypaint/issues/236
        try:
            save_to_callback_function = self.pixbuf.save_to_callbackv
        except AttributeError:
            save_to_callback_function = self.pixbuf.save_to_callback
        save_to_callback_function(
            gdk_pixbuf_save_func,
            None,
            mime['type'],
            list(mime['options'].keys()),  # must be a sequence (list)
            list(mime['options'].values()),  # must be a sequence (list)
        )

        # Move to the beginning of the buffer to allow read operations
        writer.seek(0)

        return self.info._replace(data=writer.read())

    def call_update_func(self):
        """
        Wrapper around the update function
        """
        if not self.update_func or self.batch_update:
            return

        self.update_func(
            self, self.parent_row.tag, self.parent_row.multi_id, self.get_value
        )

    def set_pixbuf(self, pixbuf, mime=None):
        """
        Updates the displayed cover image and info values
        """
        self.pixbuf = pixbuf

        if pixbuf is None:
            self.image.set_from_icon_name('list-add', Gtk.IconSize.DIALOG)
            self.info_label.set_markup('')
        else:
            self.image.set_from_pixbuf(
                pixbuf.scale_simple(100, 100, GdkPixbuf.InterpType.BILINEAR)
            )

            width, height = pixbuf.get_width(), pixbuf.get_height()
            if mime is None:
                # TRANSLATORS: do not translate 'width' and 'height'
                markup = _('{width}x{height} pixels').format(width=width, height=height)
            else:
                # TRANSLATORS: do not translate 'format', 'width', and 'height'
                markup = _('{format} ({width}x{height} pixels)').format(
                    format=self.mime_info.get(mime, self.mime_info['image/'])['title'],
                    width=width,
                    height=height,
                )
            self.info_label.set_markup(markup)

            self.info = self.info._replace(mime=mime)

    def _on_button_clicked(self, button):
        """
        Allows setting the cover image using a file selection dialog
        """
        dialog = dialogs.FileOperationDialog(
            title=_('Select image to set as cover'),
            parent=self.get_toplevel(),
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK,
                Gtk.ResponseType.OK,
            ),
        )
        dialog.set_select_multiple(False)
        filefilter = Gtk.FileFilter()
        # Not using Gtk.FileFilter.add_pixbuf_formats since
        # not all image formats are supported in tags
        filefilter.set_name(_('Supported image formats'))
        filefilter.add_pattern('*.[jJ][pP][gG]')
        filefilter.add_pattern('*.[jJ][pP][eE][gG]')
        filefilter.add_pattern('*.[pP][nN][gG]')
        dialog.add_filter(filefilter)

        if dialog.run() == Gtk.ResponseType.OK:
            filename = dialog.get_filename()

            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
                info = GdkPixbuf.Pixbuf.get_file_info(filename)[0]
            except TypeError:
                pass
            else:
                self.batch_update = True
                self.set_pixbuf(pixbuf, info.get_mime_types()[0])
                self.type_selection.set_active(self.default_type)
                self.type_selection.set_sensitive(True)
                self.description_entry.set_text(
                    os.path.basename(filename).rsplit('.', 1)[0]
                )
                self.description_entry.set_sensitive(True)
                self.batch_update = False
                self.call_update_func()

        dialog.destroy()

    def _on_button_drag_data_received(
        self, widget, context, x, y, selection, info, time
    ):
        """
        Allows setting the cover image via drag and drop
        """
        if selection.target.name() == 'text/uri-list':
            filename = Gio.File.new_for_uri(selection.get_uris()[0]).get_path()

            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
                info = GdkPixbuf.Pixbuf.get_file_info(filename)[0]
            except TypeError:
                pass
            else:
                self.batch_update = True
                self.set_pixbuf(pixbuf, info['mime_types'][0])
                self.type_selection.set_active(self.default_type)
                self.description_entry.set_sensitive(True)
                self.description_entry.set_text(
                    os.path.basename(filename).rsplit('.', 1)[0]
                )
                self.description_entry.set_sensitive(True)
                self.batch_update = False
                self.call_update_func()

    def _on_type_selection_changed(self, combobox):
        """
        Notifies about changes in the cover type
        """
        self.info = self.info._replace(type=self.type_model[combobox.get_active()][0])
        self.call_update_func()

    def _on_description_entry_changed(self, entry):
        """
        Notifies about changes in the cover description
        """
        self.info = self.info._replace(desc=entry.get_text())
        self.call_update_func()


class PropertyField(Gtk.Box):
    def __init__(self, property_type='text'):
        Gtk.Box.__init__(self, homogeneous=False, spacing=5)

        # Informs of special formatting required
        self.property_type = property_type
        self.field = Gtk.Entry()
        self.field.set_editable(False)
        self.pack_start(self.field, True, True, 0)
        self.set_hexpand(True)
        self.parent_row = None

        if self.property_type == 'location':
            self.folder_button = Gtk.Button()
            self.folder_button.set_tooltip_text(_('Open Directory'))
            self.folder_button.set_image(
                Gtk.Image.new_from_icon_name('folder-open', Gtk.IconSize.BUTTON)
            )
            self.pack_start(self.folder_button, False, False, 0)
            self.folder_button.connect("clicked", self.folder_button_clicked)

    def register_parent_row(self, parent_row):
        self.parent_row = parent_row

    def set_value(self, val, all_vals=None, doupdate=True):
        if self.property_type == 'bitrate':
            try:
                val = str(float(val) / 1000.0) + ' kbps'
            except (TypeError, ValueError):
                pass
        elif self.property_type == 'timestamp':
            d = datetime.datetime.fromtimestamp(val)
            val = d.strftime("%x %X")
        elif self.property_type == 'time':
            val = "%(m)d:%(s)02d" % {'m': val // 60, 's': val % 60}
        elif self.property_type == 'location':
            f = Gio.File.new_for_uri(val)
            val = f.get_parse_name()

            if not f.get_path():
                # Sanitize URLs of remote locations
                val = common.sanitize_url(val)
                # Disable folder button for non-browsable locations
                self.folder_button.set_sensitive(False)
        else:
            val = str(val)

        if doupdate:
            self.field.set_text(val)
            self.field.set_tooltip_text(val)

    def folder_button_clicked(self, w):
        common.open_file_directory(self.field.get_text())

    def register_update_func(self, f):
        pass

    def register_all_func(self, f):
        pass


class AllButton(Gtk.ToggleButton):
    def __init__(self, parent_field, id_num=0):
        Gtk.ToggleButton.__init__(self)
        self.set_tooltip_text(_("Apply current value to all tracks"))
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.connect("toggled", self.set_all_mode)
        self.field = parent_field
        self.id_num = id_num
        im = Gtk.Image.new_from_icon_name('edit-copy', Gtk.IconSize.BUTTON)
        self.set_image(im)
        self.set_active(True)
        self.set_active(False)

    def set_all_mode(self, w=None, do_apply=True):

        if self.get_active and do_apply and self.field.parent_row:
            tag = self.field.parent_row.tag
            multi_id = self.field.parent_row.multi_id
            if self.field.all_func is not None:
                self.field.all_func(tag, multi_id, self.field.get_value, self.id_num)


class SavingProgressWindow(Gtk.Window):
    def __init__(self, parent, total, text=_("Saved %(count)s of %(total)s.")):
        Gtk.Window.__init__(self)
        self.count = 0
        self.total = total
        self.text = text

        if parent:
            self.set_transient_for(parent)
        self.set_modal(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_focus_on_map(False)
        self.add(Gtk.Frame())
        self.get_child().set_shadow_type(Gtk.ShadowType.OUT)
        vbox = Gtk.Box(spacing=12, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(12)
        self._label = Gtk.Label()
        self._label.set_use_markup(True)
        self._label.set_markup(self.text % {'count': 0, 'total': self.total})
        vbox.pack_start(self._label, True, True, 0)
        self._progress = Gtk.ProgressBar()
        self._progress.set_size_request(300, -1)
        vbox.pack_start(self._progress, True, True, 0)

        self.get_child().add(vbox)

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.show_all()
        while Gtk.events_pending():
            Gtk.main_iteration()

    def step(self):
        self.count += 1
        self._progress.set_fraction(common.clamp(self.count / float(self.total), 0, 1))
        self._label.set_markup(self.text % {'count': self.count, 'total': self.total})
        while Gtk.events_pending():
            Gtk.main_iteration()


# vim: et sts=4 sw=4
