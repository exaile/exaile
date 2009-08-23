# Moodbar -  Replace standard progress bar with moodbar
# Copyright (C) 2009  Solyianov Michael <crantisz@gmail.com>
#
# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.


import cgi, gtk, gobject, os, os.path, subprocess
from xl import event, xdg
from xl.nls import gettext as _

import logging
logger = logging.getLogger(__name__)

ExaileModbar = None

class ExModbar:
    #Setup and getting values------------------------------------------------
    
    def __init__(self):
         self.moodbar=''
         self.buff=''
         self.brush=None
         self.modwidth=0
         self.curpos=0
         self.modTimer=None
         self.haveMod=False
         self.playingTrack=''
         self.seeking=False
         self.setuped=False
         self.runed=False
         self.pid=0
         self.uptime=0

         self.moodsDir=os.path.join(xdg.get_cache_dir(), "moods")
         if not os.path.exists(self.moodsDir): 
             os.mkdir(self.moodsDir)

    def set_ex(self, ex):
         self.exaile=ex

    def get_size(self):
         progress_loc = self.mod.get_allocation()
         return progress_loc.width

    #Setup-------------------------------------------------------------------
   
    def changeBarToMod(self):
         place=self.pr.bar.get_parent()
         self.mod = gtk.DrawingArea()
         self.mod.pangolayout = self.mod.create_pango_layout("")
         self.mod.set_size_request(-1, 24)
         place.pack_start(self.mod, False, True, 0)
         place.reorder_child(self.mod, 2)
         self.mod.realize()
         self.pr.bar.hide()
         self.mod.show()

    def changeModToBar(self):
         if hasattr(self, 'mod'):
             self.mod.destroy()
             self.pr.bar.show()

    def setupUi(self):
              self.setuped=True
              self.pr=self.exaile.gui.main.progress_bar
              self.changeBarToMod()
              self.mod.seeking=False
              self.mod.connect("expose-event", self.drawMod)
              self.mod.add_events(gtk.gdk.BUTTON_PRESS_MASK) 
              self.mod.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
              self.mod.add_events(gtk.gdk.POINTER_MOTION_MASK)
              self.mod.connect("button-press-event", self.modSeekBegin) 
              self.mod.connect("button-release-event", self.modSeekEnd)
              self.mod.connect("motion-notify-event", self.modSeekMotionNotify) 
              self.brush = self.mod.window.new_gc()
              
              track = self.exaile.player.current
              
              self.lookformod(track)

    def destroy(self):
         if self.modTimer: gobject.source_remove(self.modTimer)


    #playing ----------------------------------------------------------------
   
    def lookformod(self,track):
         if not track or not track.is_local(): 
             return

         self.playingTrack=str(track.get_loc())
         self.playingTrack=self.playingTrack.replace("file://","")
         modLoc=self.moodsDir+'/'+ self.playingTrack.replace('/','-')+".mood"
         modLoc=modLoc.replace("'",'')
         needGen=False
         self.curpos=self.exaile.player.get_progress()
         if os.access(modLoc, 0):
             self.modwidth=0
             if not self.readMod(modLoc): 
                 needGen=True
             self.updateplayerpos() 
         else: needGen=True
         if needGen:
             self.pid = subprocess.Popen(['/usr/bin/moodbar',
                 self.playingTrack, '-o', modLoc])
         self.haveMod=not needGen
       
         if self.modTimer: gobject.source_remove(self.modTimer)
         self.modTimer = gobject.timeout_add(1000, self.updateMod)


    def play_start(self, type, player, track):
         self.lookformod(track)

    def play_end (self, type, player, track):
         if self.modTimer: gobject.source_remove(self.modTimer)
         self.modTimer = None
         self.haveMod = False
         self.mod.queue_draw_area(0, 0, self.get_size(), 24)

    #update player's ui -----------------------------------------------------

    def updateMod(self):
         self.updateplayerpos()
         if not self.haveMod:
           logger.debug('Searching for mood...')
           modLoc=self.moodsDir+'/'+ self.playingTrack.replace('/','-')+".mood"
           modLoc=modLoc.replace("'",'')
           if self.readMod(modLoc):
              logger.debug("Mood found.")
              self.haveMod=True 
              self.modwidth=0
         self.modTimer = gobject.timeout_add(1000, self.updateMod)

    def updateplayerpos(self):
         if self.modTimer: self.curpos=self.exaile.player.get_progress()
         self.mod.queue_draw_area(0, 0, self.get_size(), 24)


    #reading mod from file and update mood preview --------------------------
   
    def readMod(self, moodLoc):
       retur=True
       self.moodbar=''
       try:  
          if moodLoc=='':
             for i in range(3000): 
                  self.moodbar=self.moodbar+chr(255)
             return True 
          else:
             f=open(moodLoc,'rb')     
             for i in range(3000):
                 r=f.read(1)
                 if r=='':
                      r=chr(0)
                      retur=False
                 self.moodbar=self.moodbar+r
             f.close()
             return retur 
          
       except: 
          logger.debug('Could not read moodbar.')
          self.moodbar=''
          for i in range(3000):
              self.moodbar=self.moodbar+chr(0)
          return False


    def genBuff(self):
        width=self.get_size()
        self.modwidth=width
        b=''
        hh=[0.2,0.4,0.7,0.8,0.9,1,1,0.98,0.93,0.85,0.80,0.80,0.80,
                0.85,0.93,0.98,1,1,0.9,0.8,0.7,0.6,0.4,0.2]
        #hh=[0.5,0.55,0.6,0.65,0.7,1,0.95,0.92,0.88,0.84,0.80,0.80,
                #0.80,0.84,0.88,0.92,0.95,1,0.7,0.65,0.6,0.55,0.5,0.45]
        #hh=[0.2,0.4,0.7,0.8,0.9,1,1,1,1,1,1,1,1,1,1,1,1,1,0.9,0.8,
                # 0.7,0.6,0.4,0.2]
        for h in range(24):
             for x in range(width):
                   for i in range(3):
                         b=b+chr(int(ord(
                             self.moodbar[int(x*1000/width)*3+i])*hh[h]))
        return b

 
    #Drawing mood UI---------------------------------------------------------
  
    def drawMod(self,this,area):
        
         self.uptime+=1
         gc = self.brush 
         this=self.mod
         gc.foreground = this.get_colormap().alloc_color(0x0000, 
                 0x0000, 0x0000)
         track = self.exaile.player.current
         
         try:
            if not self.get_size()==self.modwidth: 
                  self.buff=self.genBuff()
            if (self.haveMod):
                 this.window.draw_rgb_image(gc, 0, 0, self.modwidth, 24, 
                         gtk.gdk.RGB_DITHER_NONE, self.buff, self.modwidth*3)
            else:
               
               for i in range(5): 
                   gc.foreground = this.get_colormap().alloc_color(0xAAAA*i/5,
                              0xAAAA*i/5, 0xAAAA*i/5)
                   this.window.draw_rectangle(gc, True, 0, 0+i, 
                           self.modwidth, 24-i*2)

               if self.modTimer and track.is_local():    
                   gc.foreground = this.get_colormap().alloc_color(0xBBBB, 
                           0xBBBB, 0xBBBB)
                   this.window.draw_rectangle(gc, True,  
                             (self.modwidth/10)*(self.uptime%10), 
                             5, self.modwidth/10, 14)
               
      
         except:
            for i in range(5):  
              gc.foreground = this.get_colormap().alloc_color(0xFFFF*i/5, 
                      0x0000, 0x0000)
              this.window.draw_rectangle(gc, True, 0, 0+i, 
                      self.modwidth, 24-i*2)
            
            if track and track.is_local(): 
              self.lookformod(track)
            
            return False
            
         track = self.exaile.player.current
         if not track or not track.is_local(): return

         if self.modTimer:
            gc.foreground = this.get_colormap().alloc_color(0xFFFF, 
                    0xFFFF, 0xFFFF)
            gc.line_width=2
            this.window.draw_arc(gc, True, int(self.curpos*self.modwidth)-15, 
                    -5, 30, 30,  60*64, 60*64)
            gc.foreground = this.get_colormap().alloc_color(0x0000, 
                    0x0000, 0x0000)

            this.window.draw_line(gc, int(self.curpos*self.modwidth), 10, 
                                      int(self.curpos*self.modwidth)-10, -5)
            this.window.draw_line(gc, int(self.curpos*self.modwidth), 10, 
                                      int(self.curpos*self.modwidth)+10, -5)
   
            length = self.exaile.player.current.get_duration()
            seconds = self.exaile.player.get_time()
            remaining_seconds = length - seconds
            text = ("%d:%02d / %d:%02d" %
               ( seconds // 60, seconds % 60, remaining_seconds // 60,
               remaining_seconds % 60))
   
            this.pangolayout.set_text(text)
            this.window.draw_layout(gc, self.modwidth/2-50, 
                    3, this.pangolayout)
            this.window.draw_layout(gc, self.modwidth/2-52, 
                    1, this.pangolayout)
            gc.foreground = this.get_colormap().alloc_color(0xFFFF, 
                    0xFFFF, 0xFFFF)

            this.window.draw_layout(gc, self.modwidth/2-51, 
                    2, this.pangolayout)
         
 
    #seeking-----------------------------------------------------------------

    def modSeekBegin(self,this,event):
        self.seeking = True


    def modSeekEnd(self,this,event):
        global exaile1
        self.seeking = False
        track = self.exaile.player.current
        if not track or not track.is_local(): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_size()
        value = mouse_x / progress_loc
        if value < 0: value = 0
        if value > 1: value = 1
        
        self.curpos=value
        length = track.get_duration()
        self.mod.queue_draw_area(0, 0, progress_loc, 24)
        #redrawMod(self)

        seconds = float(value * length)
        self.exaile.player.seek(seconds)  

    def modSeekMotionNotify(self,this,  event):
        if self.seeking:
            track = self.exaile.player.current
            if not track or not track.is_local(): return

            mouse_x, mouse_y = event.get_coords()
            progress_loc = self.get_size()
            value = mouse_x / progress_loc
            if value < 0: value = 0
            if value > 1: value = 1
        
            
            self.curpos=value
            self.mod.queue_draw_area(0, 0, progress_loc, 24)
    

    #------------------------------------------------------------------------



def enable(exaile):
    global ExaileModbar
    ExaileModbar=ExModbar()
    ExaileModbar.set_ex(exaile)

    try:
        subprocess.call(['moodbar', '--help'], stdout=-1, stderr=-1)
    except OSError:
        raise NotImplementedError(_('Moodbar executable is not available.'))
        return False

    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    global ExaileModbar
    track = ExaileModbar.exaile.player.current
    ExaileModbar.readMod('')
    ExaileModbar.setupUi()       
    event.add_callback(ExaileModbar.play_start, 'playback_track_start')
    event.add_callback(ExaileModbar.play_end, 'playback_player_end')

def disable(exaile):
    global ExaileModbar
    ExaileModbar.changeModToBar()
    event.remove_callback(ExaileModbar.play_start, 'playback_track_start')
    event.remove_callback(ExaileModbar.play_end, 'playback_player_end')
    ExaileModbar.destroy()
    ExaileModbar = None



#have errors from time to time:
#python: ../../src/xcb_lock.c:77: _XGetXCBBuffer: Assertion `((int) ((xcb_req) - (dpy->request)) >= 0)' failed.

#exaile.py: Fatal IO error 11 (Resource temporarily unavailable) on X server :0.0.

#Xlib: sequence lost (0xe0000 > 0xd4add) in reply type 0x0!
#python: ../../src/xcb_io.c:176: process_responses: Assertion `!(req && current_request && !(((long) (req->sequence) - (long) (current_request)) <= 0))' failed.






