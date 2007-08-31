#!/usr/bin/env python
import gtk
import xl.plugins as plugins

PLUGIN_NAME = "No Taskbar Entry"
PLUGIN_AUTHORS = ['Jonas Wagner <veers' + chr(32+32) + 'gmx' + '.ch>']
PLUGIN_VERSION = "0.1.1"
PLUGIN_DESCRIPTION = r"""Removes exaile from the taskbar"""

PLUGIN_ENABLED = False
PLUGIN_ICON = None
PLUGIN = None

def initialize():
	APP.window.set_property("skip-taskbar-hint", True)
	return True

def destroy():
	APP.window.set_property("skip-taskbar-hint", False)
