# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging
import os.path

import xl.settings

from _utils import Event, PluginInfo, get_database_path_from_beets_config, get_default_view_pattern

#: str: Base dir to plugin
BASE_DIR = os.path.dirname(os.path.realpath(__file__))

#: PluginInfo: Plugin info
PLUGIN_INFO = PluginInfo(BASE_DIR)


def get_name(name, join_exp='-'):
    """
        Gets a plugin "unique" attribute name
        :param name: str - attribute name
        :param join_exp: str ('-' as default)
        :return: str
    """
    return join_exp.join(['plugin', PLUGIN_INFO.id, name])


def create_event(name):
    """
        Creates a Event
        :param name: str
        :return: Event
    """
    return Event(get_name(name))


def get_path(*paths):
        """
            Get a path on plugin
            :param paths:
            :return: str (joining paths with base dir)
        """
        return os.path.join(BASE_DIR, *paths)


class Logger:
    """
        A wrapper to logging.Logger
    """
    def __init__(self, name):
        self.__logger = logging.getLogger(name)

    def critical(self, msg, *args, **kwargs):
        self.log(logging.CRITICAL, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, exc_info=1, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.__logger.log(level, '%s ' + msg, PLUGIN_INFO.name, *args, **kwargs)


class _Settings:
    """
        A wrapper to handle settings
    """
    #: Default values
    DEFAULTS = {
        'current_view_pattern': lambda: '',
        'database': get_database_path_from_beets_config,
        'draw_separators':
            lambda: xl.settings.get_option('gui/draw_separators', True),
        'expand': lambda: 30,
        'font': lambda: 'Sans 12',
        'icon_size': lambda: 16,
        'icons':
            lambda: {
                'album': 'image-x-generic',
                'albumartist': 'artist',
                'artist': 'artist',
                'genre': 'genre',
                'media': 'media-optical',
                'original_year': 'office-calendar',
                'title': 'audio-x-generic',
                'year': 'office-calendar',
            },
        'monitor': lambda: 30,
        'patterns': get_default_view_pattern
    }

    #: Event: Setting changed event
    EVENT = create_event('setting-changed')

    @staticmethod
    def __get_full_name(name):
        """
            Gets the setting full name
            :param name: setting name
            :return: str - (e.g. 'plugin/PLUGIN_ID/database' for 'database')
        """
        return get_name(name, '/')

    def __getitem__(self, item):
        """
            Get option from settings
            :param item: str - local name
            :return: the value, the value from self.DEFAULTS or None
        """
        return xl.settings.get_option(
            self.__get_full_name(item),
            self.DEFAULTS.get(item, lambda: None)()
        )

    def __setitem__(self, key, value):
        """
            Set option on settings
            It only sets if it's different from current
            Logs self.EVENT
            :param key: str - local name
            :param value: the value
            :return: None
        """
        if self[key] != value:
            xl.settings.set_option(
                self.__get_full_name(key),
                value
            )
            self.EVENT.log(None, key)


#: _Settings: Global settings
SETTINGS = _Settings()
