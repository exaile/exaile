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

import copy
from collections import OrderedDict
import datetime
import io
import os
import string

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from xl.nls import gettext as _
from xl.metadata._base import CoverImage
from xl import (
    common,
    metadata,
    trax,
    xdg
)

from xlgui.widgets import dialogs
from xl.metadata.tags import tag_data, get_default_tagdata


class TrackPropertiesDialog(GObject.GObject):

    def __init__(self, parent, tracks, current_position=0, with_extras=False):
        """
            :param parent: the parent window for modal operation
            :type parent: :class:`Gtk.Window`
            :param tracks: the tracks to process
            :type tracks: list of :class:`xl.trax.Track` objects
            :param current_position: the position of the currently
                selected track in the list
            :type current_position: int
            :param with_extras: whether there are extra, non-selected tracks in
                `tracks` (currently happens when only 1 track is selected)
            :type with_extras: bool
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
            parent=self.builder.get_object('main_container'),
            buttons=Gtk.ButtonsType.CLOSE
        )

        self.remove_tag_button = self.builder.get_object('remove_tag_button')
        self.cur_track_label = self.builder.get_object('current_track_label')
        self.apply_button = self.builder.get_object('apply_button')
        self.prev_button = self.builder.get_object('prev_track_button')
        self.next_button = self.builder.get_object('next_track_button')

        self.tags_table = self.builder.get_object('tags_table')
        self.properties_table = self.builder.get_object('properties_table')
        self.rows = []

        self.new_tag_combo = self.builder.get_object('new_tag_combo')
        self.new_tag_combo_list = Gtk.ListStore(str, str)
        for tag, tag_info in tag_data.iteritems():
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
            'album',
            'discnumber',
            'date',
            'genre',
            'cover',
            'comment',
            '__startoffset',
            '__stopoffset'
        ]
        
        self.def_tags = OrderedDict([(tag, tag_data[tag]) for tag in def_tags])

        # Store the tracks and a working copy
        self.tracks = tracks
        self.trackdata = self._tags_copy(tracks)
        self.trackdata_original = self._tags_copy(tracks)
        self.current_position = current_position

        self._build_from_track(self.current_position)

        self.dialog.resize(600, 350)
        self.dialog.show()

        self.rows[0].field.grab_focus()

    def _get_field_widget(self, tag_info, ab):
        tag_type = tag_info.type
                
        if tag_type == 'int':
            field = TagNumField(
                tag_info.min,
                tag_info.max,
                all_button=ab
            )
        elif tag_type == 'dblnum':
            field = TagDblNumField(
                tag_info.min,
                tag_info.max,
                all_button=ab
            )
        elif tag_type == 'time':
            field = TagNumField(
                tag_info.min,
                tag_info.max,
                all_button=ab
            )
        elif tag_type == 'image':
            field = TagImageField()
        elif tag_type == 'multiline':
            field = TagTextField(all_button=ab)
        else:
            field = TagField(all_button=ab)
            
        return field

    def _tags_copy(self, tracks):
        l = []
        for track in tracks:
            t = {}
            for tag, tag_info in self.def_tags.iteritems():
                if tag_info.use_disk:
                    tagval = track.get_tag_disk(tag)
                else:
                    tagval = track.get_tag_raw(tag)
                
                if tagval:
                    if isinstance(tagval, list):
                        t[tag] = tagval[:]
                    else:
                        t[tag] = [ tagval ]
                else:
                    t[tag] = ['']

                if tag_info.type == 'dblnum':
                    for i, entry in enumerate(t[tag]):
                        if len(entry.split('/')) < 2:
                            t[tag][i] += '/0'

            for tag in track.list_tags():
                if tag not in self.def_tags:
                    tagval = track.get_tag_raw(tag)
                    if isinstance(tagval, list):
                        t[tag] = tagval[:]
                    else:
                        t[tag] = [ tagval ]

            l.append(t)

        return l

    def _tags_write(self, data):
        errors = []
        dialog = SavingProgressWindow(self.dialog, len(data))
        for n, trackdata in data:
            track = self.tracks[n]
            poplist = []

            for tag in trackdata:
                if not tag.startswith("__"):
                    if tag in ("tracknumber", "discnumber") \
                       and trackdata[tag] == ["0/0"]:
                        poplist.append(tag)
                        continue
                    track.set_tag_raw(tag, trackdata[tag])
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
                track.set_tag_raw(tag, None)

            if not track.write_tags():
                errors.append(track.get_loc_for_io());
                
            trax.track._CACHER.remove(track)
            dialog.step()
        dialog.destroy()
        
        if len(errors) > 0:
            self.message.clear_buttons()
            self.message.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            self.message.show_error(
                _('Writing of tags failed'),
                _('Tags could not be written to the following files:\n'
                  '{files}').format(files='\n'.join(errors))
            )

    def _build_from_track(self, position):

        for table in [self.tags_table, self.properties_table]:
            for child in table.get_children():
                table.remove(child)

            table.resize(1,4)

        self.rows = []

        # Previous, next and current track label
        self.prev_button.set_sensitive(True)
        self.next_button.set_sensitive(True)

        if position == 0:
            self.prev_button.set_sensitive(False)

        if position == (len(self.trackdata) - 1):
            self.next_button.set_sensitive(False)

        self.cur_track_label.set_text(
            _("Editing track %(current)d of %(total)d") % {
                'current': self.current_position + 1,
                'total': len(self.tracks)
            }
        )

        trackdata = self.trackdata[position]

        if len(self.trackdata) == 1:
            ab = False
        else:
            ab = True

        for tag, tag_info in self.def_tags.iteritems():
            
            for i, entry in enumerate(trackdata.get(tag, [''])):
                
                field = self._get_field_widget(tag_info, ab)
                
                row = TagRow(self, self.tags_table, field, tag, entry, i)
                self.rows.append(row)

                try:
                    if self.trackdata[self.current_position][tag] != \
                       self.trackdata_original[self.current_position][tag]:
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
                    self.rows.append(TagRow(self, self.tags_table, field, tag, entry, i))
                else:
                    field = PropertyField(tag_info.type)
                    self.rows.append(TagRow(self, self.properties_table, field, tag, entry, i))
        
        self._check_for_changes()
        self._build_tables_from_rows()

    def _build_tables_from_rows(self):

        tables = [self.tags_table, self.properties_table]

        #clear the tables to start with
        for table in tables:
            for child in table.get_children():
                table.remove(child)

            table.resize(1,4)

        cur_row = {tables[0]:0, tables[1]:0}

        paddings = [0, Gtk.AttachOptions.FILL, Gtk.AttachOptions.FILL|Gtk.AttachOptions.EXPAND, 0]

        for row in self.rows:
            columns = [
                    Gtk.Label(),
                    row.label,
                    row.field,
                    Gtk.Label()]

            for col, content in enumerate(columns):
                row.table.attach(content, col, col + 1, cur_row[row.table],
                        cur_row[row.table] + 1,
                        xoptions=paddings[col], yoptions=0)

            cur_row[row.table] += 1
            row.table.resize(cur_row[row.table] + 1, 4)

        for table in tables:
            table.show_all()

        self.remove_tag_button.toggled()

    def on_apply_button_clicked(self, w):
        modified = []
        for n, trackdata in enumerate(self.trackdata):
            if trackdata != self.trackdata_original[n]:
                modified.append((n, trackdata))

        if modified:
            if len(modified) != 1:
                dialog = Gtk.MessageDialog(None,
                    Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION,
                    Gtk.ButtonsType.YES_NO,
                    _('Are you sure you want to apply the changes to all tracks?'),
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

    def on_close_button_clicked(self, w):
        if self.trackdata != self.trackdata_original:
            def on_response(message, response):
                """
                    Applies changes before closing if requested
                """
                if response == Gtk.ResponseType.APPLY:
                    self.apply_button.clicked()

                self.dialog.destroy()

            self.message.connect('response', on_response)
            self.message.clear_buttons()
            self.message.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            self.message.add_button(Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY)
            self.message.show_question(
                _('Apply changes before closing?'),
                _('Your changes will be lost if you do not apply them now.')
            )
        else:
            self.dialog.destroy()

    def on_prev_track_button_clicked(self, widget):
        self.current_position -= 1
        self._build_from_track(self.current_position)

    def on_next_track_button_clicked(self, widget):
        self.current_position += 1
        self._build_from_track(self.current_position)

    def on_title_case_button_clicked(self, w):
        for row in self.rows:
            if isinstance(row.field, TagField) \
               or isinstance(row.field, TagTextField):
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

class TagRow(object):
    def __init__(self, parent, parent_table, field, tag_name, value, multi_id):
        self.parent = parent
        self.table = parent_table
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

        self.name = name
        self.label = Gtk.Label()

        if multi_id == 0:
            self.label.set_text(_('%s:') % name.capitalize())
            self.label.create_pango_context()
            self.label.set_alignment(0.0, .50)

        self.clear_button = Gtk.Button()
        self.clear_button.set_image(Gtk.Image.new_from_stock(
            Gtk.STOCK_CLEAR, Gtk.IconSize.BUTTON))
        self.clear_button.set_relief(Gtk.ReliefStyle.NONE)
        self.clear_button.connect("clicked", self.clear)

        if not isinstance(field, PropertyField):
            self.field.pack_start(self.clear_button, False, False, 0)

        self.field.show_all()

        # Remove mode settings
        self.remove_mode = False
        self.remove_button = Gtk.Button()
        self.remove_button.set_image(Gtk.Image.new_from_stock(
            Gtk.STOCK_REMOVE, Gtk.IconSize.BUTTON))
        self.remove_button.connect("clicked", parent.remove_row, self.tag, self.multi_id)

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

class TagField(Gtk.HBox):
    def __init__(self, all_button=True):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

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

        if all_vals != None and self.all_button != None:
            # Set the value of the all button
            self.all_button.set_active(all(val == v for v in all_vals))

    def get_value(self):
        return unicode(self.field.get_text(), 'utf-8')

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.field.connect("changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f

class TagTextField(Gtk.HBox):
    def __init__(self, all_button=True):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

        self.buffer = Gtk.TextBuffer()
        self.field = Gtk.TextView.new_with_buffer(self.buffer)
        self.field.set_size_request(200, 150) # XXX
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

        if all_vals != None and self.all_button != None:
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
        return unicode(self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(),
            True
        ), 'utf-8')

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.buffer.connect("changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f

class TagNumField(Gtk.HBox):
    def __init__(self, min=0, max=10000, step=1, page=10, all_button=True):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

        # Create the widgets
        self.field = Gtk.SpinButton()
        self.field.set_range(min, max)
        self.field.set_increments(step, page)
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
            if val != '':
                self.field.set_value(float(val))
            else:
                self.field.set_value(0)

        if all_vals != None and self.all_button != None:
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
        return unicode(int(self.field.get_value()))

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        self.field.connect("value-changed", f, tag, multi_id, self.get_value)

    def register_all_func(self, f):
        self.all_func = f

class TagDblNumField(Gtk.HBox):

    def __init__(self, min=0, max=10000, step=1, page=10, all_button=True):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

        self.field = [Gtk.SpinButton(), Gtk.SpinButton()]
        self.all_func = None
        self.parent_row = None
        for f in self.field:
            f.set_range(min, max)
            f.set_increments(step, page)

        # TRANSLATORS: This is the 'of' between numbers in fields like
        # tracknumber, discnumber, etc. in the tagger.
        lbl = Gtk.Label(label=_('of:'))
        self.all_button = [None, None]
        if all_button:
            self.all_button = [AllButton(self), AllButton(self, 1)]

        self.pack_start(self.field[0], True, True, 0)
        if all_button and self.all_button[0] != None:
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
                if vals[x] != '':
                    self.field[x].set_value(float(vals[x]))
                else:
                    self.field[x].set_value(0)

        if all_val != None:
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

                if self.all_button[i] != None:
                    if flags[i]:
                        self.all_button[i].set_active(True)
                    else:
                        self.all_button[i].set_active(False)

    def get_value(self):
        f0 = unicode(int(self.field[0].get_value()))
        f1 = unicode(int(self.field[1].get_value()))
        return f0 + '/' + f1

    def register_update_func(self, f):
        tag = self.parent_row.tag
        multi_id = self.parent_row.multi_id
        val = unicode(self.field[0].get_value()) + '/' \
                + unicode(self.field[1].get_value())
        self.field[0].connect("value-changed", f, tag, multi_id, self.get_value)
        self.field[1].connect("value-changed", f, tag, multi_id, self.get_value)

class TagImageField(Gtk.HBox):
    def __init__(self, all_button=True):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

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
                'options': {'quality': '90'}
            },
            'image/png': {
                'title': _('PNG image'),
                'type': 'png',
                'options': {}
            },
            'image/': {
                'title': _('Image'),
                # Store unknown images as JPEG
                'type': 'jpeg',
                'options': {'quality': '90'}
            },
            # TODO: Handle linked images
            '-->': {
                'title': _('Linked image')
            }
        }

        builder = Gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'trackproperties_dialog_cover_row.ui'))
        builder.connect_signals(self)
        cover_row = builder.get_object('cover_row')
        cover_row.reparent(self)

        button = builder.get_object('button')
        button.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        button.drag_dest_add_uri_targets()

        self.image = builder.get_object('image')
        self.info_label = builder.get_object('info_label')
        self.type_model = builder.get_object('type_model')
        self.type_selection = builder.get_object('type_selection')
        self.type_selection.set_sensitive(False)
        self.description_entry = builder.get_object('description_entry')
        self.description_entry.set_sensitive(False)

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

        if not None in (all_vals, self.all_button):
            self.all_button.set_active(all(val == v for v in all_vals))

    def get_value(self):
        if not self.pixbuf:
            return None

        mime = self.mime_info[self.info.mime]
        # Retrieve proper image data
        writer = io.BytesIO()
        self.pixbuf.save_to_callback(writer.write, mime['type'], mime['options'])
        # Move to the beginning of the buffer to allow read operations
        writer.seek(0)

        return self.info._replace(data=writer.read())

    def call_update_func(self):
        """
            Wrapper around the update function
        """
        if not self.update_func or self.batch_update:
            return

        self.update_func(self, self.parent_row.tag, self.parent_row.multi_id, self.get_value)

    def set_pixbuf(self, pixbuf, mime=None):
        """
            Updates the displayed cover image and info values
        """
        self.pixbuf = pixbuf

        if pixbuf is None:
            self.image.set_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.DIALOG)
            self.info_label.set_markup('')
        else:
            self.image.set_from_pixbuf(pixbuf.scale_simple(
                100, 100, GdkPixbuf.InterpType.BILINEAR))

            width, height = pixbuf.get_width(), pixbuf.get_height()
            if mime is None:
                # TRANSLATORS: do not translate 'width' and 'height'
                markup = _('{width}x{height} pixels').format(width=width, height=height)
            else:
                # TRANSLATORS: do not translate 'format', 'width', and 'height'
                markup = _('{format} ({width}x{height} pixels)').format(
                    format=self.mime_info.get(mime, self.mime_info['image/'])['title'],
                    width=width, height=height
                )
            self.info_label.set_markup(markup)

            self.info = self.info._replace(mime=mime)

    def on_button_clicked(self, button):
        """
            Allows setting the cover image using a file selection dialog
        """
        dialog = dialogs.FileOperationDialog(
            title=_('Select image to set as cover'),
            parent=self.get_toplevel(),
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                     Gtk.STOCK_OK, Gtk.ResponseType.OK)
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
                self.set_pixbuf(pixbuf, info['mime_types'][0])
                self.type_selection.set_active(self.default_type)
                self.type_selection.set_sensitive(True)
                self.description_entry.set_text(os.path.basename(filename).rsplit('.', 1)[0])
                self.description_entry.set_sensitive(True)
                self.batch_update = False
                self.call_update_func()

        dialog.destroy()

    def on_button_drag_data_received(self, widget, context, x, y, selection, info, time):
        """
            Allows setting the cover image via drag and drop
        """
        if selection.target == 'text/uri-list':
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
                self.description_entry.set_text(os.path.basename(filename).rsplit('.', 1)[0])
                self.description_entry.set_sensitive(True)
                self.batch_update = False
                self.call_update_func()

    def on_type_selection_changed(self, combobox):
        """
            Notifies about changes in the cover type
        """
        self.info = self.info._replace(type=self.type_model[combobox.get_active()][0])
        self.call_update_func()

    def on_description_entry_changed(self, entry):
        """
            Notifies about changes in the cover description
        """
        self.info = self.info._replace(desc=entry.get_text())
        self.call_update_func()

class PropertyField(Gtk.HBox):
    def __init__(self, property_type='text'):
        Gtk.HBox.__init__(self, homogeneous=False, spacing=5)

        # Informs of special formatting required
        self.property_type = property_type
        self.field = Gtk.Entry()
        self.field.set_editable(False)
        self.pack_start(self.field, True, True, 0)
        self.parent_row = None

        if self.property_type == 'location':
            self.folder_button = Gtk.Button()
            self.folder_button.set_tooltip_text(_('Open Directory'))
            self.folder_button.set_image(Gtk.Image.new_from_stock(
                Gtk.STOCK_OPEN, Gtk.IconSize.BUTTON))
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
            d = GLib.DateTime.new_from_timeval_local(val)
            val = d.format("%c")
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
        common.open_file_directory(self.field.get_text().decode('utf-8'))

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
        self.set_active(True)
        self.set_active(False)

    def set_all_mode(self, w=None, do_apply=True):

        if self.get_active():
            if do_apply and self.field.parent_row:
                tag = self.field.parent_row.tag
                multi_id = self.field.parent_row.multi_id
                if self.field.all_func != None:
                    self.field.all_func(tag, multi_id, self.field.get_value, self.id_num)
            im = Gtk.Image()
            im.set_from_stock(Gtk.STOCK_DND_MULTIPLE, Gtk.IconSize.BUTTON)
            self.set_image(im)
        else:
            im = Gtk.Image()
            im.set_from_stock(Gtk.STOCK_DND, Gtk.IconSize.BUTTON)
            self.set_image(im)


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
        vbox = Gtk.VBox(spacing=12)
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
        self._progress.set_fraction(
                common.clamp(self.count / float(self.total), 0, 1))
        self._label.set_markup(self.text % {
            'count': self.count,
            'total': self.total
        })
        while Gtk.events_pending():
            Gtk.main_iteration()


# vim: et sts=4 sw=4
