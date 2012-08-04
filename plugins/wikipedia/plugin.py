#encoding:utf-8

# Copyright (C) 2006 Amit Man <amit.man@gmail.com>
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

import gtk
import HTMLParser
import urllib2
import random
import threading
from gettext import gettext as _

from sentencesplitter import SentenceSplitter
import config

b = gtk.Button()
PLUGIN_ICON = b.render_icon('gtk-info', gtk.ICON_SIZE_MENU)
b.destroy()

class content(HTMLParser.HTMLParser,threading.Thread):
    
    def __init__(self, the_page):
        threading.Thread.__init__(self)
        HTMLParser.HTMLParser.__init__(self)
        self.sentencesplitter=SentenceSplitter()
        self.in_paragraph=False
        self.num_of_para=-1 # when we first meet tag p, we will be 0
        self.paraString=[]
        self.paraSentances=[]
        self.end_of_intro=False
        self.cant_find_page=False
        self.gotimage=False
        
        self.feed(the_page)
        self.parse_to_sentances()
        

    def handle_starttag(self,tag,attrs):
        if tag == 'p':
            #if not self.end_of_intro:
                self.in_paragraph=True
                self.num_of_para=self.num_of_para+1
                self.paraString.append('')
            #print 'len of parastring: %d' % len(self.paraString)
            #print 'start paragraph: %d' % self.num_of_para
       
        if tag =='table':
            if  attrs[0][0] == 'id' and attrs[0][1]=='toc':
                self.end_of_intro=True

        if tag =='img':
            if not self.gotimage:
                for desc in attrs:
                    if desc[0]=='src':
                        src=desc[1]
                        print src
                        if src[-3:] != 'jpg':
                            print 'breaking'
                            break
                        print 'good pic'
                        self.gotimage=True
                        print src
                        
                        
                        headers = { 'User-Agent' : config.USER_AGENT }
                        req = urllib2.Request(src, None, headers)
                        response = urllib2.urlopen(req)
                        image = response.read()
                        imagefile=file('didyouknow_tmp.img','w')
                        imagefile.write(image)
                        imagefile.close
                    
    def handle_endtag(self,tag):
        if tag =='p':
            self.in_paragraph=False
            #if the last paragraph was empty
            if not len(self.paraString[self.num_of_para]):
                self.num_of_para=self.num_of_para-1
                self.paraString.pop()

    def handle_data(self,data):
        if data=='Wikipedia does not have an article with this exact name.':
            print "cant find wikipedia page"
            self.no_page()
        
        if self.in_paragraph: #and not self.end_of_intro:
            self.paraString[self.num_of_para]=self.paraString[self.num_of_para]+data
        

    def parse_to_sentances(self):
        for s in self.paraString:
            self.paraSentances.append(self.sentencesplitter.split(s))


    def get_random_fact(self):
        if self.cant_find_page:
            return "Cant find info on wikipedia"
        else:
            s=''
            random_para=random.randint(0,len(self.paraSentances)-1)
            random_sen=random.randint(0,len(self.paraSentances[random_para])-1)
            if random_sen > 0:
                s=self.half_sentence(self.paraSentances[random_para][random_sen-1],'begin')+' '
            s=s+self.paraSentances[random_para][random_sen]
            if random_sen < len(self.paraSentances[random_para])-1:
                    s=s+' '+self.half_sentence(self.paraSentances[random_para][random_sen+1],'end')
            return s

    def half_sentence(self,sentence,side='begin'):
        wa=sentence.split(' ')
        word_count=len(wa)
        if side=='end':
            wa=wa[0:(word_count/2)]+['... ']
        if side == 'begin':
            wa=[' ...']+wa[(word_count/2):word_count]
        return (' '.join(wa))


    def no_page(self):
        self.cant_find_page=True

ig=None
newSong=True
songName=''
APP = None
BUTTON = None
MENU_ITEM = None
TIPS = gtk.Tooltips()

D=None
L=None

def play_track(exaile, track):
    """
        Called when playback on a track starts ("play-track" event)
    """
    global ig
    
    if track.type != 'stream':
        ig.get_song_info(exaile,track)

def stop_track(exaile, track):
    global ig
    global songName
    songName=''
    
def track_information_updated(exaile):

    global ig
    global songName
    global enable_popups
    track=exaile.player.current
    if (ig.enable_popups):
        
        #if track.type == 'stream':
        if songName != track.title:
            songName=track.title
            print "TRYING: to find on %s " % track.artist
            ig.get_song_info(exaile,track)
            ig.show_random_info()

class InfoGiver:

    def __init__(self,APP,toggle_button):

        self.toggle_button=toggle_button
        self.c=None
        self.enable_popups=False
        wtree=gtk.glade.xml_new_from_buffer(XML_STRING, len(XML_STRING))
        self.D=wtree.get_widget('window')
        self.L=wtree.get_widget('label')
        self.image=wtree.get_widget('image')
        self.vbox1=wtree.get_widget('vbox1')
        self.title=wtree.get_widget('title')
        self.event=wtree.get_widget('event')
        self.sep_event=wtree.get_widget('sep_event')
        self.title_event=wtree.get_widget('title_event')
        self.event.connect('button_press_event', self.start_dragging)
        self.event.connect('button_press_event', self.close_by_double_click)
        self.event.connect('button_release_event', self.stop_dragging)
        self.sep_event.connect('button_press_event', self.start_dragging)
        self.sep_event.connect('button_press_event', self.close_by_double_click)
        self.title_event.connect('button_press_event', self.close_by_double_click)
        self.sep_event.connect('button_release_event', self.stop_dragging)
        self.title_event.connect('button_press_event', self.start_dragging)
        self.title_event.connect('button_release_event', self.stop_dragging)
        self.__handler = None
        self.B=wtree.get_widget('button')
        self.D.hide();
        self.D.connect('destroy',self.popup_destroyed)
        self.B.connect('clicked',self.activated)
        bg_color = gtk.gdk.color_parse('#567EA2');
        self.D.modify_bg(gtk.STATE_NORMAL, bg_color)
        self.title_event.modify_bg(gtk.STATE_NORMAL, bg_color)
        self.sep_event.modify_bg(gtk.STATE_NORMAL, bg_color)
        self.event.modify_bg(gtk.STATE_NORMAL, bg_color)
        
#------------------------------------------------
# dragging capability. copied from xlmisc.py


    def close_by_double_click(self,widget,event):
        
        if event.type == gtk.gdk._2BUTTON_PRESS:
            bg_color = gtk.gdk.color_parse('white');
            self.toggle_button.modify_bg(gtk.STATE_NORMAL, bg_color)
            self.enable_popups = False
            self.D.hide()
   

    def start_dragging(self, widget, event):
        """
            Called when the user starts dragging the window
        """
        self.__start = event.x, event.y
        self.__handler = self.D.connect('motion_notify_event',
            self.dragging)
        self.__timeout = None


    def stop_dragging(self, widget, event):
        """
            Called when the user stops dragging the mouse
        """
        global POPUP
        if self.__handler: self.D.disconnect(self.__handler)
        self.__handler = None
#        if self.start_timer:
#            self.__timeout = gobject.timeout_add(4000, self.D.hide)
#        settings = self.exaile.settings
#        (w, h) = self..get_size()
#        (x, y) = self.window.get_position()

#        settings['osd/x'] = x
#        settings['osd/y'] = y
#        settings['osd/h'] = h
#        settings['osd/w'] = w
    
#        POPUP = OSDWindow(self.exaile, get_osd_settings(settings))

    def dragging(self, widget, event):
        """
            Called when the user drags the window
        """
        self.D.move(int(event.x_root - self.__start[0]),
            int(event.y_root - self.__start[1]))

#-------------------------------------------------------------        
        
    def toggle_popups(self,b):
        
        if self.enable_popups == False:
            self.enable_popups = True
            bg_color = gtk.gdk.color_parse('red');
            self.toggle_button.modify_bg(gtk.STATE_NORMAL, bg_color)
            if APP.player.current != None:
                self.get_song_info(APP,APP.player.current)
                self.show_random_info()
            #else:
            #    self.label.set_label('no track is playing yet..')
            #    self.dialog.show_all()
        #moving from enable popups to diable them        
        elif self.enable_popups == True:
            bg_color = gtk.gdk.color_parse('white');
            self.toggle_button.modify_bg(gtk.STATE_NORMAL, bg_color)
            self.enable_popups = False
            self.D.hide()


    def activated(self,b):
        self.show_random_info()
        
    def get_song_info(self,exaile,track):
        if not self.enable_popups:
            return
        
        locale = exaile.settings.get_str('wikipedia_locale', 'en')
        url = "http://%s.wikipedia.org/wiki/%s" % (locale, track.artist)
        url = url.replace(" ", "_")
        headers = { 'User-Agent' : config.USER_AGENT }
        req = urllib2.Request(url, None, headers)
        response = urllib2.urlopen(req)
        the_page = response.read()
        self.c=content(the_page)
        self.c.start()
        #adding image
        if self.c.gotimage:
            self.image.set_from_file('didyouknow_tmp.img')
        else:
            raise "No Image found"
            
        self.title.set_label(_('Artist: ')+ track.artist+'\n\n'+self.c.paraSentances[0][0]);


    def show_random_info(self):
        self.D.show()
        self.L.show()
        if not self.enable_popups:
            return
                        
        self.L.set_label(_("Did you know...\n\n%s") % (self.c.get_random_fact()))

        #self.dialog.show_all()
        self.vbox1.resize_children()
            
    def kill_window(self):
        try:
            self.D.destroy()
        except:
            pass

    def popup_destroyed(self,w):
        self.enable_popups=False
        bg_color = gtk.gdk.color_parse('white');
        self.toggle_button.modify_bg(gtk.STATE_NORMAL, bg_color)


XML_STRING = None
def load_data(zip):
    global XML_STRING
    XML_STRING = zip.get_data('gui.glade')

