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

import os, time

class Playlist(object):
    name = None
    smart_playlist = True

    def sort(self, entries):
        pass

    def safe_cmp(self, a, b, key):
        if a.has_key(key) and b.has_key(key):
            return cmp(a[key], b[key])
        elif a.has_key(key):
            return 1
        elif b.has_key(key):
            return -1
        else: return 0

    def safe_cmp_series(self, a, b, key_list):
        if len(key_list) == 0:
            return 0
        key = key_list[0]
        r = self.safe_cmp(a, b, key)
        if r != 0:
            return r
        else:
            return self.safe_cmp_series(a, b, key_list[1:])
        
class Library(Playlist):
    def __init__(self):
        self.name = "Library"
        self.smart_playlist = False

    def contains(self, md):
        return True

class Genre(Playlist):
    def __init__(self, name, genre):
        self.name = name
        self.genre = genre
    
    def contains(self, md):
        if not(md.has_key('daap.songgenre')): return False
        else:
            songgenre = md['daap.songgenre'].lower()
            if type(self.genre) == str:
                return songgenre == self.genre
            elif type(self.genre) == list:
                return songgenre in self.genre

class YearRange(Playlist):
    def __init__(self, name, first,last=None):
        self.name = name
        if last == None:
            last = first
        self.last = last
        self.first = first

    def contains(self, md):
        if not(md.has_key('daap.songyear')): return False
        else:
            year = md['daap.songyear']
            return year >= self.first and year <= self.last
    
    def sort(self, entries):
        def s(a,b):
            return self.safe_cmp_series(a, b, ['daap.songyear', 
                                               'daap.songartist', 
                                               'daap.songalbum',
                                               'daap.songtracknumber'])
        entries.sort(cmp=s)
    
class Recent(Playlist):
     def __init__(self, name, seconds=604800):
     	 self.name = name
	 self.seconds = seconds

     def contains(self, md):
         f_mtime = os.stat(md.get_original_filename()).st_mtime
         return ((f_mtime + self.seconds) > time.time())

class Rating(Playlist):
    def __init__(self, name, rating):
        self.name = name
        self.rating = rating

    def contains(self, md):
        if md.has_key('daap.songuserrating'):
            return md['daap.songuserrating'] >= self.rating
        else: return False
