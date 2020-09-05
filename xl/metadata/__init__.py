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
from typing import Optional
import urllib.parse

from gi.repository import Gio

from xl.metadata._base import BaseFormat, CoverImage, NotWritable, NotReadable

from xl.metadata import (
    aiff,
    ape,
    asf,
    flac,
    mka,
    mod,
    mp3,
    mp4,
    mpc,
    ogg,
    sid,
    speex,
    tta,
    wav,
    wv,
)

#: dictionary mapping extensions to Format classes.
formats = {
    # fmt: off
    '669'   : mod.ModFormat,
    'aac'   : mp4.MP4Format,
    'ac3'   : None,
    'aif'   : aiff.AIFFFormat,
    'aifc'  : aiff.AIFFFormat,
    'aiff'  : aiff.AIFFFormat,
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
    # fmt: on
}


# Dummy format class to use with unsupported format instead of directly
# instantiating BaseFormat, which may cause issues with tag mapping
# initialization in subclasses (see issue #539)
class DummyFormat(BaseFormat):
    pass


def get_format(loc: str) -> Optional[BaseFormat]:
    """
    get a Format object appropriate for the file at loc.
    if no suitable object can be found, None is returned.

    :param loc: The location to read from as a Gio URI
        (from Track.get_loc_for_io())
    """
    loc = Gio.File.new_for_uri(loc).get_path()
    if not loc:
        return None

    ext = os.path.splitext(loc)[1]
    ext = ext[1:]  # remove the pesky .
    ext = ext.lower()

    try:
        formatclass = formats[ext]
    except KeyError:
        return None  # not supported

    if formatclass is None:
        formatclass = DummyFormat

    try:
        return formatclass(loc)
    except NotReadable:
        return None


# vim: et sts=4 sw=4
