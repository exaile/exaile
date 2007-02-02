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

import mutagen.m4a

def get_tag(f, name):
    name = '\xa9%s' % name
    if not f.has_key(name):
        return ''
    else: return f[name]

def set_tag(f, name, value):
    name = "\xa9%s" % name
    f[name] = value

def fill_tag_from_path(tr):
    f = mutagen.m4a.M4A(tr.loc)
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
    f = mutagen.m4a.M4A(self.loc)

    try:
        f['trkn'] = (int(self.track), f['trkn'][1])
        f['disk'] = (int(self.disc_id), f['disk'][1])
    except:
        xlmisc.log_exception()

    set_tag(f, 'nam', self.title)
    set_tag(f, 'ART', self.artist)
    set_tag(f, 'alb', self.album)
    set_tag(f, 'gen', self.genre)

    f.save()
