# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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
# Arunas Radzvilavicius, arunas.rv@gmail.com

from gi.repository import Gtk
from gi.repository import Pango


class AboutWindow:
    def __init__(self):

        self.book = None
        self.showing = False

        self.win = Gtk.Window()
        self.win.set_title("About")
        self.win.set_default_size(300, 200)
        self.win.set_geometry_hints(self.win, min_width=100, min_height=100)
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.add(self.vbox)

        self.scrollwin = Gtk.ScrolledWindow()
        self.scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.vbox.pack_start(self.scrollwin, True, True, 0)

        self.textview = Gtk.TextView()
        self.textview.set_cursor_visible(False)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_justification(Gtk.Justification.LEFT)
        self.textview.set_left_margin(4)
        self.textview.set_left_margin(4)

        self.scrollwin.add(self.textview)

        self.textbuffer = Gtk.TextBuffer()
        self.textbuffer.create_tag('bold', weight=Pango.Weight.BOLD)
        self.textview.set_buffer(self.textbuffer)

        self.hbox = Gtk.Box()
        self.vbox.pack_start(self.hbox, False, False, 2)

        self.closebutton = Gtk.Button("Close")
        self.closebutton.connect("pressed", self.closebutton_pressed)
        self.closeimage = Gtk.Image.new_from_icon_name(
            'window-close', Gtk.IconSize.MENU
        )
        self.closebutton.set_image(self.closeimage)
        self.hbox.pack_end(self.closebutton, False, False)

        self.vbox.show_all()

        self.win.connect("delete-event", self.on_delete)

    def set_text(self, book):
        self.book = book
        titlelength = len(book.title)
        if book.info is None:
            book.info = "No information."
        self.textbuffer.set_text(book.title + '\n\n' + book.info + '\n')
        start = self.textbuffer.get_iter_at_offset(0)
        end = self.textbuffer.get_iter_at_offset(titlelength)
        self.textbuffer.apply_tag_by_name('bold', start, end)

    def on_delete(self, window, event):
        self.win.hide()
        self.showing = False
        return True

    def closebutton_pressed(self, widget):
        self.win.hide()
        self.showing = False
