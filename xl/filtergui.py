# Filter Widget/Dialog
# Copyright (c) 2006 Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Generic widget and dialog for filtering items.

They resemble the configuration dialogs of Evolution's mail filters
and Rhythmbox's automatic playlists.
"""

from gettext import gettext as _

import gtk

class FilterDialog(gtk.Dialog):
    """Dialog to filter a list of items.

    Consists of a FilterWidget and an Add button.
    """

    def __init__(self, title, criteria):
        """Create a filter dialog.

        Parameters:
        - title: title of the dialog window
        - criteria: possible criteria; see FilterWindow
        """

        gtk.Dialog.__init__(self, title, buttons=(
            gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        top = gtk.HBox()
        top.set_border_width(5)
        top.set_spacing(5)

        top.pack_start(gtk.Label(_("Name:")), False)
        self.name_entry = gtk.Entry()
        top.pack_start(self.name_entry)
        self.vbox.pack_start(top)
        top.show_all()

        self.filter = f = FilterWidget(criteria)
        f.add_row()
        f.set_border_width(5)
        self.vbox.pack_start(f)
        f.show()

        bottom = gtk.HBox()
        bottom.set_border_width(5)
        self.match_any = gtk.CheckButton(_('Match any of the criteria'))
        bottom.pack_start(self.match_any)

        btn = gtk.Button()
        btn.connect('clicked', lambda *x: self.filter.add_row())
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        btn.add(image)
        align = gtk.Alignment(xalign=1)
        align.add(btn)
        bottom.pack_end(align)
        self.vbox.pack_start(bottom)
        bottom.show_all()
        align.show_all()

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

class FilterWidget(gtk.Table):
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
                # name - field class/factory -  result generator
                (N_('is'), (EntryField, lambda x: 'Year=%d' % int(x))),
                (N_('is between'), (
                    lambda x: EntryLabelEntryField(x, _('and')),
                    lambda x, y:
                        'Year BETWEEN %s AND %s' % (int(x), int(y)))),
                (N_('is this year'), (NothingField,
                    lambda: time.localtime()[0])),
            ]),
        ]

    The field class is a class following this interface:

        class Field(gtk.Widget):
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

        gtk.Table.__init__(self)
        self.set_col_spacings(10)
        self.set_row_spacings(2)
        self.criteria = criteria
        self.rows = []
        self.n = 0

    def get_result(self):
        """Return a list of results produced by the criterion objects.
        """
        return [f[0].get_result() for f in self.rows]

    def add_row(self):
        """Add a new criteria row."""

        criterion = Criterion(self.criteria)
        criterion.show()

        remove_btn = gtk.Button()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON)
        remove_btn.add(image)
        remove_btn_handler_id = remove_btn.connect(
            'clicked', self.__remove_clicked, self.n)
        remove_btn.show_all()

        self.attach(criterion, 0, 1, self.n, self.n + 1,
            gtk.EXPAND | gtk.FILL, gtk.SHRINK)
        self.attach(remove_btn, 1, 2, self.n, self.n + 1,
            gtk.FILL, gtk.SHRINK)

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
                    gtk.EXPAND | gtk.FILL, gtk.SHRINK)
                self.attach(btn, 1, 2, iRow - 1, iRow,
                    gtk.FILL, gtk.SHRINK)
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

class Criterion(gtk.HBox):
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
        gtk.HBox.__init__(self, spacing=5)
        if isinstance(subcriteria, tuple):
            field_class, result_generator = subcriteria
            self.child = field_class(result_generator)
        else:
            self.combo = combo = gtk.combo_box_new_text()
            self.subcriteria = subcriteria
            for subc in subcriteria:
                combo.append_text(_(subc[0]))
            combo.set_active(0)
            combo.connect('changed', self._combo_changed)
            combo.show()
            self.pack_start(combo, False)
            self.child = Criterion(subcriteria[0][1])
        self.child.show()
        self.pack_start(self.child)

    def _combo_changed(self, widget):
        """Called when the combo box changes its value."""
        state = self.child.get_state() 
        self.remove(self.child)
        self.child = Criterion(self.subcriteria[self.combo.get_active()][1])
        if state: self.child.set_state(state)
        self.pack_start(self.child)
        self.child.show()

    def get_result(self):
        """Return the result from the field object."""
        return self.child.get_result()

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

class MultiEntryField(gtk.HBox):
    """Helper field that can be subclassed to get fields with multiple
       GtkEntry widgets and multiple labels."""
    def __init__(self, result_generator, n=2, labels=None, widths=None):
        gtk.HBox.__init__(self, spacing=5)
        self.generate_result = result_generator
        self.entries = []
        for iEntry in xrange(n):
            entry = gtk.Entry()
            if iEntry < len(widths):
                w = widths[iEntry]
                if w is not None:
                    entry.set_size_request(w, -1)
            self.entries.append(entry)
            if iEntry < len(labels):
                txt = labels[iEntry]
                if txt is not None:
                    l = gtk.Label(txt)
                    self.pack_start(l, False)
                    l.show()
            self.pack_start(entry)
            entry.show()
        if n < len(labels):
            txt = labels[n]
            if txt is not None:
                l = gtk.Label(txt)
                self.pack_start(l, False)
                l.show()
    def get_result(self):
        return self.generate_result(*self.get_state())
    def get_state(self):
        return [unicode(e.get_text(), 'utf-8') for e in self.entries]
    def set_state(self, state):
        for i, e in enumerate(self.entries):
            if len(state) > i: e.set_text(unicode(state[i]))

class EntryField(gtk.Entry):
    def __init__(self, result_generator):
        gtk.Entry.__init__(self)
        self.generate_result = result_generator
    def get_result(self):
        return self.generate_result(unicode(self.get_text(), 'utf-8'))
    def get_state(self):
        return self.get_text()
    def set_state(self, state):
        if type(state) == list or type(state) == tuple:
            state = state[0]
        self.set_text(unicode(state))

class EntryLabelEntryField(MultiEntryField):
    def __init__(self, result_generator, label):
        MultiEntryField.__init__(self, result_generator, n=2,
            labels=(None, label, None),
            widths=(50, 50))

class SpinLabelField(gtk.HBox):
    def __init__(self, result_generator, label='', top=99999):
        gtk.HBox.__init__(self, spacing=5)
        self.generate_result = result_generator
        self.spin = gtk.SpinButton(gtk.Adjustment(0, 0, top, 1, 0, 0))
        self.pack_start(self.spin)
        self.pack_start(gtk.Label(label))
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

    def get_result(self):
        return self.generate_result(self.spin.get_value())

class SpinButtonAndComboField(gtk.HBox):
    def __init__(self, result_generator, items=()):
        gtk.HBox.__init__(self, spacing=5)
        self.generate_result = result_generator

        adjustment = gtk.Adjustment(0, 0, 99999, 1, 0, 0)
        self.entry = gtk.SpinButton(adjustment=adjustment)
        self.pack_start(self.entry)

        self.combo = gtk.combo_box_new_text()
        for item in items:
            self.combo.append_text(item)
        self.combo.set_active(0)
        self.pack_start(self.combo)
        self.show_all()

    def get_result(self):
        return self.generate_result(*self.get_state())

    def set_state(self, state):
        if not isinstance(state, (tuple, list)):
            return

        print state

        # TODO: Check length.
        try:
            self.entry.set_value(int(state[0]))
        except ValueError:
            pass
        count = 0
        model = self.combo.get_model()
        iter = model.get_iter_first()
        while True:
            text = model.get_value(iter, 0)
            if text == state[1]:
                self.combo.set_active(count)

            count += 1
            iter = model.iter_next(iter)
            if not iter: break

    def get_state(self):
        return [self.entry.get_value(), 
            unicode(self.combo.get_active_text(), 'utf-8')]
