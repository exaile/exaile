# Moodbar -  Replace standard progress bar with moodbar
# Copyright (C) 2009-2010  Solyianov Michael <crantisz@gmail.com>
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

import moodbarprefs
import gtk
import glib
import os
import subprocess
import colorsys
from xl import event, player, settings, xdg
from xl.nls import gettext as _

import logging
logger = logging.getLogger(__name__)

ExaileModbar = None

class ExModbar(object):

    #Setup and getting values------------------------------------------------

    def __init__(self, player, progress_bar):
        self.pr = progress_bar
        self.player = player

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
        self.ivalue=0
        self.qvalue=0
        self.moodsDir=os.path.join(xdg.get_cache_dir(), "moods")
        if not os.path.exists(self.moodsDir):
            os.mkdir(self.moodsDir)

    def __inner_preference(klass):
        """functionality copy from notyfication"""
        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    defaultstyle = __inner_preference(moodbarprefs.DefaultStylePreference)
    flat = __inner_preference(moodbarprefs.FlatPreference)
    theme = __inner_preference(moodbarprefs.ThemePreference)
    cursor = __inner_preference(moodbarprefs.CursorPreference)

    darkness = __inner_preference(moodbarprefs.DarknessPreference)
    color = __inner_preference(moodbarprefs.ColorPreference)

    def get_size(self):
         progress_loc = self.mod.get_allocation()
         return progress_loc.width

    #Setup-------------------------------------------------------------------

    def changeBarToMod(self):
         place=self.pr.get_parent()
         self.mod = gtk.DrawingArea()
         self.mod.pangolayout = self.mod.create_pango_layout("")
         self.mod.set_size_request(-1, 24)
         place.remove(self.pr)
         place.add(self.mod)
         self.mod.realize()
         self.mod.show()

    def changeModToBar(self):
         if hasattr(self, 'mod'):
             place=self.mod.get_parent()
             place.remove(self.mod)
             place.add(self.pr)
             self.mod.destroy()

    def setupUi(self):
            self.setuped=True
            self.changeBarToMod()
            self.mod.seeking=False
            self.mod.connect("expose-event", self.drawMod)
            self.mod.add_events(gtk.gdk.BUTTON_PRESS_MASK)
            self.mod.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
            self.mod.add_events(gtk.gdk.POINTER_MOTION_MASK)
            self.mod.connect("button-press-event", self.modSeekBegin)
            self.mod.connect("button-release-event", self.modSeekEnd)
            self.mod.connect("motion-notify-event", self.modSeekMotionNotify)
            self.brush = self.mod.props.window.new_gc()

            track = self.player.current

            self.lookformod(track)

    def add_callbacks(self):
        event.add_callback(
            self.play_start,
            'playback_track_start',
            self.player
        )
        event.add_callback(
            self.play_end,
            'playback_player_end',
            player.PLAYER
        )

    def remove_callbacks(self):
        event.remove_callback(
            self.play_start,
            'playback_track_start',
            self.player
        )
        event.remove_callback(
            self.play_end,
            'playback_player_end',
            player.PLAYER
        )

    def destroy(self):
         if self.modTimer: glib.source_remove(self.modTimer)


    #playing ----------------------------------------------------------------

    def lookformod(self,track):
         if not track or not (track.is_local() or track.get_tag_raw('__length')):
             self.haveMod=False
             return

         self.playingTrack=str(track.get_loc_for_io())
         self.playingTrack=self.playingTrack.replace("file://","")
         modLoc=self.moodsDir+'/'+ self.playingTrack.replace('/','-')+".mood"
         modLoc=modLoc.replace("'",'')
         needGen=False
         self.curpos = self.player.get_progress()
         if os.access(modLoc, 0):
             self.modwidth=0
             if not self.readMod(modLoc):
                 needGen=True
             self.updateplayerpos()
         else: needGen=True
         if needGen:
             self.pid = subprocess.Popen(['/usr/bin/moodbar',
                 track.get_local_path(), '-o', modLoc])
         self.haveMod=not needGen

         if self.modTimer: glib.source_remove(self.modTimer)
         self.modTimer = glib.timeout_add_seconds(1, self.updateMod)


    def play_start(self, type, player, track):
         self.lookformod(track)

    def play_end (self, type, player, track):
         if self.modTimer: glib.source_remove(self.modTimer)
         self.modTimer = None
         self.haveMod = False
         self.mod.queue_draw_area(0, 0, self.get_size(), 24)

    #update player's ui -----------------------------------------------------

    def updateMod(self):
         self.updateplayerpos()
         if not self.haveMod:
           logger.debug(_('Searching for mood...'))
           modLoc=self.moodsDir+'/'+ self.playingTrack.replace('/','-')+".mood"
           modLoc=modLoc.replace("'",'')
           if self.readMod(modLoc):
              logger.debug(_("Mood found."))
              self.haveMod=True
              self.modwidth=0
         self.modTimer = glib.timeout_add_seconds(1, self.updateMod)

    def updateplayerpos(self):
         if self.modTimer:
             self.curpos = self.player.get_progress()
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
          logger.debug(_('Could not read moodbar.'))
          self.moodbar=''
          for i in range(3000):
              self.moodbar=self.moodbar+chr(0)
          return False


    def genBuff(self):
        width=self.get_size()
        self.modwidth=width
        darkmulti=(1-self.darkness/10)

        #logger.info(darkmulti)
        hh=[0.2,0.4,0.7,0.8,0.9,1,1,0.98,0.93,0.85,0.80,0.80,0.80,
                0.85,0.93,0.98,1,1,0.9,0.8,0.7,0.6,0.4,0.2]
        #hh=[0.5,0.55,0.6,0.65,0.7,1,0.95,0.92,0.88,0.84,0.80,0.80,
        #0.80,0.84,0.88,0.92,0.95,1,0.7,0.65,0.6,0.55,0.5,0.45]
        #hh=[0.2,0.4,0.7,0.8,0.9,1,1,1,1,1,1,1,1,1,1,1,1,1,0.9,0.8,
        # 0.7,0.6,0.4,0.2]
        self.defaultstyle_old =self.defaultstyle
        self.theme_old=self.theme
        self.flat_old=self.flat
        self.color_old =self.color
        self.darkness_old =self.darkness
        self.cursor_old=self.cursor
        gc = self.brush
        self.bgcolor = self.mod.style.bg[gtk.STATE_NORMAL]
        redf=self.bgcolor.red/255
        greenf=self.bgcolor.green/255
        bluef=self.bgcolor.blue/255
        colortheme=gtk.gdk.Color(self.color)
        c1,self.ivalue,self.qvalue=colorsys.rgb_to_yiq(float(colortheme.red)/256/256, float(colortheme.green)/256/256, float(colortheme.blue)/256/256)
        gc.foreground = self.bgcolor;
        gc.line_width=1
        self.pixmap = gtk.gdk.Pixmap(self.mod.window, width, 24)
        self.pixmap2 = gtk.gdk.Pixmap(self.mod.window, width, 24)
        self.pixmap.draw_rectangle(gc, True, 0, 0, self.modwidth, 24)
        self.pixmap2.draw_rectangle(gc, True, 0, 0, self.modwidth, 24)
        if self.flat:
             if self.theme:
                flatcolor1r=float(colortheme.red)/256/256
                flatcolor1g=float(colortheme.green)/256/256
                flatcolor1b=float(colortheme.blue)/256/256
                flatcolor2r=darkmulti*float(colortheme.red)/256/256
                flatcolor2g=darkmulti*float(colortheme.green)/256/256
                flatcolor2b=darkmulti*float(colortheme.blue)/256/256
             else:
                flatcolor1r=flatcolor1g=flatcolor1b=0.5
                flatcolor2r=flatcolor2g=flatcolor2b=0.5*darkmulti
        #render ---------------------------------------------------------
        for x in range(width):
        #reading color
           r=float(ord(self.moodbar[int(x*1000/width)*3]))/256
           g=float(ord(self.moodbar[int(x*1000/width)*3+1]))/256
           b=float(ord(self.moodbar[int(x*1000/width)*3+2]))/256
           if (self.theme or self.defaultstyle):
                c1,c2,c3=colorsys.rgb_to_yiq(r, g, b)

           if (self.theme):
                c2=c2+self.ivalue
                if c2>1: c2=1
                if c2<-1: c2=-1
                c3=c3+self.qvalue
                if c3>1: c3=1
                if c3<-1: c3=-1
           if self.defaultstyle:
                r,g,b=colorsys.yiq_to_rgb(0.5,c2,c3)
                waluelength=int(c1*24)
           else:
                if self.theme:
                    r,g,b=colorsys.yiq_to_rgb(c1,c2,c3)
           if not self.defaultstyle:
                buff=''
                for h in range(24):
                   buff=buff+chr(int(r*255*hh[h]+redf*(1-hh[h])))+chr(int(g*255*hh[h]+greenf*(1-hh[h])))+chr(int(b*255*hh[h]+bluef*(1-hh[h])))
                self.pixmap.draw_rgb_image(gc, x, 0, 1, 24,
                         gtk.gdk.RGB_DITHER_NONE, buff, 3)

                if self.cursor:
                   buff2=''
                   for h in range(24*3):
                         buff2=buff2+chr(int(ord(buff[h])*(darkmulti+(1-darkmulti)*(1-hh[int(h/3)]))))

                   self.pixmap2.draw_rgb_image(gc, x, 0, 1, 24,
                         gtk.gdk.RGB_DITHER_NONE, buff2, 3)

           else:
                if self.flat:
                   gc.foreground = self.mod.get_colormap().alloc_color(
                      int(flatcolor1r*0xFFFF),
                      int(flatcolor1g*0xFFFF),
                      int(flatcolor1b*0xFFFF)
                   )
                else:
                   gc.foreground = self.mod.get_colormap().alloc_color(
                      int(r*0xFFFF),
                      int(g*0xFFFF),
                      int(b*0xFFFF)
                   )
                self.pixmap.draw_line(gc, x, 13-waluelength, x, 12+waluelength)

                if self.cursor:
                  if self.flat:
                     gc.foreground = self.mod.get_colormap().alloc_color(
                        int(flatcolor2r*0xFFFF),
                        int(flatcolor2g*0xFFFF),
                        int(flatcolor2b*0xFFFF)
                     )
                  else:
                     r,g,b=colorsys.yiq_to_rgb(0.5*darkmulti,c2,c3)
                     gc.foreground = self.mod.get_colormap().alloc_color(
                        int(r*0xFFFF),
                        int(g*0xFFFF),
                        int(b*0xFFFF)
                     )
                  self.pixmap2.draw_line(gc, x, 13-waluelength, x, 12+waluelength)

        #if not self.defaultstyle:
        #    self.pixmap2.draw_drawable(gc,self.pixmap, 0, 0, 0, 0, self.modwidth, 24)
        #    gc.foreground = self.mod.get_colormap().alloc_color(
        #                int(0xCCCC*darkmulti),  int(0xCCCC*darkmulti),  int(0xCCCC*darkmulti))
        #    gc.function=gtk.gdk.AND
        #    self.pixmap2.draw_rectangle(gc, True, 0, 0, self.modwidth, 24)
        #    gc.function=gtk.gdk.COPY
        return b


    #Drawing mood UI---------------------------------------------------------

    def drawMod(self,this,area):
         darkmulti=(1-self.darkness/10)
         self.uptime+=1
         gc = self.brush
         self.bgcolor = self.mod.style.bg[gtk.STATE_NORMAL]
         redf=self.bgcolor.red
         greenf=self.bgcolor.green
         bluef=self.bgcolor.blue
         #logger.info(greenf)
         this=self.mod
         gc.foreground = this.get_colormap().alloc_color(
             0x0000,
             0x0000,
             0x0000
         )
         track = self.player.current
         if self.theme:
                flatcolor1r,flatcolor1g,flatcolor1b=colorsys.yiq_to_rgb(0.5,self.ivalue,self.qvalue)
                flatcolor2r,flatcolor2g,flatcolor2b=colorsys.yiq_to_rgb(0.5*darkmulti,self.ivalue,self.qvalue)
         else:
                flatcolor1r=flatcolor1g=flatcolor1b=0.5
                flatcolor2r=flatcolor2g=flatcolor2b=0.5*darkmulti
         try:

            if not self.get_size()==self.modwidth:
                  self.buff=self.genBuff()
            if (not self.defaultstyle==self.defaultstyle_old or
                 not self.theme==self.theme_old or
                 not self.flat==self.flat_old or
                 not self.color==self.color_old or
                 not self.darkness==self.darkness_old or
                 not self.cursor==self.cursor_old):
                    self.buff=self.genBuff()
            if (self.haveMod):
                 this.props.window.draw_drawable(gc,self.pixmap, 0, 0, 0, 0, self.modwidth, 24)

            else:
              if not self.defaultstyle:
                for i in range(5):
                   gc.foreground = this.get_colormap().alloc_color(
                       int(flatcolor1r*0xFFFF*i/5+redf*((5-float(i))/5)),
                       int(flatcolor1g*0xFFFF*i/5+greenf*((5-float(i))/5)),
                       int(flatcolor1b*0xFFFF*i/5+bluef*((5-float(i))/5))
                   )
                   this.props.window.draw_rectangle(gc, True, 0, 0+i,
                           self.modwidth, 24-i*2)

              if self.modTimer and track.is_local():
                   gc.foreground = this.get_colormap().alloc_color(
                       int(flatcolor2r*0xFFFF),
                       int(flatcolor2g*0xFFFF),
                       int(flatcolor2b*0xFFFF)
                   )
                   this.props.window.draw_rectangle(gc, True,
                             (self.modwidth/10)*(self.uptime%10),
                             5, self.modwidth/10, 14)
              if self.defaultstyle:
                   gc.foreground = this.get_colormap().alloc_color(
                       int(flatcolor1r*0xFFFF),
                       int(flatcolor1g*0xFFFF),
                       int(flatcolor1b*0xFFFF)
                   )
                   this.props.window.draw_rectangle(gc, True,
                           0,12, self.modwidth, 2)

         except:
            for i in range(5):
              gc.foreground = this.get_colormap().alloc_color(
                  int(0xFFFF*i/5),
                  0x0000,
                  0x0000
              )
              this.props.window.draw_rectangle(gc, True, 0, 0+i,
                     self.modwidth, 24-i*2)

            #if track and track.is_local():
            #self.lookformod(track)

            return False

         track = self.player.current
         if not track or not (track.is_local() or \
                 track.get_tag_raw('__length')): return

         if self.modTimer:
            if self.cursor:
                if not self.haveMod:
                   if not self.defaultstyle:
                      for i in range(5):
                          gc.foreground = this.get_colormap().alloc_color(
                              int(flatcolor2r*0xFFFF*i/5+int(redf*((5-float(i))/5))),
                              int(flatcolor2g*0xFFFF*i/5+int(greenf*((5-float(i))/5))),
                              int(flatcolor2b*0xFFFF*i/5+int(bluef*((5-float(i))/5)))
                          )
                          this.props.window.draw_rectangle(gc, True, 0, 0+i,
                                 int(self.curpos*self.modwidth), 24-i*2)
                   else:
                      gc.foreground = this.get_colormap().alloc_color(
                          int(flatcolor2r*0xFFFF),
                          int(flatcolor2g*0xFFFF),
                          int(flatcolor2b*0xFFFF)
                      )
                      this.props.window.draw_rectangle(gc, True,
                           0,12, int(self.curpos*self.modwidth), 2)
                else:
                    this.props.window.draw_drawable(gc,self.pixmap2, 0, 0, 0, 0, int(self.curpos*self.modwidth), 24)


            else:
                gc.foreground  = self.bgcolor;
                gc.line_width=2
                this.props.window.draw_arc(gc, True, int(self.curpos*self.modwidth)-15,
                        -5, 30, 30,  60*64, 60*64)
                gc.foreground = this.get_colormap().alloc_color(
                    0x0000,
                    0x0000,
                    0x0000
                )

                this.props.window.draw_line(gc, int(self.curpos*self.modwidth), 10,
                                      int(self.curpos*self.modwidth)-10, -5)
                this.props.window.draw_line(gc, int(self.curpos*self.modwidth), 10,
                                      int(self.curpos*self.modwidth)+10, -5)

            length = self.player.current.get_tag_raw('__length')
            seconds = self.player.get_time()
            remaining_seconds = length - seconds
            text = ("%d:%02d / %d:%02d" %
                ( seconds // 60, seconds % 60, remaining_seconds // 60,
                remaining_seconds % 60))
            gc.foreground = this.get_colormap().alloc_color(
                0x0000,
                0x0000,
                0x0000
            )
            this.pangolayout.set_text(text)

            this.props.window.draw_layout(gc, int(self.modwidth/2)-35,
                     4, this.pangolayout)
            this.props.window.draw_layout(gc, int(self.modwidth/2)-37,
                     2, this.pangolayout)
            this.props.window.draw_layout(gc, int(self.modwidth/2)-35,
                     2, this.pangolayout)
            this.props.window.draw_layout(gc, int(self.modwidth/2)-37,
                     4, this.pangolayout)
            gc.foreground = this.get_colormap().alloc_color(
                0xFFFF,
                0xFFFF,
                0xFFFF
            )

            this.props.window.draw_layout(gc, int(self.modwidth/2)-36,
                     3, this.pangolayout)


    #seeking-----------------------------------------------------------------

    def modSeekBegin(self,this,event):
        self.seeking = True


    def modSeekEnd(self,this,event):
        self.seeking = False
        track = self.player.current
        if not track or not (track.is_local() or \
                track.get_tag_raw('__length')): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_size()
        value = mouse_x / progress_loc
        if value < 0: value = 0
        if value > 1: value = 1

        self.curpos=value
        length = track.get_tag_raw('__length')
        self.mod.queue_draw_area(0, 0, progress_loc, 24)
        #redrawMod(self)

        seconds = float(value * length)
        self.player.seek(seconds)

    def modSeekMotionNotify(self,this,  event):
        if self.seeking:
            track = self.player.current
            if not track or not (track.is_local() or \
                    track.get_tag_raw('__length')): return

            mouse_x, mouse_y = event.get_coords()
            progress_loc = self.get_size()
            value = mouse_x / progress_loc
            if value < 0: value = 0
            if value > 1: value = 1


            self.curpos=value
            self.mod.queue_draw_area(0, 0, progress_loc, 24)


    #------------------------------------------------------------------------


def _enable_main_moodbar(exaile):
    global ExaileModbar
    ExaileModbar = ExModbar(
        player=player.PLAYER,
        progress_bar=exaile.gui.main.progress_bar
    )

    ExaileModbar.readMod('')
    ExaileModbar.setupUi()
    ExaileModbar.add_callbacks()


def _disable_main_moodbar():
    global ExaileModbar
    ExaileModbar.changeModToBar()
    ExaileModbar.remove_callbacks()
    ExaileModbar.destroy()
    ExaileModbar = None


def enable(exaile):
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
    _enable_main_moodbar(exaile)


def disable(exaile):
    _disable_main_moodbar()


def get_preferences_pane():
    return moodbarprefs

#have errors from time to time:
#python: ../../src/xcb_lock.c:77: _XGetXCBBuffer: Assertion `((int) ((xcb_req) - (dpy->request)) >= 0)' failed.

#exaile.py: Fatal IO error 11 (Resource temporarily unavailable) on X server :0.0.

#Xlib: sequence lost (0xe0000 > 0xd4add) in reply type 0x0!
#python: ../../src/xcb_io.c:176: process_responses: Assertion `!(req && current_request && !(((long) (req->sequence) - (long) (current_request)) <= 0))' failed.

#0.0.4 haven't errors
