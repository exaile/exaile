#!/usr/bin/env python

# Copyright (C) 2008 Darlan Cavalcante Moreira
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


import gtk
from gettext import gettext as _
import xl.plugins as plugins
 
PLUGIN_NAME        = _("Enhanced Playlist Tabs")
PLUGIN_AUTHORS     = ['Darlan Cavalcante Moreira <darcamo@gmail.com>']
PLUGIN_VERSION     = '0.1'
PLUGIN_DESCRIPTION = _(r"""Allow closing a tab with a middle mouse click, hide the close button and expand the tabs.""")

PLUGIN_ENABLED     = False
PLUGIN_ICON        = None
 

GLADE_XML          = None
APP                = None
NOTEBOOK           = None
CONFWINDOW         = None
CONNS              = plugins.SignalContainer()
HIDECLOSEBUTTON    = False
EXPANDTABS         = False


def load_data(zip):
    """
        Called by Exaile to load the data from the zipfile
    """
    global GLADE_XML_STRING
    GLADE_XML_STRING = zip.get_data('gui.glade')
    

def initialize():
    """
        Called when the plugin is enabled
    """
    global APP, NOTEBOOK, CONFWINDOW, XML_STRING, HIDECLOSEBUTTON, EXPANDTABS, GLADE_XML

    GLADE_XML = gtk.glade.xml_new_from_buffer(GLADE_XML_STRING, len(GLADE_XML_STRING))
    CONFWINDOW        = GLADE_XML.get_widget('configwindow')
    okButton          = GLADE_XML.get_widget('OkButton')
    hideCheckButton   = GLADE_XML.get_widget('HideCheckButton')
    expandCheckButton = GLADE_XML.get_widget('ExpandCheckButton')

    CONNS.connect(okButton, 'clicked', on_OkButton_clicked)
    CONNS.connect(hideCheckButton, 'toggled', on_hideCheckButton_toggle)
    CONNS.connect(expandCheckButton, 'toggled', on_expandCheckButton_toggle)

    
    NOTEBOOK = APP.playlists_nb

    # When Exaile is initialized there is no tab (they are loaded after this plugin)
    CONNS.connect(NOTEBOOK, 'page-added', on_new_tab)

    HIDECLOSEBUTTON = APP.settings.get_boolean('hideclosebutton',default=False, plugin=plugins.name(__file__))
    EXPANDTABS = APP.settings.get_boolean('expandtabs',default=False, plugin=plugins.name(__file__))
    hideCheckButton.set_active(HIDECLOSEBUTTON)
    expandCheckButton.set_active(EXPANDTABS)

    for tab in NOTEBOOK:
        on_new_tab(NOTEBOOK, tab)
        show_hide_close_button(tab)
        NOTEBOOK.child_set_property(tab,'tab-expand',EXPANDTABS)
    return True

 
def destroy():
    """
        Called when the plugin is disabled
    """
    global CONNS, HIDECLOSEBUTTON, CONFWINDOW
    CONNS.disconnect_all()

    CONFWINDOW.hide()
    CONFWINDOW.destroy()
    CONFWINDOW = None

    HIDECLOSEBUTTON = False
    for tab in NOTEBOOK:
        show_hide_close_button(tab)
        NOTEBOOK.child_set_property(tab,'tab-expand',False)


def on_new_tab(notebook=None, tab=None, number=None):
    global CONNS, NOTEBOOK, EXPANDTABS
    tablabel = notebook.get_tab_label(tab)
    CONNS.connect(tablabel, "button-press-event", close_tab, tab)

    # If CloseButton should be invisible
    show_hide_close_button(tab)

    # If tab should expand
    NOTEBOOK.child_set_property(tab,'tab-expand',EXPANDTABS)


def show_hide_close_button(tab):
    """
        Show or hide the close button in the tab according to the value of the global variable HIDECLOSEBUTTON.
    """
    global NOTEBOOK, HIDECLOSEBUTTON
    tablabel = NOTEBOOK.get_tab_label(tab)
    hbox = tablabel.get_children()[0]
    closeButton = hbox.get_children()[1]
    if HIDECLOSEBUTTON:
        closeButton.hide()
    else:
        closeButton.show()


def close_tab(notebook=None,event=None, tab=None):
    global APP
    if (event.button == 2):
        APP.close_page(tab)


def on_OkButton_clicked(button=None):
    CONFWINDOW.hide()


def on_hideCheckButton_toggle(button=None):
    global HIDECLOSEBUTTON, NOTEBOOK
    HIDECLOSEBUTTON = button.get_active()
    APP.settings.set_boolean('hideclosebutton', HIDECLOSEBUTTON, plugin=plugins.name(__file__))
    for tab in NOTEBOOK:
        show_hide_close_button(tab)


def on_expandCheckButton_toggle(button=None):
    global EXPANDTABS
    EXPANDTABS = button.get_active()
    APP.settings.set_boolean('expandtabs', EXPANDTABS, plugin=plugins.name(__file__))
    for tab in NOTEBOOK:
        NOTEBOOK.child_set_property(tab,'tab-expand',EXPANDTABS)
    

def configure():
    """
        Called when the user clicks Configure in the Plugin Manager
    """
    global CONFWINDOW
    if(CONFWINDOW):
        CONFWINDOW.show()

