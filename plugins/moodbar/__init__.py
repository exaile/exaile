# Moodbar -  Replace standard progress bar with moodbar
# Copyright (C) 2009-2010  Solyianov Michael <crantisz@gmail.com>
#
# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

import moodbarloader
import moodbarprefs
import moodbarwidget

import os
import subprocess
import colorsys
from xl import event, player, settings, xdg
from xl.nls import gettext as _

import logging
logger = logging.getLogger(__name__)

ExaileModbar = None
PreviewMoodbar = None


class ExModbar(object):

    # Setup and getting values------------------------------------------------

    def __init__(self, player, progress_bar):
        self.pr = progress_bar
        self.player = player

        self.loader = moodbarloader.MoodbarLoader()
        self.moodbar = ''
        self.modwidth = 0
        self.curpos = 0
        self.modTimer = None
        self.haveMod = False
        self.playingTrack = ''
        self.seeking = False
        self.setuped = False
        self.runed = False
        self.pid = 0
        self.uptime = 0
        self.ivalue = 0
        self.qvalue = 0
        self.moodsDir = os.path.join(xdg.get_cache_dir(), "moods")
        if not os.path.exists(self.moodsDir):
            os.mkdir(self.moodsDir)

    def __inner_preference(klass):
        """functionality copy from notyfication"""

        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    defaultstyle = __inner_preference(moodbarprefs.DefaultStylePreference)
    flat = __inner_preference(moodbarprefs.FlatPreference)
    theme = __inner_preference(moodbarprefs.ThemePreference)
    cursor = __inner_preference(moodbarprefs.CursorPreference)

    darkness = __inner_preference(moodbarprefs.DarknessPreference)
    color = __inner_preference(moodbarprefs.ColorPreference)

    def get_size(self):
        progress_loc = self.mod.get_allocation()
        return progress_loc.width

    #Setup-------------------------------------------------------------------

    def changeBarToMod(self):
        place = self.pr.get_parent()
        self.mod = moodbarwidget.Moodbar(self.loader)
        self.mod.set_size_request(-1, 24)
        place.remove(self.pr)
        place.add(self.mod)
        self.mod.realize()
        self.mod.show()

    def changeModToBar(self):
        if hasattr(self, 'mod'):
            place = self.mod.get_parent()
            place.remove(self.mod)
            place.add(self.pr)
            self.mod.destroy()

    def setupUi(self):
        self.setuped = True
        self.changeBarToMod()
        self.mod.seeking = False
        self.mod.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.mod.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.mod.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.mod.connect("button-press-event", self.modSeekBegin)
        self.mod.connect("button-release-event", self.modSeekEnd)
        self.mod.connect("motion-notify-event", self.modSeekMotionNotify)

        track = self.player.current

        self.lookformod(track)

    def add_callbacks(self):
        event.add_callback(
            self.play_start,
            'playback_track_start',
            self.player
        )
        event.add_callback(
            self.play_end,
            'playback_player_end',
            self.player
        )
        event.add_callback(self.option_set, 'plugin_moodbar_option_set')

        # Initialize tint.
        self.option_set('plugin_moodbar', settings, moodbarprefs.ColorPreference.name)

    def remove_callbacks(self):
        event.remove_callback(
            self.play_start,
            'playback_track_start',
            self.player
        )
        event.remove_callback(
            self.play_end,
            'playback_player_end',
            self.player
        )
        event.remove_callback(self.option_set, 'plugin_moodbar_option_set')

    def option_set(self, event, settings, option):
        opt_theme = moodbarprefs.ThemePreference.name
        opt_color = moodbarprefs.ColorPreference.name
        if option not in (opt_theme, opt_color):
            return
        if settings.get_option(opt_theme):
            c = settings.get_option(opt_color)
            if c is not None:
                color = Gdk.RGBA()
                if len(c) == 9 and c[0] == '#':
                    alpha = int(c[-2:], 16) / 255.0
                    c = c[:-2]
                else:
                    alpha = 1
                if alpha == 1:
                    alpha = 0.1
                color.parse(c)
                color.alpha = alpha
                self.mod.set_tint(color)
                return
        self.mod.set_tint(None)

    def destroy(self):
        if self.modTimer: GLib.source_remove(self.modTimer)

    # playing ----------------------------------------------------------------

    def lookformod(self, track):
        if not track or not (track.is_local() or track.get_tag_raw('__length')):
            self.haveMod = False
            return

        self.playingTrack = str(track.get_loc_for_io())
        self.playingTrack = self.playingTrack.replace("file://", "")
        modLoc = self.moodsDir + '/' + self.playingTrack.replace('/',
                                                                 '-') + ".mood"
        modLoc = modLoc.replace("'", '')
        needGen = False
        self.curpos = self.player.get_progress()
        if os.access(modLoc, 0):
            self.modwidth = 0
            if not self.mod.load_mood(modLoc):
                needGen = True
            self.updateplayerpos()
        else:
            needGen = True
        if needGen:
            self.mod.load_mood(None)
            self.updateplayerpos()
            self.pid = subprocess.Popen(['moodbar',
                                         track.get_local_path(), '-o', modLoc])
        self.haveMod = not needGen

        if self.modTimer: GLib.source_remove(self.modTimer)
        self.modTimer = GLib.timeout_add_seconds(1, self.updateMod)

    def play_start(self, type, player, track):
        self.lookformod(track)

    def play_end(self, type, player, track):
        if self.modTimer: GLib.source_remove(self.modTimer)
        self.modTimer = None
        self.haveMod = False
        self.mod.load_mood(None)
        self.mod.set_seek_position(None)
        self.mod.set_text(None)

    # update player's ui -----------------------------------------------------

    def updateMod(self):
        self.updateplayerpos()
        if not self.haveMod:
            logger.debug(_('Searching for mood...'))
            modLoc = self.moodsDir + '/' + self.playingTrack.replace(
                '/', '-') + ".mood"
            modLoc = modLoc.replace("'", '')
            if self.mod.load_mood(modLoc):
                logger.debug(_("Mood found."))
                self.haveMod = True
                self.modwidth = 0
        self.modTimer = GLib.timeout_add_seconds(1, self.updateMod)

    def updateplayerpos(self):
        if self.modTimer:
            if not self.seeking:
                self.curpos = self.player.get_progress()
                self.mod.set_seek_position(self.curpos)
            length = self.player.current.get_tag_raw('__length')
            seconds = self.player.get_time()
            remaining_seconds = length - seconds
            text = ("%d:%02d / %d:%02d" %
                    (seconds // 60, seconds % 60, remaining_seconds // 60,
                     remaining_seconds % 60))
            self.mod.set_text(text)
        else:
            if not self.seeking:
                self.mod.set_seek_position(None)

    #reading mod from file and update mood preview --------------------------

    def readMod(self, moodLoc):
        retur = True
        self.moodbar = ''
        try:
            if moodLoc == '':
                for i in range(3000):
                    self.moodbar = self.moodbar + chr(255)
                return True
            else:
                f = open(moodLoc, 'rb')
                for i in range(3000):
                    r = f.read(1)
                    if r == '':
                        r = chr(0)
                        retur = False
                    self.moodbar = self.moodbar + r
                f.close()
                return retur

        except:
            logger.debug(_('Could not read moodbar.'))
            self.moodbar = ''
            for i in range(3000):
                self.moodbar = self.moodbar + chr(0)
            return False

    #seeking-----------------------------------------------------------------

    def modSeekBegin(self, this, event):
        self.seeking = True

    def modSeekEnd(self, this, event):
        self.seeking = False
        track = self.player.current
        if not track or not (track.is_local() or \
                track.get_tag_raw('__length')):
            return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_size()
        value = mouse_x / progress_loc
        if value < 0: value = 0
        if value > 1: value = 1

        self.curpos = value
        length = track.get_tag_raw('__length')
        self.mod.set_seek_position(value)

        seconds = float(value * length)
        self.player.seek(seconds)

    def modSeekMotionNotify(self, this, event):
        if self.seeking:
            track = self.player.current
            if not track or not (track.is_local() or \
                    track.get_tag_raw('__length')):
                return

            mouse_x, mouse_y = event.get_coords()
            progress_loc = self.get_size()
            value = mouse_x / progress_loc
            if value < 0: value = 0
            if value > 1: value = 1

            self.curpos = value
            self.mod.set_seek_position(value)
            #todo: text

    #------------------------------------------------------------------------


def _enable_main_moodbar(exaile):
    global ExaileModbar
    logger.debug("Enabling main moodbar")
    ExaileModbar = ExModbar(
        player=player.PLAYER,
        progress_bar=exaile.gui.main.progress_bar
    )

    #ExaileModbar.readMod('')
    ExaileModbar.setupUi()
    ExaileModbar.add_callbacks()


def _disable_main_moodbar():
    global ExaileModbar
    logger.debug("Disabling main moodbar")
    ExaileModbar.changeModToBar()
    ExaileModbar.remove_callbacks()
    ExaileModbar.destroy()
    ExaileModbar = None


def _enable_preview_moodbar(event, preview_plugin, nothing):
    global PreviewMoodbar
    logger.debug("Enabling preview moodbar")
    PreviewMoodbar = ExModbar(
        player=preview_plugin.player,
        progress_bar=preview_plugin.progress_bar
    )

    #PreviewMoodbar.readMod('')
    PreviewMoodbar.setupUi()
    PreviewMoodbar.add_callbacks()


def _disable_preview_moodbar(event, preview_plugin, nothing):
    global PreviewMoodbar
    logger.debug("Disabling preview moodbar")
    PreviewMoodbar.changeModToBar()
    PreviewMoodbar.remove_callbacks()
    PreviewMoodbar.destroy()
    PreviewMoodbar = None


def enable(exaile):
    try:
        subprocess.call(['moodbar', '--help'], stdout=-1, stderr=-1)
    except OSError:
        raise NotImplementedError(_('Moodbar executable is not available.'))
        return False

    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _get_preview_plugin_if_active(exaile):
    previewdevice = exaile.plugins.enabled_plugins.get('previewdevice', None)
    return getattr(previewdevice, 'PREVIEW_PLUGIN', None)

def _enable(eventname, exaile, nothing):
    _enable_main_moodbar(exaile)

    event.add_callback(_enable_preview_moodbar, 'preview_device_enabled')
    event.add_callback(_disable_preview_moodbar, 'preview_device_disabling')

    preview_plugin = _get_preview_plugin_if_active(exaile)
    if getattr(preview_plugin, 'hooked', False):
        _enable_preview_moodbar('', preview_plugin, None)


def disable(exaile):
    _disable_main_moodbar()

    event.remove_callback(_enable_preview_moodbar, 'preview_device_enabled')
    event.remove_callback(_disable_preview_moodbar, 'preview_device_disabling')

    preview_plugin = _get_preview_plugin_if_active(exaile)
    if getattr(preview_plugin, 'hooked', False):
        _disable_preview_moodbar('', preview_plugin, None)


def get_preferences_pane():
    return moodbarprefs

#have errors from time to time:
#python: ../../src/xcb_lock.c:77: _XGetXCBBuffer: Assertion `((int) ((xcb_req) - (dpy->request)) >= 0)' failed.

#exaile.py: Fatal IO error 11 (Resource temporarily unavailable) on X server :0.0.

#Xlib: sequence lost (0xe0000 > 0xd4add) in reply type 0x0!
#python: ../../src/xcb_io.c:176: process_responses: Assertion `!(req && current_request && !(((long) (req->sequence) - (long) (current_request)) <= 0))' failed.

#0.0.4 haven't errors
