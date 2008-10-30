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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk, gtk.glade, cairo, gobject
from xl import xdg, common
from xl.nls import gettext as _
from xlgui import guiutil, cover
from xlgui.main import PlaybackProgressBar

class CoverWidget(guiutil.ScalableImageWidget):
    def __init__(self):
        guiutil.ScalableImageWidget.__init__(self)
        self.set_image_size(cover.COVER_WIDTH, cover.COVER_WIDTH)
        self.set_image(xdg.get_data_path('images/nocover.png'))

    def cover_found(self, object, cover):
        from xl import cover as c
        self.set_image_data(c.get_cover_data(cover))

class OSDWindow(object):
    """
        A popup window to show information on the current playing track
    """
    def __init__(self, settings, cover=None, covers=None, 
        player=None, draggable=False):
        """
            Initializes the popup
        """
        self.draggable = draggable
        self.settings = settings
        self.player = player
        self.covers = covers
        self.cover = cover
        self.progress_widget = None
        self.setup_osd()
        self._handler = None
        self._cover_sig = None
        self._timeout = None

    def destroy(self):
        if self.progress_widget:
            self.progress_widget.destroy()
            self.progress_widget = None
        if self._cover_sig:
            self.cover.disconnect(self._cover_sig)
        self.window.destroy()

    def setup_osd(self, settings=None):
        if not settings:
            settings = self.settings

        # if there are current progress widgets, destroy them to
        # remove unneeded signals
        if self.progress_widget:
            self.progress_widget.destroy()

        self.settings = settings
        self.xml = gtk.glade.XML(xdg.get_data_path('glade/osd_window.glade'), 
            'OSDWindow', 'exaile')
        self.window = self.xml.get_widget('OSDWindow')

        self.color = gtk.gdk.color_parse(settings.get_option('osd/bg_color',
            '#567ea2'))
        self.event = self.xml.get_widget('osd_event_box')
        self.box = self.xml.get_widget('image_box')

        self.progress = self.xml.get_widget('osd_progressbar')
        self.cover_widget = CoverWidget()
        if self.cover:
            self._cover_sig = self.cover.connect('cover-found', 
                self.cover_widget.cover_found)
        self.cover_widget.set_image_size(
            settings.get_option('osd/h', 95) - 8,
            settings.get_option('osd/h', 95) - 8)

        if self.player:
            self.progress_widget = PlaybackProgressBar(self.progress,
                self.player)

        self.box.pack_start(self.cover_widget)
        # Try to set the window opacity.  To do that we need the RGBA colormap,
        # which for some reason may not be available even if
        # Widget.is_composited is true.  In GTK+ >=2.12 all this can just be
        # modified to use Window.set_opacity.
        colormap = None
        # Widget.is_composited is only in GTK+ >=2.10.
        is_composited = getattr(self.window, 'is_composited', None)
        if is_composited and is_composited():
            screen = self.window.get_screen()
            colormap = screen.get_rgba_colormap()
        if colormap:
            self.window.set_colormap(colormap)
            self.window.set_app_paintable(True)
            self.window.connect("expose-event", self.expose_callback)

            self.progress.set_colormap(colormap)
            self.progress.set_app_paintable(True)
            self.progress.connect("expose-event", self.expose_callback)
        else:
            # Just set the background color in the old fashioned way
            self.window.modify_bg(gtk.STATE_NORMAL, self.color)
            self.progress.modify_bg(gtk.STATE_NORMAL, self.color)
            
        self.title = self.xml.get_widget('osd_title_label')
        text = "<span font_desc='%s' foreground='%s'>%s</span>" % \
            (self.settings.get_option('osd/text_font', 'Sans 11'),
            self.settings.get_option('osd/text_color', '#ffffff'),
            self.settings.get_option('osd/display_text', 
                "<b>{title}</b>\n{artist}\non {album} - {length}"))
        self.title.set_markup(text)
        self.text = text

        self.window.set_size_request(
            settings.get_option('osd/w', 400), 
            settings.get_option('osd/h', 95))
        self.window.move(settings.get_option('osd/x', 0), 
            settings.get_option('osd/y', 0))

        self.event.connect('button_press_event', self.start_dragging)
        self.event.connect('button_release_event', self.stop_dragging)
        self._handler = None

    def expose_callback(self, widget, event):
        cr = widget.window.cairo_create()
        cr.set_operator(cairo.OPERATOR_SOURCE)

        cr.rectangle(event.area.x, event.area.y,
            event.area.width, event.area.height)
        cr.clip()

        opacity = int(self.settings.get_option('osd/opacity', 75))
        
        cr.set_source_rgba(self.color.red/65535.0, self.color.green/65535.0, 
                self.color.blue/65535.0, opacity/100.0)
        cr.paint()
        return False

    def start_dragging(self, widget, event):
        """
            Called when the user starts dragging the window
        """
        if not self.draggable:
            self.window.hide()
            return
        self._start = event.x, event.y
        self._handler = self.window.connect('motion_notify_event',
            self.dragging)

    def stop_dragging(self, widget, event):
        """
            Called when the user stops dragging the mouse
        """
        if self._handler: self.window.disconnect(self._handler)
        self._handler = None
        settings = self.settings
        (w, h) = self.window.get_size()
        (x, y) = self.window.get_position()

        settings['osd/x'] = int(x)
        settings['osd/y'] = int(y)
        settings['osd/h'] = int(h)
        settings['osd/w'] = int(w)
    
    def dragging(self, widget, event):
        """
            Called when the user drags the window
        """
        self.window.move(int(event.x_root - self._start[0]),
            int(event.y_root - self._start[1]))

    def hide(self):
        self.window.hide()

    def show(self, track, timeout=4000):

        text = self.text.replace('&', '&amp;')
        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            value = track[item]
            if not value: value = ''
            elif type(value) == list or type(value) == tuple:
                value = '/'.join(value)

            if not isinstance(value, basestring):
                value = unicode(value)
            text = text.replace('{%s}' % item, common.escape_xml(value))
        text = text.replace("\\{", "{")
        text = text.replace("\\}", "}")

        text = "<span font_desc='%s' foreground='%s'>%s</span>" % \
            (self.settings.get_option('osd/text_font', 'Sans 11'),
            self.settings.get_option('osd/text_color', '#ffffff'),
                text)
        self.title.set_markup(text)
        self.window.show_all()
        if self._timeout:
            gobject.source_remove(self._timeout)
        self._timeout = gobject.timeout_add(timeout, self.hide)

