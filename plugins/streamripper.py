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

import gtk, plugins, subprocess, os, time
from xl import common, media, xlmisc
PLUGIN_NAME = "Streamripper!"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""Allows you to record streams with
streamripper\n\nRequires the command line version of streamripper to be
installed"""

PLUGIN_ENABLED = False
button = gtk.Button()
PLUGIN_ICON = button.render_icon('gtk-media-record', gtk.ICON_SIZE_MENU)
button.destroy()
PLUGIN = None
APP = None
BUTTON = None
STREAMRIPPER_PID = None
STREAMRIPPER_OUT = None
CURRENT_TRACK = None

def configure():
    """
        Shows the configuration dialog for streamripper
    """
    exaile = APP
    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    table = gtk.Table(2, 2)
    table.set_row_spacings(2)
    bottom = 0
    label = gtk.Label("Save Location:    ")
    label.set_alignment(0.0, 0.0)

    table.attach(label, 0, 1, bottom, bottom + 1)

    location = exaile.settings.get("%s_save_location" % plugins.name(__file__),
        os.getenv("HOME"))
    save_loc = gtk.FileChooserButton("Location")
    save_loc.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
    save_loc.set_current_folder(location)

    table.attach(save_loc, 1, 2, bottom, bottom + 1)
    bottom += 1

    label = gtk.Label("Relay Port:")
    label.set_alignment(0.0, 0.0)
    table.attach(label, 0, 1, bottom, bottom + 1)

    port = exaile.settings.get("%s_relay_port" % plugins.name(__file__), '8000')
    port_entry = gtk.Entry()
    port_entry.set_text(port)
    port_entry.set_max_length(6)
    table.attach(port_entry, 1, 2, bottom, bottom + 1, gtk.SHRINK)

    dialog.child.pack_start(table)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:
        exaile.settings["%s_save_location" % plugins.name(__file__)] = \
            save_loc.get_current_folder()
        exaile.settings["%s_relay_port" % plugins.name(__file__)] = \
            port_entry.get_text()

def toggle_record(widget, event=None):
    """
        Toggles streamripper
    """
    global STREAMRIPPER_PID, STREAMRIPPER_OUT, CURRENT_TRACK
    track = APP.current_track
    if not STREAMRIPPER_PID:
        if not track: return True
        if not isinstance(track, media.StreamTrack):
            common.error(APP.window, "You can only record streams")
            widget.set_active(False)
            return True

        savedir = SETTINGS.get('%s_save_location' %
            plugins.name(__file__),
            os.getenv("HOME"))
        port = SETTINGS.get_int('%s_relay_port' % plugins.name(__file__),
            8000)
        outfile = APP.get_settings_dir() + "/streamripper.log"

        STREAMRIPPER_OUT = open(outfile, "w+", 0)
        STREAMRIPPER_OUT.write("Streamripper log file started: %s\n" %
            time.strftime("%c", time.localtime()))
        STREAMRIPPER_OUT.write(
            "-------------------------------------------------\n\n\n")

        if SETTINGS.get_boolean("kill_streamripper", True):
            xlmisc.log("Killing any current streamripper processes")
            os.system("killall -9 streamripper")

        track.stop()
        sub = subprocess.Popen(['streamripper', track.loc, '-r',
            str(port), '-d', savedir], stderr=STREAMRIPPER_OUT)
        ret = sub.poll()

        xlmisc.log("Streamripper return value was %s" % ret)
        xlmisc.log("Using streamripper to play location: %s" % track.loc)
        APP.status.set_first("Streamripping location: %s..." %
            track.loc, 4000)
        if ret != None:
            common.error(APP.window, _("There was an error"
                " executing streamripper."))
            return True
        STREAMRIPPER_PID = sub.pid
        track.stream_url = "http://localhost:%d" % port
        track.play(APP.on_next)
        CURRENT_TRACK = track

        return False
    else:
        if not STREAMRIPPER_PID:
            common.error(APP.window, _("Streamripper is not running."))
        os.system("kill -9 %d" % STREAMRIPPER_PID)
        track.stop()
        CURRENT_TRACK = None
        track.play(APP.on_next)
        STREAMRIPPER_PID = None

    return False

def initialize():
    """
        Checks for streamripper, initializes the plugin
    """
    global APP, SETTINGS, BUTTON
    exaile = APP
    try:
        subprocess.call(['streamripper'], stdout=-1, stderr=-1)
    except OSError:
        print "Streamripper is not available, disabling streamripper plugin"
        return False

    APP = exaile
    SETTINGS = exaile.settings
    BUTTON = gtk.ToggleButton()
    BUTTON.connect('button-release-event', toggle_record)
    image = gtk.Image()
    image.set_from_stock('gtk-media-record', gtk.ICON_SIZE_SMALL_TOOLBAR)
    BUTTON.set_image(image)

    toolbar = APP.xml.get_widget('play_toolbar')
    toolbar.pack_start(BUTTON, False, False)
    toolbar.reorder_child(BUTTON, 3)

    BUTTON.show()

    return True

def stop():
    """
        Stops streamripper by killing it if it's still running, and closes the
        log file
    """
    global STREAMRIPPER_OUT, STREAMRIPPER_PID
    if BUTTON:  
        BUTTON.set_active(False)
    if STREAMRIPPER_OUT:
        try:
            STREAMRIPPER_OUT.close()
        except OSError:
            pass
        STREAMRIPPER_OUT = None

    if STREAMRIPPER_PID:
        os.system("kill -9 %d" % STREAMRIPPER_PID)
        STREAMRIPPER_PID = None

def stop_track(track):
    """
        Called when playback has stopped on a track
    """
    stop()

def destroy():
    """
        Called when the plugin is disabled.  If streamripper is currently
        running, kill it and restart the track without using streamripper
    """
    global BUTTON, CURRENT_TRACK
    stop()
    if CURRENT_TRACK:
        CURRENT_TRACK.stream_url = None
        if CURRENT_TRACK.is_playing():
            CURRENT_TRACK.stop()
            CURRENT_TRACK.play(APP.on_next)
        CURRENT_TRACK = None
    if not BUTTON: return
    toolbar = APP.xml.get_widget('play_toolbar')
    toolbar.remove(BUTTON)
    BUTTON.hide()
    BUTTON.destroy()
    BUTTON = None
