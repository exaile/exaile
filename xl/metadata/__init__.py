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
import gio

from _base import BaseFormat, NotWritable, NotReadable
import urlparse

import ape, asf, flac, mod, mp3, mp4, mpc, ogg, sid, speex, tta, wav, wv

# lossy:    aac (in m4a), ac3, mp2, mp3, musepack, speex, vorbis, wma
# lossless: aiff, alac (in m4a), ape, flac, tta, wav, wavpack
# chip:     669, amf, dsm, far, it, med, mod, mtm, okt, s3m, spc, stm, ult, xm
# other:    au
# tags not read:  midi, real, shorten (can we fix these?)

#: dictionary mapping extensions to Format classes.
formats = {
        '669'   : mod.ModFormat,
        'ac3'   : None,
        'aif'   : wav.WavFormat,
        'aiff'  : wav.WavFormat,
        'ape'   : ape.MonkeysFormat,
        'amf'   : mod.ModFormat,
        'au'    : wav.WavFormat,
        'dsm'   : mod.ModFormat,
        'far'   : mod.ModFormat,
        'flac'  : flac.FlacFormat,
        'it'    : mod.ModFormat,
        'm4a'   : mp4.MP4Format,
        'med'   : mod.ModFormat,
        'mka'   : None,
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

# pass get_loc_for_io() to this.
def get_format(loc):
    """
        get a Format object appropriate for the file at loc.
        if no suitable object can be found, None is returned.

        :param loc: The location to read from. can be any gio-parseable
            path or uri.
    """
    loc = gio.File(loc).get_path()
    if not loc:
        return None
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


# vim: et sts=4 sw=4

