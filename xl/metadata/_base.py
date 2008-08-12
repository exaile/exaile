# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
from xl import common

INFO_TAGS = ['bitrate', 'length', 'lyrics']

class NotWritable(Exception):
    pass

class BaseFormat(object):
    MutagenType = None
    tag_mapping = {}
    others = True
    writable = False

    def __init__(self, loc):
        self.loc = loc
        self.open = False
        self.mutagen = None
        self.load()

    def load(self):
        """
            Loads the tags from the file.
        """
        if self.MutagenType:
            self.mutagen = self.MutagenType(self.loc)

    def save(self):
        """
            Saves any changes to the tags.
        """
        if self.writable and self.mutagen:
            self.mutagen.save()

    def _get_raw(self):
        if self.MutagenType:
            return self.mutagen            
        else:
            return {'title':os.path.split(self.loc)[-1]}

    def _get_tag(self, raw, tag):
        try:
            return raw[tag]
        except KeyError:
            return None

    def read_all(self):
        all = self.read_tags(common.VALID_TAGS)
        all.update(self.read_tags(INFO_TAGS))
        return all

    def read_tags(self, tags):
        """
            get the values for the specified tags.

            returns a dict of the found values. if no value was found for a 
            requested tag it will not exist in the returned dict
        """
        raw = self._get_raw()
        td = {}
        for tag in tags:
            t = None
            if tag in INFO_TAGS:
                try:
                    t = self.get_info(tag)
                except KeyError:
                    pass
            if t == None and tag in self.tag_mapping:
                try:
                    t = self._get_tag(raw, self.tag_mapping[tag])
                    if type(t) in [str, unicode]:
                        t = [t]
                    else:
                        t = [unicode(u) for u in list(t)]
                except (KeyError, TypeError):
                    pass
            if t == None and self.others:
                try:
                    t = self._get_tag(raw, tag)
                    if type(t) in [str, unicode]:
                        t = [t]
                    else:
                        t = [unicode(u) for u in list(t)]
                except (KeyError, TypeError):
                    pass

            if t not in [None, []]:
                td[tag] = t
        return td

    def _set_tag(self, raw, tag, value):
        raw[tag] = value

    def write_tags(self, tagdict):
        if not self.MutagenType:
            raise NotWritable
        else:
            raw = self._get_raw()
            # add tags if it doesn't have them
            try:
                raw.add_tags()
            except (ValueError, NotImplementedError):
                pass

            # info tags are not actually writable
            for tag in INFO_TAGS:
                try:
                    del tagdict[tag]
                except:
                    pass

            for tag in tagdict:
                if tag in self.tag_mapping:
                    self._set_tag(raw, self.tag_mapping[tag], tagdict[tag])
                elif self.others:
                    self._set_tag(raw, tag, tagdict[tag])
            self.save()

    def get_info(self, info):
        if info == "length":
            return self.get_length()
        elif info == "bitrate":
            return self.get_bitrate()
        else:
            raise KeyError

    def get_length(self):
        try:
            return self.mutagen.info.length
        except:
            try:
                return self.mutagen['length']
            except:
                return None

    def get_bitrate(self):
        try:
            return self.mutagen.info.bitrate
        except:
            try:
                return self.mutagen['bitrate']
            except:
                return None

# vim: et sts=4 sw=4

