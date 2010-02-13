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

import mutagen.id3, mutagen.mp3, re, spydaap, re, os, struct, sys
from spydaap.daap import do
mutagen.id3.ID3.PEDANTIC = False

class Mp3Parser(spydaap.parser.Parser):
    mp3_string_map = {
        'TIT1': 'daap.songgrouping',
        'TIT2': 'dmap.itemname',
        'TPE1': 'daap.songartist',
        'TPE3': 'daap.songalbumartist',
        'TCOM': 'daap.songcomposer',
        'TCON': 'daap.songgenre',
        'TALB': 'daap.songalbum',
        }

    mp3_int_map = {
        'TBPM': 'daap.songbeatsperminute',
        'TDRC': 'daap.songyear',
        'TCMP': 'daap.songcompilation',
        #'TLEN': 'daap.songtime',
        }
#do('daap.songdiscnumber', 1),
#        do('daap.songgenre', 'Test'),
#        do('daap.songdisccount', 1),
#        do('daap.songcompilation', False),
#        do('daap.songuserrating', 1),
                
    def handle_rating(self, mp3, d):
        popm = mp3.tags.getall('POPM')
        if popm != None and len(popm) > 0:
            rating = int(popm[0].rating * (0.39215686274509803))
            d.append(do('daap.songuserrating', rating))

    def handle_track(self, mp3, d):
        tracknumber = None
        trackcount = None
        if mp3.tags.has_key('TRCK'):
            t = str(mp3.tags['TRCK']).split('/')
            tracknumber = self.my_int(t[0])
            if (len(t) == 2):
                trackcount = self.my_int(t[1])
        if tracknumber: d.append(do('daap.songtracknumber', tracknumber))
        if trackcount: d.append(do('daap.songtrackcount', trackcount))

    def handle_disc(self, mp3, d):
        discnumber = None
        disccount = None
        if mp3.tags.has_key('TPOS'):
            t = str(mp3.tags['TPOS']).split('/')
            discnumber = self.my_int(t[0])
            if (len(t) == 2):
                disccount = self.my_int(t[1])
        if discnumber: d.append(do('daap.songdiscnumber', discnumber))
        if disccount: d.append(do('daap.songdisccount', disccount))

    file_re = re.compile(".*\\.[mM][pP]3$")
    def understands(self, filename):
        return self.file_re.match(filename)

    def parse(self, filename):
        d = []
        mp3 = None
        try:
            mp3 = mutagen.mp3.MP3(filename)
        except mutagen.mp3.HeaderNotFoundError:
            pass
        except struct.error:
            pass
        if mp3 != None:
            if mp3.tags != None:
                self.handle_string_tags(self.mp3_string_map, mp3, d)
                self.handle_int_tags(self.mp3_int_map, mp3, d)
                self.handle_rating(mp3, d)
                self.handle_track(mp3, d)
                self.handle_disc(mp3, d)
            self.add_file_info(filename, d)
            d.extend([do('daap.songtime', mp3.info.length * 1000),
                      do('daap.songbitrate', mp3.info.bitrate / 1000),
                      do('daap.songsamplerate', mp3.info.sample_rate),
                      do('daap.songformat', 'mp3'),
                      do('daap.songdescription', 'MPEG Audio File'),
                      ])
            name = self.set_itemname_if_unset(os.path.basename(filename), d)
            return (d, name)
        else:
            return (None, None)
