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

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import md5

import os, struct, spydaap.cache, StringIO
from spydaap.daap import do

class MetadataCache(spydaap.cache.OrderedCache):
    def __init__(self, cache_dir, parsers):
        self.parsers = parsers
        super(MetadataCache, self).__init__(cache_dir)

    def get_item_by_pid(self, pid, n=None):
        return MetadataCacheItem(self, pid, n)
    
    def build(self, dir, marked={}, link=False):
        for path, dirs, files in os.walk(dir):
            for d in dirs:
                if os.path.islink(os.path.join(path, d)):
                    self.build(os.path.join(path,d), marked, True)
            for fn in files:
                ffn = os.path.join(path, fn)
                digest = md5.md5(ffn).hexdigest()
                marked[digest] = True
                md = self.get_item_by_pid(digest)
                if (not(md.get_exists()) or \
                        (md.get_mtime() < os.stat(ffn).st_mtime)):
                    for p in self.parsers:
                        if p.understands(ffn):                  
                            (m, name) = p.parse(ffn)
                            if m != None:
                                MetadataCacheItem.write_entry(self.dir,
                                                              name, ffn, m)
        if not(link):
            for item in os.listdir(self.dir):
                if (len(item) == 32) and not(marked.has_key(item)):
                    os.remove(os.path.join (self.dir, item))
            self.build_index()

class MetadataCacheItem(spydaap.cache.OrderedCacheItem):
    @classmethod
    def write_entry(self, dir, name, fn, daap):
        data = "".join([ d.encode() for d in daap])
        data = struct.pack('!i%ss' % len(name), len(name), name) + data
        data = struct.pack('!i%ss' % len(fn), len(fn), fn) + data
        cachefn = os.path.join(dir, md5.md5(fn).hexdigest())
        f = open(cachefn, 'w')
        f.write(data)
        f.close()

    def __init__(self, cache, pid, id):
        super(MetadataCacheItem, self).__init__(cache, pid, id)
        self.file = None
        self.daap = None
        self.name = None
        self.original_filename = None
        self.daap_raw = None
        self.md = None

    def __getitem__(self, k):
        return self.md[k]

    def has_key(self, k):
        return self.get_md().has_key(k)

    def read(self):
        f = open(self.path)
        fn_len = struct.unpack('!i', f.read(4))[0]
        self.original_filename = f.read(fn_len)
        name_len = struct.unpack('!i', f.read(4))[0]
        self.name = f.read(name_len)
        self.daap_raw = f.read()
        f.close()

    def get_original_filename(self):
        if self.original_filename == None:
            self.read()
        return self.original_filename 
    
    def get_name(self):
        if self.name == None:
            self.read()
        return self.name

    def get_dmap_raw(self):
        if self.daap_raw == None:
            self.read()
        return self.daap_raw

    def get_md(self):
        if self.md == None:
            self.md = {}
            s = StringIO.StringIO(self.get_dmap_raw())
            l = len(self.get_dmap_raw())
            data = []
            while s.tell() != l:
                d = do()
                d.processData(s)
                data.append(d)
            for d in data:
                self.md[d.codeName()] = d.value
        return self.md
