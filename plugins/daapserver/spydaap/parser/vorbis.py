#Copyright (C) 2008 Erik Hetzner

#This file is part of Spydaap. Spydaap is free software: you can
#redistribute it and/or modify it under the terms of the GNU General
#Public License as published by the Free Software Foundation, either
#version 3 of the License, or (at your option) any later version.

#Spydaap is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

import mutagen, re, spydaap, re, os, sys
from spydaap.daap import do

# * TODO Implement song.songtrackcount, song.disccount
#daap.songbeatsperminute
#daap.songcomment
#daap.songdateadded
#daap.songdatemodified,
#daap.songdisabled,
#daap.songeqpreset
#daap.songformat
#daap.songdescription
#daap.songrelativevolume,
#daap.songsize,
#daap.songstarttime,
#daap.songstoptime,
#daap.songtime,
#daap.songuserrating,
#daap.songdatakind,
#daap.songdataurl

class VorbisParser(spydaap.parser.Parser):
    vorbis_string_map = {
        'grouping' : 'daap.songgrouping',
        'title'    : 'dmap.itemname',
        'artist'   : 'daap.songartist',
        'composer' : 'daap.songcomposer',
        'genre'    : 'daap.songgenre',
        'album'    : 'daap.songalbum',
        'albumartist': 'daap.songalbumartist',
        }

    vorbis_int_map = {
        'bpm'         : 'daap.songbeatsperminute',
        'date'        : 'daap.songyear',
        'year'        : 'daap.songyear',
        'compilation' : 'daap.songcompilation',
        }

    def handle_track(self, flac, d):
        tracknumber = None
        trackcount = None
        if flac.tags.has_key('tracknumber'):
            t = str(flac.tags['tracknumber']).split('/')
            tracknumber = self.my_int(t[0])
            if (len(t) == 2):
                trackcount = self.my_int(t[1])
        if flac.tags.has_key('tracktotal'):
            trackcount = self.my_int(flac.tags['tracktotal'])
        if tracknumber: d.append(do('daap.songtracknumber', tracknumber))
        if trackcount: d.append(do('daap.songtrackcount', trackcount))

    def handle_disc(self, flac, d):
        discnumber = None
        disccount = None
        if flac.tags.has_key('discnumber'):
            t = unicode(flac.tags['discnumber'][0]).split('/')
            discnumber = self.my_int(t[0])
            if (len(t) == 2):
                disccount = self.my_int(t[1])
        if flac.tags.has_key('disctotal'):
            disccount = self.my_int(flac.tags['disctotal'])
        if discnumber: d.append(do('daap.songdiscnumber', discnumber))
        if disccount: d.append(do('daap.songdisccount', disccount))
        
    file_re = re.compile(".*\\.([fF][lL][aA][cC]|[oO][gG]{2})$")
    def understands(self, filename):
        return self.file_re.match(filename)

    def parse(self, filename):
        md = mutagen.File(filename)
        d = []
        if md.tags != None:
            self.handle_string_tags(self.vorbis_string_map, md, d)
            self.handle_int_tags(self.vorbis_int_map, md, d)
            self.handle_track(md, d)
            self.handle_disc(md, d)
        self.add_file_info(filename, d)
        d.extend([do('daap.songtime', md.info.length * 1000),
                  do('daap.songsamplerate', md.info.sample_rate)])
        name = self.set_itemname_if_unset(os.path.basename(filename), d)
        if hasattr(self, 'parse_extra_vorbis'):
            self.parse_extra_vorbis(filename, md, d)
        return (d, name)
