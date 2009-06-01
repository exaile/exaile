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

moodbar=''
buff=''
brush=1
modwidth=0
curpos=0
modTimer=0
moodsDir=''
haveMod=0
playingTrack=''
exaile1=1
runed=False
pid=0
"""
def on_play(type, player, track):
    title = " / ".join(track['title'] or _("Unknown"))
    artist = " / ".join(track['artist'] or "")
    album = " / ".join(track['album'] or "")
    summary = cgi.escape(title)
"""

def genBuff(moodbar,width):
    global modwidth
    modwidth=width
    b=''
    hh=[0.4,0.1,0.4,0.5,0.6,0.7,0.8,1,1,1,0.9,0.85,0.8,0.75,0.7,0.63,0.55,0.47,0.39,0.3,0.2,0,0.6,0.2]
    for h in range(24):
       for x in range(width):
          for i in range(3):
             b=b+chr(int(ord(moodbar[int(x*1000/width)*3+i])*hh[h]))
    return b

def redrawMod(self):
    global moodbar
    global modwidth
    global curpos
    global buff
    sizes=self.get_allocation()
    global brush
    res=True
    brush.function=gtk.gdk.COPY
    try:
       if not sizes.width==modwidth : buff=genBuff(moodbar, sizes.width)
       self.window.draw_rgb_image(brush, 0, 0, modwidth, 24, gtk.gdk.RGB_DITHER_NONE, buff, modwidth*3)
    except:
       global haveMod 
       self.window.draw_rectangle(brush, True, 0, 0, modwidth, 24)
       haveMod=False  
       res=False   
    brush.line_style=gtk.gdk.LINE_SOLID
    brush.line_width=2
    brush.function=gtk.gdk.INVERT
 
    
    self.window.draw_arc(brush, True, int(curpos*modwidth)-15, -5, 30, 30,  60*64, 60*64)
    return res

def drawMod(self, area):
    redrawMod(self)
    


def readMod(moodLoc):
   
  global moodbar
  try:  
    if moodLoc=='':
       moodbar=''
       for i in range(3000): moodbar=moodbar+chr(255)
       return True 
    else:
       f=open(moodLoc,'rb')     
       moodbar=''
       for i in range(3000):
         r=f.read(1)
         moodbar=moodbar+r
       f.close()
       return True  
  except: return False 

"""
####################################################3      replace bar to mod                
"""

def changeBarToMod(exaile):
    pr=exaile.gui.main.progress_bar
    
    place=pr.bar.get_parent()
    #print(place)
    pr.mod = gtk.DrawingArea()

    #mod = gtk.Button()
    pr.mod.set_size_request(-1, 24)
    place.pack_start(pr.mod, False, True, 0)
    place.reorder_child(pr.mod, 2)
    pr.mod.realize()
    pr.bar.hide()
    pr.mod.show()

def changeModToBar(exaile):
    pr=exaile.gui.main.progress_bar
    #pr.mod.hide()
    if hasattr(pr, 'mod'):
        pr.mod.destroy()

def showMod(exaile):
    pr=exaile.gui.main.progress_bar
    pr.bar.hide()
    if hasattr(pr, 'mod'):
        pr.mod.show()
    print('showing modbar')  

def hideMod(exaile):
    pr=exaile.gui.main.progress_bar
    if hasattr(pr, 'mod'):
        pr.mod.hide()
    pr.bar.show() 
    print('hideing modbar') 
"""
##########################################################3    seeking               
"""
def modSeekBegin(self, widget):
    self.seeking = True
    print ('seek begin')


def modSeekEnd(self,  event):
        global exaile1
        self.seeking = False
        track = exaile1.player.current
        if not track or not track.is_local(): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_allocation()
        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1
        
        global curpos         
        curpos=value
        length = track.get_duration()
        redrawMod(self)

        seconds = float(value * length)
        exaile1.player.seek(seconds)

          

def modSeekMotionNotify(self,  event):
    if self.seeking:
        global exaile1

        track = exaile1.player.current
        if not track or not track.is_local(): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_allocation()
        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1
        
        global curpos         
        curpos=value
        
        redrawMod(self)
"""
##########################################################3    play / start               
"""

def play_start(type, player, track):
    global modTimer
    global haveMod
    global playingTrack
    global modsDir
    global exaile1
    global modwidth
    global runed
    global pid 
##run gui
    if not runed:
          runed=True;
          changeBarToMod(exaile1)

          pr=exaile1.gui.main.progress_bar
          pr.mod.seeking=False
          pr.mod.connect("expose-event", drawMod)
          pr.mod.add_events(gtk.gdk.BUTTON_PRESS_MASK) 
          pr.mod.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
          pr.mod.add_events(gtk.gdk.POINTER_MOTION_MASK)
          pr.mod.connect("button-press-event", modSeekBegin) 
          pr.mod.connect("button-release-event", modSeekEnd)
          pr.mod.connect("motion-notify-event", modSeekMotionNotify) 

          global brush 
          brush = pr.mod.window.new_gc()
##end of run gui
    
    haveMod=False
    playingTrack=str(track.get_loc())
    #playingTrack=playingTrack.replace("\'","\\\'")
    #playingTrack=playingTrack.replace("\"","\\\"")
    modLoc=moodsDir+'/'+ playingTrack.replace('/','-')+".mood"
    modLoc=modLoc.replace("'",'')
    if os.access(modLoc, 0):
         modwidth=0
         showMod(exaile1)   
         haveMod=True
         readMod(modLoc) 
         updateplayerpos() 
           
    else: 
         comand='"'+playingTrack+'" -o "'+modLoc+'"'
         print ('SUSTEM: /usr/bin/moodbar '+comand)
         
         hideMod(exaile1)
         pid = subprocess.Popen(['/usr/bin/moodbar',playingTrack, '-o',modLoc])


    modTimer = gobject.timeout_add(1000, updateMod)

def play_end (type, player, track):
    global modTimer
    if modTimer: gobject.source_remove(modTimer)
    modTimer = None

def updateMod():
    global haveMod
    global playingTrack
    global modsDir
    global exaile1
    global modwidth
    global modTimer
    global pid
    if haveMod: 
       updateplayerpos()
       
    else:
       
       modLoc=moodsDir+'/'+ playingTrack.replace('/','-')+".mood"
       modLoc=modLoc.replace("'",'')
       print ("haven't Mod")
       if readMod(modLoc):
           
           print ("find!!")  
           modwidth=0
           haveMod=True
           
           if updateplayerpos():
              showMod(exaile1)
    
    modTimer = gobject.timeout_add(1000, updateMod)

def updateplayerpos():
    global exaile1
    global curpos  
    curpos=exaile1.player.get_progress()
    #eprint (curpos)
    return redrawMod(exaile1.gui.main.progress_bar.mod)


    """
##########################################################3    enable plugin              
    """

def enable(exaile):
   
    global exaile1
    exaile1 =exaile

    global moodsDir
    moodsDir=os.path.join(xdg.get_config_dir(), "moods")
#    moodsDir=exaile.settings.loc.replace("settings.ini","")+'moods'
    if not os.access(moodsDir, 0): os.mkdir(moodsDir)
    readMod('')
    global runed

    try:
        subprocess.call(['moodbar', '--help'], stdout=-1, stderr=-1)
    except OSError:
        raise NotImplementedError('Moodbar executable is not available.')
        return False

    if runed:
          runed=True;
          changeBarToMod(exaile)

          pr=exaile1.gui.main.progress_bar
          pr.mod.seeking=False
          pr.mod.connect("expose-event", drawMod)
          pr.mod.add_events(gtk.gdk.BUTTON_PRESS_MASK) 
          pr.mod.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
          pr.mod.add_events(gtk.gdk.POINTER_MOTION_MASK)
          pr.mod.connect("button-press-event", modSeekBegin) 
          pr.mod.connect("button-release-event", modSeekEnd)
          pr.mod.connect("motion-notify-event", modSeekMotionNotify) 

          global modTimer  
          modTimer = gobject.timeout_add(1000, updateMod)         


    event.add_callback(play_start, 'playback_start')
    event.add_callback(play_end, 'playback_end')

def disable(exaile):
    hideMod(exaile)
    changeModToBar(exaile)
    event.remove_callback(play_start, 'playback_start')
    event.remove_callback(play_end, 'playback_end')
    global modTimer
    if modTimer: gobject.source_remove(modTimer)
    modTimer = None


