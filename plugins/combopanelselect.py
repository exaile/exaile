# Copyright (C) 2007 Aren Olson
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

import pygtk
pygtk.require("2.0")
import gtk
import xl.plugins as plugins

PLUGIN_NAME = "Panel List"
PLUGIN_AUTHORS = ['Aren Olson <reacocard@gmail.com>']
PLUGIN_VERSION = '0.1.2'
PLUGIN_DESCRIPTION = r"""Moves the sidepanel's tab list into a drop-down menu."""

PLUGIN_ENABLED = False
PLUGIN_ICON = None

APP = None
CBOX = None
NOTEBOOK = None
CONNS = plugins.SignalContainer()


def switch_page(widget=None, junk=None):
    global APP, CBOX, CONNS, NOTEBOOK

    NOTEBOOK.set_current_page(CBOX.get_active())

def update_list(spam=None, eggs=None, sausage=None):
    global APP, CBOX, CONNS, NOTEBOOK

    for i in range(20): #bad!!
        CBOX.remove_text(0)
    for pagenum in range(NOTEBOOK.get_n_pages()):
        name = NOTEBOOK.get_tab_label(NOTEBOOK.get_nth_page(pagenum))
        CBOX.append_text(name.get_text())
    change_active()

def change_active(spam=None, eggs=None, sausage=None):
    global APP, CBOX, CONNS, NOTEBOOK

    CBOX.set_active(NOTEBOOK.get_current_page())

def initialize():
    global APP, CBOX, CONNS, NOTEBOOK

    NOTEBOOK = APP.xml.get_widget('side_notebook')

    xml_string = '''<glade-interface>
                    <widget class="GtkComboBox" id="panels_combo_box">
                        <property name="visible">True</property>
                        <property name="items" translatable="yes"></property>
                        <property name="add_tearoffs">False</property>
                        <property name="focus_on_click">True</property>
                    </widget>
                    </glade-interface>'''

    combo_xml = gtk.glade.xml_new_from_buffer(xml_string, len(xml_string))

    CBOX = combo_xml.get_widget('panels_combo_box')

    #CBOX = gtk.ComboBox()
    side_panel = APP.xml.get_widget('side_panel')
    side_panel.pack_start(CBOX, False, False, 2)
    side_panel.reorder_child(CBOX, 0)
    CBOX.show()
    update_list()
    change_active()
    CBOX.connect('changed', switch_page)
    CONNS.connect(NOTEBOOK, 'page-added', update_list)
    CONNS.connect(NOTEBOOK, 'page-removed', update_list)
    CONNS.connect(NOTEBOOK, 'page-reordered', update_list)
    #CONNS.connect(NOTEBOOK, 'switch-page', change_active)
    NOTEBOOK.set_show_tabs(False)

    return True

def destroy():
    global APP, CBOX, CONNS, NOTEBOOK
    CBOX.destroy()
    CBOX = None
    NOTEBOOK.set_show_tabs(True)
    CONNS.disconnect_all()
