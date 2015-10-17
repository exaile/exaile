# Filter Widget/Dialog
# Copyright (C) 2006 Johannes Sasongko <sasongko@gmail.com>
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

"""Generic widget and dialog for filtering items.

They resemble the configuration dialogs of Evolution's mail filters
and Rhythmbox's automatic playlists.
"""

from gi.types import GObjectMeta
from gi.repository import Gtk
import urllib

from xl.nls import gettext as _

class FilterDialog(Gtk.Dialog):
    """Dialog to filter a list of items.

    Consists of a FilterWidget and an Add button.
    """

    def __init__(self, title, parent, criteria):
        """Create a filter dialog.

        Parameters:
        - title: title of the dialog window
        - criteria: possible criteria; see FilterWindow
        """

        Gtk.Dialog.__init__(self, title, parent, buttons=(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
            Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT))

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        top = Gtk.HBox()
        top.set_border_width(5)
        top.set_spacing(5)

        top.pack_start(Gtk.Label(_("Name:")), False, True, 0)
        self.name_entry = Gtk.Entry()
        top.pack_start(self.name_entry, True, True, 0)
        self.vbox.pack_start(top, False, True, 0)
        top.show_all()

        self.filter = f = FilterWidget(sorted(criteria, key=lambda k: _(k[0])))
        f.add_row()
        f.set_border_width(5)
        self.vbox.pack_start(f, True, True, 0)
        f.show_all()

        bottom = Gtk.HBox()
        bottom.set_border_width(5)
        self.match_any = Gtk.CheckButton(_('Match any of the criteria'))
        bottom.pack_start(self.match_any, True, True, 0)
        self.random = Gtk.CheckButton(_('Randomize results'))
        bottom.pack_start(self.random, True, True, 0)

        btn = Gtk.Button()
        btn.connect('clicked', lambda *x: self.filter.add_row())
        image = Gtk.Image()
        image.set_from_icon_name('list-add', Gtk.IconSize.BUTTON)
        btn.add(image)
        align = Gtk.Alignment.new(1, 0, 0, 0)
        align.add(btn)
        bottom.pack_end(align, True, True, 0)
        self.vbox.pack_start(bottom, False, True, 0)

        # add the limit checkbox, spinner
        limit_area = Gtk.HBox()
        limit_area.set_border_width(5)
        self.lim_check = Gtk.CheckButton(_("Limit to: "))
        limit_area.pack_start(self.lim_check, False, True, 0)

        self.lim_spin = Gtk.SpinButton.new_with_range(0, 1000000000, 1)
        self.lim_spin.set_value(1.0)
        self.lim_spin.set_sensitive(False)

        self.lim_check.connect('toggled', lambda b:
            self.lim_spin.set_sensitive(self.lim_check.get_active()))

        limit_area.pack_start(self.lim_spin, False, True, 0)
        limit_area.pack_start(Gtk.Label(_(" tracks")), False, True, 0)
        self.vbox.pack_start(limit_area, False, True, 0)
        limit_area.show_all()

        bottom.show_all()
        align.show_all()
        self.show_all()

    def set_limit(self, limit):
        """
            Sets the limit for the number of items that should be returned
        """
        if limit > -1:
            self.lim_check.set_active(True)
            self.lim_spin.set_value(limit)
        else:
            self.lim_check.set_active(False)

    def get_limit(self):
        """
            Get the limit value
        """
        if self.lim_check.get_active():
            return int(self.lim_spin.get_value())
        else:
            return -1

    def get_random(self):
        """
            Returns if the playlist should be random
        """
        return self.random.get_active()

    def set_random(self, random):
        """
            Sets if this playlist should be random
        """
        self.random.set_active(random)

    def get_match_any(self):
        """
            Returns true if this dialog should match any of the criteria
        """
        return self.match_any.get_active()

    def set_match_any(self, any):
        """
            Sets whether this dialog should match any of the criteria or not
        """
        self.match_any.set_active(any)

    def get_name(self):
        """
            Returns the text in the name_entry
        """
        return unicode(self.name_entry.get_text(), 'utf-8')

    def set_name(self, name):
        """
            Sets the text in the name_entry
        """
        self.name_entry.set_text(name)

    def get_result(self):
        """Return the user's input as a list of filter criteria.

        See FilterWidget.get_result.
        """
        # TODO: display error message
        return self.filter.get_result()

    def get_state(self):
        """Return the filter state.

        See FilterWidget.get_state.
        """
        return self.filter.get_state()

    def set_state(self, state):
        """Set the filter state.

        See FilterWidget.set_state.
        """
        self.filter.set_state(state)

class FilterWidget(Gtk.Table):
    """Widget to filter a list of items.

    This widget only includes the criteria selector (Criterion widgets)
    and their Remove buttons; it does not include an Add button.

    Attributes:
    - criteria: see example
    - rows: list of (criterion, remove_btn, remove_btn_handler_id)
    - n: number of rows

    Example of criteria:

        [
            # name
            (N_('Year'), [
                # name - field class/factory
                (N_('is'), EntryField),
                (N_('is between'),
                    lambda x: EntryLabelEntryField(x, _('and'))),
                (N_('is this year'), NothingField)
            ]),
        ]

    The field class is a class following this interface:

        class Field(Gtk.Widget):
            def __init__(self, result_generator):
                pass
            def get_result(self):
                return object
            def get_state(self):
                return object
            def set_state(self, state):
                pass

    Although not required, these methods should use unicode instead of
    str objects when dealing with strings.
    """

    def __init__(self, criteria):
        """Create a filter widget.

        Parameter:
        - criteria: see FilterWidget
        """

        super(FilterWidget, self).__init__()
        self.set_col_spacings(10)
        self.set_row_spacings(2)
        self.criteria = criteria
        self.rows = []
        self.n = 0

    def add_row(self):
        """Add a new criteria row."""

        criterion = Criterion(self.criteria)
        criterion.show()
        
        if len(self.rows) != 0:
            criterion.set_state(self.rows[-1][0].get_state())

        remove_btn = Gtk.Button()
        image = Gtk.Image()
        image.set_from_icon_name('list-remove', Gtk.IconSize.BUTTON)
        remove_btn.add(image)
        remove_btn_handler_id = remove_btn.connect(
            'clicked', self.__remove_clicked, self.n)
        remove_btn.show_all()

        self.attach(criterion, 0, 1, self.n, self.n + 1,
            Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, Gtk.AttachOptions.SHRINK)
        self.attach(remove_btn, 1, 2, self.n, self.n + 1,
            Gtk.AttachOptions.FILL, Gtk.AttachOptions.SHRINK)

        self.rows.append((criterion, remove_btn, remove_btn_handler_id))
        self.n += 1

    def remove_row(self, row):
        """Remove a criteria row."""
        rows = self.rows
        for iRow in xrange(row, len(rows)):
            crit, btn, handler = rows[iRow]
            self.remove(crit)
            self.remove(btn)
            btn.disconnect(handler)
            if iRow != row:  # shift up
                self.attach(crit, 0, 1, iRow - 1, iRow,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, Gtk.AttachOptions.SHRINK)
                self.attach(btn, 1, 2, iRow - 1, iRow,
                    Gtk.AttachOptions.FILL, Gtk.AttachOptions.SHRINK)
                handler = btn.connect(
                    'clicked', self.__remove_clicked, iRow - 1)
                rows[iRow - 1] = crit, btn, handler
        self.n -= 1
        del rows[self.n]
        if self.n:
            self.resize(self.n, 2)

    def __remove_clicked(self, widget, data):
        self.remove_row(data)

    def get_state(self):
        """Return the filter state.

        See set_state for the state format.
        """
        state = []
        for row in self.rows:
            state.append(row[0].get_state())
            state[-1][0].reverse() # reverse so it reads more nicely
        return state

    def set_state(self, state):
        """Set the filter state.

        Format:

            [
                ( [criterion1_1, criterion1_2, ...], filter1 ),
                ( [criterion2_1, criterion2_2, ...], filter2 ),
                ...
            ]
        """
        n_present = len(self.rows)
        n_required = len(state)
        for i in xrange(n_present, n_required):
            self.add_row()
        for i in xrange(n_present, n_required, -1):
            self.remove_row(i - 1) # i is one less than n
        for i, cstate in enumerate(state):
            cstate[0].reverse() # reverse so it becomes a stack
            self.rows[i][0].set_state(cstate)

class Criterion(Gtk.HBox):
    """Widget representing one filter criterion.

    It contains either:
    - one combo box and another criterion object, or
    - a field object.
    """

    def __init__(self, subcriteria):
        """Create a criterion object.

        Parameters:
        - subcriteria: a list of possible subcriteria;
          see criteria in FilterWidget
        """
        super(Criterion, self).__init__(spacing=5)
        if isinstance(subcriteria, (Gtk.Widget, GObjectMeta)):
            field_class = subcriteria
            self.child = field_class()
        else:
            self.combo = combo = Gtk.ComboBoxText()
            if len(subcriteria) > 10:
                self.combo.set_wrap_width(5)
            self.subcriteria = subcriteria
            for subc in subcriteria:
                combo.append_text(_(subc[0]))
            combo.set_active(0)
            combo.connect('changed', self._combo_changed)
            combo.show()
            self.pack_start(combo, False, True, 0)
            self.child = Criterion(subcriteria[0][1])
        self.child.show()
        self.pack_start(self.child, True, True, 0)

    def _combo_changed(self, widget):
        """Called when the combo box changes its value."""
        state = self.child.get_state()
        self.remove(self.child)
        self.child = Criterion(self.subcriteria[self.combo.get_active()][1])
        if state: self.child.set_state(state)
        self.pack_start(self.child, True, True, 0)
        self.child.show()

    def get_state(self):
        """Return the criterion state.

        See set_state for the state format.
        """
        state = self.child.get_state()
        if isinstance(self.child, Criterion):
            state[0].append(self.subcriteria[self.combo.get_active()][0])
        else:
            state = ([], state)
        return state

    def set_state(self, state):
        """Set the criterion state.

        Format:

            ([..., grandchild_state, child_state, self_state], filter)

        Note the reverse order of the list. This is to give the
        impression of it being a stack responding to pop().
        """
        if isinstance(self.child, Criterion):
            text = state[0].pop()
            for i, subc in enumerate(self.subcriteria):
                if subc[0] == text:
                    self.combo.set_active(i)
                    break
            self.child.set_state(state)
        else:
            if len(state) > 1:
                self.child.set_state(state[1])

# Sample fields

class ComboEntryField(Gtk.HBox):
    '''Select from multiple fixed values, but allow the user to enter text'''
    
    def __init__(self, values):
        Gtk.HBox.__init__(self)
        
        self.combo = Gtk.ComboBoxText.new_with_entry()
        for value in values:
            self.combo.append_text(value)
        
        self.pack_start(self.combo, True, True, 0)
        self.combo.show()
    
    def get_state(self):
        return self.combo.get_active_text()
    
    def set_state(self, state):
        self.combo.get_child().set_text(str(state))

class NullField(Gtk.HBox):
    '''Used as a placeholder for __null__ values'''
    
    def get_state(self):
        return ['__null__']
        
    def set_state(self, state):
        pass
    

class MultiEntryField(Gtk.HBox):
    """Helper field that can be subclassed to get fields with multiple
       GtkEntry widgets and multiple labels."""
    def __init__(self, labels):
        """Create a field with the specified labels and widths.

        Parameter:
        - labels: sequence of string, integer, or None values;
          string represents label,
          integer represents Entry widget with a specific width,
          None represents Entry widget with default width
        """
        Gtk.HBox.__init__(self, spacing=5)
        self.entries = []
        for label in labels:
            if label is None:
                widget = Gtk.Entry()
                self.entries.append(widget)
            elif isinstance(label, (int, long, float)):
                widget = Gtk.Entry()
                widget.set_size_request(label, -1)
                self.entries.append(widget)
            else:
                widget = Gtk.Label(label=unicode(label))
            self.pack_start(widget, False, True, 0)
            widget.show()
    def get_state(self):
        return [unicode(e.get_text(), 'utf-8') for e in self.entries]
    def set_state(self, state):
        entries = self.entries
        for i in xrange(min(len(entries), len(state))):
            entries[i].set_text(unicode(state[i]))

class EntryField(Gtk.Entry):
    def __init__(self):
        Gtk.Entry.__init__(self)
    def get_state(self):
        return unicode(self.get_text(), 'utf-8')
    def set_state(self, state):
        if type(state) == list or type(state) == tuple:
            state = state[0]
        self.set_text(unicode(state))
        
class QuotedEntryField(Gtk.Entry):
    def __init__(self):
        Gtk.Entry.__init__(self)
    def get_state(self):
        return unicode(urllib.quote(self.get_text()), 'utf-8')
    def set_state(self, state):
        if type(state) == list or type(state) == tuple:
            state = state[0]
        self.set_text(unicode(urllib.unquote(str(state))))

class EntryLabelEntryField(MultiEntryField):
    def __init__(self, label):
        MultiEntryField.__init__(self, (50, label, 50))

class SpinLabelField(Gtk.HBox):
    def __init__(self, label='', top=99999, lower=-99999):
        Gtk.HBox.__init__(self, spacing=5)
        self.spin = Gtk.SpinButton.new_with_range(lower, top, 1)
        self.spin.set_value(0)
        self.pack_start(self.spin, False, True, 0)
        self.pack_start(Gtk.Label.new(label), False, True, 0)
        self.show_all()
    def get_state(self):
        return self.spin.get_value()
    def set_state(self, state):
        if type(state) == list or type(state) == tuple:
            state = state[0]
        try:
            self.spin.set_value(int(state))
        except ValueError:
            pass

class SpinButtonAndComboField(Gtk.HBox):
    def __init__(self, items=()):
        Gtk.HBox.__init__(self, spacing=5)
        self.items = items

        self.entry = Gtk.SpinButton.new_with_range(0, 99999, 1)
        self.entry.set_value(0)
        self.pack_start(self.entry, True, True, 0)

        self.combo = Gtk.ComboBoxText()
        for item in items:
            self.combo.append_text(_(item))
        self.combo.set_active(0)
        self.pack_start(self.combo, True, True, 0)
        self.show_all()

    def set_state(self, state):
        if not isinstance(state, (tuple, list)) or len(state) < 2:
            return

        # TODO: Check length.
        try:
            self.entry.set_value(int(state[0]))
        except ValueError:
            pass
        combo_state = _(state[1])
        try:
            index = self.items.index(combo_state)
        except ValueError:
            pass
        else:
            self.combo.set_active(index)

    def get_state(self):
        active_item = self.items[self.combo.get_active()]

        if not isinstance(active_item, unicode):
            active_item = unicode(active_item, 'utf-8')

        return [self.entry.get_value(), active_item]
