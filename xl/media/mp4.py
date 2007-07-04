# encoding: utf-8

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

from xl import xlmisc

try:
    from mutagen.mp4 import MP4 as MP4
except ImportError:
    from mutagen.m4a import M4A as MP4

TYPE = 'aac'

def get_tag(f, name):
    name = '\xa9%s' % name
    if not f.has_key(name):
        return ''
    else: return f[name][0]

def set_tag(f, name, value):
    name = "\xa9%s" % name
    f[name] = value

def fill_tag_from_path(tr):
    f = MP4(tr.io_loc)
    tr.length = f.info.length
    tr.bitrate = f.info.bitrate
    
    tr.title = get_tag(f, 'nam')
    tr.artist = get_tag(f, 'ART')
    tr.album = get_tag(f, 'alb')
    tr.genre = get_tag(f, 'gen')
    try:
        tr.track = f['trkn'][0]
    except:
        tr.track = -1

    try:
        tr.disc_id = f['disk'][0]
    except:
        tr.disc_id = -1

    tr.year = get_tag(f, 'day')

def write_tag(tr):
    f = MP4(tr.io_loc)

    try:
        f['trkn'] = (int(tr.track), f['trkn'][1])
        f['disk'] = (int(tr.disc_id), f['disk'][1])
    except:
        xlmisc.log_exception()

    set_tag(f, 'nam', tr.title)
    set_tag(f, 'ART', tr.artist)
    set_tag(f, 'alb', tr.album)
    set_tag(f, 'gen', tr.genre)

    f.save()
