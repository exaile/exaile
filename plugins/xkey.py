#!/usr/bin/env python
#
#"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Copyright (C) 2007 Hubert Berezowski
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
#
#
#
#"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#   .~SSS' '' ' s      `~:.   '.SSSS'''''a  
#     >Ss''''.'SSSs       ';    >SSS'''.'SS
#   ,'''S', ~ 'SSSSSs    `~   ,''''S'' ~'SS
# '''',''   A. `'SSSSSs    ,''''''     a. '
#'' s    K. ..N.  '.SSSS'''''''s   a;.,:~a  
#''SSSs    E.~  Y   >SSS'''';'SSSs   ~a.'`     
# \SSSSSs    Y    ,''''S''` ~ `'SSSSs  ~;a   
#   \SSSSSs    ,''''''''   <@.   `'SSSSs ~ 
#;k    \SSSS''''''''s'  <s..  s..   '.SSSS'
#df     ,SSS'''',.'SSSs   `s``~~a >   >SSS'
#     `''''S',`   ~'.SSSs   ~s.    ,''''S''
#
# ADD KEYBOARD SHORTCUTS TO EXAILE


import xl.plugins as plugins
import thread
import select
import gtk
from Xlib.display import Display
from Xlib import X 

PLUGIN_NAME = "Keyboard Shortcuts"
PLUGIN_AUTHORS = ['Hubert Berezowski <hubertb2@wp.pl>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r""" Keyboard Shortcuts via the X Server.
\n\n
Requires Python-Xlib
\n
http://python-xlib.sourceforge.net/"""


PLUGIN_ENABLED = False

b = gtk.Button()
PLUGIN_ICON = b.render_icon(gtk.STOCK_BOLD, gtk.ICON_SIZE_MENU)
b.destroy()
 
CONNS = plugins.SignalContainer()




class XlibKeys:
    def __init__(self):
        '''
        test for settings and connect them with xlib 
        '''


        # actionlist, the keys of the keyb dictionary, sorting order in the configure panel
        self.actionlist = ['play','pause','stop','next Track','previous Track','seek +5sec.','seek -5sec.','volume up','volume down']

        # load settings or use default
        try:
            self.getsettings()
        except:
            # keyb = 'name':[keyname,keycode,shift,ctrl,alt,mod1,mod2,callback]
            self.keyb = {'play':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.play'],
                         'stop':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.stop'],
                         'pause':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.toggle_pause'],
                         'next Track':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.next'],
                         'previous Track':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.previous'],
                         'seek +5sec.':['not defined', 0, 0, 0, 0, 0, 0, 'seekForward5'],
                         'seek -5sec.':['not defined', 0, 0, 0, 0, 0, 0, 'seekBack5'],
                         'volume up':['not defined', 0, 0, 0, 0, 0, 0, 'volUp5'],
                         'volume down':['not defined', 0, 0, 0, 0, 0, 0, 'volDown5'],                                                  
                         }            

        # connect loaded settings with X
        self.listen()



    def freeKey(self):
        '''##########################################################################
        stop grabbing
        '''
        self.grabbing = False
        


    def grabKey(self,action):
        '''##########################################################################
        Connect / disconnect Keys to grab
        '''
        # Make a xlib Mask for every key in the settings-dict
        for key in self.keyb.keys():
            if self.keyb[key][0] != 'not defined':
                maske = ''
                if self.keyb[key][2] == 1:
                    maske += '|X.ShiftMask'
                if self.keyb[key][3] == 1:
                    maske += '|X.ControlMask'
                if self.keyb[key][4] == 1:
                    maske += '|X.Mod1Mask'
                if self.keyb[key][5] == 1:
                    maske += '|X.Mod2Mask'
                if self.keyb[key][6] == 1:
                    maske += '|X.Mod3Mask'

            
                def checkmask(maske):
                    # make sure the mask is valid
                    if maske != '':
                        amaske = maske.lstrip('|')
                        return eval(amaske)
                    else:
                        return X.AnyModifier
            
                if action == 'grab':
                    # ...and grab it...
                    #print 'grab hit'
                    self.root.grab_key(self.keyb[key][1], checkmask(maske),  1,X.GrabModeAsync, X.GrabModeAsync)
                    #print 'grabbed '+str(self.keyb[key][1])
                elif action == 'free':
                    # ...or ungrab it.
                    self.root.ungrab_key(self.keyb[key][1], checkmask(maske))
                    #print 'ungrabbed '+str(self.keyb[key][1])
                
    def listen(self):
        '''##########################################################################
        connect xlib to the dictionary with the keys
        '''


        def keylisten():
            # select display to listen on
            self.disp = Display()
            self.root = self.disp.screen().root
            # specify event
            self.root.change_attributes(event_mask = X.KeyPressMask)

            self.grabbing = True
            self.grabKey('grab')

            #print 'listening'
            while self.grabbing == True:

                self.disp.pending_events()
                readable = select.select([self.disp], [], [], 1)


                if [self.disp] in readable:
                    i = self.disp.pending_events()
                    while i > 0:
                        event = self.disp.next_event()
                        if event.type == X.KeyPress:
                            self.ButtonHit(event.detail)
                            i = i - 1

            # free display
            self.grabKey('free')
            self.disp.close()
            thread.exit()        
            print "this print command doesn't make any sense"


        # start the listentread                    
        thread.start_new_thread(keylisten,())

        

    def ButtonHit(self,event):
        '''##########################################################################
        a mapped button was hit! do specified exaile action
        '''
        # first specify actions:
        def seekBack5():
            APP.player.seek(APP.player.get_position()/1000000000-5)
            APP.show_osd()

        def seekForward5():
            APP.player.seek(APP.player.get_position()/1000000000+5)
            APP.show_osd()
            
        def volUp5():
            APP.volume.set_value(APP.volume.value+2)
            
        def volDown5():
            APP.volume.set_value(APP.volume.value-2)

        for i in self.keyb.values():
            if i[1] == event:
                eval (i[7]+'()')



    def savesettings(self):
        '''##########################################################################
        Save the working dictionary a a string
        '''
        #print 'savesettings'
        for k in self.keyb.keys():
            #print self.keyb[k]
            APP.settings.set_str(k, str(self.keyb[k]), plugin=plugins.name(__file__))



        
    def getsettings(self):
        '''##########################################################################
        Get the string and convert it back to the state it was before saving
        '''
        #value = get_str('setting_name_1', default='some string', plugin=plugins.name(__file__))
        # this dictionary will hold the setting
        self.keyb = {}

        for action in self.actionlist:


            # get values, remove garbage and split values into a list
            values = APP.settings.get_str(action, default='some string', plugin=plugins.name(__file__)).strip('[]').rsplit(',')

            # convert values into desired types
            clean = [values[0].lstrip(' ').strip('\''),int(values[1]),int(values[2]),int(values[3]),int(values[4]),int(values[5]),int(values[6]),values[7].lstrip(' ').strip('\'')]

            # finally put all into the dict
            self.keyb[action] = clean
            


    def configdialog(self):
        '''##########################################################################

        '''
        def defineNewKey(widget,data):

            def keypressed(widget, event):
                mod = 0
                if 'GDK_SHIFT_MASK' in event.state.value_names:
                    self.keyb[data][2] = 1
                    mod += 1
                else:
                    self.keyb[data][2] = 0
                    
                if 'GDK_CONTROL_MASK' in event.state.value_names:
                    self.keyb[data][3] = 1
                    mod += 1                    
                else:
                    self.keyb[data][3] = 0

                if 'GDK_MOD1_MASK' in event.state.value_names:
                    self.keyb[data][4] = 1
                    mod += 1
                else:
                    self.keyb[data][4] = 0

                if 'GDK_MOD2_MASK' in event.state.value_names:
                    self.keyb[data][5] = 1
                    mod += 1
                else:
                    self.keyb[data][5] = 0

                if 'GDK_MOD3_MASK' in event.state.value_names:
                    self.keyb[data][6] = 1
                    mod += 1
                else:
                    self.keyb[data][6] = 0
                
                if event.string == '':
                    print 'mod hit'
                    
                elif mod == 0:
                    print 'no mod used'
                    
                else:
                    # If the user entered a valid keycombination, save the key in the dict
                    # and reload the main-plugin-configuration dialog
                    # so that the label on the button shows the correct key
                    # but first check if the key is already mapped
                    used = ''
                    for kcode in self.keyb:
                        if self.keyb[kcode][1] == event.hardware_keycode:
                            if self.keyb[kcode][0] != self.keyb[data][0]:
                                used = kcode
                            
                    if used == '':
                        self.keyb[data][0] = gtk.gdk.keyval_name(event.keyval)
                        self.keyb[data][1] = event.hardware_keycode
                        pkeyinfo.destroy()
                        dialog.destroy()
                        self.configdialog()
                    else:
                        useddialog = gtk.MessageDialog(APP.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                                       gtk.MESSAGE_INFO, gtk.BUTTONS_OK, "Key already mapped by %s" % used)
                        useddialog.run()
                        useddialog.destroy()

                
                
            pkeyinfo = gtk.MessageDialog(APP.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                         gtk.MESSAGE_INFO, gtk.BUTTONS_NONE,
                                         "Please Press a Key for '%s' while holding one or more modifier Keys (ctrl, shift, alt)" % data)
            
            pkeyinfo.add_events(gtk.gdk.KEY_PRESS_MASK)
            pkeyinfo.connect('key-press-event', keypressed)
            pkeyinfo.run()
        
        def clearKey(widget, data):
            self.keyb[data][0]='not defined'
            self.keyb[data][1]=0
            self.keyb[data][2]=0
            self.keyb[data][3]=0
            self.keyb[data][4]=0
            self.keyb[data][5]=0                                
            self.keyb[data][6]=0
            dialog.destroy()
            self.configdialog()
            
        # MAIN ----------------------------------------------------+
        #    label     key-button             clear-button         |
        #               L  defineNewKey()      L  self.clearKey()  |      
        #                   L  Keypressed()                        |
        #----------------------------------------------------------+


        dialog = gtk.Dialog("Configure Exaile Shortcuts",
                            APP.window,
                            gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        
        beschreibung = gtk.Label('The shortcuts will be globally accessible in X')
        dialog.vbox.pack_start(beschreibung, False, False, 0)

        def updatebuttons():
            for key in self.actionlist:            
                packung = gtk.HBox(False, 0)

                knopf = str(self.keyb[key][0])
                if self.keyb[key][2] == 1:
                    knopf += ' + shift'
                if self.keyb[key][3] == 1:
                    knopf += ' + ctrl'
                if self.keyb[key][4] == 1:
                    knopf += ' + mod1'
                if self.keyb[key][5] == 1:
                    knopf += ' + mod2'
                if self.keyb[key][6] == 1:
                    knopf += ' + mod3'

                name  = gtk.Label(key)
                name.set_width_chars(15)
                kname = gtk.Button(knopf)
                clk   = gtk.Button('clear')

                kname.connect("clicked",defineNewKey, key)
                clk.connect("clicked",clearKey, key)
                
                packung.pack_start(name, False, False, 5)
                packung.pack_start(kname, True, True, 5)
                packung.pack_start(clk, False, False, 2)
                dialog.vbox.pack_start(packung, False, False, 5)
                name.show()
                kname.show()
                clk.show()
                packung.show()

                                

        self.grabbing = False
        updatebuttons()
        beschreibung.set_padding(5, 3)
        beschreibung.show()
        dialog.set_border_width(5)

        dial = dialog.run()
        if dial == gtk.RESPONSE_ACCEPT:
            self.savesettings()
            self.listen()
        elif dial == gtk.RESPONSE_REJECT:
            self.getsettings()
            self.listen()
        dialog.destroy()





def initialize():
    """
        Called when the plugin is enabled
    """
    APP.window.cuts = XlibKeys()
    return True
 
def destroy():
    """
        Called when the plugin is disabled
    """
    APP.window.cuts.freeKey()

    CONNS.disconnect_all()
 
def configure():
    """
        Called when the user clicks Configure in the Plugin Manager
    """
    APP.window.cuts.configdialog()


