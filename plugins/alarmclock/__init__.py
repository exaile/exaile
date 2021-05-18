import logging

from gi.repository import GLib

from xl import player, event
from xl import settings as xl_settings
from . import acprefs


LOGGER = logging.getLogger(__name__)


class AlarmClock:
    def __init__(self):
        self.__timeout_id = None
        self.__fade_id = None
        self.__current_volume = None
        event.add_callback(self.__on_option_set, 'plugin_alarmclock_option_set')
        self.__update_timeout()

    def stop_timeout(self):
        if self.__timeout_id is not None:
            GLib.Source.remove(self.__timeout_id)
            self.__timeout_id = None

    def abort_fade(self):
        if self.__fade_id is not None:
            GLib.Source.remove(self.__fade_id)
            self.__fade_id = None
            max_volume = self.__get_pref(acprefs.MaxVolumePreference)
            player.PLAYER.set_volume(max_volume)

    @staticmethod
    def __is_weekday_enabled(day_nr):
        "day_nr starts with 1=Monday, 2=Tuesday, ..., 7=Sunday"
        if day_nr < 1 or day_nr > 7:
            raise ValueError

        weekdays = [
            acprefs.MondayPreference,
            acprefs.TuesdayPreference,
            acprefs.WednesdayPreference,
            acprefs.ThursdayPreference,
            acprefs.FridayPreference,
            acprefs.SaturdayPreference,
            acprefs.SundayPreference,
        ]
        pref_class = weekdays[day_nr - 1]
        return AlarmClock.__get_pref(pref_class)

    @staticmethod
    def __get_pref(pref_class):
        return xl_settings.get_option(pref_class.name, pref_class.default)

    def __update_timeout(self):
        LOGGER.debug("Updating timeout")
        self.stop_timeout()
        current = GLib.DateTime.new_now_local()
        hour = self.__get_pref(acprefs.HourPreference)
        minute = self.__get_pref(acprefs.MinutesPreference)
        tmp_timer = GLib.DateTime.new_local(
            current.get_year(),
            current.get_month(),
            current.get_day_of_month(),
            hour,
            minute,
            0,
        )

        next_timer = None
        for delta_days in range(0, 8):  # current weekday is checked twice intentional
            next_timer = tmp_timer.add_days(delta_days)
            if next_timer.difference(current) <= 0:
                next_timer = None
                continue
            if self.__is_weekday_enabled(next_timer.get_day_of_week()):
                break
            else:
                next_timer = None
                continue

        if next_timer is None:  # no alarm enabled
            LOGGER.debug("No alarm enabled")
            return

        diff = next_timer.difference(current) // 1000
        LOGGER.debug(
            "Alarm due in %i seconds (%i hours)", diff // 1000, diff // 3600000
        )
        self.__timeout_id = GLib.timeout_add(diff, self.__on_timeout_finished)

    def __on_timeout_finished(self):
        LOGGER.debug("Finished timeout")
        # make alarm
        if self.__get_pref(acprefs.FadingPreference):
            min_volume = self.__get_pref(acprefs.MinVolumePreference)
            self.__current_volume = min_volume
            player.PLAYER.set_volume(self.__current_volume)
            timer_step = self.__get_pref(acprefs.TimerStepPreference)
            self.__fade_id = GLib.timeout_add(timer_step * 1000, self.__fade_in)
        else:
            max_volume = self.__get_pref(acprefs.MaxVolumePreference)
            player.PLAYER.set_volume(max_volume)

        if not player.PLAYER.is_playing():
            if player.PLAYER.is_paused():
                player.PLAYER.unpause()
            elif player.PLAYER.current is not None:
                player.PLAYER.play(player.PLAYER.current)
            else:
                # TODO: handle this case better
                LOGGER.error("No song found to play")

        # prepare for next run
        self.__update_timeout()
        return GLib.SOURCE_REMOVE

    def __fade_in(self):
        increment = self.__get_pref(acprefs.IncrementPreference)
        # try to detect whether the user interacted with exaile and abort
        delta_volume = abs(player.PLAYER.get_volume() - self.__current_volume)
        if (
            player.PLAYER.is_paused()
            or not player.PLAYER.is_playing()
            or delta_volume > (increment / 2)
        ):
            self.__fade_id = None
            LOGGER.debug("Aborting fade in because of user interaction")
            return GLib.SOURCE_REMOVE

        new_volume = self.__current_volume + increment

        max_volume = self.__get_pref(acprefs.MaxVolumePreference)
        # check whether we finished fading in
        if new_volume >= max_volume:
            player.PLAYER.set_volume(max_volume)
            self.__fade_id = None
            LOGGER.debug("Finished fading in.")
            return GLib.SOURCE_REMOVE

        self.__current_volume = new_volume
        player.PLAYER.set_volume(new_volume)
        return GLib.SOURCE_CONTINUE

    def __on_option_set(self, _event, _settings, option):
        if 'alarm_' not in option:
            self.__update_timeout()


class AlarmclockPlugin:
    def __init__(self):
        self.__alarm_clock = None

    def enable(self, _exaile):
        self.__alarm_clock = AlarmClock()

    def disable(self, _exaile):
        self.__alarm_clock.stop_timeout()
        self.__alarm_clock.abort_fade()

    def get_preferences_pane(self):
        return acprefs


plugin_class = AlarmclockPlugin
