# Settings
#
# stores settings


from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError

import os

from xl import event

TYPE_MAPPING = {
        'I': int,
        'S': str,
        'F': float,
        'B': bool }

class SettingsManager(SafeConfigParser):
    """
        Manages exaile's settings
    """
    settings = None
    def __init__(self, loc):
        """
            Sets up the SettingsManager. Expects a loc to a file
            where settings will be stored.
        """
        SafeConfigParser.__init__(self)
        self.loc = loc

        try:
            self.read(self.loc)
        except:
            pass

        SettingsManager.settings = self

    def set_option(self, option, value):
        """
            Set an option (in section/key syntax) to the specified value.
        """
        value = self._val_to_str(value)
        section, key = option.split('/')
        try:
            self.set(section, key, value)
        except NoSectionError:
            self.add_section(section)
            self.set(section, key, value)
        event.log_event('option_set', self, option)

    def get_option(self, option, default=None):
        """
            Get the value of an option (in section/key syntax), returning
            default if the key does not exist yet.
        """
        section, key = option.split('/')
        try:
            value = self.get(section, key)
            value = self._str_to_val(value)
        except NoSectionError:
            value = default
        except NoOptionError:
            value = default
        return value

    def _val_to_str(self, value):
        """
            Turns a value of some type into a string so it
            can be a configuration value.
        """
        for k, v in TYPE_MAPPING.iteritems():
            if v == type(value):
                return k + ": " + str(value)
        raise ValueError("We don't know how to store that kind of setting")

    def _str_to_val(self, value):
        """
            Convert setting strings back to normal values.
        """
        kind = value.split(':')[0]
        value = value.split(':')[1][1:]
        if kind in TYPE_MAPPING.keys():
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
        f = open(self.loc, 'w')
        self.write(f)
