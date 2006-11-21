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

        self.filter = f = FilterWidget(criteria)
        f.add_criterion()
        f.set_border_width(5)
        self.vbox.pack_start(f)
        f.show()

        btn = gtk.Button()
        btn.connect('clicked', lambda *x: self.filter.add_criterion())
        btn.set_border_width(5)
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        btn.add(image)
        align = gtk.Alignment(xalign=1)
        align.add(btn)
        self.vbox.pack_start(align, False)
        align.show_all()

    def get_result(self):
        """Return the user's input as a list of strings."""
        return self.filter.get_result()

class FilterWidget(gtk.Table):
    """Widget to filter a list of items.

    This widget only includes the criteria selector (Criterion widgets)
    and their Remove buttons; it does not include an Add button.

    Attributes:
    - criteria: see example
    - applied_criteria:
      list of (criterion, remove_btn, remove_btn_handler_id)
    - n: number of criteria

    Example of criteria:

        [
            # name
            ('Year', [
                # name - field class/factory -  result generator
                ('is', (EntryField, lambda x: 'Year = %d' % int(x))),
                ('is between', (
                    lambda: EntryLabelEntryField('and'),
                    lambda x, y:
                        'Year BETWEEN %s AND %s' % (int(x), int(y)))),
                ('is this year', (NothingField,
                    lambda: time.localtime()[0])),
            ]),
        ]

    The field class is a class following this interface:

        class Field(gtk.Widget):
            def __init__(self, result_generator):
                pass
            def get_result(self):
                return ''
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
        self.applied_criteria = []
        self.n = 0

    def get_result(self):
        """Return a list of strings produced by the criterion objects.
        """
        return [f[0].get_result() for f in self.applied_criteria]

    def add_criterion(self):
        """Add a new criterion object."""

        criterion = Criterion(self.criteria)
        criterion.show()

        remove_btn = gtk.Button()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON)
        remove_btn.add(image)
        remove_btn_handler_id = remove_btn.connect(
            'clicked', self._removed, self.n)
        remove_btn.show_all()

        self.attach(criterion, 0, 1, self.n, self.n + 1,
            gtk.EXPAND | gtk.FILL, gtk.SHRINK)
        self.attach(remove_btn, 1, 2, self.n, self.n + 1,
            gtk.FILL, gtk.SHRINK)

        self.applied_criteria.append(
            (criterion, remove_btn, remove_btn_handler_id))
        self.n += 1

    def _removed(self, button, row):
        """Called when a Remove button is activated."""
        ac = self.applied_criteria
        for iRow in xrange(row, len(ac)):
            crit, btn, handler = ac[iRow]
            self.remove(crit)
            self.remove(btn)
            btn.disconnect(handler)
            if iRow != row:  # shift up
                self.attach(crit, 0, 1, iRow - 1, iRow,
                    gtk.EXPAND | gtk.FILL, gtk.SHRINK)
                self.attach(btn, 1, 2, iRow - 1, iRow,
                    gtk.FILL, gtk.SHRINK)
                handler = btn.connect('clicked', self._removed, iRow - 1)
                ac[iRow - 1] = crit, btn, handler
        self.n -= 1
        del ac[self.n]
        if self.n:
            self.resize(self.n, 2)

class Criterion(gtk.HBox):
    """Widget representing one filter criterion.

    It consists of one combo box and either another criterion object
    or a field object.
    """

    def __init__(self, choices):
        """Create a criterion object.

        Parameters:
        - choices: a list of possible criterion choices;
          see criteria in FilterWidget
        """
        gtk.HBox.__init__(self, spacing=5)
        if isinstance(choices, tuple):
            field_class, result_generator = choices
            self.child = field_class(result_generator)
        else:
            self.combo = combo = gtk.combo_box_new_text()
            self.choices = choices
            for choice in choices:
                combo.append_text(choice[0])
            combo.set_active(0)
            combo.connect('changed', self._changed)
            combo.show()
            self.pack_start(combo, False)
            self.child = Criterion(choices[0][1])
        self.child.show()
        self.pack_start(self.child)

    def _changed(self, widget):
        """Called when the combo box changes its value."""
        self.remove(self.child)
        self.child = Criterion(self.choices[self.combo.get_active()][1])
        self.pack_start(self.child)
        self.child.show()

    def get_result(self):
        """Return the result of the field descendant object."""
        return self.child.get_result()

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
            try:
                w = widths[iEntry]
            except:
                w = None
            if w:
                entry.set_size_request(w, -1)
            self.entries.append(entry)
            try:
                s = labels[iEntry]
            except:
                s = None
            if s:
                l = gtk.Label(s)
                self.pack_start(l, False)
                l.show()
            self.pack_start(entry)
            entry.show()
        try:
            s = labels[n]
        except:
            s = None
        if s:
            l = gtk.Label(s)
            self.pack_start(l, False)
            l.show()
    def get_result(self):
        return self.generate_result(*(e.get_text() for e in self.entries))

class EntryField(gtk.Entry):
    def __init__(self, result_generator):
        gtk.Entry.__init__(self)
        self.generate_result = result_generator
    def get_result(self):
        return self.generate_result(self.get_text())

class EntryAndEntryField(MultiEntryField):
    def __init__(self, result_generator):
        MultiEntryField.__init__(self, result_generator, n=2,
            labels=(None, 'and', None),
            widths=(50, 50))
