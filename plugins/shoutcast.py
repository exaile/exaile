#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

PLUGIN_NAME = "Shoutcast Radio"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""Allows you to browse the Shoutcast Streaming Radio
network"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None
import xl.common, urllib, os, re, gobject

class ShoutcastDriver(object):
    """
        Shoutcast Streaming Radio Driver
    """
    def __init__(self, panel):
        self.model = panel.model
        self.folder_icon = panel.folder
        self.note_icon = panel.track
        self.tree = panel.tree

    @xl.common.threaded
    def load_streams(self, node, load_node):
        """
            Loads the shoutcast streams
        """
        reg = re.compile(r'<OPTION VALUE="TopTen">-=\[Top 25 Streams\]=-(.*?)</SELECT>', re.DOTALL)

        data = urllib.urlopen('http://www.shoutcast.com').read()

        m = reg.search(data)
        lines = m.group(1).split('\n')

        gobject.idle_add(self.show_streams, lines, node, load_node)

    def show_streams(self, lines, node, load_node):
        """
            Actually displays the stream information
        """

        self.model.remove(load_node)
        self.last_node = None
        for line in lines:
            m = re.search(r'(\t+)<OPTION VALUE="(.*?)">', line)
            if m:
                tabcount = m.group(1)
                genre = m.group(2)
                if not tabcount == '\t\t': 
                    self.add_function(node, genre)
                else:
                    self.add_function(self.last_node, genre,
                        True)

        self.tree.expand_row(self.model.get_path(node), False)

    def add_function(self, node, genre, note_icon=False):
        icon = self.folder_icon
        if note_icon: icon = self.note_icon
        node = self.model.append(node, [icon, urllib.unquote(genre)])
        if not note_icon:
            self.last_node = node

        return False

    def __str__(self):
        return PLUGIN_NAME

def initialize():
    """
        Sets up the shoutcast driver
    """
    global PLUGIN

    PLUGIN = ShoutcastDriver(APP.pradio_panel)
    APP.pradio_panel.add_driver(PLUGIN)

    return True


def destroy():
    global PLUGIN

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    PLUGIN = None
