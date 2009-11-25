# daap.py
#
# DAAP classes and methods.
#
# original work (c) 2004, Davyd Madeley <davyd@ucc.asn.au>
#
# Later iTunes authentication work and object model
# copyright 2005 Tom Insam <tom@jerakeen.org>
#
# Stripped clean + a few bug fixes, Erik Hetzner

import struct, sys
import logging
from spydaap.daap_data import *

__all__ = ['DAAPError', 'DAAPObject', 'do']

log = logging.getLogger('daap')

def DAAPParseCodeTypes(treeroot):
    # the treeroot we are given should be a
    # dmap.contentcodesresponse
    if treeroot.codeName() != 'dmap.contentcodesresponse':
        raise DAAPError("DAAPParseCodeTypes: We cannot generate a dictionary from this tree.")
        return
    for object in treeroot.contains:
        # each item should be one of two things
        # a status code, or a dictionary
        if object.codeName() == 'dmap.status':
            pass
        elif object.codeName() == 'dmap.dictionary':
            code    = None
            name    = None
            dtype   = None
            # a dictionary object should contain three items:
            # a 'dmap.contentcodesnumber' the 4 letter content code
            # a 'dmap.contentcodesname' the name of the code
            # a 'dmap.contentcodestype' the type of the code
            for info in object.contains:
                if info.codeName() == 'dmap.contentcodesnumber':
                    code    = info.value
                elif info.codeName() == 'dmap.contentcodesname':
                    name    = info.value
                elif info.codeName() == 'dmap.contentcodestype':
                    try:
                        dtype   = dmapDataTypes[info.value]
                    except:
                        log.debug('DAAPParseCodeTypes: unknown data type %s for code %s, defaulting to s', info.value, name)
                        dtype   = 's'
                else:
                    raise DAAPError('DAAPParseCodeTypes: unexpected code %s at level 2' % info.codeName())
            if code == None or name == None or dtype == None:
                log.debug('DAAPParseCodeTypes: missing information, not adding entry')
            else:
                try:
                    dtype = dmapFudgeDataTypes[name]
                except: pass
                #print("** %s %s %s", code, name, dtype)
                dmapCodeTypes[code] = (name, dtype)
        else:
            raise DAAPError('DAAPParseCodeTypes: unexpected code %s at level 1' % info.codeName())

class DAAPError(Exception): pass

class DAAPObject(object):
    def __init__(self, code=None, value=None, **kwargs):
        if (code != None):
            if (len(code) == 4):
                self.code = code
            else:
                self.code = dmapNames[code]
            if self.code == None or not dmapCodeTypes.has_key(self.code):
                self.type = None
            else:
                self.type = dmapCodeTypes[self.code][1]
            self.value = value
            if self.type == 'c' and type(self.value) == list:
                self.contains = value
        if kwargs.has_key('parent'):
            kwargs['parent'].contains.append(self)

    def getAtom(self, code):
        """returns an atom of the given code by searching 'contains' recursively."""
        if self.code == code:
            if self.type == 'c':
                return self
            return self.value

        # ok, it's not us. check our children
        if hasattr(self, 'contains'):
            for object in self.contains:
                value = object.getAtom(code)
                if value: return value
        return None

    def codeName(self):
        if self.code == None or not dmapCodeTypes.has_key(self.code):
            return None
        else:
            return dmapCodeTypes[self.code][0]

    def objectType(self):
        if self.code == None or not dmapCodeTypes.has_key(self.code):
            return None
        else:
            return dmapCodeTypes[self.code][1]

    def printTree(self, level = 0, out = sys.stdout):
        if hasattr(self, 'value'):
            out.write('\t' * level + '%s (%s)\t%s\t%s\n' % (self.codeName(), self.code, self.type, self.value))
        else:
            out.write('\t' * level + '%s (%s)\t%s\t%s\n' % (self.codeName(), self.code, self.type, None))
        if hasattr(self, 'contains'):
            for object in self.contains:
                object.printTree(level + 1)

    def encode(self):
        # generate DMAP tagged data format
        # step 1 - find out what type of object we are
        if self.type == 'c':
            # our object is a container,
            # this means we're going to have to
            # check contains[]
            value   = ''
            for item in self.contains:
                # get the data stream from each of the sub elements
                if type(item) == str:
                    #preencoded
                    value += item
                else:
                    value += item.encode()
            # get the length of the data
            length  = len(value)
            # pack: 4 byte code, 4 byte length, length bytes of value
            data = struct.pack('!4sI%ss' % length, self.code, length, value)
            return data
        else:
            # we don't have to traverse anything
            # to calculate the length and such
            # we want to encode the contents of
            # value for our value
            if self.type == 'v':
                value = self.value.split('.')
                self.value = struct.pack('!HH', int(value[0]), int(value[1]))
                packing = "4s"
            elif self.type == 'l':
                packing = 'q'
            elif self.type == 'ul':
                packing = 'Q'
            elif self.type == 'i':
                if (type(self.value) == str and len(self.value) <= 4):
                    packing = '4s'
                else:
                    packing = 'i'
            elif self.type == 'ui':
                packing = 'I'
            elif self.type == 'h':
                packing = 'h'
            elif self.type == 'uh':
                packing = 'H'
            elif self.type == 'b':
                packing = 'b'
            elif self.type == 'ub':
                packing = 'B'
            elif self.type == 't':
                packing = 'I'
            elif self.type == 's':
                packing = '%ss' % len(self.value)
            else:
                raise DAAPError('DAAPObject: encode: unknown code %s' % self.code)
                return
            # calculate the length of what we're packing
            length  = struct.calcsize('!%s' % packing)
            # pack: 4 characters for the code, 4 bytes for the length, and 'length' bytes for the value
            data = struct.pack('!4sI%s' % packing, self.code, length, self.value)
            return data

    def processData(self, str):
        # read 4 bytes for the code and 4 bytes for the length of the objects data
        data = str.read(8)

        if not data: return
        self.code, self.length = struct.unpack('!4sI', data)

        # now we need to find out what type of object it is
        if self.code == None or not dmapCodeTypes.has_key(self.code):
            self.type = None
        else:
            self.type = dmapCodeTypes[self.code][1]

        if self.type == 'c':
            start_pos = str.tell()
            self.contains = []
            # the object is a container, we need to pass it
            # it's length amount of data for processessing
            eof = 0
            while str.tell() < start_pos + self.length:
                object  = DAAPObject()
                self.contains.append(object)
                object.processData(str)
            return

        # not a container, we're a single atom. Read it.
        code = str.read(self.length)

        if self.type == 'l':
            # the object is a long long number,
            self.value  = struct.unpack('!q', code)[0]
        elif self.type == 'ul':
            # the object is an unsigned long long
            self.value  = struct.unpack('!Q', code)[0]
        elif self.type == 'i':
            # the object is a number,
            self.value  = struct.unpack('!i', code)[0]
        elif self.type == 'ui':
            # unsigned integer
            self.value  = struct.unpack('!I', code)[0]
        elif self.type == 'h':
            # this is a short number,
            self.value  = struct.unpack('!h', code)[0]
        elif self.type == 'uh':
            # unsigned short
            self.value  = struct.unpack('!H', code)[0]
        elif self.type == 'b':
            # this is a byte long number
            self.value  = struct.unpack('!b', code)[0]
        elif self.type == 'ub':
            # unsigned byte
            self.value  = struct.unpack('!B', code)[0]
        elif self.type == 'v':
            # this is a version tag
            self.value  = float("%s.%s" % struct.unpack('!HH', code))
        elif self.type == 't':
            # this is a time string
            self.value  = struct.unpack('!I', code)[0]
        elif self.type == 's':
            # the object is a string
            # we need to read length characters from the string
            try:
                self.value  = unicode(
                    struct.unpack('!%ss' % self.length, code)[0], 'utf-8')
            except UnicodeDecodeError:
                # oh, urgh
                self.value = unicode(
                    struct.unpack('!%ss' % self.length, code)[0], 'latin-1')
        else:
            # we don't know what to do with this object
            # put it's raw data into value
            log.debug('DAAPObject: Unknown code %s for type %s, writing raw data', code, self.code)
            self.value  = code

do = DAAPObject
