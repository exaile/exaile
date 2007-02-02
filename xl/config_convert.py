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

import fileinput, xlmisc, re

class ConvertIniToConf:

    def __init__(self, settings, loc):
        self.settings = settings
        self.loc = loc
        self.osettings = {}

        try:
            for line in fileinput.input(loc):
                line = line.strip()
                try:
                    (key, value) = line.split(" = ")
                    self.osettings[key] = value
                except ValueError:
                    pass
        except:
            xlmisc.log("Error reading settings file, using defaults.")

        old_map = {
            "tab_placement": ("ui/tab_placement", self.conv_int),
            "use_popup": ("osd/enabled", self.conv_bool),
            "last_active": self.conv_int,
            "show_track_col_Album": ("ui/track_columns", self.add_rem_list),
            "open_last": self.conv_bool,
            "Artist_trackcol_width": self.conv_width,
            "show_track_col_Rating": ("ui/track_columns", self.add_rem_list),
            "save_queue": self.conv_bool,
            "trackslist_defaults_set": ("ui/trackslist_defaults_set", self.conv_bool),
            "use_tray": ("ui/use_tray", self.conv_bool),
            "show_track_col_Length": ("ui/track_columns", self.add_rem_list),
            "watch_exclude_dirs": self.conv_watch_exclude,
            "show_track_col_Genre": ("ui/track_columns", self.add_rem_list),
            "show_track_col_#": ("ui/track_columns", self.add_rem_list),
            "show_track_col_Title": ("ui/track_columns", self.add_rem_list),
            "osd_h": ("osd/h", self.conv_int),
            "osd_bgcolor": ("osd/bgcolor", self.conv_str),
            "audio_sink": self.conv_str,
            "mainw_width": ("ui/mainw_width", self.conv_int),
            "search_paths": ("search_paths", self.conv_co_list),
            "Length_trackcol_width": self.conv_width,
            "mainw_height": ("ui/mainw_height", self.conv_int),
            "osd_x": ("osd/x", self.conv_int),
            "osd_y": ("osd/y", self.conv_int),
            "col_active_view": ("ui/col_active_view", self.conv_int),
            "show_track_col_Artist": ("ui/track_columns", self.add_rem_list),
            "osd_textcolor": ("osd/text_color", self.conv_str),
            "Title_trackcol_width": self.conv_width,
            "amazon_locale": self.conv_str,
            "osd_w": ("osd/w", self.conv_int),
            "fetch_covers": self.conv_bool,
            "Album_trackcol_width": self.conv_width,
            "use_splash": ("ui/use_splash", self.conv_bool),
            "art_filenames": ("art_filenames", self.conv_ss_list),
            "lastfm_user": ("lastfm/user", self.conv_str),
            "files_panel_dir": self.conv_str,
            "osd_tray": ("osd/tray", self.conv_bool),
            "active_view": ("ui/active_view", self.conv_int),
            "#_trackcol_width": self.conv_width,
            "repeat": self.conv_bool,
            "osd_display_text": ("osd/display_text", self.conv_str),
            "ensure_visible": ("ui/ensure_visible", self.conv_bool),
            "mainw_sash_pos": ("ui/mainw_sash_pos", self.conv_int),
            "osd_text_font": ("osd/text_font", self.conv_str),
            "wikipedia_locale": self.conv_str,
            "cd_device": self.conv_str,
            "scan_interval": self.conv_float,
            "lastfm_pass": ("lastfm/pass", self.conv_str),
            "show_track_col_Bitrate": ("ui/track_columns", self.add_rem_list),
            "watch_directories": self.conv_bool,
            "show_track_col_Year": ("ui/track_columns", self.add_rem_list),
            "mainw_x": ("ui/mainw_x", self.conv_int),
            "mainw_y": ("ui/mainw_y", self.conv_int)
        }

        for setting in self.osettings.keys():
            if old_map.has_key(setting):
                v = old_map[setting]
                if isinstance(v, tuple):
                    v[1](setting, v[0])
                else:
                    v(setting, setting)
            elif re.match("^[A-Za-z_]+\.py.*$", setting):
                self.conv_plugin(setting)

    def conv_int(self, old_key, new_key):
        self.settings.set_int(new_key, int(self.osettings[old_key]))
    
    def conv_float(self, old_key, new_key):
        self.settings.set_float(new_key, float(self.osettings[old_key]))

    def conv_str(self, old_key, new_key):
        self.settings.set_str(new_key, str(self.osettings[old_key].replace(r"\n", '\n')))

    def conv_bool(self, old_key, new_key):
        self.settings.set_boolean(new_key, self.osettings[old_key])

    def conv_width(self, old_key, old_key_again):
        name, new_key_prefix = old_key.split("_", 1)
        self.settings.set_int("ui/%s_%s" % (new_key_prefix, name), int(self.osettings[old_key]))

    def add_rem_list(self, old_key, new_key):
        values = self.settings.get_list(new_key)

        col_name = old_key.rsplit("_", 1)[1]

        if self.osettings[old_key] == 'true' or self.osettings[old_key] == 'True':
            if col_name not in values:
                values.append(col_name)
                self.settings.set_list(new_key, values)
        else:
            if col_name in values:
                values.remove(col_name)
                self.settings.set_list(new_key, values)

    def conv_ss_list(self, old_key, new_key):
        values = self.osettings[old_key].split(" ")
        self.settings.set_list(new_key, values)

    def conv_co_list(self, old_key, new_key):
        values = self.osettings[old_key].split(":")
        self.settings.set_list(new_key, values)

    def conv_watch_exclude(self, old_key, new_key):
        values = self.osettings[old_key]
        if values == "incomplete":
            self.settings.set_list(new_key, [])
        else:
            self.conv_ss_list(old_key, new_key)

    def conv_plugin(self, old_key):
        py_ext = old_key.find('.py')
        key_name = old_key[py_ext+4:]
        plugin_name = old_key[:py_ext]

        if key_name == "plugin_enabled":
            self.settings.set_boolean("enabled", self.osettings[old_key], plugin=plugin_name)
        else:
            value = self.osettings[old_key]

            if re.match("^\d+$", value):
                self.settings.set_int(key_name, int(value), plugin=plugin_name)
            elif re.match("^\d*\.\d+$", value):
                self.settings.set_float(key_name, float(value), plugin=plugin_name)
            elif re.match("^[Tt]rue|[Ff]alse$", value):
                self.settings.set_boolean(key_name, value, plugin=plugin_name)
            else:
                self.settings.set_str(key_name, value, plugin=plugin_name)
