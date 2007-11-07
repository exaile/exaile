# Copyright (C) 2006 Adam Olsen
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

from xl import media, library, common, xlmisc, editor
from gettext import gettext as _, ngettext
import gtk, gtk.glade
import re, os
import playlist as trackslist

TAG_STRINGS = {
    "title":            _('Title'),
    "version":          _('Version'),
    "album":            _('Album'),
    "tracknumber":      _('Track Number'),
    "artist":           _('Artist'),
    "genre":            _('Genre'),
    "performer":        _('Performer'),
    "copyright":        _('Copyright'),
    "license":          _('License'),
    "organization":     _('Organization'),
    "description":      _('Description'),
    "location":         _('Location'),
    "contact":          _('Contact'),
    # TRANSLATORS: International Standard Recording Code
    "isrc":             _('ISRC'),
    "date":             _('Date'),
    "arranger":         _('Arranger'),
    "author":           _('Author'),
    "composer":         _('Composer'),
    "conductor":        _('Conductor'),
    "lyricist":         _('Lyricist'),
    "discnumber":       _('Disc Number'),
    "labelid":          _('Label ID'),
    "part":             _('Part'),
    "website":          _('Website'),
    "language":         _('Language'),
    # TRANSLATORS: Beats per minute
    "bpm":              _('BPM'),
    "albumartist":      _('Album Artist'),
    "originaldate":     _('Original Date'),
    "originalalbum":    _('Original Album'),
    "originalartist":   _('Original Artist'),
    "recordingdate":    _('Recording Date'),
    "encodedby":        _('Encoded By'),
}

TAGNAME, VALUE, OLDVALUE, ERROR, ADDED, REMOVED, EDITED = range(0,7)

class TrackEditor(object):
    """
        A track properties editor
    """


    def __init__(self, exaile, tracks):
        """
            Initializes the panel 
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = gtk.glade.XML('exaile.glade', 'TrackEditorDialog', 'exaile')
        self.dialog = self.xml.get_widget('TrackEditorDialog')
        self.dialog.set_transient_for(self.exaile.window)
        self.action_area = self.xml.get_widget('track_editor_action_area')

        # FIXME: most of the metadata isn't stored in the database
        # so we have to load it explicitly from disk each time
        self.songs = [media.read_from_path(song.io_loc) 
                                    for song in tracks.get_selected_tracks()]
        
        self.count = len(self.songs)
        self.unsaved_tags = {}
        self.tags_to_add = {}
        self.selected_songs = editor.TrackGroup() 

        self.get_widgets()
        self.setup_left()
        self.setup_right()
        self.connect_events()

        self.tags_save.set_sensitive(False)
        self.tags_clear.set_sensitive(False)

        self.on_trackview_selection_changed(self.trackview)

        self.dialog.show()

    def get_widgets(self):
        """
            Gets all widgets from the glade definition file
        """
        xml = self.xml
        self.trackview = xml.get_widget('te_trackview')
        self.trackview_selection = self.trackview.get_selection()
        self.trackview_down = xml.get_widget('te_trackview_down')
        self.trackview_up = xml.get_widget('te_trackview_up')
        self.trackview_remove = xml.get_widget('te_trackview_remove')

        self.nb = xml.get_widget('te_nb')
        
        self.tag_view = xml.get_widget('te_tag_view')
        self.tags_add = xml.get_widget('te_tags_add')
        self.tags_remove = xml.get_widget('te_tags_remove')
        self.tags_clear = xml.get_widget('te_tags_clear')
        self.tags_save = xml.get_widget('te_tags_save')

        self.tagsfrompath_cb = xml.get_widget('te_path_patterns_cb')
        self.path_pattern_add = xml.get_widget('te_path_pattern_add')
        self.path_pattern_remove = xml.get_widget('te_path_pattern_remove')
        self.tagsfrompath_view = xml.get_widget('te_tagsfrompath_view')
        self.replace_tags1 = xml.get_widget('te_replace_tags1')
        self.replace_tags2 = xml.get_widget('te_replace_tags2')
        self.tagsfrompath_save = xml.get_widget('te_tagsfrompath_save')
        
        self.tracknum_start = xml.get_widget('te_tracknum_start')
        self.tracknum_total = xml.get_widget('te_tracknum_total')
        self.tracknum_view = xml.get_widget('te_tracknum_view')
        self.tracknum_save = xml.get_widget('te_tracknum_save')
        self.trackview = xml.get_widget('te_trackview')

    def connect_events(self):
        """
            Sets up the callbacks for all the events
        """
        self.trackview_down.connect('clicked', self.on_trackview_updown_clicked, False)
        self.trackview_up.connect('clicked', self.on_trackview_updown_clicked, True)
        self.trackview_remove.connect('clicked', self.on_trackview_remove_clicked)
        self.trackview_selection.connect('changed', self.on_trackview_selection_changed)

        self.nb.connect('switch_page', self.on_nb_page_switched)

        self.tags_clear.connect('clicked', self.on_tags_clear_clicked)
        self.tags_save.connect('clicked', self.on_tags_save_clicked)
        self.tags_remove.connect('clicked', self.on_tags_remove_clicked)
        self.tags_add.connect('clicked', self.on_tags_add_clicked)

        self.tagsfrompath_cb.connect('changed', self.on_path_patterns_changed)
        self.path_pattern_add.connect('clicked', self.on_path_pattern_add_clicked)
        self.path_pattern_remove.connect('clicked', self.on_path_pattern_remove_clicked)
        self.tagsfrompath_save.connect('clicked', self.on_tagsfrompath_save_clicked)

        self.tracknum_view.get_model().connect('row-deleted', \
            lambda *x: self.update_tracknum_view(True))

        self.tracknum_start.connect('output', \
            lambda *x: self.update_tracknum_sb())
        self.tracknum_start.connect('value-changed', \
            lambda *x: self.update_tracknum_view())

        self.tracknum_total.connect('output', \
            lambda *x: self.update_tracknum_sb())
        self.tracknum_total.connect('value-changed', \
            lambda *x: self.update_tracknum_view())

        self.tracknum_save.connect('clicked', self.on_tracknum_save_clicked)

    def setup_left(self):
        """
            Build the treeview in the left pane
        """
        tv = self.trackview
        liststore = gtk.ListStore(str, int)
        selection = self.trackview_selection
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Tracks')

        tv.set_model(liststore)
        tv.append_column(col)
        col.pack_start(cell, True)
        col.add_attribute(cell, 'text', 0)
        tv.set_reorderable(True)

        for i, song in enumerate(self.songs):
            liststore.append([song.filename, i])

        selection.select_path((0,))
        return

    def setup_right(self):
        """
            Set up the treeviews in the tabs etc
        """
        # tags view
        # TRANSLATORS: A media file tag
        tag_column = gtk.TreeViewColumn(_("Tag"))
        tag_cell = gtk.CellRendererText()
        value_column = gtk.TreeViewColumn(_("Value"))
        value_cell = gtk.CellRendererText()
        value_cell.set_property("editable", True)
        value_cell.connect("edited", self.on_tag_cell_edited)

        # the tag itself, tag ID ('artist' instead of 
        # _('Artist')), the index (since every tag value is a
        # list), and whether a tag is
        # being removed, added or updated.
        model = gtk.ListStore(str, str, int, bool, bool, bool, bool)
        self.tag_view.set_model(model)

        self.tag_view.append_column(tag_column)
        tag_column.pack_start(tag_cell, True)
        tag_column.add_attribute(tag_cell, 'strikethrough', REMOVED)
        tag_column.set_cell_data_func(tag_cell, self.tagname_data_func)

        self.tag_view.append_column(value_column)
        value_column.pack_start(value_cell, True)
        value_column.add_attribute(value_cell, 'strikethrough', REMOVED)
        value_column.set_cell_data_func(value_cell, self.tagvalue_data_func)

        # track num view
        track_column = gtk.TreeViewColumn(_('Track'))
        track_cell = gtk.CellRendererText()
        num_column = gtk.TreeViewColumn(_('Track Number'))
        num_cell = gtk.CellRendererText()
        total_column = gtk.TreeViewColumn(_('Total Tracks'))
        total_cell = gtk.CellRendererText()

        # song object, title, tracknum, total tracks
        model = gtk.ListStore(object, str, int, int)
        self.tracknum_view.set_model(model)

        self.tracknum_view.append_column(track_column)
        track_column.pack_start(track_cell, True)
        track_column.add_attribute(track_cell, 'text', 1)

        self.tracknum_view.append_column(num_column)
        num_column.pack_start(num_cell, True)
        num_column.add_attribute(num_cell, 'text', 2)

        self.tracknum_view.append_column(total_column)
        total_column.pack_start(total_cell, True)
        total_column.add_attribute(total_cell, 'text', 3)

        # tags from path combobox and view

        def sep_func(model, iter, data=None):
            """
                Draw a separator after the default patterns
            """
            return int(model.get_string_from_iter(iter)) \
                        == len(TagsFromPattern.default_patterns)

        self.tagsfrompath_cb.set_row_separator_func(sep_func)
        self.populate_tagsfrompath_cb()
        self.tagsfrompath_cb.set_active(0)


        # this builds the model and everything, no need to do it here
        self.update_tagsfrompath_view()
        
        # update this view since its tab is displayed by default
        self.update_tag_view()

        return
    
    def tagname_data_func(self, column, cell, model, iter, *args):
        """
            Converts the tagname to a translated value
        """
        cell.set_property('markup', TAG_STRINGS[model.get_value(iter, TAGNAME)])
        
    def tagvalue_data_func(self, column, cell, model, iter, *args):
        """
            Sets all kinds of properties for the tag value
        """
        tag, value, oldvalue, error, added, removed, edited = \
            model[model.get_string_from_iter(iter)]

        if error:
            cell.set_property('markup', get_error(error))
        else:
            cell.set_property('markup', value)
        cell.set_property('editable', not removed and not error)

    def get_selected_tracks(self):
        """
            Returns a TrackGroup of the selected tracks
        """
        (liststore, paths) = self.trackview_selection.get_selected_rows()
        ret = []
        for path in paths:
            iter = liststore.get_iter(path)
            i = liststore.get_value(iter, 1)
            ret.append(self.songs[i])
        return editor.TrackGroup(ret)

    def update_tag_view(self):
        """
            Display tags
        """
        model = self.tag_view.get_model()
        self.tag_view.set_model(None)
        model = self.selected_songs.make_model()
        self.tag_view.set_model(model)
        self.tags_save.set_sensitive(False)
        self.tags_clear.set_sensitive(False)

    def update_tagsfrompath_view(self):
        """
            The most annoying treeview to update ;)
        """
        view = self.tagsfrompath_view
        if self.selected_songs: pattern_text = self.tagsfrompath_cb.get_active_text()
        else: 
            pattern_text = ""
        if not pattern_text: 
            self.tagsfrompath_view.set_model(None)
            return
        try: pattern = TagsFromPattern(pattern_text)
        except re.error: 
            xlmisc.log('Tags From Pattern: invalid pattern')
            return

        invalid = []
        for header in pattern.headers:
            if not min([track.can_change(header) \
                for track in self.selected_songs]):
                invalid.append(header)
        
        if len(invalid):
            msg = ngettext("All files currently selected do not support"
                           " editing the tag <b>%s</b>.",
                           "All files currently selected do not support"
                           " editing the tags <b>%s</b>.",
                           len(invalid))
            common.error(self.dialog, msg % ', '.join(invalid))
            pattern = TagsFromPattern('')

        view = self.tagsfrompath_view

        view.set_model(None)
        model = gtk.ListStore(object, str, *([str] * len(pattern.headers)))
        for col in view.get_columns():
            view.remove_column(col)
        
        col = gtk.TreeViewColumn(_('File'), gtk.CellRendererText(), text=1)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        view.append_column(col)

        for i, header in enumerate(pattern.headers):
            render = gtk.CellRendererText()
            render.set_property('editable', True)
            render.connect('edited', self.tagsfrompath_row_edited, model, i + 2)
            col = gtk.TreeViewColumn(TAG_STRINGS[header], render, text=i + 2)
            col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            view.append_column(col)

        for song in self.selected_songs:
            basename = os.path.basename(song.io_loc)
            row = [song, basename]
            match = pattern.match(song)
            for h in pattern.headers:
                text = match.get(h, '')
                #for f in self.filters:
                #    if f.active: text = f.filter(h, text)
                if not song.is_multi():
                    text = u", ".join(text.split("\n"))
                row.append(text)
            model.append(row=row)

        view.set_model(model)
        return

    def tagsfrompath_row_edited(self, renderer, path, new, model, colnum):
        row = model[path]
        if row[colnum] != new:
            row[colnum] = new

    def update_tracknum_view(self, reordered=False):
        """
            Update the track numbering view. If reordered is True,
            it means we will preserve the order of the songs.
        """
        self.update_tracknum_sb()
        start = self.tracknum_start.get_value()
        total = self.tracknum_total.get_value()
        #if total == 0: total = None
        model = self.tracknum_view.get_model()

        if reordered:
            for i, row in enumerate(model):
                row[2] = i + start
        else:
            model.clear()
            for i, song in enumerate(self.selected_songs):
                model.append([song, song.title, i + start, total])
        
        return

    def populate_tagsfrompath_cb(self):
        """
            Constructs the combobox in the Tags from Path tab
        """
        cb = self.tagsfrompath_cb
        cb.set_active(-1)
        cb.get_model().clear()
        map(cb.append_text, TagsFromPattern.default_patterns)
        patterns = self.exaile.settings.get_list('tagsfrompath_patterns', [])

        if patterns:
            map(cb.append_text, [''] + patterns)
        else:
            return

    def on_nb_page_switched(self, nb, page, page_num, *args):
        """
            Update the affected tree view when the page is changed
        """
        if self.check_changed():
            msg = _('Do you want to save your changes in the Tags tab?')
            if common.yes_no_dialog(self.dialog, msg) == gtk.RESPONSE_YES:
                self.write_tags()
                self.update_tag_view()
        return

    def on_trackview_remove_clicked(self, widget, *args):
        """
            Remove the selected tracks from the list
        """
        selection = self.trackview_selection
        (liststore, paths) = selection.get_selected_rows()
        
        paths.sort(reverse=True)
        for path in paths:
            iter = liststore.get_iter(path)
            self.songs.pop(liststore.get_value(iter, 1))
            liststore.remove(iter)
        selection.select_path(0)

    def on_trackview_updown_clicked(self, widget, up):
        """
            Move the selection one step up or down
        """
        selection = self.trackview_selection
        (liststore, paths) = selection.get_selected_rows()
        size = len(self.trackview)

        if not paths: return

        paths.sort()
        old = int(paths[0][0])

        if (up and old == 0) or (not up and old == size - 1):
            return
        else:
            if up:
                new = old - 1
            else:
                new = old + 1

        selection.unselect_all()
        selection.select_path(str(new))

    def check_changed(self):
        """
            Check whether anything has changed in the tag view
        """
        model = self.tag_view.get_model()
        for row in model:
            if True in [row[ADDED], row[REMOVED], row[EDITED]]:
                return True
        return False

    def on_trackview_selection_changed(self, widget, *args):
        """
            Update the track list inside the active tab
        """
        if self.check_changed():
            msg = _('Do you want to save your changes in the Tags tab?')
            if common.yes_no_dialog(self.dialog, msg) == gtk.RESPONSE_YES:
                self.write_tags()

        self.selected_songs = self.get_selected_tracks()

        self.update_tag_view()
        self.update_tagsfrompath_view()
        self.update_tracknum_view()
        return

    def on_tag_cell_edited(self, widget, path, new_text, *args):
        """
            Gets called whenever the user has edited a row in the tag view.
        """
        if new_text == widget.get_property('text'): return
        
        model = self.tag_view.get_model()
        iter = model.get_iter(path)

        oldval = model.get_value(iter, VALUE)
        model.set_value(iter, OLDVALUE, oldval)
        model.set_value(iter, VALUE, new_text)
        model.set_value(iter, EDITED, True)

        self.tags_save.set_sensitive(True)
        self.tags_clear.set_sensitive(True)

    def on_tags_clear_clicked(self, widget, *args):
        """
            Remove the changes from the tag view
        """
        self.update_tag_view()

    def on_tags_save_clicked(self, widget, *args):
        """
            Write changes and refresh the affected rows in the main window
        """
        self.write_tags()
        self.update_tag_view()

    def write_tags(self):
        """
            Write the changes to disk
        """
        model = self.tag_view.get_model()
        errors = self.selected_songs.write_tags(self.exaile, model)

        if errors:
            message = ""
            count = 1
            for error in errors:
                message += "%d: %s\n" % (count, error)
                count += 1
            self.dialog.hide()
            common.scrolledMessageDialog(self.exaile.window, message, _("Some errors"
                " occurred")) 

    def on_tags_add_clicked(self, widget, *args):
        """
            Add a tag to the track(s)
        """
        dialog = AddTagDialog(self.dialog)
        
        if dialog.run() != gtk.RESPONSE_OK:
            dialog.destroy()
            return
        try:
            tag = dialog.get_tag()
            value = dialog.get_value()

            if self.selected_songs.get_tag_status(tag) \
                == editor.TAG_UNSUPPORTED:
                raise xlmisc.TagUnsupportedException(tag)

            row = [tag, value, None, editor.TAG_NO_ERROR, True, False, False]
            self.tag_view.get_model().append(row)
            self.tags_save.set_sensitive(True)
            self.tags_clear.set_sensitive(True)
        except xlmisc.TagUnsupportedException, e:
            msg =_("The tag <b>%s</b> is not supported"
                   " by all selected tracks") % e.tag
            common.error(self.dialog, msg)
        except:
            xlmisc.log_exception()
        dialog.destroy()

        return

    def on_tags_remove_clicked(self, widget, *args):
        """
            Set the tag in question to None and remove from the tag list
        """
        (model, iter) = self.tag_view.get_selection().get_selected()
        model.set_value(iter, REMOVED, True)
        self.tags_save.set_sensitive(True)
        self.tags_clear.set_sensitive(True)
        
    def on_path_patterns_changed(self, widget, *args):
        """
            Update the treeview
        """
        self.update_tagsfrompath_view()
        return

    def on_path_pattern_add_clicked(self, widget, *args):
        """
            Pop up a dialog so the user can add a new path pattern
        """
        dialog = gtk.Dialog()
        dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, \
            gtk.STOCK_OK, gtk.RESPONSE_OK)
        entry = gtk.Entry()
        dialog.vbox.pack_start(entry, True, True)
        
        dialog.show_all()
        resp = dialog.run()
        val = unicode(entry.get_text(), 'utf-8')
        dialog.destroy()
        if resp != gtk.RESPONSE_OK or not val:
            return

        patterns = self.exaile.settings.get_list('tagsfrompath_patterns', [])
        patterns.append(val)
        self.exaile.settings.set_list('tagsfrompath_patterns', patterns)
        self.populate_tagsfrompath_cb()
        act = len(patterns + TagsFromPattern.default_patterns) 
        self.tagsfrompath_cb.set_active(act) # select the last item

    def on_path_pattern_remove_clicked(self, widget, *args):
        """
            Remove the pattern from the combobox, if it's not a default one.
        """
        active = self.tagsfrompath_cb.get_active()
        l = len(TagsFromPattern.default_patterns)
        if active > l:
            patterns = self.exaile.settings.get_list('tagsfrompath_patterns', [])
            del(patterns[active - l - 1])
            self.exaile.settings.set_list('tagsfrompath_patterns', patterns)
            self.populate_tagsfrompath_cb()
            self.tagsfrompath_cb.set_active(0)
        elif active < l:
            common.error(self.dialog, _("The default patterns can't be removed."))
            pass

    def on_tagsfrompath_save_clicked(self, widget, *args):
        """
            Write to disk. If a value is None, don't write it
        """
        # FIXME: how do we know when a click on 'save' will blank
        # out a lot of valuable tags and when it's a wanted effect?
        append = self.replace_tags2.get_active()
        cols = self.tagsfrompath_view.get_columns()
        errors = []
        exaile = self.exaile
        for row in self.tagsfrompath_view.get_model():
            track = row[0]
            for i, col in enumerate(cols[1:]):
                if not row[i+2]: continue
                tag = (col.get_title()).lower().replace(' ', '')
                track.set_tag(tag, row[i + 2], append)
            try:
                media.write_tag(track)
                library.save_track_to_db(exaile.db, track)
                try:
                    exaile.all_songs.remove(exaile.all_songs.for_path(track.loc))
                    exaile.all_songs.append(track)
                except:
                    xlmisc.log_exception()

                exaile.tracks.refresh_row(track)
            except:
                errors.append(_("Unknown error writing tag for %s") % track.loc)
                xlmisc.log_exception()
        return

    def on_tracknum_save_clicked(self, widget, *args):
        """
            Write to disk
        """
        errors = []
        exaile = self.exaile
        
        for row in self.tracknum_view.get_model():
            track = row[0]
            if row[3]:
                track.set_tag('tracknumber', "/".join([str(row[2]), str(row[3])]))
            else:
                track.set_tag('tracknumber', row[2])
            try:
                media.write_tag(track)
                library.save_track_to_db(exaile.db, track)
                try:
                    exaile.all_songs.remove(exaile.all_songs.for_path(track.loc))
                    exaile.all_songs.append(track)
                except:
                    xlmisc.log_exception()

                exaile.tracks.refresh_row(track)
            except:
                errors.append(_("Unknown error writing tag for %s") % track.loc)
                xlmisc.log_exception()
        return

    def update_tracknum_sb(self):
        """
            Make sure we don't get any weird values for our track numbering
        """
        start = self.tracknum_start.get_value()
        total = self.tracknum_total.get_value()

        l = len(self.selected_songs)
        if total < (start + l - 1): 
            self.tracknum_total.set_value(start + l - 1)

class TagsFromPattern(object):
    """
        Gratefully borrowed from Quod Libet
        FIXME: you can't have the same tag twice (hard to fix)
    """
    default_patterns = ['<artist>/<album>/<tracknumber> - <title>', 
                        '<tracknumber>. <title>',
                        '<tracknumber> - <title>',
                        '<tracknumber> - <artist> - <title>',
                        '<artist> - <album>/<tracknumber>. <title>']
    def __init__(self, pattern):
        self.compile(pattern)

    def compile(self, pattern):
        self.headers = []
        self.slashes = len(pattern) - len(pattern.replace(os.path.sep,'')) + 1
        self.pattern = None

        # patterns look like <tagname> non regexy stuff <tagname> ...
        pieces = re.split(r'(<[A-Za-z0-9_]+>)', pattern)
        override = { '<tracknumber>': r'\d\d?', '<discnumber>': r'\d\d??' }
        for i, piece in enumerate(pieces):
            if not piece: continue
            if piece[0]+piece[-1] == '<>' and piece[1:-1].isalnum():
                piece = piece.lower()   # canonicalize to lowercase tag names
                pieces[i] = '(?P%s%s)' % (piece, override.get(piece, '.+?'))
                self.headers.append(piece[1:-1].encode("ascii", "replace"))
            else:
                pieces[i] = re.escape(piece)
                
        # some slight magic to anchor searches "nicely"
        # nicely means if it starts with a <tag>, anchor with a /
        # if it ends with a <tag>, anchor with .xxx$
        # but if it's a <tagnumber>, don't bother as \d+ is sufficient
        # and if it's not a tag, trust the user
        if pattern.startswith('<') and not pattern.startswith('<tracknumber>')\
                and not pattern.startswith('<discnumber>'):
            pieces.insert(0, os.path.sep)
        if pattern.endswith('>') and not pattern.endswith('<tracknumber>')\
                and not pattern.endswith('<discnumber>'):
            pieces.append(r'(?:\.[A-Za-z0-9_+]+)$')

        self.pattern = re.compile(''.join(pieces))

    def match(self, song):
        song = song.io_loc
        # only match on the last n pieces of a filename, dictated by pattern
        # this means no pattern may effectively cross a /, despite .* doing so
        sep = os.path.sep
        matchon = sep+sep.join(song.split(sep)[-self.slashes:])
        match = self.pattern.search(matchon)

        # dicts for all!
        if match is None: return {}
        else: return match.groupdict()
                
class AddTagDialog(gtk.Dialog):
    """
        Dialog shown when the user wants to add a tag
    """
    def __init__(self, parent):
        super(AddTagDialog, self).__init__(_("Add a Tag"), parent)
        self.set_border_width(3)
        self.set_has_separator(False)
        self.set_resizable(False)
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add = self.add_button(gtk.STOCK_ADD, gtk.RESPONSE_OK)
        self.add.set_sensitive(False)
        self.set_default_response(gtk.RESPONSE_OK)

        self.combo = gtk.combo_box_new_text()
        self.populate_combo()
        self.combo.set_active(0)
        self.entry = gtk.Entry()
        self.entry.connect('changed', self.on_entry_changed)

        self.vbox.pack_start(self.combo, True, True)
        self.vbox.pack_start(self.entry, True, True)
        self.show_all()

    def populate_combo(self):
        """
            Place the tags in the combobox
        """
        for tag in TAG_STRINGS.values():
            self.combo.append_text(tag)

    def on_entry_changed(self, entry, *args):
        """
            Check if there's any text in the entry, set add button sensitivity
        """
        if entry.get_property('text'):
            self.add.set_sensitive(True)
        else:
            self.add.set_sensitive(False)

    def get_tag(self):
        """
            Returns the tag that the user has selected
        """
        return TAG_STRINGS.keys()[self.combo.get_active()]

    def get_value(self):
        """
            Returns the value that the user has inserted
        """
        return self.entry.get_property('text')

    def run(self):
        self.show()
        return super(AddTagDialog, self).run()
        
class AskSaveDialog(gtk.Dialog):
    """
        Ask the user if he wants to save his changes or not
    """
    def __init__(self, parent):
        gtk.Dialog.__init__(self, _("Save changes?"), parent)
        return

def update_rating(caller, num):
    """
        Updates the rating based on which menu id was clicked
    """
    rating = num + 1

    cur = caller.db.cursor()
    for track in caller.get_selected_tracks():
        
        path_id = library.get_column_id(caller.db, 'paths', 'name',
            track.loc)
        caller.db.execute("UPDATE tracks SET user_rating=? WHERE path=?",
            (rating, path_id)) 
        track.rating = rating
        if isinstance(caller, trackslist.TracksListCtrl):
            caller.refresh_row(track)

def get_error(i):
    """
        Returns a textual error with pango tags for the tag view
    """
    before = '<span foreground="gray" style="italic">'
    after = '</span>'
    if i == editor.TAG_MISSING: 
        ret = _("Tag missing from one or more files")
    elif i == editor.TAG_DIFFERENT: 
        ret = _("Tag different in one or more files")
    elif i == editor.TAG_UNSUPPORTED: 
        ret = _("Tag unsupported in one or more files")
    elif i == editor.TAG_MULTI: 
        ret = _("Multiple tag values found, not supported by all tracks")
    else:
        ret = _("Unable to display tag for unknown reason")

    return before + ret + after
