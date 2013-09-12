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

import gtk, pango

class AboutWindow():
    def __init__(self):

        self.book=None
        self.showing=False

        self.win=gtk.Window()
        self.win.set_title("About")
        self.win.set_default_size(300, 200)
        self.win.set_geometry_hints(self.win, min_width=100, min_height=100)
        self.vbox=gtk.VBox()
        self.win.add(self.vbox)

        self.scrollwin=gtk.ScrolledWindow()
        self.scrollwin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(self.scrollwin, True, True, 0)

        self.textview=gtk.TextView()
        self.textview.set_cursor_visible(False)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(gtk.WRAP_WORD)
        self.textview.set_justification(gtk.JUSTIFY_LEFT)
        self.textview.set_left_margin(4)
        self.textview.set_left_margin(4)

        self.scrollwin.add(self.textview)

        self.textbuffer=gtk.TextBuffer()
        self.textbuffer.create_tag('bold', weight=pango.WEIGHT_BOLD)
        self.textview.set_buffer(self.textbuffer)

        self.hbox=gtk.HBox()
        self.vbox.pack_start(self.hbox, False, False, 2)

        self.closebutton=gtk.Button("Close")
        self.closebutton.connect("pressed", self.closebutton_pressed)
        self.closeimage=gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        self.closebutton.set_image(self.closeimage)
        self.hbox.pack_end(self.closebutton, False, False)

        self.vbox.show_all()

        self.win.connect("delete-event", self.on_delete)


    def set_text(self, book):
        self.book=book
        titlelength=len(book.title)
        if book.info==None:
            book.info="No information."
        self.textbuffer.set_text(book.title+'\n\n'+book.info+'\n')
        start=self.textbuffer.get_iter_at_offset(0)
        end=self.textbuffer.get_iter_at_offset(titlelength)
        self.textbuffer.apply_tag_by_name('bold',start, end)

    def on_delete(self, window, event):
        self.win.hide()
        self.showing=False
        return True

    def closebutton_pressed(self, widget):
        self.win.hide()
        self.showing=False

