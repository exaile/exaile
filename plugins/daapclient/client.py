import http.client
import logging
from io import BytesIO

from spydaap.daap import DAAPError, DAAPObject, DAAPParseCodeTypes


log = logging.getLogger('daapclient')


class DAAPClient:
    def __init__(self):
        self.socket = None
        self.request_id = 0

    #        self._old_itunes = 0

    def connect(self, hostname, port=3689, password=None, user_agent=None):
        if self.socket is not None:
            raise DAAPError("DAAPClient: already connected.")
        #        if ':' in hostname:
        #            raise DAAPError('cannot connect to ipv6 addresses')
        # if it's an ipv6 address
        if ':' in hostname and hostname[0] != '[':
            hostname = '[' + hostname + ']'
        self.hostname = hostname
        self.port = port
        self.password = password
        self.user_agent = user_agent
        #        self.socket = httplib.HTTPConnection(hostname, port)
        self.socket = http.client.HTTPConnection(hostname + ':' + str(port))
        self.getContentCodes()  # practically required
        self.getInfo()  # to determine the remote server version

    def _get_response(self, r, params={}, gzip=1):
        """Makes a request, doing the right thing, returns the raw data"""

        if params:
            l = ['%s=%s' % (k, v) for k, v in params.items()]
            r = '%s?%s' % (r, '&'.join(l))

        log.debug('getting %s', r)

        headers = {'Client-DAAP-Version': '3.0', 'Client-DAAP-Access-Index': '2'}

        if self.user_agent:
            headers['User-Agent'] = self.user_agent

        if gzip:
            headers['Accept-encoding'] = 'gzip'

        if self.password:
            import base64

            b64 = base64.encodestring('%s:%s' % ('user', self.password))[:-1]
            headers['Authorization'] = 'Basic %s' % b64

        # TODO - we should allow for different versions of itunes - there
        # are a few different hashing algos we could be using. I need some
        # older versions of iTunes to test against.
        if self.request_id > 0:
            headers['Client-DAAP-Request-ID'] = self.request_id

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

        response = self.socket.getresponse()
        return response

    def request(self, r, params={}, answers=1):
        """Make a request to the DAAP server, with the passed params. This
        deals with all the cikiness like validation hashes, etc, etc"""

        # this returns an HTTP response object
        response = self._get_response(r, params)
        status = response.status
        content = response.read()
        # if we got gzipped data base, gunzip it.
        if response.getheader("Content-Encoding") == "gzip":
            log.debug("gunzipping data")
            old_len = len(content)
            compressedstream = BytesIO(content)
            import gzip

            gunzipper = gzip.GzipFile(fileobj=compressedstream)
            content = gunzipper.read()
            log.debug("expanded from %s bytes to %s bytes", old_len, len(content))
        # close this, we're done with it
        response.close()

        if status == 401:
            raise DAAPError('DAAPClient: %s: auth required' % r)
        elif status == 403:
            raise DAAPError('DAAPClient: %s: Authentication failure' % r)
        elif status == 503:
            raise DAAPError(
                'DAAPClient: %s: 503 - probably max connections to server' % r
            )
        elif status == 204:
            # no content, ie logout messages
            return None
        elif status != 200:
            raise DAAPError(
                'DAAPClient: %s: Error %s making request' % (r, response.status)
            )

        return self.readResponse(content)

    def readResponse(self, data):
        """Convert binary response from a request to a DAAPObject"""
        data_str = BytesIO(data)
        daapobj = DAAPObject()
        daapobj.processData(data_str)
        return daapobj

    def getContentCodes(self):
        # make the request for the content codes
        response = self.request('/content-codes')
        # now parse and add this information to the dictionary
        DAAPParseCodeTypes(response)

    def getInfo(self):
        self.request('/server-info')

        # detect the 'old' iTunes 4.2 servers, and set a flag, so we use
        # the real MD5 hash algo to verify requests.

    #        version = response.getAtom("apro") or response.getAtom("ppro")
    #        if int(version) == 2:
    #            self._old_itunes = 1

    # response.printTree()

    def login(self):
        response = self.request("/login")
        sessionid = response.getAtom("mlid")
        if sessionid is None:
            log.debug('DAAPClient: login unable to determine session ID')
            return
        log.debug("Logged in as session %s", sessionid)
        return DAAPSession(self, sessionid)


class DAAPSession:
    def __init__(self, connection, sessionid):
        self.connection = connection
        self.sessionid = sessionid
        self.revision = 1

    def request(self, r, params={}, answers=1):
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
        self.request("/logout")
        log.debug('DAAPSession: expired session id %s', self.sessionid)


# the atoms we want. Making this list smaller reduces memory footprint,
# and speeds up reading large libraries. It also reduces the metainformation
# available to the client.
daap_atoms = "dmap.itemid,dmap.itemname,daap.songalbum,daap.songartist,daap.songalbumartist,daap.songformat,daap.songtime,daap.songsize,daap.songgenre,daap.songyear,daap.songtracknumber,daap.songdiscnumber"


class DAAPDatabase:
    def __init__(self, session, atom):
        self.session = session
        self.name = atom.getAtom("minm")
        self.id = atom.getAtom("miid")

    def tracks(self):
        """returns all the tracks in this database, as DAAPTrack objects"""
        response = self.session.request(
            "/databases/%s/items" % self.id, {'meta': daap_atoms}
        )
        # response.printTree()
        track_list = response.getAtom("mlcl").contains
        return [DAAPTrack(self, t) for t in track_list]

    def playlists(self):
        response = self.session.request("/databases/%s/containers" % self.id)
        db_list = response.getAtom("mlcl").contains
        return [DAAPPlaylist(self, d) for d in db_list]


class DAAPPlaylist:
    def __init__(self, database, atom):
        self.database = database
        self.id = atom.getAtom("miid")
        self.name = atom.getAtom("minm")
        self.count = atom.getAtom("mimc")

    def tracks(self):
        """returns all the tracks in this playlist, as DAAPTrack objects"""
        response = self.database.session.request(
            "/databases/%s/containers/%s/items" % (self.database.id, self.id),
            {'meta': daap_atoms},
        )
        track_list = response.getAtom("mlcl").contains
        return [DAAPTrack(self.database, t) for t in track_list]


class DAAPTrack:

    attrmap = {
        'name': 'minm',
        'artist': 'asar',
        'album': 'asal',
        'id': 'miid',
        'type': 'asfm',
        'time': 'astm',
        'size': 'assz',
    }

    def __init__(self, database, atom):
        self.database = database
        self.atom = atom

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        elif name in DAAPTrack.attrmap:
            return self.atom.getAtom(DAAPTrack.attrmap[name])
        raise AttributeError(name)

    def request(self):
        """returns a 'response' object for the track's mp3 data.
        presumably you can strem from this or something"""

        # gotta bump this every track download
        self.database.session.connection.request_id += 1

        # get the raw response object directly, not the parsed version
        return self.database.session.connection._get_response(
            "/databases/%s/items/%s.%s" % (self.database.id, self.id, self.type),
            {'session-id': self.database.session.sessionid},
            gzip=0,
        )

    def save(self, filename):
        """saves the file to 'filename' on the local machine"""
        log.debug("saving to '%s'", filename)
        mp3 = open(filename, "wb")
        r = self.request()
        # doing this all on one lump seems to explode a lot. TODO - what
        # is a good block size here?
        data = r.read(32 * 1024)
        while data:
            mp3.write(data)
            data = r.read(32 * 1024)
        mp3.close()
        r.close()
        log.debug("Done")
