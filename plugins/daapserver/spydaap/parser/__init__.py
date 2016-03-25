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

import os, re
from spydaap.daap import do

class Parser:
    def handle_string_tags(self, map, md, daap):
        h = {}
        for k in list(md.tags.keys()):
            if k in map:
                tag = [ str(t) for t in md.tags[k] ]
                tag = [ t for t in tag if t != "" ]
                if not(map[k] in h): h[map[k]] = []
                h[map[k]] = h[map[k]] + tag
        for k in list(h.keys()):
            h[k].sort()
            daap.append(do(k, "/".join(h[k])))

    def handle_int_tags(self, map, md, daap):
        for k in list(md.tags.keys()):
            if k in map:
                val = md.tags[k]
                if type(val) == list:
                    val = val[0]
                intval = self.my_int(str(val))
                if intval: daap.append(do(map[k], intval))

    def add_file_info(self, filename, daap):
        statinfo = os.stat(filename)
        daap.extend([do('daap.songsize', os.path.getsize(filename)),
                     do('daap.songdateadded', statinfo.st_ctime),
                     do('daap.songdatemodified', statinfo.st_ctime)])
    
    def set_itemname_if_unset(self, name, daap):
        for d in daap:
            if d.code == 'minm': return d.value
        daap.extend([do('minm', name)])
        return name

    def clean_int_string(self, s):
        return re.sub('[^0-9]', '', str(s))
    
    def my_int(self, s):
        try:
            return int(self.clean_int_string(s))
        except: return None
