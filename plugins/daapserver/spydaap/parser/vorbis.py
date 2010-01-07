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

class VorbisParser(spydaap.parser.Parser):
    vorbis_string_map = {
        'title': 'dmap.itemname',
        'artist': 'daap.songartist',
        'composer': 'daap.songcomposer',
        'genre': 'daap.songgenre',
        'album': 'daap.songalbum'
        }

    vorbis_int_map = {
        'bpm': 'daap.songbeatsperminute',
        'date': 'daap.songyear',
        'year': 'daap.songyear',
        'tracknumber': 'daap.songtracknumber',
        'tracktotal': 'daap.songtrackcount',
        'discnumber': 'daap.songdiscnumber'
        }
        
    file_re = re.compile(".*\\.([fF][lL][aA][cC]|[oO][gG]{2})$")
    def understands(self, filename):
        return self.file_re.match(filename)

    def parse(self, filename):
        try:
            md = mutagen.File(filename)
            d = []
            if md.tags != None:
                self.handle_string_tags(self.vorbis_string_map, md, d)
                self.handle_int_tags(self.vorbis_int_map, md, d)
            self.add_file_info(filename, d)
            d.extend([do('daap.songtime', md.info.length * 1000),
                      do('daap.songsamplerate', md.info.sample_rate)])
            name = self.set_itemname_if_unset(os.path.basename(filename), d)
            if hasattr(self, 'parse_extra_vorbis'):
                self.parse_extra_vorbis(filename, md, d)
            return (d, name)
        except Exception, e:
            sys.stderr.write("Caught exception: while processing %s: %s " % (filename, str(e)) )
            return (None, None)
