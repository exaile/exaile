# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

"""
    Central storage of application and user settings
"""

import ast
from configparser import RawConfigParser, NoSectionError, NoOptionError
import logging
import os
import sys
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

from xl import event, xdg
from xl.common import VersionError, glib_wait, glib_wait_seconds
from xl.nls import gettext as _

MANAGER = None


class SettingsManager(RawConfigParser):
    """
    Manages Exaile's settings
    """

    VERSION: ClassVar[int] = 2

    _last_serial: ClassVar[int] = 0

    # xl.common.glib_wait needs instances of this class to be hashable to use
    # as key in its WeakKeyDictionary. We simply use an increasing serial
    # number as this hash.
    _serial: int

    def __init__(self, location=None, default_location=None):
        """
        Sets up the settings manager. Expects a location
        to a file where settings will be stored. Also sets up
        periodic saves to disk.

        :param location: the location to save the settings to,
            settings will never be stored if this is None
        :type location: str or None
        :param default_location: the default location to
            initialize settings from
        """
        RawConfigParser.__init__(self)

        self.location = location
        self._saving = False
        self._dirty = False

        self._serial = self.__class__._last_serial = self.__class__._last_serial + 1

        if default_location is not None:
            try:
                self.read(default_location)
            except Exception:
                pass

        if location is not None:
            try:
                self.read(self.location) or self.read(
                    self.location + ".new"
                ) or self.read(self.location + ".old")
            except Exception:
                pass

        version = self.get_option('settings/version')
        if version and version > self.VERSION:
            raise VersionError(_('Settings version is newer than current.'))
        if version != self.VERSION:
            self.set_option('settings/version', self.VERSION)

        # save settings every 30 seconds
        if location is not None:
            self._timeout_save()

    def __hash__(self):
        return self._serial

    @glib_wait_seconds(30)
    def _timeout_save(self):
        """Save every 30 seconds"""
        self.save()
        return True

    def copy_settings(self, settings):
        """
        Copies one all of the settings contained
        in this instance to another

        :param settings: the settings object to copy to
        :type settings: :class:`xl.settings.SettingsManager`
        """
        for section in self.sections():
            for (key, value) in self.items(section):
                settings._set_direct('%s/%s' % (section, key), value)

    def clone(self):
        """
        Creates a copy of this settings object
        """
        settings = SettingsManager(None)
        self.copy_settings(settings)
        return settings

    def set_option(self, option, value, save=True):
        """
        Set an option (in ``section/key`` syntax) to the specified value

        :param option: the full path to an option
        :type option: string
        :param value: the value the option should be assigned
        :type value: any
        :param save: If True, cause the settings to be written to file
        """
        value = self._val_to_str(value)
        splitvals = option.split('/')
        section, key = "/".join(splitvals[:-1]), splitvals[-1]

        try:
            self.set(section, key, value)
        except NoSectionError:
            self.add_section(section)
            self.set(section, key, value)

        self._dirty = True

        if save:
            self.delayed_save()

        section = section.replace('/', '_')

        event.log_event('option_set', self, option)
        event.log_event('%s_option_set' % section, self, option)

    def get_option(self, option: str, default: Any = None) -> Any:
        """
        Get the value of an option (in ``section/key`` syntax),
        returning *default* if the key does not exist yet

        :param option: the full path to an option
        :param default: a default value to use as fallback
        :returns: the option value or *default*
        """
        splitvals = option.split('/')
        section, key = "/".join(splitvals[:-1]), splitvals[-1]

        try:
            value = self.get(section, key)
            value = self._str_to_val(value)
        except NoSectionError:
            value = default
        except NoOptionError:
            value = default

        return value

    def has_option(self, option):
        """
        Returns information about the existence
        of a particular option

        :param option: the option path
        :type option: string
        :returns: whether the option exists or not
        :rtype: bool
        """
        splitvals = option.split('/')
        section, key = "/".join(splitvals[:-1]), splitvals[-1]

        return RawConfigParser.has_option(self, section, key)

    def remove_option(self, option):
        """
        Removes an option (in ``section/key`` syntax),
        thus will not be saved anymore

        :param option: the option path
        :type option: string
        """
        splitvals = option.split('/')
        section, key = "/".join(splitvals[:-1]), splitvals[-1]

        RawConfigParser.remove_option(self, section, key)

    def _set_direct(self, option, value):
        """
        Sets the option directly to the value,
        only for use in copying settings.

        :param option: the option path
        :type option: string
        :param value: the value to set
        :type value: any
        """
        splitvals = option.split('/')
        section, key = "/".join(splitvals[:-1]), splitvals[-1]

        try:
            self.set(section, key, value)
        except NoSectionError:
            self.add_section(section)
            self.set(section, key, value)

        event.log_event('option_set', self, option)

    def _val_to_str(self, value):
        """
        Turns a value of some type into a string so it
        can be a configuration value.
        """
        for kind, type_ in (
            # bool is subclass of int so it must appear earlier
            ('B', bool),
            ('I', int),
            ('F', float),
            ('L', list),
            ('D', dict),
        ):
            if isinstance(value, type_):
                return '%s: %r' % (kind, value)
        if isinstance(value, str):
            return 'S: %s' % value  # Not quoted, hence %s

        raise ValueError(
            "Don't know how to store setting %r of type %s" % (value, type(value))
        )

    def _str_to_val(self, configstr):
        """
        Convert setting strings back to normal values.
        """
        try:
            kind, value = configstr.split(': ', 1)
        except ValueError:
            return ''

        if kind == 'B':  # Must appear before I
            return value == 'True'
        if kind in 'SU':  # U is for backwards compatibility (Python 2 unicode)
            return value
        try:
            if kind == 'I':
                return int(value)
            if kind == 'F':
                return float(value)
            for kind in 'LD':
                return ast.literal_eval(value)
        except Exception:
            logger.exception("Failed decoding value %r of kind %s", value, kind)
            return value

        raise ValueError("Unknown type of setting on: %s", configstr)

    @glib_wait(500)
    def delayed_save(self):
        '''Save options after a delay, waiting for multiple saves to accumulate'''
        self.save()

    def save(self):
        """
        Save the settings to disk
        """
        if self.location is None:
            logger.debug("Save requested but not saving settings, " "location is None")
            return

        if self._saving or not self._dirty:
            return

        self._saving = True

        logger.debug("Saving settings...")

        with open(self.location + ".new", 'w') as f:
            self.write(f)

            try:
                # make it readable by current user only, to protect private data
                os.fchmod(f.fileno(), 384)
            except Exception:
                pass  # fail gracefully, eg if on windows

            f.flush()

        try:
            os.rename(self.location, self.location + ".old")
        except Exception:
            pass  # if it doesn'texist we don't care

        os.rename(self.location + ".new", self.location)

        try:
            os.remove(self.location + ".old")
        except Exception:
            pass

        self._saving = False
        self._dirty = False


location = xdg.get_config_dir()


# Provide a mechanism for setting up default settings for different platforms
if sys.platform == 'win32':
    __settings_file = 'settings-win32.ini'
elif sys.platform == 'darwin':
    __settings_file = 'settings-osx.ini'
else:
    __settings_file = 'settings.ini'


MANAGER = SettingsManager(
    os.path.join(location, "settings.ini"), xdg.get_config_path("settings.ini")
)

get_option = MANAGER.get_option
set_option = MANAGER.set_option

# vim: et sts=4 sw=4
