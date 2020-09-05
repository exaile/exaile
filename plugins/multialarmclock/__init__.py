# Copyright (C) 2010 by Brian Parma
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


from gi.repository import GLib
from gi.repository import Gtk

import time
import os
from xlgui import guiutil
from xl import event, player, settings, xdg, common
from functools import wraps
import logging
from . import macprefs
from .cellrenderers import CellRendererDays

import json

write = lambda x: json.dumps(x, indent=2)
read = json.loads

logger = logging.getLogger(__name__)

PLUGIN_ENABLED = False
TIMER_ID = None
MENU_ITEM = None
ALARM_CLOCK_MAIN = None
MY_BUILDER = None


def _init(prefsdialog, builder):
    '''Since I don't know if init() or enable() will be called first, save builder and setup UI if enabled() was already called.'''
    logger.debug('_init() called')
    global MY_BUILDER, ALARM_CLOCK_MAIN

    # note that we get a new builder everytime the prefs dialog is closed and re-opened
    MY_BUILDER = builder
    if ALARM_CLOCK_MAIN is not None:
        ALARM_CLOCK_MAIN.init_ui(builder)


def get_preferences_pane():
    '''Return prefs pane for preferences dialog'''
    logger.debug('get_preferences_pane() called')
    macprefs.init = _init
    return macprefs


def idle_add(f):
    '''Decorator that runs a function through GLib.idle_add'''

    @wraps(f)
    def idler(*args, **kwargs):
        GLib.idle_add(f, *args, **kwargs)

    return idler


###><><><### Alarm Clock Stuph ###><><><###


class Alarm:
    """
    Class for individual alarms.
    """

    def __init__(self, time="09:00", days=None, name="New Alarm", active=True, dict={}):
        self.active = active
        self.time = time
        self.name = name
        if days is None:
            self.days = [True] * 7
        else:
            self.days = days

        # For setting attributes by dictionary
        self.__dict__.update(dict)

    def on(self):
        self.active = True

    def off(self):
        self.active = False

    def toggle(self):
        if self.active:
            self.off()
        else:
            self.on()


class AlarmClock:
    """
    Class that handles the TreeView interaction and keeps track of alarms.
    """

    def __init__(self, exaile):
        self.RANG = {}  # Keep track of alarms that have gone off
        self.exaile = exaile
        #        self.view_window = None
        #        self.view = None

        # Create Model
        self.model = Gtk.ListStore(bool, str, str, object, str)

        # Load any saved alarms
        self.load_list()

    def _create_view(self):
        '''Create treeview to display model'''
        # Create View
        view = Gtk.TreeView()
        view.set_model(self.model)

        # setup view
        cr = Gtk.CellRendererToggle()
        cr.connect('toggled', self.enable_cb)
        col = Gtk.TreeViewColumn('Enabled', cr, active=0)
        view.append_column(col)

        cr = Gtk.CellRendererText()
        cr.connect('edited', self.text_edited, 1)
        cr.set_property('editable', True)
        col = Gtk.TreeViewColumn('Name', cr, text=1)
        view.append_column(col)

        cr = Gtk.CellRendererText()
        cr.connect('edited', self.text_edited, 2)
        cr.set_property('editable', True)
        col = Gtk.TreeViewColumn('Time', cr, text=2)
        view.append_column(col)

        # custom CellRenderer for Days Popup
        cr = CellRendererDays()
        cr.connect('days-changed', self.days_changed)
        cr.set_property('editable', True)
        col = Gtk.TreeViewColumn('Days', cr, days=3, text=4)
        view.append_column(col)

        return view

    def enable_cb(self, cell, path):
        '''Callback for toggling an alarm on/off'''
        active = self.model[path][0]
        self.model[path][0] = not active

        logger.debug(
            'Alarm {0} {1}abled.'.format(self.model[path][1], 'dis' if active else 'en')
        )

        # save change
        self.save_list()

    def init_ui(self, builder):
        '''Called by exaile to initialize prefs pane.  Set up pefs UI'''
        logger.debug('init_ui() called.')

        #        if self.view_window is not None:
        # already setup
        #            return

        # grab widgets
        view_window = builder.get_object('alarm_scrolledwindow')
        add_button = builder.get_object('add_button')
        del_button = builder.get_object('remove_button')

        # when a plugin is disabled and re-enabled, the preferences pane is not re-created until the prefs dialog is closed
        # so if we recycle our class and create a new one, we have to replace the old TreeView with our new one.
        #   NOTE: reloading the plugin from prefs page (DEBUG MODE) breaks this anyway
        child = view_window.get_child()
        view = self._create_view()
        if child is not None:
            logger.debug('stale treeview found, replacing...')
            guiutil.gtk_widget_replace(child, view)
        else:
            view_window.add(view)

        # signals
        add_button.connect('clicked', self.add_button)
        del_button.connect('clicked', self.delete_button, view.get_selection())

    def days_changed(self, cr, path, days):
        '''Callback for change of selected days for selected alarm'''
        # update model
        self.model[path][3] = days

        # update display
        days_str = ['Su', 'M', 'Tu', 'W', 'Th', 'F', 'Sa']
        self.model[path][4] = ','.join([days_str[i] for i in range(0, 7) if days[i]])

        # save changes
        self.save_list()

    def text_edited(self, cr, path, new_text, idx):
        '''Callback for edit of text columns (name and time)'''
        old_text = self.model[path][idx]
        if old_text == new_text:
            return  # No change

        if idx == 1:  # Name edit
            self.model[path][1] = new_text

            # save change
            self.save_list()

        elif idx == 2:  # Time edit
            # validate
            try:
                t = time.strptime(new_text, '%H:%M')
                new_text = time.strftime('%H:%M', t)  # ensure consistent 0-padding
            except ValueError:
                logger.warning('Invalid time format, use: HH:MM (24-hour)')
                return

            # update
            self.model[path][2] = new_text

            # save change
            self.save_list()

    def add_alarm(self, alarm):
        '''Add an alarm to the model'''
        # update display
        days_str = ['Su', 'M', 'Tu', 'W', 'Th', 'F', 'Sa']
        day_disp = ','.join([days_str[i] for i in range(0, 7) if alarm.days[i]])
        self.model.append([alarm.active, alarm.name, alarm.time, alarm.days, day_disp])

        # save list changes - NO, called by loader

    #        self.save_list()

    def add_button(self, widget):
        '''Callback for clicking add button'''
        # generate unique name
        names = [row[1] for row in self.model]
        base = 'Alarm'
        name = base
        i = 0
        while name in names:
            i = i + 1
            name = base + ' {0}'.format(i)

        # add the new alarm
        alarm = Alarm(name=name)
        self.add_alarm(alarm)

        # save list changes
        self.save_list()

    def delete_button(self, widget, selection):
        '''Callback for clicking the delete button'''
        # get selected row
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            model.remove(tree_iter)

            # save list changes
            self.save_list()
        else:
            logger.info('No alarm selected for removal.')

    def load_list(self):
        '''Load alarms from file'''
        logger.debug('load_list() called.')
        path = os.path.join(xdg.get_data_dirs()[0], 'alarmlist.dat')
        try:
            # Load Alarm List from file.
            # Open in non-binary mode, because we are reading json
            # string.
            with open(path, 'r') as f:
                raw = f.read()
                try:
                    alist = _read(raw)
                    assert isinstance(
                        alist, list
                    )  # should be list of dicts (new format)

                except Exception:
                    try:
                        # try to import old format
                        for line in raw.strip().split('\n'):
                            a = Alarm(dict=eval(line, {'__builtin__': None}))
                            logger.debug(
                                'loaded alarm {0} ({1}) from file.'.format(
                                    a.name, a.time
                                )
                            )
                            self.add_alarm(a)

                        # force save in new format
                        logger.info('Old alarm file format found, converting.')
                        self.save_list()

                    except Exception as e:
                        logger.warning(
                            'Failed to load alarm data from file: {0}'.format(e)
                        )

                else:
                    for a in alist:
                        alarm = Alarm(dict=a)
                        logger.debug(
                            'loaded alarm {0} ({1}) from file.'.format(
                                alarm.name, alarm.time
                            )
                        )
                        self.add_alarm(alarm)

        except IOError as e:  # File might not exist
            logger.warning('Could not open file: {0}'.format(e.strerror))

    @idle_add
    def save_list(self):
        '''Save alarms to file'''
        logger.debug('save_list() called.')

        # Save List
        path = os.path.join(xdg.get_data_dirs()[0], 'alarmlist.dat')

        if len(self.model) > 0:
            alist = [
                {'active': row[0], 'name': row[1], 'time': row[2], 'days': row[3]}
                for row in self.model
            ]

            # Open in non-binary mode, because we are writing json
            # string.
            with open(path, 'w') as f:
                f.write(_write(alist))
                logger.debug('saving {0} alarms.'.format(len(alist)))


###><><><### Globals ###><><><###

# This is here because sometimes get_prefs_pane gets called before _enabled
# ALARM_CLOCK_MAIN = AlarmClock(exaile)


@common.threaded
def fade_in(main, exaile):
    '''Fade exaile's volume from min to max'''
    logger.debug('fade_in() called.')

    # pull settings
    temp_volume = (
        settings.get_option('plugin/multialarmclock/fade_min_volume', 0) / 100.0
    )
    fade_max_volume = (
        settings.get_option('plugin/multialarmclock/fade_max_volume', 100) / 100.0
    )
    fade_inc = settings.get_option('plugin/multialarmclock/fade_increment', 1) / 100.0
    time_per_inc = settings.get_option('plugin/multialarmclock/fade_time', 30) / (
        (fade_max_volume - temp_volume) / fade_inc
    )

    while temp_volume < fade_max_volume:
        logger.debug('set volume to {0}'.format(temp_volume))

        settings.set_option('player/volume', temp_volume)
        temp_volume += fade_inc
        time.sleep(time_per_inc)
        if player.PLAYER.is_paused() or not player.PLAYER.is_playing():
            return

    settings.set_option('player/volume', fade_max_volume)


def check_alarms(main, exaile):
    """
    Called every timeout.  If the plugin is not enabled, it does
    nothing.  If the current time matches the time specified and the
    current day is selected, it starts playing
    """
    if not main:
        return True  # TODO: new way?

    current = time.strftime("%H:%M", time.localtime())
    currentDay = int(time.strftime("%w", time.localtime()))

    # generate list of alarms from model
    alist = [
        Alarm(active=row[0], name=row[1], time=row[2], days=row[3])
        for row in main.model
    ]
    # print(current , [ a.time for a in alist if a.active ])
    for al in alist:
        if al.active and al.time == current and al.days[currentDay] is True:
            check = time.strftime("%m %d %Y %H:%M")  # clever...

            if check in main.RANG:
                logger.debug('Alarm {0} in RANG'.format(al.name))
                return True

            logger.info('Alarm {0} hit.'.format(al.name))

            # tracks to play?
            count = len(player.QUEUE)
            if player.QUEUE.current_playlist:
                count += len(player.QUEUE.current_playlist)
            else:
                count += len(exaile.gui.main.get_selected_page().playlist)

            if count == 0:
                logger.warning('No tracks queued for alarm to play.')
                return True

            if (
                player.PLAYER.is_playing()
            ):  # Check if there are songs in playlist and if it is already playing
                logger.info('Alarm hit, but already playing')
                return True

            if settings.get_option('plugin/multialarmclock/fading_on'):
                fade_in(main, exaile)

            if settings.get_option('plugin/multialarmclock/restart_playlist_on'):
                logger.debug('try to restart playlist')
                if player.QUEUE.current_playlist:
                    player.QUEUE.current_playlist.set_current_position(-1)
                else:
                    player.QUEUE.set_current_playlist(
                        exaile.gui.main.get_selected_page().playlist
                    )

            player.QUEUE.play()

            main.RANG[check] = True

    return True


###><><><### Plugin Handling Functions ###><><><###


def enable(exaile):
    '''Called by exaile to enable plugin'''
    if exaile.loading:
        logger.debug('waitin for loaded event')
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


@idle_add
def _enable(stuff, exaile, junk):
    """
    Enable plugin.  Start timer and create class.
    """
    logger.debug('_enable called')
    global TIMER_ID, MENU_ITEM, ALARM_CLOCK_MAIN, MY_BUILDER

    if ALARM_CLOCK_MAIN is None:
        ALARM_CLOCK_MAIN = AlarmClock(exaile)

    main = ALARM_CLOCK_MAIN

    if MY_BUILDER is not None:
        # '''Since I don't know if init() or enable() will be called first, save builder and setup UI if enabled() was already called.'''
        main.init_ui(MY_BUILDER)

    TIMER_ID = GLib.timeout_add_seconds(5, check_alarms, main, exaile)


def disable(exaile):
    """
    Called when plugin is unloaded.  Stop timer.
    """
    global TIMER_ID, MENU_ITEM, ALARM_CLOCK_MAIN, MY_BUILDER

    # Cleanup
    if TIMER_ID is not None:
        GLib.source_remove(TIMER_ID)
        TIMER_ID = None

    if ALARM_CLOCK_MAIN is not None:
        ALARM_CLOCK_MAIN = None


#   disable/enable doesn't re-call init(), so if we scrap and re-create the class, we wont' get our Gtk.Builder back, and there will
#   be a disconnect between the Alarm class and the UI in the prefs page
#   NOTE: reloading the plugin from prefs page (DEBUG MODE) breaks this anyway
#    if MY_BUILDER is not None:
#        MY_BUILDER = None
