# Copyright (C) 2006 Aren Olson
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

import time, os, gtk, subprocess, xl.media
from xl import common
from gettext import gettext as _
import xl.plugins as plugins

PLUGIN_NAME = _("Sound Juicer")
PLUGIN_AUTHORS = ['Aren Olson <reacocard@gmail.com>']
PLUGIN_VERSION = '0.1.3'
PLUGIN_DESCRIPTION = _(r"""Allows importing of cds with sound-juicer.""")

PLUGIN_ENABLED = False
w = gtk.Button()
PLUGIN_ICON = w.render_icon('gtk-cdrom', gtk.ICON_SIZE_MENU)

APP = None
MENU_ITEM = None
SETTINGS = None
TIPS = gtk.Tooltips()

def launch_sound_juicer(widget):
	args = ['sound-juicer']
        subprocess.Popen(args, stdout=-1, stderr=-1)

def initialize():
	"""
		Adds the 'Import CD' menuitem.
	"""
	global SETTINGS, APP, MENU_ITEM

	try:
	        ret = subprocess.call(['sound-juicer', '--help'], stdout=-1, stderr=-1)
	except OSError:
		raise plugins.PluginInitException(_("Sound Juicer was not found in your $PATH. "
			"Disabling the Sound Juicer plugin."))
		return False

	menu = APP.xml.get_widget('file_menu_menu')
	MENU_ITEM = gtk.ImageMenuItem(_('Import Disc'))
	MENU_ITEM.label = gtk.Label(_('Import Disc'))
	MENU_ITEM.connect('activate',launch_sound_juicer)
	image = gtk.Image()
	image.set_from_stock('gtk-cdrom', gtk.ICON_SIZE_MENU)
	MENU_ITEM.set_image(image)
	menu.append(MENU_ITEM)
	menu.reorder_child(MENU_ITEM,5)
	MENU_ITEM.show_all()
	return True

def destroy():
	"""
		Removes the 'Import CD' menuitem.
	"""
	MENU_ITEM.destroy()
