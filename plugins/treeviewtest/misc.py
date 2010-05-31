# Copyright (C) 2010 Aren Olson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.


class MetadataList(object):
    __slots__ = ['__list', 'metadata']
    """
        Like a list, but also associates an arbitrary object of metadata
        with each entry.

        To set metadata, just set it on the metadata property. eg.
        >>> l = MetadataList()
        >>> l.append('test')
        >>> l.metadata[0] = 'foo'
        >>> l.insert(0, 'bar')
        >>> l[0], l.metadata[0]
        'bar', None
        >>> l[1], l.metadata[1]
        'test', 'foo'

        Do NOT attempt to overwrite or resize the metadata property itself,
        you are allowed only to assign by index or same-size slice. Other
        modifications are unsupported and will probably break things.

        List aspects that are not supported:
            sort
            comparisons other than equality
            multiply
    """
    def __init__(self, iterable=[], metadata=[]):
        self.__list = list(iterable)
        meta = list(metadata)
        if meta and len(meta) != len(self.__list):
            raise ValueError, "Length of metadata must match length of items."
        if not meta:
            meta = [None] * len(self.__list)
        self.metadata = meta

    def __repr__(self):
        return "MetadataList(%s)"%self.__list

    def __len__(self):
        return len(self.__list)

    def __iter__(self):
        return self.__list.__iter__()

    def __add__(self, other):
        l = MetadataList(self, self.metadata)
        l.extend(other)
        return l

    def __iadd__(self, other):
        self.extend(other)
        return self

    def __eq__(self, other):
        if isinstance(other, MetadataList):
            other = list(other)
        return self.__list == other

    def __getitem__(self, i):
        val = self.__list.__getitem__(i)
        if isinstance(i, slice):
            return MetadataList(val, self.metadata.__getitem__(i))
        else:
            return val

    def __setitem__(self, i, value):
        self.__list.__setitem__(i, value)
        if isinstance(value, MetadataList):
            metadata = list(value.metadata)
        else:
            metadata = [None]*len(value)
        self.metadata.__setitem__(i, metadata)

    def __delitem__(self, i):
        self.__list.__delitem__(i)
        self.metadata.__delitem__(i)

    def append(self, other, metadata=None):
        self.insert(len(self), other, metadata=metadata)

    def extend(self, other):
        self[len(self):len(self)] = other

    def insert(self, i, item, metadata=None):
        if i >= len(self):
            i = len(self)
            e = len(self)+1
        else:
            e = i
        self[i:e] = [item]
        self.metadata[i:e] = [metadata]

    def pop(self, i=-1):
        item = self[i]
        del self[i]
        return item

    def remove(self, item):
        del self[self.index(item)]

    def reverse(self):
        self.__list.reverse()
        self.metadata.reverse()

    def index(self, i):
        return self.__list.index(i)

    def count(self, i):
        return self.__list.count(i)

