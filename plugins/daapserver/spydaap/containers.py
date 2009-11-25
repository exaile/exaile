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

import os, struct, md5, spydaap.cache
from spydaap.daap import do

class ContainerCache(spydaap.cache.OrderedCache):
    def __init__(self, cache_dir, container_list):
        self.container_list = container_list
        super(ContainerCache, self).__init__(cache_dir)

    def get_item_by_pid(self, pid, n=None):
        return ContainerCacheItem(self, pid, None)

    def build(self, md_cache):
        def build_do(md, id):
            d = do('dmap.listingitem',
                   [ do('dmap.itemkind', 2),
                     do('dmap.itemid', md.id),
                     do('dmap.itemname', md.get_name()),
                     do('dmap.containeritemid', id)
                     ] )
            return d
        pid_list = []
        for pl in self.container_list:
            entries = [n for n in md_cache if pl.contains(n)]
            pl.sort(entries)
            d = do('daap.playlistsongs',
                   [ do('dmap.status', 200),
                     do('dmap.updatetype', 0),
                     do('dmap.specifiedtotalcount', len(entries)),
                     do('dmap.returnedcount', len(entries)),
                     do('dmap.listing',
                        [ build_do (md,id) for (id, md) in enumerate(entries) ])
                     ])
            ContainerCacheItem.write_entry(self.dir, pl.name, d, len(entries))
            pid_list.append(md5.md5(pl.name).hexdigest())
        self.build_index(pid_list)
        
class ContainerCacheItem(spydaap.cache.OrderedCacheItem):
    @classmethod
    def write_entry(self, dir, name, d, length):
        data = struct.pack('!i', length)
        data = data + struct.pack('!i%ss' % len(name), len(name), name)
        data = data + d.encode()
        cachefn = os.path.join(dir, md5.md5(name).hexdigest())
        f = open(cachefn, 'w')
        f.write(data)
        f.close()

    def __init__(self, cache, pid, id):
        super(ContainerCacheItem, self).__init__(cache, pid, id)
        self.daap_raw = None
        self.name = None
        self._len = None

    def read(self):
        f = open(self.path)
        self._len = struct.unpack('!i', f.read(4))[0]
        name_len = struct.unpack('!i', f.read(4))[0]
        self.name = f.read(name_len)
        self.daap_raw = f.read()
        f.close()

    def get_daap_raw(self):
        if self.daap_raw == None:
            self.read()
        return self.daap_raw

    def get_name(self):
        if self.name == None:
            self.read()
        return self.name
    
    def __len__(self):
        if self._len == None:
            self.read()
        return self._len

