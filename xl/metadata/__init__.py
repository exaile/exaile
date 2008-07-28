# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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


import os
from xl import common
import mutagen
from _base import *

import flac, mp3, mp4, mpc, ogg, tta, wv

formats = {
        'aac'   : mp4.MP4Format,
        'ac3'   : None,
        'flac'  : flac.FlacFormat,
        'm4a'   : mp4.MP4Format,
        'mp2'   : mp3.MP3Format,
        'mp3'   : mp3.MP3Format,
        'mp4'   : mp4.MP4Format,
        'mod'   : None,
        'oga'   : ogg.OggFormat,
        'ogg'   : ogg.OggFormat,
        's3m'   : None,
        'tta'   : tta.TTAFormat,
        'wav'   : None,
        'wv'    : wv.WavpackFormat,
        }

# pass get_loc_for_io() to this.
def getFormat(loc):
    """
        get a Format object appropriate for the file at loc.
        if no suitable object can be found, a default object that
        defines title from the filename is used instead.
    """
    (path, ext) = os.path.splitext(loc.lower())
    ext = ext[1:] # remove the pesky .

    try:
        format = formats[ext]
    except KeyError:
        return None # not supported

    if format is None:
        format = BaseFormat

    return format(loc)

# vim: et sts=4 sw=4

