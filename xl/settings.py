# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# Settings
#
# stores settings


from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError

import os, logging
logger = logging.getLogger(__name__)

from xl import event
# FIXME: Drop this after getting rid of non-callable 'unicode' object error
from xl.nls import gettext as _

TYPE_MAPPING = {
        'I': int,
        'S': str,
        'F': float,
        'B': bool,
        'L': list,
        'U': unicode}

class SettingsManager(SafeConfigParser):
    """
        Manages exaile's settings
    """
    settings = None
    def __init__(self, loc=None):
        """
            Sets up the SettingsManager. Expects a loc to a file
            where settings will be stored.
        """
        logger.info(_("Loading settings"))
        SafeConfigParser.__init__(self)
        self.loc = loc
        self._saving = False
        self._dirty = False

        if loc:
            try:
                self.read(self.loc)
            except:
                pass

        if not SettingsManager.settings:
            SettingsManager.settings = self

            # save settings every 30 seconds
            event.timeout_add(30000, self._timeout_save)

    def _timeout_save(self):
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
        settings = SettingsManager()
        self.copy_settings(settings)
        return settings

    def set_option(self, option, value):
        """
            Set an option (in section/key syntax) to the specified value.
        """
        value = self._val_to_str(value)
        splitvals = option.split('/')
        section, key = "".join(splitvals[:-1]), splitvals[-1]
        try:
            self.set(section, key, value)
        except NoSectionError:
            self.add_section(section)
            self.set(section, key, value)
        self._dirty = True
        event.log_event('option_set', self, option)

    def get_option(self, option, default=None):
        """
            Get the value of an option (in section/key syntax), returning
            default if the key does not exist yet.
        """
        splitvals = option.split('/')
        section, key = "".join(splitvals[:-1]), splitvals[-1]
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
        section, key = "".join(splitvals[:-1]), splitvals[-1]
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
        raise ValueError("We don't know how to store that kind of setting: ",
            type(value))

    def _str_to_val(self, value):
        """
            Convert setting strings back to normal values.
        """
        kind = value.split(':')[0]
        value = value.split(':')[1][1:]

        # lists are special case
        if kind == 'L':
            return eval(value)

        if kind in TYPE_MAPPING.keys():
            if kind == 'B':
                if value != 'True':
                    return False
            value = TYPE_MAPPING[kind](value)
            return value
        else:
            raise ValueError("An Unknown type of setting was found!")

    def __setitem__(self, option, value):
        """
            same as set_option
        """
        self.set_option(option, value)

    def __getitem__(self, option):
        """
            same as get_option
        """
        return self.get_option(option)

    def save(self):
        """
            Save the settings to disk
        """
        if self._saving or self._dirty: return
        self._saving = True
        f = open(self.loc, 'w')
        self.write(f)
        self._saving = False
        self._dirty = False

# vim: et sts=4 sw=4

