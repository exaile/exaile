# Copyright (C) 2008-2009 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

# Settings
#
# stores settings


from __future__ import with_statement

import logging, os
from ConfigParser import RawConfigParser, NoSectionError, NoOptionError

logger = logging.getLogger(__name__)

from xl import event, xdg
from xl.common import VersionError
from xl.nls import gettext as _

TYPE_MAPPING = {
        'I': int,
        'S': str,
        'F': float,
        'B': bool,
        'L': list,
        'D': dict,
        'U': unicode
        }

_SETTINGSMANAGER = None

class SettingsManager(RawConfigParser):
    """
        Manages exaile's settings
    """
    settings = None
    __version__ = 1
    def __init__(self, loc, defaultloc=None):
        """
            Sets up the SettingsManager. Expects a loc to a file
            where settings will be stored.

            If loc is None, these settings will never be stored nor read from a
            file

            defaultloc is a loc to initialize settings from
        """
        RawConfigParser.__init__(self)
        self.loc = loc
        self._saving = False
        self._dirty = False

        if defaultloc is not None:
            try:
                self.read(defaultloc)
            except:
                pass

        if loc is not None:
            try:
                self.read(self.loc) or \
                    self.read(self.loc + ".new") or \
                    self.read(self.loc + ".old")
            except:
                pass

        if not self.get_option('settings/version', 0):
            self.set_option('settings/version', self.__version__)

        if self.get_option('settings/version', 0) > self.__version__:
            raise VersionError(_('Settings version is newer than current.'))

        # save settings every 30 seconds
        if loc is not None:
            event.timeout_add(30000, self._timeout_save)

    def _timeout_save(self):
        logger.debug("Requesting save from timeout...")
        self.save()
        return True

    def copy_settings(self, settings):
        """
            Copies one all of the settings contained in this instance to
            another
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

    def set_option(self, option, value):
        """
            Set an option (in section/key syntax) to the specified value.
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
        event.log_event('option_set', self, option)
        event.log_event('%s_option_set'%section, self, option)

    def get_option(self, option, default=None):
        """
            Get the value of an option (in section/key syntax), returning
            default if the key does not exist yet.
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

    def _set_direct(self, option, value):
        """
            Sets the option directly to the value, only for use in copying
            settings.
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
        for k, v in TYPE_MAPPING.iteritems():
            if v == type(value):
                if v == list:
                    return k + ": " + repr(value)
                else:
                    return k + ": " + str(value)
        raise ValueError(_("We don't know how to store that kind of setting: "),
            type(value))

    def _str_to_val(self, value):
        """
            Convert setting strings back to normal values.
        """
        try:
            kind, value = value.split(': ', 1)
        except ValueError:
            return ''

        # Lists are special case
        if kind == 'L':
            return eval(value)

        # So are dictionaries
        if kind == 'D':
            return eval(value)

        if kind in TYPE_MAPPING.keys():
            if kind == 'B':
                if value != 'True':
                    return False
            value = TYPE_MAPPING[kind](value)
            return value
        else:
            raise ValueError(_("An Unknown type of setting was found!"))

    def save(self):
        """
            Save the settings to disk
        """
        if self.loc is None:
            logger.debug("Save requested but not saving settings, loc is None")
            return
        if self._saving or not self._dirty: return
        self._saving = True

        logger.debug("Saving settings...")
        with open(self.loc + ".new", 'w') as f:
            self.write(f)
            try:
                # make it readable by current user only, to protect private data
                os.fchmod(f.fileno(), 384)
            except:
                pass # fail gracefully, eg if on windows
            f.flush()
        try:
            os.rename(self.loc, self.loc + ".old")
        except:
            pass # if it doesn'texist we don't care
        os.rename(self.loc + ".new", self.loc)
        try:
            os.remove(self.loc + ".old")
        except:
            pass

        self._saving = False
        self._dirty = False

_SETTINGSMANAGER = SettingsManager(
        os.path.join(xdg.get_config_dir(), "settings.ini" ),
        xdg.get_config_path("settings.ini")
        )

get_option = _SETTINGSMANAGER.get_option
set_option = _SETTINGSMANAGER.set_option

# vim: et sts=4 sw=4
