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

import mutagen.id3, mutagen.mp3, re, spydaap, re, os, sys
from spydaap.daap import do
mutagen.id3.ID3.PEDANTIC = False

class Mp3Parser(spydaap.parser.Parser):
    mp3_string_map = {
        'TIT1': 'daap.songgrouping',
        'TIT2': 'dmap.itemname',
        'TPE1': 'daap.songartist',
        'TCOM': 'daap.songcomposer',
        'TCON': 'daap.songgenre',
        'TPE1': 'daap.songartist',
        'TALB': 'daap.songalbum',
        }

    mp3_int_map = {
        'TBPM': 'daap.songbeatsperminute',
        'TDRC': 'daap.songyear',
        #'TLEN': 'daap.songtime',
        }
#do('daap.songdiscnumber', 1),
#        do('daap.songgenre', 'Test'),
#        do('daap.songdisccount', 1),
#        do('daap.songcompilation', False),
#        do('daap.songuserrating', 1),
                
    def handle_rating(self, mp3, d):
        try:
            popm = mp3.tags.getall('POPM')
            if popm != None:
                rating = int(popm[0].rating * (0.39215686274509803))
                d.append(do('daap.songuserrating', rating))
        except: pass

    def handle_track(self, mp3, d):
        try:
            if mp3.tags.has_key('TRCK'):
                t = str(mp3.tags['TRCK']).split('/')
                d.append(do('daap.songtracknumber', int(t[0])))
                if (len(t) == 2):
                    d.append(do('daap.songtrackcount', int(t[1])))
        except: pass

    def handle_disc(self, mp3, d):
        try:
            if mp3.tags.has_key('TPOS'):
                t = str(mp3.tags['TPOS']).split('/')
                d.append(do('daap.songdiscnumber', int(t[0])))
                if (len(t) == 2):
                    d.append(do('daap.songdisccount', int(t[1])))
        except: pass

    file_re = re.compile(".*\\.[mM][pP]3$")
    def understands(self, filename):
        return self.file_re.match(filename)

    def parse(self, filename):
        try:
            mp3 = mutagen.mp3.MP3(filename)
            d = []
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
        except Exception, e:
            sys.stderr.write("Caught exception: while processing %s: %s " % (filename, str(e)) )
            return (None, None)
