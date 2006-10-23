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

import fileinput, traceback, xlmisc

"""
    This module provides for easy parsing of configuration files
"""

class Config(dict):
    """
        Allows for easy parsing of configuration files
    """
    def __init__(self, loc):
        """
            Expects the location of a file.  Opens the file, and parses it
            to populate the dictionary
        """
        self.loc = loc

        try:
            for line in fileinput.input(loc):
                line = line.strip()
                try:
                    (key, value) = line.split(" = ")
                    self[key] = value
                except ValueError:
                    pass
        except:
            xlmisc.log("Error reading settings file, using defaults.")

    def get(self, key, default=None):
        """
            Gets a value from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = None

        if key in self: value = self[key]
        if value == None:
            value = default
            
        if type(value) == str or type(value) == unicode:
            value = value.replace(r"\n", "\n")
        return value

    def get_int(self, key, default=0):
        """
            Gets an int from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, default)
        if value == None:
            value = default

        try:
            value = int(value)
        except ValueError:
            value = 0

        return value

    def get_float(self, key, default=0): 
        """
            Gets a float from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, default)
        if value == None:
            value = default

        return float(value)
    

    def get_boolean(self, key, default=False): 
        """
            Gets a bool from the settings.  If default is passed, and the value
            does not exist in the current settings, the default is returned
        """
        value = self.get(key, default)
        if value == "false" or value == False: return False
        if value == "true" or value == True: return True
        if value == None:
            return default
    

    def set_boolean(self, key, value): 
        """
            Sets a boolean
        """
        if value: self[key] = "true"
        else: self[key] = "false"
    

    def save(self): 
        """
            Saves the settings
        """
        handle = open(self.loc, "w+")
        for key, value in self.iteritems():
            handle.write("%s = %s\n" % (key, 
                str(value).replace("\n", r"\n")))

        handle.close()
    

    def __setitem__(self, key, value): 
        """
            sets a value and saves all values to the file
        """
        if isinstance(value, bool):
            self.set_boolean(key, value)
        else:
            dict.__setitem__(self, key, value)
        self.save()
