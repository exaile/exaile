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

import gtk, pynotify, plugins, traceback

PLUGIN_NAME = "LibNotify Plugin"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = "Uses libnotify to inform you when a new song starts"
PLUGIN_ENABLED = False
button = gtk.Button()
PLUGIN_ICON = button.render_icon('gtk-info', gtk.ICON_SIZE_MENU)
button.destroy()
DEFAULT_SUMMARY = '{title}'
DEFAULT_BODY = '{artist}\n<i>on {album}</i>'

EXAILE = None
pynotify.init('exailenotify')

def configure(exaile):
    """
        Shows a configuration dialog that allows you to change the summary and
        body of the notification popup
    """
    settings = exaile.settings
    summary = settings.get('%s_summary' % plugins.name(__file__),
        DEFAULT_SUMMARY)
    body = settings.get('%s_body' % plugins.name(__file__), 
        DEFAULT_BODY)

    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    main = dialog.child
    label = gtk.Label("Notification Summary:")
    label.set_alignment(0.0, 0.0)
    main.pack_start(label, False, False)

    summary_entry = gtk.Entry()
    summary_entry.set_text(summary)
    main.pack_start(summary_entry, True, False)

    label = gtk.Label("Notification Body:")
    label.set_alignment(0.0, 0.0)
    main.pack_start(label, False, False)

    body_view = gtk.TextView()
    body_view.get_buffer().set_text(body)
    scroll = gtk.ScrolledWindow()
    scroll.add(body_view)
    scroll.set_shadow_type(gtk.SHADOW_IN)
    scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

    main.pack_start(scroll, True, True)
    dialog.resize(280, 240)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:   
        buf = body_view.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        settings['%s_body' % plugins.name(__file__)] = \
            buf.get_text(start, end)
        settings['%s_summary' % plugins.name(__file__)] = \
            summary_entry.get_text()

def initialize(exaile):
    """
        Initializes the plugin. 
        In this plugin, not much needs to be done except for set up the
        globals
    """
    global EXAILE
    EXAILE = exaile

    return True

def play_track(track):
    """
        Called when a track starts playing.
        Displays a notification via notification daemon
    """
    settings = EXAILE.settings

    vals = dict()
    vals['summary'] = settings.get('%s_summary' % plugins.name(__file__),
        DEFAULT_SUMMARY)
    vals['body'] = settings.get('%s_body' % plugins.name(__file__),
        DEFAULT_BODY)

    for k, val in vals.iteritems():
        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            try:
                value = getattr(track, item)
                if type(value) != str and type(value) != unicode:
                    value = unicode(value)

                vals[k] = vals[k].replace("{%s}" % item, value)
            except AttributeError:
                trackback.print_exc()

    notify = pynotify.Notification(vals['summary'], vals['body'])
    pixbuf = gtk.gdk.pixbuf_new_from_file(EXAILE.cover.loc)
    pixbuf = pixbuf.scale_simple(50, 50, gtk.gdk.INTERP_BILINEAR)
    notify.set_icon_from_pixbuf(pixbuf)
    notify.show()

def destroy():
    """
        No cleanup needs to be done for this plugin
    """
    pass
