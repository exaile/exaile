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
#   .~SSS' '' ' s'     `~:.  `.SSSSS'''''aS  
#     >Ss''''.'SSSs       ';    >SSS'''.'SS
#   ,'''S', ~`'SSSSSs    `~   ,''''S''  .  
# '''',''   A. `'SSSSSs    ,''''','    `A;.
#'' s'   K. ..N. `'SSSSS'''''''sSs. ~a;.,;   
#''SSSs    E.~  Y   >SSS'''';'.SSSSs. ~a.``      
#`'SSSSSs    Y    ,''''S',' ,. `'SSSSs. ~;>   
#  `'SSSSSs.   ,'''''','    'I;. `'SSSSs. ,  
#;k   `'SSSS''''''''s'  <E;... ~L. `'SSSS''
#df     ,SSS'''''.'SSSs   `X. ``~'E>  >SS''
#     `''''S''''` `'SSSSs   ~A.    ,`'''S''
#
# ADD KEYBOARD SHORTCUTS TO EXAILE



from gettext import gettext as _

import xl.plugins as plugins

import gtk
from gobject import source_remove,io_add_watch
from Xlib.display import Display
from Xlib import X 

PLUGIN_NAME = _("Keyboard Shortcuts")
PLUGIN_AUTHORS = ['Hubert Berezowski <hubertb2@wp.pl>']
PLUGIN_VERSION = '0.1.5'
PLUGIN_DESCRIPTION = _(r""" Keyboard Shortcuts via the X Server.
\n\n
Requires Python-Xlib
\n
http://python-xlib.sourceforge.net/""")


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
        self.actionlist = ['play','pause','stop','next Track','previous Track','seek forward','seek backward','volume up','volume down','show osd']

        # load settings or use default
        try:
            self.getsettings()
        except:

            #        [key] [button] [ 1=pressed 0=unpressed       ] [ a function the key will call ]
            #        [   ] [text  ] [ leave this 0                ] [ or a direct exaile command ]
            #         v      v       v       v     v    v   v    v    v        v
            # keyb = 'name':[keyname,keycode,shift,ctrl,alt,mod1,mod2,callback,callback-arguments]
            #         ^       ^      ^       ^     ^    ^   ^    ^    ^        ^        
            # keyb = '*   ':[str    ,int    ,int  ,int ,int,int,int  ,str     ,str               ]

            
            self.keyb = {'play':          ['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.play',''],
                         'stop':          ['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.stop',''],
                         'pause':         ['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.toggle_pause',''],
                         'next Track':    ['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.next',''],
                         'previous Track':['not defined', 0, 0, 0, 0, 0, 0, 'APP.player.previous',''],
                         'seek forward':  ['not defined', 0, 0, 0, 0, 0, 0, 'seekForward','5'],
                         'seek backward': ['not defined', 0, 0, 0, 0, 0, 0, 'seekBack','5'],
                         'volume up':     ['not defined', 0, 0, 0, 0, 0, 0, 'volUp5','2'],
                         'volume down':   ['not defined', 0, 0, 0, 0, 0, 0, 'volDown5','2'],
                         'show osd':      ['not defined', 0, 0, 0, 0, 0, 0, 'APP.show_osd',''],
                         }

        # connect loaded settings with X
        # start listening
        self.listen()

    def ButtonHit(self,event):
        '''##########################################################################
        a mapped button was hit! do specified exaile action
        '''
        # specify actions:
        def seekBack(step):
            APP.player.seek(APP.player.get_position()/1000000000-step)
            APP.show_osd()

        def seekForward(step):
            APP.player.seek(APP.player.get_position()/1000000000+step)
            APP.show_osd()
            
        def volUp5(step):
            APP.volume.set_value(APP.volume.value+step)
            
        def volDown5(step):
            APP.volume.set_value(APP.volume.value-step)
            
        # run the function keyb[callback]([arguments]) if keyb[kecode] == x.event
        for i in self.keyb.values():
            if i[1] == event:
                eval (i[7]+'('+i[8]+')')

    def extras(self,key):
        '''#########################################################################
         called by updatebuttons() in the configure method. will return a gtk widget
         which will be between the label and key-button.
         '''
        def setextra(value):
            self.keyb[key][8]=str(value.value)
            
        if key == 'seek forward':
            container = gtk.HBox(False, 0)
            adjustments = gtk.Adjustment(float(self.keyb[key][8]), 1, 50, 1, 0, 0)
            adjustments.connect("value_changed", setextra)
            zeichen = gtk.Label(" ")        
            label = gtk.Label(_("sec."))        
            steps = gtk.HScale(adjustments)        
            steps.set_value_pos(gtk.POS_LEFT)
            steps.set_usize( 100, 0)
            container.pack_start(zeichen, True, True, 3)        
            container.pack_start(steps, True, True, 3)        
            container.pack_start(label, False, False, 3)
            zeichen.show()
            steps.show()
            label.show()

            return container

        if key == 'seek backward':
            container = gtk.HBox(False, 0)
            adjustments = gtk.Adjustment(float(self.keyb[key][8]), 1, 50, 1, 0, 0)
            adjustments.connect("value_changed", setextra)
            zeichen = gtk.Label("-")                    
            label = gtk.Label(_("sec."))        
            steps = gtk.HScale(adjustments)        
            steps.set_value_pos(gtk.POS_LEFT)
            steps.set_usize( 100, 0)
            container.pack_start(zeichen, True, True, 3)        
            container.pack_start(steps, True, True, 3)        
            container.pack_start(label, False, False, 3)
            #steps.set_inverted(True)
            zeichen.show()
            steps.show()
            label.show()

            return container

        if key == 'volume up':
            zeichen = gtk.Label(" ")                    
            container = gtk.HBox(False, 0)
            adjustments = gtk.Adjustment(float(self.keyb[key][8]), 0, 25, 1, 0, 0)
            adjustments.connect("value_changed", setextra)
            steps = gtk.HScale(adjustments)        
            steps.set_value_pos(gtk.POS_LEFT)
            steps.set_usize( 100, 0)
            label = gtk.Label("%")        
            container.pack_start(zeichen, True, True, 3)        
            container.pack_start(steps, True, True, 3)
            container.pack_start(label, False, False, 3)
            steps.show()
            zeichen.show()
            label.show()
            
            return container

        if key == 'volume down':
            zeichen = gtk.Label("-")            
            container = gtk.HBox(False, 0)
            adjustments = gtk.Adjustment(float(self.keyb[key][8]), 0, 25, 1, 0, 0)
            adjustments.connect("value_changed", setextra)
            steps = gtk.HScale(adjustments)        
            #steps.set_inverted(True)
            steps.set_value_pos(gtk.POS_LEFT)
            steps.set_usize( 100, 0)
            label = gtk.Label("%")                    
            container.pack_start(zeichen, True, True, 3)                    
            container.pack_start(steps, True, True, 3)
            container.pack_start(label, False, False, 3)
            steps.show()
            zeichen.show()
            label.show()
            
            return container


    
##################################################################################
#
# If you want to add your custom shortcut, this is as far as you have to edit this
# file. The Rest is generic stuff that should work with any action. As long as it
# follows following pattern:
#
#     in the __init__ method:
#         a valid entry(see comments) in the keyb dictionary and actionlist
#
#  optional:
#     in the Buttonhit method:
#         a function called by the 7the entry in the dict
#
#     in the extras method:
#         additional config menu items
#
##################################################################################


    def freeKey(self):
        '''#######################################################################
        stop grabbing without a trace (i hope)
        '''

        source_remove(self.listener)
        self.grabKey('free')
        #self.disp.close()


    def grabKey(self,action):
        '''#######################################################################
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
                    self.disp.flush()
                    #print 'ungrabbed '+str(self.keyb[key][1])
                
    def listen(self):
        '''##########################################################################
        connect xlib to the dictionary with the keys
        '''


        # select display to listen on
        self.disp = Display()
        self.root = self.disp.screen().root
        # specify event
        self.root.change_attributes(event_mask = X.KeyPressMask)

        self.grabKey('grab')

        #print 'listening'
        def checkKey(arg1,arg2):
            #print arg1,arg2
            event = self.disp.next_event()
            if event.type == X.KeyPress:
                self.ButtonHit(event.detail)
            return True
    
        self.listener = io_add_watch(self.disp, 1 ,checkKey)
        print self.disp.pending_events()


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
            clean = [values[0].lstrip(' ').strip('\''),int(values[1]),int(values[2]),int(values[3]),int(values[4]),int(values[5]),int(values[6]),values[7].lstrip(' ').strip('\''),values[8].lstrip(' ').strip('\'')]

            # finally put all into the dict
            self.keyb[action] = clean
            


    def configdialog(self):
        '''##########################################################################

        '''
        def defineNewKey(widget,data):

            def keypressed(widget, event):
                mod = 0
                # put pressed modifiers into the list and count them
                ####
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

                #### now sort out the exceptions
                # omitt doing an action for modifier key events                
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
                        updatebuttons()
                    else:
                        useddialog = gtk.MessageDialog(APP.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                                       gtk.MESSAGE_INFO,
                                                       gtk.BUTTONS_OK,
                                                       _("Key already mapped by %s") % used)
                        useddialog.run()
                        useddialog.destroy()

                
            #######################################################################
#        dialog = gtk.Dialog("Configure Exaile Shortcuts",
#                            APP.window,
#                            gtk.DIALOG_DESTROY_WITH_PARENT,
#                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
#                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        

                        
            pkeyinfo = gtk.MessageDialog(APP.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                         gtk.MESSAGE_INFO, gtk.BUTTONS_CANCEL,
                                         _("Please Press a Key for '%s' while holding one or more modifier Keys (ctrl, shift, alt)") % data)
            
            pkeyinfo.add_events(gtk.gdk.KEY_PRESS_MASK)
            pkeyinfo.connect('key-press-event', keypressed)
            pkeyinfo.run()
            pkeyinfo.destroy()
            
        def clearKey(widget, data):
            # user clicked the 'clear' button
            self.keyb[data][0]='not defined'
            self.keyb[data][1]=0
            self.keyb[data][2]=0
            self.keyb[data][3]=0
            self.keyb[data][4]=0
            self.keyb[data][5]=0                              
            self.keyb[data][6]=0
            updatebuttons()
            
        # packung -------------------------------------------------+
        #    label     key-button             clear-button         |
        #               L  defineNewKey()      L  self.clearKey()  |      
        #                   L  Keypressed()                        |
        #----------------------------------------------------------+


        dialog = gtk.Dialog(_("Configure Exaile Shortcuts"),
                            APP.window,
                            gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        
        beschreibung = gtk.Label(_('The shortcuts will be globally accessible in X'))
        dialog.vbox.pack_start(beschreibung, False, False, 0)

        def updatebuttons():
            # remove the refreshbox container holding the old buttons
            #try:
            dialog.vbox.remove(self.refreshbox)

            # create the context for the buttons 
            self.refreshbox = gtk.VBox(True, 0)
            dialog.vbox.pack_start(self.refreshbox, False, False, 5)
            beschreibung.set_padding(5, 3)
            beschreibung.show()
            dialog.set_border_width(5)
            
            
            for key in self.actionlist:

                # create something like this for every key:
                #
                #  +- packung -----------------------------------+
                #  | [ name ] ( [ extra ] )? [ kname ] [ clk ]   |
                #  +---------------------------------------------+
                #
                # and put it in the refresh-vbox:
                #  
                #       +- dialog.vbox -------+
                #       | beschreibung(label) |
                #   --> | +- refreshbox ----+ |
                #       | |  [ packung 1 ]  | |
                #       | |  [ packung 2 ]  | |
                #       | |  etc ...        | |
                #   --> | +-----------------+ |
                #       |        [cancel][ok] |
                #       +---------------------+                
                
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
                self.refreshbox.pack_start(packung, False, False, 5)                
                packung.pack_start(name, False, False, 5)

                # check for extra options
                if self.keyb[key][8] != '':
                    extra = self.extras(key)
                    packung.pack_start(extra, False, False,5)
                    extra.show()

                packung.pack_start(kname, True, True, 5)
                packung.pack_start(clk, False, False, 2)
                name.show()
                kname.show()
                clk.show()
                packung.show()
            self.refreshbox.show()

            
               

        # ungrab keys, so that no key is blocked while defining a new shortcut
        self.grabKey('free')
        source_remove(self.listener)

        # create the context for the buttons 
        self.refreshbox = gtk.VBox(True, 0)
        dialog.vbox.pack_start(self.refreshbox, False, False, 5)
        beschreibung.set_padding(5, 3)
        beschreibung.show()
        dialog.set_border_width(5)


        updatebuttons()
        
        # If user clicked 'ok' save settings else reload settings
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


