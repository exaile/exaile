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

"""Generic widget and dialog for filtering items.

They resemble the configuration dialogs of Evolution's mail filters
and Rhythmbox's automatic playlists.
"""

import gobject
import gtk

from xl.nls import gettext as _

class FilterDialog(gtk.Dialog):
    """Dialog to filter a list of items.

    Consists of a FilterWidget and an Add button.
    """

    def __init__(self, title, parent, criteria):
        """Create a filter dialog.

        Parameters:
        - title: title of the dialog window
        - criteria: possible criteria; see FilterWindow
        """

        gtk.Dialog.__init__(self, title, parent, buttons=(
            gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        top = gtk.HBox()
        top.set_border_width(5)
        top.set_spacing(5)

        top.pack_start(gtk.Label(_("Name:")), False)
        self.name_entry = gtk.Entry()
        top.pack_start(self.name_entry)
        self.vbox.pack_start(top, False)
        top.show_all()

        self.filter = f = FilterWidget(criteria)
        f.add_row()
        f.set_border_width(5)
        self.vbox.pack_start(f)
        f.show_all()

        bottom = gtk.HBox()
        bottom.set_border_width(5)
        self.match_any = gtk.CheckButton(_('Match any of the criteria'))
        bottom.pack_start(self.match_any)
        self.random = gtk.CheckButton(_('Randomize results'))
        bottom.pack_start(self.random)

        btn = gtk.Button()
        btn.connect('clicked', lambda *x: self.filter.add_row())
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        btn.add(image)
        align = gtk.Alignment(xalign=1)
        align.add(btn)
        bottom.pack_end(align)
        self.vbox.pack_start(bottom, False)

        # add the limit checkbox, spinner
        limit_area = gtk.HBox()
        limit_area.set_border_width(5)
        self.lim_check = gtk.CheckButton(_("Limit to: "))
        limit_area.pack_start(self.lim_check, False)

        self.lim_spin = gtk.SpinButton(gtk.Adjustment(1, 0, 1000000000, 1))
        self.lim_spin.set_sensitive(False)

        self.lim_check.connect('toggled', lambda b:
            self.lim_spin.set_sensitive(self.lim_check.get_active()))

        limit_area.pack_start(self.lim_spin, False)
        limit_area.pack_start(gtk.Label(_(" tracks")), False)
        self.vbox.pack_start(limit_area, False)
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
                # name - field class/factory
                (N_('is'), EntryField),
                (N_('is between'),
                    lambda x: EntryLabelEntryField(x, _('and'))),
                (N_('is this year'), NothingField)
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
        if isinstance(subcriteria, (gtk.Widget,
            gobject.GObjectMeta)):
            field_class = subcriteria
            self.child = field_class()
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

class NullField(gtk.HBox):
    '''Used as a placeholder for __null__ values'''
    
    def get_state(self):
        return ['__null__']
        
    def set_state(self, state):
        pass
    

class MultiEntryField(gtk.HBox):
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
        gtk.HBox.__init__(self, spacing=5)
        self.entries = []
        for label in labels:
            if label is None:
                widget = gtk.Entry()
                self.entries.append(widget)
            elif isinstance(label, (int, long, float)):
                widget = gtk.Entry()
                widget.set_size_request(label, -1)
                self.entries.append(widget)
            else:
                widget = gtk.Label(unicode(label))
            self.pack_start(widget, False)
            widget.show()
    def get_state(self):
        return [unicode(e.get_text(), 'utf-8') for e in self.entries]
    def set_state(self, state):
        entries = self.entries
        for i in xrange(min(len(entries), len(state))):
            entries[i].set_text(unicode(state[i]))

class EntryField(gtk.Entry):
    def __init__(self):
        gtk.Entry.__init__(self)
    def get_state(self):
        return unicode(self.get_text(), 'utf-8')
    def set_state(self, state):
        if type(state) == list or type(state) == tuple:
            state = state[0]
        self.set_text(unicode(state))

class EntryLabelEntryField(MultiEntryField):
    def __init__(self, label):
        MultiEntryField.__init__(self, (50, label, 50))

class SpinLabelField(gtk.HBox):
    def __init__(self, label='', top=99999, lower=-99999):
        gtk.HBox.__init__(self, spacing=5)
        self.spin = gtk.SpinButton(gtk.Adjustment(0, lower, top, 1, 0, 0))
        self.pack_start(self.spin, False)
        self.pack_start(gtk.Label(label), False)
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

class SpinButtonAndComboField(gtk.HBox):
    def __init__(self, items=()):
        gtk.HBox.__init__(self, spacing=5)
        self.items = items

        adjustment = gtk.Adjustment(0, 0, 99999, 1, 0, 0)
        self.entry = gtk.SpinButton(adjustment=adjustment)
        self.pack_start(self.entry)

        self.combo = gtk.combo_box_new_text()
        for item in items:
            self.combo.append_text(_(item))
        self.combo.set_active(0)
        self.pack_start(self.combo)
        self.show_all()

    def set_state(self, state):
        if not isinstance(state, (tuple, list)):
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
