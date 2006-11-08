#!/usr/bin/env python

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

import gtk, plugins, time, gobject

PLUGIN_NAME = "Alarm Clock"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = r"""Plays music at a specific time.\n\nNote that when the 
specified time arrives, Exaile will just act like you pressed the play button, 
so be sure you have the music you want to hear in your playlist"""

PLUGIN_ENABLED = False
PLUGIN = None
SETTINGS = None
TIMER_ID = None
RANG = dict()

def configure(exaile):
    """
        Configures the time to ring
    """
    alarm_time = exaile.settings.get("%s_alarm_time" % plugins.name(__file__), "12:30")
    (hours, minutes) = alarm_time.split(":")

    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    hbox = gtk.HBox()
    hbox.pack_start(gtk.Label("Alarm Time:  "), False, False)
    hour = gtk.SpinButton(gtk.Adjustment(1, step_incr=1))
    hour.set_range(0, 23)
    hour.set_value(int(hours))
    hbox.pack_start(hour, False, False)
    hbox.pack_start(gtk.Label(":"), False, False)
    minute = gtk.SpinButton(gtk.Adjustment(1, step_incr=1))
    minute.set_range(0, 59)
    minute.set_value(int(minutes))
    hbox.pack_start(minute, False, False)
    dialog.child.pack_start(hbox, False, False)

    dialog.show_all()
    result = dialog.run()
    dialog.hide()

    if result == gtk.RESPONSE_OK:
        hour = hour.get_value()
        minute = minute.get_value()
        exaile.settings["%s_alarm_time" % 
            plugins.name(__file__)] = "%02d:%02d" % (hour,
            minute)

def timeout_cb():
    """
        Called every two seconds.  If the plugin is not enabled, it does
        nothing.  If the current time matches the time specified, it starts
        playing
    """
    if not PLUGIN_ENABLED: return True
    alarm_time = SETTINGS.get("%s_alarm_time" % plugins.name(__file__), "")
    if not alarm_time: return True

    current = time.strftime("%H:%M", time.localtime())
    if alarm_time == current:
        check = time.strftime("%m %d %Y %H:%M")
        if RANG.has_key(check): return True
        track = EXAILE.current_track
        if track and (track.is_playing() or track.is_paused()): return True
        EXAILE.play()

        RANG[check] = True

    return True

def initialize(exaile):
    """
        Starts the timer
    """
    global TIMER_ID, SETTINGS, EXAILE
    EXAILE = exaile
    SETTINGS = exaile.settings
    TIMER_ID = gobject.timeout_add(2000, timeout_cb)
    return True

def destroy():
    """
        Stops the timer for this plugin
    """
    if TIMER_ID:
        gobject.source_remove(TIMER_ID)

icon_data = ["16 16 168 2",
"  	c None",
". 	c #666864",
"+ 	c #6E716C",
"@ 	c #6D706B",
"# 	c #6B6D69",
"$ 	c #646661",
"% 	c #6B6D68",
"& 	c #888B86",
"* 	c #838783",
"= 	c #747976",
"- 	c #6C716E",
"; 	c #6E716E",
"> 	c #737773",
", 	c #777A75",
"' 	c #626460",
") 	c #6D706A",
"! 	c #999D98",
"~ 	c #727774",
"{ 	c #919692",
"] 	c #B1B6B0",
"^ 	c #B2B7AF",
"/ 	c #B2B7B0",
"( 	c #9CA19C",
"_ 	c #686D6B",
": 	c #757974",
"< 	c #616561",
"[ 	c #696C66",
"} 	c #989B96",
"| 	c #797E7B",
"1 	c #B3B8B1",
"2 	c #DADDD6",
"3 	c #E5E8E3",
"4 	c #E9EBE7",
"5 	c #E7E9E5",
"6 	c #DFE2DD",
"7 	c #CACEC7",
"8 	c #717573",
"9 	c #737672",
"0 	c #575A58",
"a 	c #848782",
"b 	c #767A78",
"c 	c #B7BCB5",
"d 	c #E1E4DE",
"e 	c #EAECE8",
"f 	c #EBEDEA",
"g 	c #ECEEEB",
"h 	c #E6E8E5",
"i 	c #B0B2AE",
"j 	c #BCC0BA",
"k 	c #797C79",
"l 	c #6B6F6B",
"m 	c #444746",
"n 	c #5A5E5B",
"o 	c #7C807C",
"p 	c #9A9F9B",
"q 	c #E0E3DD",
"r 	c #EBEDE9",
"s 	c #EAECE9",
"t 	c #E5E6E3",
"u 	c #EEF0ED",
"v 	c #D5D6D4",
"w 	c #888887",
"x 	c #BCBCBB",
"y 	c #E7EAE5",
"z 	c #B3B7B2",
"A 	c #6A6D6A",
"B 	c #4A4D4C",
"C 	c #5E625F",
"D 	c #6E7270",
"E 	c #BEC2BD",
"F 	c #E8EAE6",
"G 	c #EDEFEB",
"H 	c #E4E6E3",
"I 	c #A1A2A0",
"J 	c #A5A5A4",
"K 	c #5F5F5E",
"L 	c #969795",
"M 	c #EAEBE9",
"N 	c #EFF1EE",
"O 	c #E0E2DF",
"P 	c #656966",
"Q 	c #535755",
"R 	c #666B68",
"S 	c #C4C7C3",
"T 	c #ECEEEA",
"U 	c #EFF0ED",
"V 	c #EFF0EE",
"W 	c #A1A1A0",
"X 	c #AFAFAF",
"Y 	c #616161",
"Z 	c #E4E5E3",
"` 	c #F4F5F3",
" .	c #F3F4F2",
"..	c #626663",
"+.	c #525654",
"@.	c #525756",
"#.	c #646866",
"$.	c #C8CAC7",
"%.	c #F1F2EF",
"&.	c #ECEDEB",
"*.	c #949594",
"=.	c #6D6D6D",
"-.	c #5A5A5A",
";.	c #D4D5D4",
">.	c #F7F8F6",
",.	c #F5F6F4",
"'.	c #646765",
").	c #4B504E",
"!.	c #474B4B",
"~.	c #B1B4B1",
"{.	c #F1F2F0",
"].	c #EBECEB",
"^.	c #CFD0CF",
"/.	c #E8E9E8",
"(.	c #C2C2C2",
"_.	c #B8B8B7",
":.	c #F2F2F1",
"<.	c #F6F7F5",
"[.	c #D2D4D2",
"}.	c #626662",
"|.	c #3F4443",
"1.	c #6F7371",
"2.	c #E7E9E7",
"3.	c #F2F3F1",
"4.	c #F5F6F5",
"5.	c #FAFAF9",
"6.	c #EDEEED",
"7.	c #F6F7F6",
"8.	c #939593",
"9.	c #585B58",
"0.	c #343939",
"a.	c #434847",
"b.	c #636763",
"c.	c #858886",
"d.	c #E2E3E2",
"e.	c #F7F8F7",
"f.	c #F9F9F9",
"g.	c #FBFBFB",
"h.	c #FCFCFC",
"i.	c #F4F5F4",
"j.	c #A2A4A3",
"k.	c #5C5F5B",
"l.	c #414544",
"m.	c #474C4B",
"n.	c #606461",
"o.	c #797C7B",
"p.	c #C6C7C7",
"q.	c #F3F4F3",
"r.	c #F7F7F7",
"s.	c #D8D9D8",
"t.	c #929492",
"u.	c #5A5D5A",
"v.	c #454948",
"w.	c #3D4242",
"x.	c #525553",
"y.	c #5C5F5C",
"z.	c #606361",
"A.	c #5B5F5C",
"B.	c #5C5F5D",
"C.	c #505350",
"D.	c #3D4140",
"E.	c #2F3437",
"F.	c #383C3D",
"G.	c #444847",
"H.	c #464A48",
"I.	c #424745",
"J.	c #393D3C",
"K.	c #313537",
"          . + @ # $             ",
"      % & * = - ; > , '         ",
"    ) ! ~ { ] ^ / ( _ : <       ",
"  [ } | 1 2 3 4 5 6 7 8 9 0     ",
"  a b c d e f g g h i j k l m   ",
"n o p q r s t u v w x y z A B   ",
"C D E F G H I J K L M N O P Q   ",
"n R S T U V W X Y Z `  .e ..+.  ",
"@.#.$.G %.&.*.=.-.;.>.,.g '.).  ",
"!.P ~.V {.].^./.(._.:.<.[.}.|.  ",
"  C 1.2.3.` 4.5.5.6.7.:.8.9.0.  ",
"  a.b.c.d.7.e.f.g.h.i.j.k.l.    ",
"    m.n.o.p.q.g.r.s.t.u.v.      ",
"      w.x.y.z.A.z.B.C.D.        ",
"        E.F.G.H.I.J.K.          ",
"                                "]
PLUGIN_ICON = gtk.gdk.pixbuf_new_from_xpm_data(icon_data)
