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

TAG_TRANSLATION = {
    '\xa9nam':      'title',
    '\xa9ART':      'artist',
    '\xa9alb':      'album',
    '\xa9gen':      'genre',
    '\xa9day':      'date',
    'trkn':         'tracknumber',
    'disk':         'discnumber',
    'cprt':         'copyright'
}

def get_tag(f, name):
    if not f.has_key(name):
        return [] 
    elif name in ['trkn', 'disk']: 
        ret = []
        for value in f[name]:
            ret.append("%d/%d" % (value[0], value[1]))
        return ret
    else: return [t for t in f[name]]

def set_tag(f, name, value):
    if type(value) is not list: value = [value]
    if name in ['trkn', 'disk']:
        try:
            f[name] = []
            for val in value:
                tmp = map(int, val.split('/'))
                f[name].append(tuple(tmp))
        except:
            xlmisc.log_exception()
    else:
        f[name] = value

def can_change(tag):
    return tag in TAG_TRANSLATION.values()

def is_multi():
    return True

def fill_tag_from_path(tr):
    try:
        f = MP4(tr.io_loc)
    except:
        xlmisc.log("Couldn't read tags from file: " + tr.loc)
        return

    tr.length = f.info.length
    tr.bitrate = f.info.bitrate
    
    for mp4_tag, tag in TAG_TRANSLATION.iteritems():
        try:
            tr.tags[tag] = get_tag(f, mp4_tag)
        except:
            tr.tags[tag] = [] 

def write_tag(tr):
    f = MP4(tr.io_loc)

    for mp4_tag, tag in TAG_TRANSLATION.iteritems():
        if tr.tags[tag]:
            set_tag(f, mp4_tag, tr.tags[tag])

    f.save()
