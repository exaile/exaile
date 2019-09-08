# EBML/Matroska parser
# Copyright (C) 2010, 2015  Johannes Sasongko <sasongko@gmail.com>
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


# This code is heavily based on public domain code by "Omion" (from the
# Hydrogenaudio forums), as obtained from Matroska's Subversion repository at
# revision 858 (2004-10-03), under "/trunk/Perl.Parser/MatroskaParser.pm".


import sys
from struct import pack, unpack
from warnings import warn

SINT, UINT, FLOAT, STRING, UTF8, DATE, MASTER, BINARY = range(8)


class EbmlException(Exception):
    pass


class EbmlWarning(Warning):
    pass


class BinaryData(bytes):
    def __repr__(self):
        return "<BinaryData>"


def bchr(n):
    """chr() that always returns bytes in Python 2 and 3"""
    return pack('B', n)


class Ebml:
    """EBML parser.

    Usage: Ebml(location, tags).parse()
    where `tags` is a dictionary of the form {id: (name, type)}.
    """

    ## Constructor and destructor

    def __init__(self, location, tags):
        self.tags = tags
        self.open(location)

    def __del__(self):
        self.close()

    ## File access.
    ## These can be overridden to provide network support.

    def open(self, location):
        """Open a location and set self.size."""
        self.file = f = open(location, 'rb')
        f = self.file
        f.seek(0, 2)
        self.size = f.tell()
        f.seek(0, 0)

    def seek(self, offset, mode):
        self.file.seek(offset, mode)

    def tell(self):
        return self.file.tell()

    def read(self, length):
        return self.file.read(length)

    def close(self):
        self.file.close()

    ## Element reading

    def readID(self):
        b = self.read(1)
        b1 = ord(b)
        if b1 & 0b10000000:  # 1 byte
            return b
        elif b1 & 0b01000000:  # 2 bytes
            return unpack(">H", b + self.read(1))[0]
        elif b1 & 0b00100000:  # 3 bytes
            return unpack(">L", b"\0" + b + self.read(2))[0]
        elif b1 & 0b00010000:  # 4 bytes
            return unpack(">L", b + self.read(3))[0]
        else:
            raise EbmlException("invalid element ID (leading byte 0x%02X)" % b1)

    def readSize(self):
        b1 = ord(self.read(1))
        if b1 & 0b10000000:  # 1 byte
            return b1 & 0b01111111
        elif b1 & 0b01000000:  # 2 bytes
            return unpack(">H", bchr(b1 & 0b00111111) + self.read(1))[0]
        elif b1 & 0b00100000:  # 3 bytes
            return unpack(">L", b"\0" + bchr(b1 & 0b00011111) + self.read(2))[0]
        elif b1 & 0b00010000:  # 4 bytes
            return unpack(">L", bchr(b1 & 0b00001111) + self.read(3))[0]
        elif b1 & 0x00001000:  # 5 bytes
            return unpack(">Q", b"\0\0\0" + bchr(b1 & 0b00000111) + self.read(4))[0]
        elif b1 & 0b00000100:  # 6 bytes
            return unpack(">Q", b"\0\0" + bchr(b1 & 0b0000011) + self.read(5))[0]
        elif b1 & 0b00000010:  # 7 bytes
            return unpack(">Q", b"\0" + bchr(b1 & 0b00000001) + self.read(6))[0]
        elif b1 & 0b00000001:  # 8 bytes
            return unpack(">Q", b"\0" + self.read(7))[0]
        else:
            assert b1 == 0
            raise EbmlException("undefined element size")

    def readInteger(self, length, signed):
        if length == 1:
            value = ord(self.read(1))
        elif length == 2:
            value = unpack(">H", self.read(2))[0]
        elif length == 3:
            value = unpack(">L", b"\0" + self.read(3))[0]
        elif length == 4:
            value = unpack(">L", self.read(4))[0]
        elif length == 5:
            value = unpack(">Q", b"\0\0\0" + self.read(5))[0]
        elif length == 6:
            value = unpack(">Q", b"\0\0" + self.read(6))[0]
        elif length == 7:
            value = unpack(">Q", b"\0" + (self.read(7)))[0]
        elif length == 8:
            value = unpack(">Q", self.read(8))[0]
        else:
            raise EbmlException("don't know how to read %r-byte integer" % length)
        if signed:
            nbits = (8 - length) + 8 * (length - 1)
            if value >= (1 << (nbits - 1)):
                value -= 1 << nbits
        return value

    def readFloat(self, length):
        if length == 4:
            return unpack('>f', self.read(4))[0]
        elif length == 8:
            return unpack('>d', self.read(8))[0]
        else:
            raise EbmlException("don't know how to read %r-byte float" % length)

    ## Parsing

    def parse(self, from_=0, to=None):
        """Parses EBML from `from_` (inclusive) to `to` (exclusive).

        Note that not all streams support seeking backwards, so prepare to handle
        an exception if you try to parse from arbitrary position.
        """
        if to is None:
            to = self.size
        self.seek(from_, 0)
        node = {}
        # Iterate over current node's children.
        while self.tell() < to:
            try:
                id = self.readID()
            except EbmlException as e:
                # Invalid EBML header. We can't reliably get any more data from
                # this level, so just return anything we have.
                warn(EbmlWarning(e))
                return node
            size = self.readSize()
            if size == 0b01111111:
                warn(EbmlWarning("don't know how to handle unknown-sized element"))
                size = to - self.tell()
            try:
                key, type_ = self.tags[id]
            except KeyError:
                self.seek(size, 1)
                continue
            try:
                if type_ is SINT:
                    value = self.readInteger(size, True)
                elif type_ is UINT:
                    value = self.readInteger(size, False)
                elif type_ is FLOAT:
                    value = self.readFloat(size)
                elif type_ is STRING:
                    value = self.read(size).decode('ascii')
                elif type_ is UTF8:
                    value = self.read(size).decode('utf-8')
                elif type_ is DATE:
                    us = self.readInteger(size, True) / 1000.0  # ns to us
                    from datetime import datetime, timedelta

                    value = datetime(2001, 1, 1) + timedelta(microseconds=us)
                elif type_ is MASTER:
                    tell = self.tell()
                    value = self.parse(tell, tell + size)
                elif type_ is BINARY:
                    value = BinaryData(self.read(size))
                else:
                    assert False, type_
            except (EbmlException, UnicodeDecodeError) as e:
                warn(EbmlWarning(e))
            else:
                try:
                    parentval = node[key]
                except KeyError:
                    parentval = node[key] = []
                parentval.append(value)
        return node


## GIO-specific code

from gi.repository import Gio


class GioEbml(Ebml):
    # NOTE: All seeks are faked using InputStream.skip because we need to use
    # BufferedInputStream but it does not implement Seekable.

    def open(self, location):
        f = Gio.File.new_for_commandline_arg(location)
        self.buffer = Gio.BufferedInputStream.new(f.read())
        self._tell = 0

        self.size = f.query_info(
            'standard::size', Gio.FileQueryInfoFlags.NONE, None
        ).get_size()

    def seek(self, offset, mode):
        if mode == 0:
            skip = offset - self._tell
        elif mode == 1:
            skip = offset
        elif mode == 2:
            skip = self.size - self._tell + offset
        else:
            raise ValueError("invalid seek mode: %r" % mode)
        if skip < 0:
            raise NotImplementedError("seeking backwards not supported")
        self._tell += skip
        self.buffer.skip(skip)

    def tell(self):
        return self._tell

    def read(self, length):
        result = self.buffer.read_bytes(length).get_data()
        self._tell += len(result)
        return result

    def close(self):
        self.buffer.close()


## Matroska-specific code

# Interesting Matroska tags.
# Tags not defined here are skipped while parsing.
MatroskaTags = {
    # Segment
    0x18538067: ('Segment', MASTER),
    # Segment Information
    0x1549A966: ('Info', MASTER),
    0x7384: ('SegmentFilename', UTF8),
    0x2AD7B1: ('TimecodeScale', UINT),
    0x4489: ('Duration', FLOAT),
    0x4461: ('DateUTC', DATE),
    0x7BA9: ('Title', UTF8),
    0x4D80: ('MuxingApp', UTF8),
    0x5741: ('WritingApp', UTF8),
    # Track
    0x1654AE6B: ('Tracks', MASTER),
    0xAE: ('TrackEntry', MASTER),
    0xD7: ('TrackNumber', UINT),
    0x83: ('TrackType', UINT),
    0xB9: ('FlagEnabled', UINT),
    0x88: ('FlagDefault', UINT),
    0x23E383: ('DefaultDuration', UINT),
    0x536E: ('Name', UTF8),
    0x22B59C: ('Language', STRING),
    0x86: ('CodecID', STRING),
    0x258688: ('CodecName', UTF8),
    # Video
    0xE0: ('Video', MASTER),
    # Audio
    0xE1: ('Audio', MASTER),
    0xB5: ('SamplingFrequency', FLOAT),
    0x78B5: ('OutputSamplingFrequency', FLOAT),
    0x9F: ('Channels', UINT),
    0x6264: ('BitDepth', UINT),
    # Attachment
    0x1941A469: ('Attachments', MASTER),
    0x61A7: ('AttachedFile', MASTER),
    0x466E: ('FileName', UTF8),
    0x465C: ('FileData', BINARY),
    # Chapters
    0x1043A770: ('Chapters', MASTER),
    0x45B9: ('EditionEntry', MASTER),
    0x45BC: ('EditionUID', UINT),
    0x45BD: ('EditionFlagHidden', UINT),
    0x45DB: ('EditionFlagDefault', UINT),
    0x45DD: ('EditionFlagOrdered', UINT),
    0xB6: ('ChapterAtom', MASTER),
    0x73C4: ('ChapterUID', UINT),
    0x91: ('ChapterTimeStart', UINT),
    0x92: ('ChapterTimeEnd', UINT),
    0x98: ('ChapterFlagHidden', UINT),
    0x4598: ('ChapterFlagEnabled', UINT),
    0x63C3: ('ChapterPhysicalEquiv', UINT),
    0x8F: ('ChapterTrack', MASTER),
    0x89: ('ChapterTrackNumber', UINT),
    0x80: ('ChapterDisplay', MASTER),
    0x85: ('ChapString', UTF8),
    0x437C: ('ChapLanguage', STRING),
    0x437E: ('ChapCountry', STRING),
    # Tagging
    0x1254C367: ('Tags', MASTER),
    0x7373: ('Tag', MASTER),
    0x63C0: ('Targets', MASTER),
    0x68CA: ('TargetTypevalue', UINT),
    0x63CA: ('TargetType', STRING),
    0x63C5: ('TagTrackUID', UINT),
    0x63C9: ('TagEditionUID', UINT),
    0x63C4: ('TagChapterUID', UINT),
    0x67C8: ('SimpleTag', MASTER),
    0x45A3: ('TagName', UTF8),
    0x447A: ('TagLanguage', STRING),
    0x4484: ('TagDefault', UINT),
    0x4487: ('TagString', UTF8),
    0x4485: ('TagBinary', BINARY),
}


def parse(location):
    return GioEbml(location, MatroskaTags).parse()


def dump(location):
    from pprint import pprint

    pprint(parse(location))


def dump_tags(location):
    from pprint import pprint

    mka = parse(location)
    segment = mka['Segment'][0]
    info = segment['Info'][0]
    try:
        timecodescale = info['TimecodeScale'][0]
    except KeyError:
        timecodescale = 1000000
    length = info['Duration'][0] * timecodescale / 1e9
    print("Length = %s seconds" % length)
    pprint(segment['Tags'][0]['Tag'])


def gio_location(location):
    """Convert location to GIO-compatible location.

    This works around broken behaviour in the Win32 GIO port (it converts paths
    into UTF-8 and requires them to be specified in UTF-8 as well).

    :type location: str
    :rtype: bytes
    """
    if sys.platform == 'win32' and '://' not in location:
        if isinstance(location, bytes):
            # Decode the path according to the FS encoding to get the Unicode
            # representation first. If the path is in a different encoding,
            # this step will fail.
            location = location.decode(sys.getfilesystemencoding())
        location = location.encode('utf-8')
    return location


if __name__ == '__main__':
    location = gio_location(sys.argv[1])
    dump_tags(location)


# vi: et sts=4 sw=4 ts=4
