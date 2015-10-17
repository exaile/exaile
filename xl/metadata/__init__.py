# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.


import os
import sys
from gi.repository import Gio

from xl.metadata._base import BaseFormat, NotWritable, NotReadable
import urlparse

from xl.metadata import (ape, asf, flac, mka, mod, mp3, mp4, mpc, ogg, sid, speex,
        tta, wav, wv)

#: dictionary mapping extensions to Format classes.
formats = {
        '669'   : mod.ModFormat,
        'ac3'   : None,
        'aif'   : wav.WavFormat,
        'aiff'  : wav.WavFormat,
        'ape'   : ape.MonkeysFormat,
        'amf'   : mod.ModFormat,
        'asf'   : asf.AsfFormat,
        'au'    : wav.WavFormat,
        'dsm'   : mod.ModFormat,
        'far'   : mod.ModFormat,
        'flac'  : flac.FlacFormat,
        'it'    : mod.ModFormat,
        'm4a'   : mp4.MP4Format,
        'med'   : mod.ModFormat,
        'mka'   : mka.MkaFormat,
        'mp2'   : mp3.MP3Format,
        'mp3'   : mp3.MP3Format,
        'mp4'   : mp4.MP4Format,
        'mpc'   : mpc.MpcFormat,
        'mid'   : None,
        'midi'  : None,
        'mod'   : mod.ModFormat,
        'mtm'   : mod.ModFormat,
        'oga'   : ogg.OggFormat,
        'ogg'   : ogg.OggFormat,
        'ogx'   : ogg.OggFormat,
        'okt'   : mod.ModFormat,
        'opus'  : ogg.OggOpusFormat,
        'ra'    : None,
        'ram'   : None,
        's3m'   : mod.ModFormat,
        'sid'   : sid.SidFormat,
        'shn'   : None,
        'snd'   : wav.WavFormat,
        'spc'   : None,
        'spx'   : speex.SpeexFormat,
        'stm'   : mod.ModFormat,
        'tta'   : tta.TTAFormat,
        'ult'   : mod.ModFormat,
        'wav'   : wav.WavFormat,
        'wma'   : asf.AsfFormat,
        'wv'    : wv.WavpackFormat,
        'xm'    : mod.ModFormat,
        }

# pass get_loc_for_io() to this.
def get_format(loc):
    """
        get a Format object appropriate for the file at loc.
        if no suitable object can be found, None is returned.

        :param loc: The location to read from as a Gio URI
    """
    loc = Gio.File.new_for_uri(loc).get_path()
    if not loc:
        return None
        
    # XXX: The path that we get from GIO is, for some reason, in UTF-8.
    # Bug? Intended? No idea.
    
    # Oddly enough, if you have a non-utf8 compatible filename (such as
    # a file from windows), then it will just return that string without 
    # converting it (but in a form that os.path will handle). Go figure.
    
    try:
        loc = loc.decode('utf-8')
    except UnicodeDecodeError:
        pass
            
    ext = os.path.splitext(loc)[1]
    ext = ext[1:] # remove the pesky .
    ext = ext.lower()

    try:
        formatclass = formats[ext]
    except KeyError:
        return None # not supported

    if formatclass is None:
        formatclass = BaseFormat

    try:
        return formatclass(loc)
    except NotReadable:
        return None


# vim: et sts=4 sw=4

