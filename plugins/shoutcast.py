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

class ShoutcastDriver(object):
    """
        Shoutcast Streaming Radio Driver
    """
    def __init__(self):
        # does nothing for now.  proof of concept
        pass

    def __str__(self):
        return PLUGIN_NAME

def initialize():
    """
        Sets up the shoutcast driver
    """
    global PLUGIN

    PLUGIN = ShoutcastDriver()
    APP.pradio_panel.add_driver(PLUGIN)

    return True


def destroy():
    global PLUGIN

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    PLUGIN = None
