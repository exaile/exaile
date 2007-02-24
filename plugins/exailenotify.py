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

import gtk, pynotify, plugins, traceback, cgi, os

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

APP = None
PLAY_ID = None
pynotify.init('exailenotify')

def configure():
    """
        Shows a configuration dialog that allows you to change the summary and
        body of the notification popup
    """
    exaile = APP
    settings = exaile.settings
    summary = settings.get_str('summary', default=DEFAULT_SUMMARY, plugin=plugins.name(__file__))
    body = settings.get_str('body', default=DEFAULT_BODY, plugin=plugins.name(__file__))

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

    show_cover_box = gtk.CheckButton('Show album covers in notification')
    show_cover_box.set_active(settings.get_boolean('show_covers', default=True,
        plugin=plugins.name(__file__)))

    attach_to_tray_box = gtk.CheckButton('Attach notification to tray icon '
        '(if available)')
    attach_to_tray_box.set_active(settings.get_boolean('attach_to_tray',
        default=True, plugin=plugins.name(__file__)))
    main.pack_start(attach_to_tray_box)


    main.pack_start(show_cover_box)
    dialog.resize(280, 240)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:   
        buf = body_view.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        settings.set_str('body', buf.get_text(start, end), plugin=plugins.name(__file__))
        settings.set_str('summary', summary_entry.get_text(), plugin=plugins.name(__file__))
        settings.set_boolean('show_covers', show_cover_box.get_active(),
            plugin=plugins.name(__file__))
        settings.set_boolean('attach_to_tray',
            attach_to_tray_box.get_active(), plugin=plugins.name(__file__))

def play_track(exaile, track):
    """
        Called when a track starts playing.
        Displays a notification via notification daemon
    """
    settings = APP.settings

    vals = dict()
    vals['summary'] = settings.get_str('summary', default=DEFAULT_SUMMARY, plugin=plugins.name(__file__))
    vals['body'] = settings.get_str('body', default=DEFAULT_BODY, plugin=plugins.name(__file__))

    for k, val in vals.iteritems():
        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            try:
                value = getattr(track, item)
                if type(value) != str and type(value) != unicode:
                    value = unicode(value)

                # escape html entities
                value = cgi.escape(value)

                vals[k] = vals[k].replace("{%s}" % item, value)
            except AttributeError:
                trackback.print_exc()

    notify = pynotify.Notification(vals['summary'], vals['body'])

    if settings.get_boolean('show_covers', default=True,
        plugin=plugins.name(__file__)):
        pixbuf = gtk.gdk.pixbuf_new_from_file(APP.cover.loc)
        pixbuf = pixbuf.scale_simple(50, 50, gtk.gdk.INTERP_BILINEAR)
    else:
        pixbuf = gtk.gdk.pixbuf_new_from_file('images%slargeicon.png' % os.sep)
        pixbuf = pixbuf.scale_simple(50, 50, gtk.gdk.INTERP_BILINEAR)

    notify.set_icon_from_pixbuf(pixbuf)

    if exaile.tray_icon and settings.get_boolean('attach_to_tray', default=True,
        plugin=plugins.name(__file__)):
        if isinstance(exaile.tray_icon, gtk.GtkTrayIcon):
            notify.set_property('status-icon', exaile.tray_icon.icon)
        else:
            notify.attach_to_widget(exaile.tray_icon.icon)

    notify.show()

def initialize():
    """
        Initializes the plugin. 
        In this plugin, not much needs to be done except for set up the
        globals
    """
    global PLAY_ID
    PLAY_ID = APP.connect('play-track', play_track)
    return True

def destroy():
    """
        No cleanup needs to be done for this plugin
    """
    global PLAY_ID
    if PLAY_ID:
        APP.disconnect(PLAY_ID)
        PLAY_ID = None
