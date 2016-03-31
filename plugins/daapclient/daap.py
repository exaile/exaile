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

import struct, sys, httplib
import logging
from daap_data import *
from cStringIO import StringIO

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
            value = ''
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
            value = self.value
            if type(value) == float:
                value = int(value)
            if self.type == 'v':
                value = value.split('.')
                value = struct.pack('!HH', int(value[0]), int(value[1]))
                packing = "4s"
            elif self.type == 'l':
                packing = 'q'
            elif self.type == 'ul':
                packing = 'Q'
            elif self.type == 'i':
                if (type(value) == str and len(value) <= 4):
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
                if type(value) == unicode:
                    value = value.encode('utf-8')
                packing = '%ss' % len(value)
            else:
                raise DAAPError('DAAPObject: encode: unknown code %s' % self.code)
                return
            # calculate the length of what we're packing
            length  = struct.calcsize('!%s' % packing)
            # pack: 4 characters for the code, 4 bytes for the length, and 'length' bytes for the value
            data = struct.pack('!4sI%s' % (packing), self.code, length, value)
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


class DAAPClient(object):
    def __init__(self):
        self.socket = None
        self.request_id = 0
#        self._old_itunes = 0

    def connect(self, hostname, port = 3689, password = None):
        if self.socket != None:
            raise DAAPError("DAAPClient: already connected.")
#        if ':' in hostname:
#            raise DAAPError('cannot connect to ipv6 addresses')
# if it's an ipv6 address
        if ':' in hostname and hostname[0] != '[':
            hostname = '['+hostname+']'
        self.hostname = hostname
        self.port     = port
        self.password = password
#        self.socket = httplib.HTTPConnection(hostname, port)
        self.socket = httplib.HTTPConnection(hostname+':'+str(port))
        self.getContentCodes() # practically required
        self.getInfo() # to determine the remote server version

    def _get_response(self, r, params = {}, gzip = 1):
        """Makes a request, doing the right thing, returns the raw data"""

        if params:
            l = ['%s=%s' % (k, v) for k, v in params.iteritems()]
            r = '%s?%s' % (r, '&'.join(l))

        log.debug('getting %s', r)

        headers = {
            'Client-DAAP-Version': '3.0',
            'Client-DAAP-Access-Index': '2',
        }

        if gzip: headers['Accept-encoding'] = 'gzip'
        
        if self.password:
            import base64
            b64 = base64.encodestring( '%s:%s'%('user', self.password) )[:-1]
            headers['Authorization'] = 'Basic %s' % b64             

        # TODO - we should allow for different versions of itunes - there
        # are a few different hashing algos we could be using. I need some
        # older versions of iTunes to test against.
        if self.request_id > 0:
            headers[ 'Client-DAAP-Request-ID' ] = self.request_id

#        if (self._old_itunes):
#            headers[ 'Client-DAAP-Validation' ] = hash_v2(r, 2)
#        else:
#            headers[ 'Client-DAAP-Validation' ] = hash_v3(r, 2, self.request_id)

        # there are servers that don't allow >1 download from a single HTTP
        # session, or something. Reset the connection each time. Thanks to
        # Fernando Herrera for this one.
        self.socket.close()
        self.socket.connect()

        self.socket.request('GET', r, None, headers)

        response    = self.socket.getresponse()
        return response;

    def request(self, r, params = {}, answers = 1):
        """Make a request to the DAAP server, with the passed params. This
        deals with all the cikiness like validation hashes, etc, etc"""

        # this returns an HTTP response object
        response    = self._get_response(r, params)
        status = response.status
        content = response.read()
        # if we got gzipped data base, gunzip it.
        if response.getheader("Content-Encoding") == "gzip":
            log.debug("gunzipping data")
            old_len = len(content)
            compressedstream = StringIO( content )
            import gzip
            gunzipper = gzip.GzipFile(fileobj=compressedstream)
            content = gunzipper.read()
            log.debug("expanded from %s bytes to %s bytes", old_len, len(content))
        # close this, we're done with it
        response.close()

        if status == 401:
            raise DAAPError('DAAPClient: %s: auth required'%r)
        elif status == 403:
            raise DAAPError('DAAPClient: %s: Authentication failure'%r)
        elif status == 503:
            raise DAAPError('DAAPClient: %s: 503 - probably max connections to server'%r)
        elif status == 204:
            # no content, ie logout messages
            return None
        elif status != 200:
            raise DAAPError('DAAPClient: %s: Error %s making request'%(r, response.status))

        return self.readResponse( content )

    def readResponse(self, data):
        """Convert binary response from a request to a DAAPObject"""
        str = StringIO(data)
        object  = DAAPObject()
        object.processData(str)
        return object

    def getContentCodes(self):
        # make the request for the content codes
        response = self.request('/content-codes')
        # now parse and add this information to the dictionary
        DAAPParseCodeTypes(response)

    def getInfo(self):
        response = self.request('/server-info')

        # detect the 'old' iTunes 4.2 servers, and set a flag, so we use
        # the real MD5 hash algo to verify requests.
#        version = response.getAtom("apro") or response.getAtom("ppro")
#        if int(version) == 2:
#            self._old_itunes = 1

        # response.printTree()

    def login(self):
        response = self.request("/login")
        sessionid   = response.getAtom("mlid")
        if sessionid == None:
            log.debug('DAAPClient: login unable to determine session ID')
            return
        log.debug("Logged in as session %s", sessionid)
        return DAAPSession(self, sessionid)


class DAAPSession(object):

    def __init__(self, connection, sessionid):
        self.connection = connection
        self.sessionid  = sessionid
        self.revision   = 1

    def request(self, r, params = {}, answers = 1):
        """Pass the request through to the connection, adding the session-id
        parameter."""
        params['session-id'] = self.sessionid
        return self.connection.request(r, params, answers)

    def update(self):
        response = self.request("/update")
        self.revision = response.getAtom('musr')
#        return response

    def databases(self):
        response = self.request("/databases")
        db_list = response.getAtom("mlcl").contains
        return [DAAPDatabase(self, d) for d in db_list]

    def library(self):
        # there's only ever one db, and it's always the library...
        return self.databases()[0]

    def logout(self):
        response = self.request("/logout")
        log.debug('DAAPSession: expired session id %s', self.sessionid)


# the atoms we want. Making this list smaller reduces memory footprint,
# and speeds up reading large libraries. It also reduces the metainformation
# available to the client.
daap_atoms = "dmap.itemid,dmap.itemname,daap.songalbum,daap.songartist,daap.songformat,daap.songtime,daap.songsize,daap.songgenre,daap.songyear,daap.songtracknumber"

class DAAPDatabase(object):

    def __init__(self, session, atom):
        self.session = session
        self.name = atom.getAtom("minm")
        self.id = atom.getAtom("miid")

    def tracks(self):
        """returns all the tracks in this database, as DAAPTrack objects"""
        response = self.session.request("/databases/%s/items"%self.id, {
            'meta':daap_atoms
        })
        #response.printTree()
        track_list = response.getAtom("mlcl").contains
        return [DAAPTrack(self, t) for t in track_list]

    def playlists(self):
        response = self.session.request("/databases/%s/containers"%self.id)
        db_list = response.getAtom("mlcl").contains
        return [DAAPPlaylist(self, d) for d in db_list]


class DAAPPlaylist(object):

    def __init__(self, database, atom):
        self.database = database
        self.id = atom.getAtom("miid")
        self.name = atom.getAtom("minm")
        self.count = atom.getAtom("mimc")

    def tracks(self):
        """returns all the tracks in this playlist, as DAAPTrack objects"""
        response = self.database.session.request("/databases/%s/containers/%s/items"%(self.database.id,self.id), {
            'meta':daap_atoms
        })
        track_list = response.getAtom("mlcl").contains
        return [DAAPTrack(self.database, t) for t in track_list]


class DAAPTrack(object):

    attrmap = {'name':'minm',
        'artist':'asar',
        'album':'asal',
        'id':'miid',
        'type':'asfm',
        'time':'astm',
        'size':'assz'}

    def __init__(self, database, atom):
        self.database = database
        self.atom = atom

    def __getattr__(self, name):
        if self.__dict__.has_key(name):
            return self.__dict__[name]
        elif DAAPTrack.attrmap.has_key(name):
            return self.atom.getAtom(DAAPTrack.attrmap[name])
        raise AttributeError(name)

    def request(self):
        """returns a 'response' object for the track's mp3 data.
        presumably you can strem from this or something"""

        # gotta bump this every track download
        self.database.session.connection.request_id += 1

        # get the raw response object directly, not the parsed version
        return self.database.session.connection._get_response(
            "/databases/%s/items/%s.%s"%(self.database.id, self.id, self.type),
            { 'session-id':self.database.session.sessionid },
            gzip = 0,
        )

    def save(self, filename):
        """saves the file to 'filename' on the local machine"""
        log.debug("saving to '%s'", filename)
        mp3 = open(filename, "wb")
        r = self.request()
        # doing this all on one lump seems to explode a lot. TODO - what
        # is a good block size here?
        data = r.read(32 * 1024)
        while (data):
          mp3.write(data)
          data = r.read(32 * 1024)
        mp3.close()
        r.close()
        log.debug("Done")


if __name__ == '__main__':
    def main():
        connection  = DAAPClient()

        # I'm new to this python thing. There's got to be a better idiom
        # for this.
        try: host = sys.argv[1]
        except IndexError: host = "localhost"
        try: port = sys.argv[2]
        except IndexError: port = 3689

        logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(levelname)s %(message)s')

        try:
            # do everything in a big try, so we can disconnect at the end

            connection.connect( host, port )

            # auth isn't supported yet. Just log in
            session     = connection.login()

            library = session.library()
            log.debug("Library name is '%s'", repr(library.name))

            tracks = library.tracks()

            # demo - save the first track to disk
            #print("Saving %s by %s to disk as 'track.mp3'"%(tracks[0].name, tracks[0].artist))
            #tracks[0].save("track.mp3")
            if len(tracks) > 0 :
                tracks[0].atom.printTree()
            else:
                print('No Tracks')
            session.update()
            print(session.revision)

        finally:
            # this here, so we logout even if there's an error somewhere,
            # or itunes will eventually refuse more connections.
            print("--------------")
            try:
                session.logout()
            except Exception: pass

    main()

