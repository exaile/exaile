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

import subprocess, logging, os
from xl import event, xdg
from xl.nls import gettext as _
import time, sys
import srprefs

# trying to not rely on the gui parts of exaile
try:
    from xlgui import commondialogs
except ImportError:
    commondialogs = None

logger = logging.getLogger(__name__)

BUTTON = None
CURRENT_TRACK = None
STREAMRIPPER_PID = None
STREAMRIPPER_OUT = None
APP = None

def get_prefs_pane():
    return srprefs

def toggle_record(widget=None, event=None):
    global STREAMRIPPER_PID, CURRENT_TRACK, STREAMRIPPER_OUT

    import gst

    track = APP.player.current
    settings = APP.settings

    if not STREAMRIPPER_PID:
        if not track: return True
        if track.is_local():
            logger.warning('Streamripper can only record streams')
            if commondialogs:
                commondialogs.error(APP.gui.main.window, _('Streamripper '
                    'can only record streams.'))
            return True

        savedir = settings.get_option('plugin/streamripper/save_location', 
            os.getenv('HOME'))
        
        try:
            port = int(settings.get_option('plugin/streamripper/relay_port', 8888))
        except ValueError:
            port = 8888

        outfile = "%s/streamripper.log" % xdg.get_config_dir()
        STREAMRIPPER_OUT = open(outfile, "w+", 0)
        STREAMRIPPER_OUT.write("Streamripper log file started: %s\n" %
            time.strftime("%c", time.localtime()))
        STREAMRIPPER_OUT.write(
            "-------------------------------------------------\n\n\n")
       

        APP.player.playbin.set_state(gst.STATE_NULL)
        sub = subprocess.Popen(['streamripper',
            APP.player.playbin.get_property('uri'), '-r',
            str(port), '-d', savedir], stdout=STREAMRIPPER_OUT)
        ret = sub.poll()

        logger.info("Using streamripper to play location: %s" % track['loc'])

        if ret != None:
            logger.warning('There was an error executing streamripper')
            if commondialogs:
                commondialogs.error(APP.gui.main.window, _("Error "
                    "executing streamripper"))
                return True

        STREAMRIPPER_PID = sub.pid
        logger.info("Proxy location: http://localhost:%d" % port)
        APP.player.playbin.set_property('uri', 'http://localhost:%d' % port)
        time.sleep(1)

        APP.player.playbin.set_state(gst.STATE_PLAYING)
        CURRENT_TRACK = track

        return False
    else:
        os.system('kill -9 %d' % STREAMRIPPER_PID)
        APP.player.playbin.set_state(gst.STATE_READY)
        APP.player.playbin.set_property('uri', track['loc'])
        CURRENT_TRACK = None
        APP.player.playbin.set_state(gst.STATE_PLAYING)
        STREAMRIPPER_PID = None
        if STREAMRIPPER_OUT:
            try:
                STREAMRIPPER_OUT.close()
            except OSError:
                pass

    return False

def playback_stop(type, player, object):
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

def initialize(type, exaile, stuff=None):
    global BUTTON, APP

    APP = exaile

    try:
        subprocess.call(['streamripper'], stdout=-1, stderr=-1)
    except OSError:
        raise NotImplementedError('Streamripper is not available.')
        return False

    # if the gui is available, add the record button
    if exaile.gui:
        import gtk

        BUTTON = gtk.ToggleButton()
        BUTTON.connect('button-release-event', toggle_record)
        image = gtk.Image()
        image.set_from_stock('gtk-media-record', gtk.ICON_SIZE_SMALL_TOOLBAR)
        BUTTON.set_image(image)
        
        toolbar = exaile.gui.play_toolbar
        toolbar.pack_start(BUTTON, False, False)
        toolbar.reorder_child(BUTTON, 3)

        BUTTON.show()

    event.add_callback(playback_stop, 'playback_end', 
        exaile.player)

def enable(exaile):
    """
        Enables the streamripper plugin
    """
    if exaile.loading:
        event.add_callback(initialize, 'exaile_loaded', exaile)
    else:
        initialize(None, exaile)

def disable(exaile):
    global BUTTON

    if BUTTON:
        exaile.gui.play_toolbar.remove(BUTTON)
        BUTTON.hide()
        BUTTON.destroy()

        BUTTON = None

    event.remove_callback(playback_stop, 'playback_end',
        exaile.player)
