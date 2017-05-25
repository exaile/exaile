# Copyright (C) 2008 Erik Hetzner

# This file is part of Spydaap. Spydaap is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.

# Spydaap is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

from hashlib import md5
import os


class Cache(object):

    def __init__(self, dir):
        self.dir = os.path.abspath(dir)
        if (not(os.path.exists(self.dir))):
            os.mkdir(self.dir)

    def get(self, id, func):
        id = md5(id).hexdigest()
        fn = os.path.join(self.dir, id)
        if (not(os.path.exists(fn))):
            f = open(fn, 'w')
            func(f)
            f.close()
        return open(fn)

    def clean(self):
        for f in os.listdir(self.dir):
            p = os.path.join(self.dir, f)
            if os.path.isfile(p):
                os.remove(p)


class OrderedCache(object):

    class Iter:

        def __init__(self, cache):
            self.cache = cache
            self.n = 0

        def __iter__(self):
            return self

        def next(self):
            if self.n >= len(self.cache):
                raise StopIteration
            self.n = self.n + 1
            return self.cache.get_item_by_id(self.n)

    def __init__(self, dir):
        self.dir = os.path.abspath(dir)
        if (not(os.path.exists(self.dir))):
            os.mkdir(self.dir)

    def __iter__(self):
        return OrderedCache.Iter(self)

    def get_item_by_id(self, id):
        fi = open(os.path.join(self.dir, 'index'), 'r')
        fi.seek((int(id) - 1) * 32)
        cfn = fi.read(32)
        fi.close()
        return self.get_item_by_pid(cfn, id)

    def __len__(self):
        return os.path.getsize(os.path.join(self.dir, 'index')) / 32

    def build_index(self, pid_list=None):
        index_fn = os.path.join(self.dir, 'index')
        if os.path.exists(index_fn):
            os.remove(index_fn)
        if pid_list is None:
            pid_list = sorted([f for f in os.listdir(self.dir) if f != "index"])
        fi = open(index_fn, 'w')
        for pid in pid_list:
            fi.write(pid)
        fi.close()

    def clean(self):
        for f in os.listdir(self.dir):
            p = os.path.join(self.dir, f)
            if os.path.isfile(p):
                os.remove(p)


class OrderedCacheItem(object):

    def __init__(self, cache, pid, id):
        self.cache = cache
        self.pid = pid
        self.id = id
        self.path = os.path.join(self.cache.dir, pid)

    def get_mtime(self):
        return os.stat(self.path).st_mtime

    def get_exists(self):
        return os.path.exists(self.path)

    def get_id(self):
        return self.id

    def get_pid(self):
        return self.pid
