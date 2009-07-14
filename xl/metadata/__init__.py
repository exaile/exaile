# Copyright (C) 2008-2009 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os

# do this so formats can inherit from stuff in _base
from _base import *
import urlparse

import asf, flac, mod, mp3, mp4, mpc, ogg, sid, speex, tta, wav, wv

# lossy:    aac (in m4a), mp2, mp3, musepack, speex, vorbis, wma
# lossless: alac (in m4a), flac, tta, wav, wavpack
# chip:     669, amf, dsm, far, it, med, mod, mtm, okt, s3m, spc, stm, ult, xm
# other:    ac3, aiff, au, midi
# tags not read:  real, shorten (can we fix these?)
formats = {
        '669'   : mod.ModFormat,
        'ac3'   : None,
        'aif'   : wav.WavFormat,
        'aiff'  : wav.WavFormat,
        'amf'   : mod.ModFormat,
        'au'    : wav.WavFormat, 
        'dsm'   : mod.ModFormat,
        'far'   : mod.ModFormat,
        'flac'  : flac.FlacFormat,
        'it'    : mod.ModFormat,
        'm4a'   : mp4.MP4Format,
        'med'   : mod.ModFormat,
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
        'okt'   : mod.ModFormat,
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

SUPPORTED_MEDIA = ['.' + ext for ext in formats.iterkeys()]

# pass get_loc_for_io() to this.
def get_format(loc):
    """
        get a Format object appropriate for the file at loc.
        if no suitable object can be found, a default object that
        defines title from the filename is used instead.
    """
    (path, ext) = os.path.splitext(loc.lower())
    ext = ext[1:] # remove the pesky .
    ext = ext.lower()

    try:
        format = formats[ext]
    except KeyError:
        return None # not supported

    if format is None:
        format = BaseFormat

    try:
        return format(loc)
    except NotReadable:
        return None
    except:
        common.log_exception(logger)
        return None

#FIXME: give this a better name. and a docstring.
def j(value):
    if not value: return value
    if hasattr(value, '__iter__') and type(value) not in (str, unicode):
        try:
            return u'\u0000'.join(value)
        except TypeError:
            return value
    else:
        return value

# vim: et sts=4 sw=4

