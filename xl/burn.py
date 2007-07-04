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

import time, subprocess

from urllib import pathname2url

def launch_burner(program, songs):
    """
        Launches a burner with the specified songs as options.
    """
    if not songs or not program:
        return 0

    # serpentine and brasero can be launched very similarly, k3b needs
    # special handling
    if program == 'serpentine':
        args = ['serpentine', '-o']
    if program == 'brasero':
        args = ['brasero', '-a']
        songs.reverse()
    if program == 'k3b':
        launch_k3b(songs)
        return

    ar = ['file://%s' % (pathname2url(song.io_loc),) \
            for song in songs if not song.type == 'stream']
    if not ar: return
    args.extend(ar)
    subprocess.Popen(args, stdout=-1,
        stderr=-1)

def check_burn_progs():
    """
        Function to check which of the supported burning programs
        are present.
    """

    # this function get called quite often, perhaps just check it once
    # when the program starts and then use the results throughout the
    # whole program?
    found = [program for program in ('serpentine', 'brasero', 'k3b') \
            if subprocess.call(['which', program], stdout=-1) == 0]
    
    return found

def launch_k3b(songs):
    """
        Start k3b and create an audio project using (command line) DCOP
    """
    subprocess.call(["k3b", "--audiocd"])

    time.sleep(5) # k3b crashes if it's starting up and we query dcop right 
                  # away (stupid qt programs :P)

    # equivalent to the shell's  PROJECT=`dcop k3b K3bInterface currentProject`
    project = subprocess.Popen(['dcop', 'k3b', 'K3bInterface', 'currentProject'], \
            stdout=subprocess.PIPE).communicate()[0]
    project = project.strip()

    # addUrls takes a list of the form '[ song1 song2 ... ]'
    args = ['dcop', project, 'addUrls', '[']
    args.extend([song.io_loc for song in songs])
    args.append(']')
    subprocess.call(args)
