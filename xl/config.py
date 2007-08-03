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

import os, re
from ConfigParser import SafeConfigParser
import ConfigParser

# ok, I know this isn't secure, but it's better than having passwords in
# plaintext in the configuration file.
XOR_KEY = "You're not drunk if you can lie on the floor without hanging on"

"""
    This module provides for easy parsing of configuration files
"""

class XlConfigParser(SafeConfigParser):
    """
        Allows for easy parsing of configuration files
    """
    def __init__(self, loc):
        """
            Expects the location of a file.  Opens the file, and parses it
            to populate the dictionary
        """
        SafeConfigParser.__init__(self)
        self.loc = loc

        if os.path.exists(self.loc):
            try:
                self.read(self.loc)
            except ConfigParser.MissingSectionHeaderError:
                self.add_section("ui")
                self.add_section("osd")
                self.add_section("lastfm")
                self.add_section("equalizer")
                self.add_section('import')
                self.add_section('replaygain')

                from config_convert import ConvertIniToConf
                converter = ConvertIniToConf(self, self.loc)

        self.add_section("ui")
        self.add_section("osd")
        self.add_section("lastfm")
        self.add_section("equalizer")
        self.add_section("import")
        self.add_section('replaygain')


    def add_section(self, section_name="", plugin=None):
        section_name_str = section_name
        if plugin:
            section_name_str = "plugin/%s" % plugin

        try:
            SafeConfigParser.add_section(self, section_name_str)
        except ConfigParser.DuplicateSectionError:
            pass


    def get_section_key(self, key, plugin=None):
        plugin_str = plugin
        if plugin:
            if plugin.endswith(".py"):
                plugin_str = plugin[:-3]
        
        if plugin_str:
            if plugin_str not in self.sections():
                self.add_section(plugin=plugin_str)

            return ("plugin/%s" % plugin_str, key)
        else:
            split_str = key.split('/', 1)
            if len(split_str) > 1:
                return (split_str[0], split_str[1])
            else:
                return ('DEFAULT', split_str[0])

    def get_section_keyv(self, key, plugin, value):
        return self.get_section_key(key, plugin) + (value,)
    
    
    def get(self, key, default=None, plugin=None):
        """
            Gets a value from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = None
        try:
            value = SafeConfigParser.get(self, *self.get_section_key(key, plugin))
            return value
        except ConfigParser.NoOptionError:
            return default
    
    
    def get_str(self, key, default="", plugin=None):
        """
            Gets a string from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, plugin=plugin)

        if value is None:
            value = str(default)

        return value.replace(r'\n', '\n')
    
    
    def get_int(self, key, default=0, plugin=None):
        """
            Gets an int from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, plugin=plugin)

        if value is None:
            value = default
        else:
            try:
                value = int(value)
            except ValueError:
                value = default

        return value

    def get_float(self, key, default=0, plugin=None): 
        """
            Gets a float from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, plugin=plugin)

        if value is None:
            value = default
        else:
            try:
                value = float(value)
            except ValueError:
                value = default

        return value
    

    def get_boolean(self, key, default=False, plugin=None): 
        """
            Gets a bool from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, plugin=plugin)

        if value is None:
            value = default

        if value == "True" or value == "true":
            value = True
        elif value == "False" or value == "false":
            value = False
        else:
            value = default

        return value


    def get_list(self, key, default=[], plugin=None):
        """
            Gets a list from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, plugin)

        if value is None:
            value = default
        else:
            try:
                value = eval(value)
            except SyntaxError:
                value = default

        return value
    
    
    def set_boolean(self, key, value, plugin=None): 
        """
            Sets a boolean
        """
        if value == "true" or value == "True": value = True
        if value == "false" or value == "False": value = False
        
        self.set(*self.get_section_keyv(key, plugin, str(value)))
    
    
    def set_str(self, key, value, plugin=None):
        """
            Sets a string
        """
        value_str = str(value)
        value_str = re.sub(r'%[^rdf%]?', r'%%', value_str)
        self.set(*self.get_section_keyv(key, plugin, value_str.replace('\n', r'\n')))
    
    
    def set_int(self, key, value, plugin=None):
        """
            Sets an int
        """
        self.set(*self.get_section_keyv(key, plugin, str(value)))
    
    
    def set_float(self, key, value, plugin=None):
        """
            Sets a float
        """
        self.set(*self.get_section_keyv(key, plugin, str(value)))
    
    
    def set_list(self, key, value, plugin=None):
        """
            Sets a list
        """
        self.set(*self.get_section_keyv(key, plugin, str(value)))

    
    def save(self): 
        """
            Saves the settings
        """
        f = open(self.loc, 'w')
        self.write(f)
        f.close()

    
    def optionxform(self, option):
        return str(option)
    

class Config:
    """
        Allows for easy parsing of configuration files
    """
    def __init__(self, loc):
        """
            Expects the location of a file.  Opens the file, and parses it
            to populate the dictionary
        """
        self.config = XlConfigParser(loc)
        self.loc = loc

    def get_crypted(self, key, default="", plugin=None):
        """
            Gets a string from the config file and decrypts it
        """
        string = self.config.get_str(key, default, plugin)
        
        # convert it from hex
        new = ''
        vals = string.split()
        for val in vals:
            try:
                new += chr(int(val, 16))
            except ValueError:
                continue

        return self.crypt(new, XOR_KEY)

    def set_crypted(self, key, value, plugin=None):
        """
            Encrypts a value and saves it to the configuration file
        """
        writestr = self.crypt(value, XOR_KEY)

        hexstr = ''
        for x in writestr:
            hexstr = hexstr + "%02X " % ord(x)

        self.config.set_str(key, hexstr, plugin)

    def crypt(self, string, key):
        """
            Encrypt/Decrypt a string'
        """

        kidx = 0
        cryptstr = ""

        for x in range(len(string)):
            cryptstr = cryptstr + \
                chr(ord(string[x]) ^ ord(key[kidx]))

            kidx = (kidx + 1) % len(key)

        return cryptstr
    
    def get_str(self, key, default="", plugin=None):
        """
            Gets a string from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        return self.config.get_str(key, default, plugin)
    
    
    def get_int(self, key, default=0, plugin=None):
        """
            Gets an int from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        return self.config.get_int(key, default, plugin)

    def get_float(self, key, default=0.0, plugin=None): 
        """
            Gets a float from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        return self.config.get_float(key, default, plugin)
    

    def get_boolean(self, key, default=False, plugin=None): 
        """
            Gets a bool from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        return self.config.get_boolean(key, default, plugin)


    def get_list(self, key, default=[], plugin=None):
        """
            Gets a list from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        return self.config.get_list(key, default, plugin)
    
    
    def get_plugins(self):
        """
            Gets a dictionary of plugins with their status
        """
        plugins = {}

        plug_sections = []
        sections = self.config.sections()

        for section in sections:
            if 'plugin/' in section:
                plug_sections.append(section)

        for plug in plug_sections:
            plugin = plug.split('/')[1]
            plugins[plugin] = self.get_boolean("enabled", False, plugin=plugin)

        return plugins
    
    
    def set_boolean(self, key, value, plugin=None): 
        """
            Sets a boolean
        """
        self.config.set_boolean(key, value, plugin)
    
    
    def set_str(self, key, value, plugin=None):
        """
            Sets a string
        """
        self.config.set_str(key, value, plugin)
    
    
    def set_int(self, key, value, plugin=None):
        """
            Sets an int
        """
        self.config.set_int(key, value, plugin)
    
    
    def set_float(self, key, value, plugin=None):
        """
            Sets an int
        """
        self.config.set_float(key, value, plugin)
    
    
    def set_list(self, key, value, plugin=None):
        """
            Sets a list
        """
        self.config.set_list(key, value, plugin)
    
    def append_list(self, key, value, plugin=None):
        """
            Appends to a list
        """
        self.config.set_list(key, self.config.get_list(key, plugin=plugin) + [value])
    
    def save(self): 
        """
            Saves the settings
        """
        self.config.save()
    

    def __setitem__(self, key, value): 
        """
            sets a value and saves all values to the file
        """
        if isinstance(value, bool):
            self.set_boolean(key, value)
        elif isinstance(value, list):
            self.set_list(key, value)
        elif isinstance(value, float):
            self.set_float(key, value)
        elif isinstance(value, int):
            self.set_int(key, value)
        elif isinstance(value, str):
            self.set_str(key, value)

    def __getitem__(self, key):
        """
            gets a value
        """
        value = self.config.get(key)
        if value is None:
            return None
        elif _is_list(value):
            return self.get_list(key)
        elif _is_int(value):
            return self.get_int(key)
        elif _is_float(value):
            return self.get_float(key)
        elif _is_bool(value):
            return self.get_boolean(key)
        else:
            return self.get_str(key)

def _is_list(s):
    return s and s[0] == '[' and s[-1] == ']'
def _is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False
def _is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
def _is_bool(s):
    return s in ('True', 'true', 'False', 'false')
