
from gi.repository import GLib

import time
import thread
from gettext import gettext as _
from xl import player
from xl.plugins import PluginsManager
import acprefs
from xl import settings


class VolumeControl:

    def __init__(self):
        self.thread = thread

    def print_debug(self):
        print(self.min_volume)
        print(self.max_volume)
        print(self.increment)
        print(self.time_per_inc)

    def fade_in(self):
        temp_volume = self.min_volume
        while temp_volume <= self.max_volume:
            # print "set volume to %s" % str(temp_volume / 100.0)
            player.PLAYER.set_volume((temp_volume / 100.0))
            temp_volume += self.increment
            time.sleep(self.time_per_inc)
            if player.PLAYER.is_paused() or not player.PLAYER.is_playing():
                self.stop_fading()

    def fade_out(self):
        temp_volume = self.max_volume
        while temp_volume >= self.min_volume:
            # print "set volume to %d" % (temp_volume / 100.0)
            player.PLAYER.set_volume((temp_volume / 100.0))
            temp_volume -= self.increment
            time.sleep(self.time_per_inc)
            if player.PLAYER.is_paused() or not player.PLAYER.is_playing():
                self.stop_fading()

    def fade_in_thread(self):
        if self.use_fading == "True":
            self.thread.start_new(self.fade_in, ())

    def stop_fading(self):
        self.thread.exit()

    def load_settings(self):
        prefix = "plugin/alarmclock/"
        # Setting name, property to save to, default value
        setting_values = (
            ('alarm_use_fading', 'use_fading', False),
            ('alarm_min_volume', 'min_volume', 0),
            ('alarm_max_volume', 'max_volume', 100),
            ('alarm_increment', 'increment', 1),
            ('alarm_time_per_inc', 'time_per_inc', 1),
        )
        for name, prop, default in setting_values:
            setattr(self, prop,
                    settings.get_option(prefix + name, default))


class Alarmclock(object):

    def __init__(self):
        self.last_activate = None
        self.timer_id = None
        self.volume_control = VolumeControl()

    def timout_alarm(self):
        """
        Called every 5 seconds.  If the plugin is not enabled, it does
        nothing.  If the current time matches the time specified, it starts
        playing
        """

        self.hour = int(settings.get_option('plugin/alarmclock/hour', 15))
        self.minuts = int(settings.get_option('plugin/alarmclock/minuts', 20))
        self.volume_control.load_settings()
        active_days = [
            settings.get_option('plugin/alarmclock/sunday', False),
            settings.get_option('plugin/alarmclock/monday', False),
            settings.get_option('plugin/alarmclock/tuesday', False),
            settings.get_option('plugin/alarmclock/wednesday', False),
            settings.get_option('plugin/alarmclock/thursday', False),
            settings.get_option('plugin/alarmclock/friday', False),
            settings.get_option('plugin/alarmclock/saturday', False)
        ]

        if True not in active_days:
            return True

        current = time.strftime("%H:%M", time.localtime())
        curhour = int(current.split(":")[0])
        curminuts = int(current.split(":")[1])
        currentDay = int(time.strftime("%w", time.localtime()))

        if curhour == self.hour and curminuts == self.minuts and \
                active_days[currentDay] == True:

            if current != self.last_activate:

                self.last_activate = current
                track = player.PLAYER.current
                if track and (player.PLAYER.is_playing() or player.PLAYER.is_paused()):
                    return True
                player.QUEUE.play()
                self.volume_control.fade_in_thread()
        else:
            self.last_activate = None

        return True

    def enable(self, exaile):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add_seconds(5, self.timout_alarm)

    def disable(self, exaile):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        self.timer_id = None

    def get_preferences_pane(self):
        return acprefs


plugin_class = Alarmclock
