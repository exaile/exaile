#!/usr/bin/python

# Modified 2009 by Brian Parma
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

from __future__ import with_statement
import gtk, time, gobject, thread, os
from gettext import gettext as _        # Not sure how to apply this sort of thing to glade files...
from xl import event, xdg
from xl import settings
#import xl.plugins as plugins
#import xl.path as xlpath
#import cPickle as pickle

PATH = os.path.dirname(os.path.realpath(__file__))
GLADE = os.path.join(PATH,'alarmclk.glade')

pb = gtk.gdk.pixbuf_new_from_file(os.path.join(PATH,'clock32.png'))

#PLUGIN_NAME                 = _("Multi-Alarm Clock")
#PLUGIN_AUTHORS              = ['Brian Parma <execrable@gmail.com>']
#PLUGIN_VERSION              = "0.1"
#PLUGIN_ICON                 = pb
#PLUGIN_DESCRIPTION          = _(r"""Plays music at a specific times and days.\n\nNote that when the 
                                #specified time arrives, Exaile will just act like you pressed the play button, 
                                #so be sure you have the music you want to hear in your playlist""")

PLUGIN_ENABLED              = False
#SETTINGS                    = None
TIMER_ID                    = None
#RANG                        = dict()
MENU_ITEM                   = None
#exaile                      = None


###><><><### Alarm Clock Stuph ###><><><###

class Alarm:
    ''' 
        Class for individual alarms.
    '''
    def __init__(self, time="09:00", days=None, name="New Alarm", dict={}):
        self.active = True
        self.time = time
        self.name = name
        if days is None:
            self.days = [False,False,False,False,False,False,False]
        else:
            self.days = days
        
        # For setting attributes by dictionary
        self.__dict__.update(dict)
        
    def on(self):
        self.active = True
        
    def off(self):
        self.active = False
        
    def toggle(self):
        if self.active:
            self.off()
        else:
            self.on()


class AlarmClock:
    '''
        Class that contains all settings info and displays the main window.
    '''
    def __init__(self, exaile):
        self.RANG = {}
        self.alarm_list = []
        self.fading = True
        self.restart = True
        self.min_volume = 0
        self.max_volume = 100
        self.increment = 5
        self.time_per_inc = 1
        self.window = None
        self.exaile = exaile
        
        self.icon = pb
        
        # Create Model
        self.model = gtk.ListStore(str,gtk.gdk.Pixbuf,object)

        # Load any saved alarms
        self.load_list()
        
    def minvolume_changed(self, widget):
        self.min_volume = widget.get_value()
        settings.set_option('plugin/multialarmclock/fade_min_volume',
                self.min_volume)
#        print 'AC: minvol change',self.min_volume,SETTINGS.get_float("alarm_min_volume", plugin=plugins.name(__file__))

    def maxvolume_changed(self, widget):
        self.max_volume = widget.get_value()        
        settings.set_option('plugin/multialarmclock/fade_max_volume',
                self.max_volume)
#        print 'AC: maxvol change'

    def increment_changed(self, widget):
        self.increment = widget.get_value()
        settings.set_option('plugin/multialarmclock/fade_increment',
                self.increment)
#        print 'AC: inc change'

    def time_changed(self, widget):
        self.time_per_inc = widget.get_value()
        settings.set_option('plugin/multialarmclock/fade_time_per_inc',
                self.time_per_inc)
#        print 'AC: time change'
        
    def selection_change(self, selection):
        model, tree_iter = self.selection.get_selected()
        if tree_iter is not None:
            alarm = model.get_value(tree_iter, 2)
            self.EnabledCB.set_active(alarm.active)
            days = ['Su','M','T','W','Th','F','S']
            day_string = ' - '
            for i,day in enumerate(alarm.days):
                if day:
                    day_string += days[i]
            self.AlarmLabel.set_text(alarm.name+' - '+alarm.time + day_string)
#        print 'AC: selection change'
        
    def fading_cb(self, widget):
        self.fading = widget.get_active()
        settings.set_option('plugin/multialarmclock/fading_on',
                self.fading)
#        print 'AC: fading ',self.fading
        
    def enable_cb(self, widget):
        model, tree_iter = self.selection.get_selected()
        if tree_iter is not None:
            alarm = model.get_value(tree_iter, 2)
            alarm.active = widget.get_active()
#            print 'AC: toggle: ', alarm.active
            
        else:
            widget.set_active(False)
#            print 'AC: notoggle'
        
    def restart_cb(self, widget):
        self.restart = widget.get_active()
        settings.set_option('plugin/multialarmclock/restart_playlist_on',
                self.restart)
#        print 'AC: restart: ',self.restart
        
    def show_ui(self, widget, exaile):
        '''
            Display main window, which is not Modal.
        '''
        if self.window:
            self.window.present()
            return
            
        self.signals = {'on_AddButton_clicked':self.add_button,
                        'on_EditButton_clicked':self.edit_button,
                        'on_DeleteButton_clicked':self.delete_button,
                        'on_EnabledCB_toggled':self.enable_cb,
                        'on_RestartCB_toggled':self.restart_cb,
                        'on_FadingCB_toggled':self.fading_cb,
                        'on_MinVolume_value_changed':self.minvolume_changed,
                        'on_MaxVolume_value_changed':self.maxvolume_changed,
                        'on_Increment_value_changed':self.increment_changed,
                        'on_Time_value_changed':self.time_changed,
                        'on_MainWindow_destroy':self.destroy}

        self.ui = gtk.glade.XML(GLADE, 'MainWindow') # load GUI from glade file
        self.ui.signal_autoconnect(self.signals)    # connect signals to GUI
        
        self.window = self.ui.get_widget('MainWindow')
        
        # Model & Treeview - model created in init()
        self.view = self.ui.get_widget('AlarmList')
        self.view.set_model(self.model)
        self.selection = self.view.get_selection()
        
        col = gtk.TreeViewColumn('Test')
        cel = gtk.CellRendererText()
        pcel = gtk.CellRendererPixbuf()
        
        self.view.append_column(col)
        
        col.pack_start(pcel,False)
        col.pack_end(cel,False)
        col.add_attribute(cel, 'text', 0)
        col.add_attribute(pcel, 'pixbuf', 1)
        
        # Set GUI Values
        self.load_settings()
        self.ui.get_widget('FadingCB').set_active(self.fading)
        self.ui.get_widget('RestartCB').set_active(self.restart)
        self.ui.get_widget('MinVolume').set_value(self.min_volume)
        self.ui.get_widget('MaxVolume').set_value(self.max_volume)        
        self.ui.get_widget('Increment').set_value(self.increment)        
        self.ui.get_widget('Time').set_value(self.time_per_inc)        
        self.EnabledCB = self.ui.get_widget('EnabledCB')
        self.AlarmLabel = self.ui.get_widget('AlarmLabel')
        
        # Set Signal for Selection Change
        self.selection.connect('changed', self.selection_change)
        
        self.window.show_all()
        
    def add_alarm(self, alarm):
        self.model.append([alarm.name,self.icon,alarm])
        self.alarm_list.append(alarm)
        
    def add_button(self, widget):
        alarm = Alarm()
        add = AddAlarm()    # create new instance each time or use a self.instance?
        if add.run(alarm):
            self.add_alarm(alarm)
            self.save_list()    # since exaile doesn't notify on program exit...
        
    def edit_button(self, widget):
        # Get currently selected alarm
        model, tree_iter = self.selection.get_selected()
        if tree_iter is not None:
            alarm = model.get_value(tree_iter, 2)
            add = AddAlarm()    # create new instance each time or use a self.instance?
            if add.run(alarm):
                model.set_value(tree_iter, 0, alarm.name) # update display incase of name change
                self.selection_change(self.selection)
                self.save_list()   
        
    def delete_button(self, widget):
        model, tree_iter = self.selection.get_selected()
        if tree_iter is not None:
            alarm = model.get_value(tree_iter, 2)
            model.remove(tree_iter)
        
            self.alarm_list.remove(alarm)
            self.save_list()   
            
    def load_settings(self):
        print 'AC: load settings'
        self.fading = settings.get_option(
                'plugin/multialarmclock/fading_on', self.fading)
        self.min_volume = settings.get_option(
                'plugin/multialarmclock/fade_min_volume', self.min_volume)
        self.max_volume = settings.get_option(
                'plugin/multialarmclock/fade_max_volume', self.max_volume)
        self.increment = settings.get_option(
                'plugin/multialarmclock/fade_increment', self.increment)
        self.time_per_inc = settings.get_option(
                'plugin/multialarmclock/fade_time_per_inc', self.time_per_inc)
        self.restart = settings.get_option(
                'plugin/multialarmclock/restart_playlist_on', self.restart)

    def load_list(self):
        path = os.path.join(xdg.get_data_dirs()[0],'alarmlist.dat')
        try:
            # Load Alarm List from file.
            with open(path,'rb') as f:
                for line in f.readlines():
                    try:
                        al = Alarm(dict=eval(line,{'__builtin__':None}))
#                        print 'AC: loaded - ',al.__dict__
                        self.add_alarm(al)
                    except:
                        print 'AC: bad alarm definition'
            
        except IOError, (e,s):  # File might not exist
            print 'AC: could not open file:', s
          

    def save_list(self):
        # Save List
        path = os.path.join(xdg.get_data_dirs()[0],'alarmlist.dat')
        if len(self.alarm_list) > 0:
            with open(path,'wb') as f:
                f.writelines((str(al.__dict__)+'\n' for al in self.alarm_list))

    def destroy(self, widget):
        self.window = None

class AddAlarm:
    def __init__(self):
        pass    
        
    def run(self, alarm):
        self.ui = gtk.glade.XML(GLADE,'AddWindow') # load GUI
        
        self.window = self.ui.get_widget('AddWindow')
        self.alarm_name = self.ui.get_widget('AlarmName')
        self.alarm_hour = self.ui.get_widget('SpinHour')
        self.alarm_minute = self.ui.get_widget('SpinMinute')
        self.alarm_days = [self.ui.get_widget('Check0'),
                           self.ui.get_widget('Check1'),
                           self.ui.get_widget('Check2'),
                           self.ui.get_widget('Check3'),
                           self.ui.get_widget('Check4'),
                           self.ui.get_widget('Check5'),
                           self.ui.get_widget('Check6')]
        
        hour, minute = alarm.time.split(':')
        self.alarm_hour.set_value(int(hour))
        self.alarm_minute.set_value(int(minute))
        self.alarm_name.set_text(alarm.name)
        for i in range(7):
            self.alarm_days[i].set_active(alarm.days[i])
        
        result = self.window.run()

        # stuff
        if result == 1: # press Ok
            hour = self.alarm_hour.get_value()
            minute = self.alarm_minute.get_value()
            alarm.time = '%02d:%02d' % (hour,minute)
            alarm.name = unicode(self.alarm_name.get_text(), 'utf-8')
            for i in range(7):
                alarm.days[i] = self.alarm_days[i].get_active()
        
        self.window.destroy()
        
        return (result == 1)
        
        
###><><><### Globals ###><><><###

def fade_in(main, exaile):
    temp_volume = main.min_volume
    while temp_volume <= main.max_volume:
        #print "AC: set volume to %s" % str(temp_volume / 100.0)
        exaile.player.set_volume( ( temp_volume / 100.0 ) )
        temp_volume += main.increment
        time.sleep( main.time_per_inc )
        if exaile.player.is_paused() or not exaile.player.is_playing():
            return


def check_alarms(main, exaile):
    """
        Called every timeout.  If the plugin is not enabled, it does
        nothing.  If the current time matches the time specified and the
        current day is selected, it starts playing
    """
    if not main: return True  # TODO: new way?


    current = time.strftime("%H:%M", time.localtime())
    currentDay = int(time.strftime("%w", time.localtime()))

    for al in main.alarm_list:
        if al.active and al.time == current and al.days[currentDay] == True:
            check = time.strftime("%m %d %Y %H:%M") # clever...
            if main.RANG.has_key(check): return True
            
            # tracks to play?
            count = len(exaile.queue.get_tracks())
            if exaile.queue.current_playlist:
                count += len(exaile.queue.current_playlist.get_tracks())
            else:
                count += len(exaile.gui.main.get_selected_playlist().playlist.get_tracks())
            print 'count:', count
            if count == 0 or exaile.player.is_playing(): return True    # Check if there are songs in playlist and if it is already playing
            if main.fading:
                thread.start_new(fade_in, (main, exaile))
            if main.restart:
                if exaile.queue.current_playlist:
                    exaile.queue.current_playlist.set_current_pos(0)
                else:
                    exaile.queue.set_current_playlist(exaile.gui.main.get_selected_playlist())
            
            exaile.queue.play()

            main.RANG[check] = True

    return True

        
###><><><### Plugin Handling Functions ###><><><###

def __enb(eventname, exaile, nothing):
    gobject.idle_add(_enable, exaile)

def enable(exaile):
       
    if exaile.loading:
        event.add_callback(__enb,'exaile_loaded')
    else:
        __enb(None, exaile, None)
        
def _enable(exaile):
    '''
        Called when plugin is loaded.  Start timer and load previously saved alarms.
    '''
    main = AlarmClock(exaile) 
    global TIMER_ID, MENU_ITEM
    
    TIMER_ID = gobject.timeout_add(5000, check_alarms, main, exaile)
    
    MENU_ITEM = gtk.MenuItem(_('Multi-Alarm Clock'))
    MENU_ITEM.connect('activate', main.show_ui, exaile)
    exaile.gui.xml.get_widget('tools_menu').get_submenu().append(MENU_ITEM)
    MENU_ITEM.show()

    
    
def disable(exaile):
    '''
        Called when plugin is unloaded.  Stop timer, destroy main window if it exists, and save current alarms.
    '''
    global TIMER_ID, MENU_ITEM
        
    # Cleanup
    if main.window:
        main.window.destroy()
        
#    if main:
        #main.save_list()       # unnecessary
#        main = None

    if TIMER_ID is not None:
        gobject.source_remove(TIMER_ID)
        TIMER_ID = None

    if MENU_ITEM:
        MENU_ITEM.hide()
        MENU_ITEM.destroy()
        MENU_ITEM = None


#def configure():
#    print 'no configure'
    # If this is clicked before plugin is initialized, define globals (so alarms can still be created)
    #global exaile, SETTINGS
    #if exaile is None:
        #exaile = APP
        #SETTINGS = exaile.settings
    # Show Window
    #main.show_ui()


