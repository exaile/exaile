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

import re, spydaap, re, os, sys
from spydaap.daap import do

class AviParser(spydaap.parser.Parser):
    file_re = re.compile(".*\\.[aA][vV][iI]$")
    def understands(self, filename):
        return self.file_re.match(filename)
    
    def parse(self, filename):
        name = filename
        statinfo = os.stat(filename)
        d = [ do ('daap.songsize', statinfo.st_size),
              do ('daap.songdateadded', statinfo.st_mtime),
              do ('daap.songdatemodified', statinfo.st_mtime),
              do ('dmap.itemname', name),
              do ('daap.songalbum', ''),
              do ('daap.songartist', ''),
              do ('daap.songbitrate', 0),
              do ('daap.songcomment', ''),
              do ('daap.songdescription', 'MPEG-4 video file'),
              do ('daap.songformat', 'avi'),
              do ('com.apple.itunes.mediakind', 2),
              do ('com.apple.itunes.has-video', True)     
              ]
        return (d, name)
