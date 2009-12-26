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
import traceback

class ExaileParser(spydaap.parser.Parser):
    _string_map = {
        'title': 'dmap.itemname',
        'artist': 'daap.songartist',
        'composer': 'daap.songcomposer',
        'genre': 'daap.songgenre',
        'album': 'daap.songalbum'
        }
    
    _int_map = {
        'bpm': 'daap.songbeatsperminute',
        'date': 'daap.songyear',
        'year': 'daap.songyear',
        'tracknumber': 'daap.songtracknumber',
        'tracktotal': 'daap.songtrackcount',
        'discnumber': 'daap.songdiscnumber'
        }

    def understands(self, filename):
        return true
     #   return self.file_re.match(filename)

    # returns a list in exaile
    def handle_int_tags(self, map, md, daap):
        for k in md.list_tags():
            if map.has_key(k):
                try:
                    tn = str(md.get_tag_raw(k)[0])
                    if '/' in tn: #
                        num, tot = tn.split('/')
                        daap.append(do(map[k], int(num)))
                        # set total?
                    else:
                        daap.append(do(map[k], int(tn)))
                except: pass
                # dates cause exceptions todo
#                    print 'Parse Exception'
#                    traceback.print_exc(file=sys.stdout)

    # We can't use functions in __init__ because exaile tracks no longer
    # give us access to .tags
    def handle_string_tags(self, map, md, daap):
        for k in md.list_tags():
            if map.has_key(k):
                try:
                    tag = [ str(t) for t in md.get_tag_raw(k)]
                    tag = [ t for t in tag if t != ""]
                    daap.append(do(map[k], "/".join(tag)))
                except: pass

    def parse(self, trk):
        try:
            #trk = mutagen.File(filename)
            d = []
            if len(trk.list_tags()) > 0:
                if 'title' in trk.list_tags():
                    name = str(trk.get_tag_raw('title')[0])
                else: name = str(trk)
                
                self.handle_string_tags(self._string_map, trk, d)
                self.handle_int_tags(self._int_map, trk, d)
#                self.handle_rating(trk, d)
            else: 
                name = str(trk)
            #statinfo = os.stat(filename)
            d.extend([#do('daap.songsize', trk.get_size()),
                      #do('daap.songdateadded', statinfo.st_ctime),
                      #do('daap.songdatemodified', statinfo.st_ctime),
                      do('daap.songtime', trk.get_tag_raw('__length') * 1000),
#                      do('daap.songbitrate', trk.get_tag_raw('__bitrate') / 1000),
#                      do('daap.songsamplerate', ogg.info.sample_rate), # todo ??
                      do('daap.songformat', trk.local_file_name().split('.')[-1]), # todo ??
                      do('daap.songdescription', 'Exaile Streaming Audio'),
                      ])
            return (d, name)
        except Exception, e:
            sys.stderr.write("Caught exception: while processing %s: %s " % (trk, str(e)) )
            return (None, None)    


