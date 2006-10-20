# $Id$

"""
~~~~~~~~~~~
PyScrobbler
~~~~~~~~~~~

Python Classes for AudioScrobbler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A set of python classes for interacting with the Last.fm AudioScrobbler
services.

AudioScrobblerQuery
    AudioScrobblerQuery is used to consume the web services that provide
    similar artists, charts, tags and so on
    
AudioScrobblerPost
    AudioScrobblerPost is used to update your personal play information for
    those of you (like me) who've been stoopid enough to write your own player.
    
AudioScrobblerQuery: AudioScrobbler Web Service Consumption
=============================================================

A set of classes for consuming the AudioScrobbler web services.
Currently we consume protocol 1.0, as defined at:
http://www.audioscrobbler.net/data/webservices

Basic usage
-----------
>>> lips = AudioScrobblerQuery(artist='The Flaming Lips')
>>> for artist in lips.similar():
...     print artist.name, artist.mbid
... 

or

>>> for i in AudioScrobblerQuery(user='offmessage').topalbums()
...     print i.name, i.image.small
... 

A certain number of the services take a querystring (for example a user's
weekly artist chart takes a start and end date).  These can be passed as
follows:

>>> offmessage = AudioScrobblerQuery(user='offmessage')
>>> for i in offmessage.weeklyartistchart(_from=1114965332, to=1115570132):
...     print i.name, i.chartposition
... 

Note that we have had to prefix the ``from`` keyword with an underscore
(``_``). This is because ``from`` is a reserved word in Python and can't be 
used as a parameter name.  Any parameter passed with a leading underscore will 
have that underscore stripped (so ``_from`` is passed as ``from``, as ``_foo`` 
would be passed as ``foo``).

If an element has an attribute (for example the artist has an ``mbid`` in
/user/.../topalbums.xml) these can be accessed as a dictionary key of that
element:

>>> offmessage = AudioScrobblerQuery(user='offmessage')
>>> for i in offmessage.topalbums():
...     print i.name, i.artist, i.artist['mbid']
... 

if you're not sure if an element has an attribute they can be accessed instead
using the ``get()`` method:

>>> offmessage = AudioScrobblerQuery(user='offmessage')
>>> for i in offmessage.topalbums():
...     print i.name, i.artist, i.artist.get('mbid', '')
... 

More control
------------
There are 2 additional keyword arguments that you can offer at the point of
instantiation of the AudioScrobblerQuery object:

host
    If the lovely people at Last.fm change their server name, or if you set up
    some kind of local proxy of their services you can set the host from which
    you get the XML.
    
    Usage:
    >>> lips = AudioScrobblerQuery(artist='The Flaming Lips', 
    ...                              host='audioscrobbler.isotoma.com')
    
    Default is ``'ws.audioscrobbler.com'``
    
version
    If another version of the web services is released, and this code still
    holds up you can set the protocol version at instantiation.  This is 
    inserted into the request URL at the correct point (i.e. 
    ws.audioscrobbler.com/**1.0**/artist/The+Flaming+Lips).
    
    Usage:
    >>> lips = AudioScrobberRequest(artist='The Flaming Lips', version='1.1')
    
    Default is ``'1.0'``

Caching
-------
Each instance of the ``AudioScrobblerQuery`` maintains its own internal cache
of requests, which are checked against the server's response.  If the server
returns a ``304`` (content not modified) we return the cached value, otherwise
we return the result that the server gave us.

This is all well and good, however at the time of writing the
``ws.audioscrobbler.com`` server does not support the ``304`` response for all
pages, so you may find yourself making requests that you are sure should be
cached, but in fact aren't.

For example:
http://ws.audioscrobbler.com/1.0/user/offmessage/topalbums.xml returns a ``304``
http://ws.audioscrobbler.com/1.0/artist/The+Flaming+Lips/similar.xml does not

I have assumed that this is for a reason, and as such honour this behaviour.
If a page does not return a ``Last-Modified`` header we do not cache it.  Any
page that does return such a header (but not the ``Pragma: no-cache`` header)
gets cached.  Any page that does return a ``Last-Modified`` header gets exactly
what it sent to us sent back to it as the ``If-Modified-Since``.  This is a fit
of pragmatism based on the fact that calculating local dates and avoiding
clock disparaties is not worth the effort.

Also, note that the AudioScrobbler servers do not return the ``ETag`` header 
and so we do not look for it or refer to it.

A last note
-----------
These classes are for consuming the AudioScrobbler web services.  As such each
of the classes here have no ``set``, ``__setitem__`` or ``__setattr__``
methods.  They are read only.  If you want to actually manipulate the
resulting XML you should access the underlying ElementTree_ instances directly
using either the ``raw()`` or ``element()`` methods provided.  You can then 
make use of the innate power of those classes directly:

``raw()`` returns an ElementTree:

>>> tree = AudioScrobblerQuery(user='offmessage').topalbums().raw()

while ``element()`` returns an Element at the point within the tree that you
currently are:

>>> lips = AudioScrobblerQuery(artist='The Flaming Lips')
>>> elements = [ x.name.element() for x in lips.similar() ]

which is equivalent to:

>>> lips = AudioScrobberRequest(artist='The Flaming Lips')
>>> elements = lips.similar().raw().findall('*/name')

As an alternative you could also look at XMLTramp_, which is another XML
manipulator designed primarily for consuming web services (and used in the
FlickrClient_ script that gave me much inspiration for these classes).

Last but not least a mention should go to BeautifulSoup_, just because it is
the most powerful and flexible of this type of application that I've used.  It
specialises in badly formed XML/HTML though, and luckily is not required in
this instance.  That said, it's a powerful beast and you should have a look at
it the minute your requirements become more complex than this code supports.

.. _ElementTree: http://effbot.org/zone/element.htm
.. _XMLTramp: http://www.aaronsw.com/2002/xmltramp/
.. _BeautifulSoup: http://www.crummy.com/software/BeautifulSoup/


AudioScrobblerPost: Update Your Personal Play History
=====================================================

A set of classes for posting playlist information to your Last.fm account.
Please note that you will need your own account to use these classes.

Some stuff about the time management and internal cache should go here.

Basic usage
-----------
>>> track = dict(artist_name="The Flaming Lips",
                 song_title="The Yeah Yeah Yeah Song",
                 length=291,
                 date_played="2006-04-29 04:20:00", 
                 album="At War With The Mystics",
                 mbid=""
                )
>>> post = AudioScrobblerPost(user='offmessage', password='mypasswd')
>>> post(**track)
>>> 

More control
------------
There are a number of keywords that can be passed at the time of instantiation
of the ``AudioScrobblerPost`` class:

verbose
    Boolean.  If you pass ``verbose=True`` every log line is also printed.
    Useful for debugging and in interactive scripts.
    
client_name
    By default pyscrobbler uses the ``tst`` client name.  If you deploy these
    classes in an application with a wide user base it seems to be advisable to
    apply for your own client name.  If lots of people start to use these
    classes as is I will apply for a unique name for them.  If you have your
    own, pass it in here (as a string)
    
client_version
    Currently we use ``1.0``.  This is because we are using the ``tst`` client
    name (see above) and anything lower seems to raise an ``UPDATE`` message
    from the post server at handshake.
    
protocol_version
    By default we use ``1.1``.  These classes are not compatible with Protocol
    1.0.  It's unlikely they will be compatible with any later versions.  The
    changes between 1.0 and 1.1 were pretty major; I can't see they'd be any
    less major for the next version.
    
host
    By default we use ``post.audioscrobbler.com``.  If the server name changes
    (or you want to run tests) you can pass a different host name here.  In
    fact, the url that we authenticate against is built as
    ``"http://%s/?%s" % (host, params)`` so as long as your host string makes
    a valid url in that format, go for it.  Note the trailing slash between
    host and the query string.  This seems to be a requirement of urllib2.  This
    means that your test auth script should be able to be called that way.

Putting them to use in real life
================================
Some advice on using these classes.

``timeout``
-----------
I've not done anything about the socket timeout on the running system.  It's
not really this code's place to do anything about it, but it is something that
probably needs sorting out, otherwise your scripts will hang for as long as your 
timeout setting if there is a problem with the Last.fm servers (which there
appears to be fairly frequently with the submissions servers).

Generally, if you are on a slow link or one with poor latency you can up the 
timeout so that your requests don't keep failing unnecessarily.  However, if
you're on a quick link you may want to lower it as low as 10 seconds, as the
wait can be agonising if you're making a few requests and the server is not
responding.

Thanks
======
I took a considerable amount of inspiration from Michael Campeotto's
FlickrClient_ script for AudioScrobblerQuery

I've taken even greater amounts of inspiration from Mike Bleyer's
iPodScrobbler_ script for AudioScrobblerPost.

.. _FlickrClient: http://micampe.it/things/flickrclient
.. _iPodScrobbler: http://www.hoc.net/mike/source/iPodScrobbler/


TODO
====
Mad leet reStructuredText epydoc mashup
    Get that sorted.

Example query script
    Actually write some example query scripts :)
    
Document use of the factory class
    AudioScrobbler
    
"""

__author__ = "Andy Theyers <andy@isotoma.com>"
__version__ = "$Revision$"[11:-2]
__docformat__ = "restructuredtext"


import datetime, locale, md5, pickle, re, site, sys, time, urllib, urllib2

from elementtree.ElementTree import ElementTree

# This is lifted in the most part from iPodScrobbler (see docs above)
# Get the base local encoding
enc = 'ascii'
try:
    enc = site.encoding
except:
    pass
if enc == 'ascii' and locale.getpreferredencoding():
    enc = locale.getpreferredencoding()
# if we are on MacOSX, we default to UTF8
# because apples python reports 'ISO8859-1' as locale, but MacOSX uses utf8
if sys.platform=='darwin':
    enc = 'utf8'

# AudioScrobblerQuery configuration settings
audioscrobbler_request_version = '1.0'
audioscrobbler_request_host = 'ws.audioscrobbler.com'

# AudioScrobblerPost configuration settings
audioscrobbler_post_version = u'1.1'
audioscrobbler_post_host = 'post.audioscrobbler.com'
client_name = u'tst'
pyscrobbler_version = u'1.0' # This is set to 1.0 while we use
                             # client_name = u'tst' as we keep getting
                             # UPDATE responses with anything less.

class AudioScrobblerError(Exception):
    
    """
    The base AudioScrobbler error from which all our other exceptions derive
    """
    
    def __init__(self, message):
        """ Create a new AudioScrobblerError.

            :Parameters:
                - `message`: The message that will be displayed to the user
        """
        self.message = message
    
    def __repr__(self):
        msg = "%s: %s"
        return msg % (self.__class__.__name__, self.message,)
    
    def __str__(self):
        return self.__repr__()

class AudioScrobblerConnectionError(AudioScrobblerError):
    
    """
    The base network error, raise by invalid HTTP responses or failures to
    connect to the server specified (DNS, timeouts, etc.)
    """
    
    def __init__(self, type, code, message):
        self.type = type
        self.code = code
        self.message = message
    
    def __repr__(self):
        msg = "AudioScrobblerConnectionError: %s: %s %s"
        return msg % (self.type.upper(), self.code, self.message,)
    
class AudioScrobblerTypeError(AudioScrobblerError):
    
    """
    If we would normally raise a TypeError we raise this instead
    """
    pass
    

class AudioScrobblerPostUpdate(AudioScrobblerError):
    
    """
    If the POST server returns an ``UPDATE`` message we raise this exception.
    This is the only case when this exception is raised, allowing you to
    happily ignore it.
    """
    
    def __repr__(self):
        msg = "An update to your AudioScrobbler client is available at %s"
        return msg % (self.message,)


class AudioScrobblerPostFailed(AudioScrobblerError):
    
    """
    If the POST server returns an ``FAILED`` message we raise this exception.
    """
    
    def __repr__(self):
        msg = "Posting track to AudioScrobbler failed.  Reason given: %s"
        return msg % (self.message,)


class AudioScrobblerHandshakeError(AudioScrobblerError):
    
    """
    If we fail the handshake this is raised.  If you're running in a long
    running process you should pass on this error, as the system keeps a
    cache which ``flushcache()`` will clear for you when the server is back.
    """
    pass

class AudioScrobbler:
    
    """ Factory for Queries and Posts.  Holds configuration for the session """
    
    def __init__(self,
                 audioscrobbler_request_version=audioscrobbler_request_version,
                 audioscrobbler_post_version=audioscrobbler_post_version,
                 audioscrobbler_request_host=audioscrobbler_request_host,
                 audioscrobbler_post_host=audioscrobbler_post_host,
                 client_name=client_name,
                 client_version=pyscrobbler_version):
                 
        self.audioscrobbler_request_version=audioscrobbler_request_version
        self.audioscrobbler_post_version=audioscrobbler_post_version
        self.audioscrobbler_request_host=audioscrobbler_request_host
        self.audioscrobbler_post_host=audioscrobbler_post_host
        self.client_name=client_name
        self.client_version=pyscrobbler_version
        
    def query(self, **kwargs):
        
        """ Create a new AudioScrobblerQuery """
        
        if len(kwargs) != 1:
            raise TypeError("__init__() takes exactly 1 argument, %s "
                            "given" % (len(kwargs),))
        ret = AudioScrobblerQuery(version=self.audioscrobbler_request_version,
                                  host=self.audioscrobbler_request_host,
                                  **kwargs)
        return ret
        
    def post(self, username, password, verbose=False):
        
        """ Create a new AudioScrobblerPost """
        
        ret = AudioScrobblerPost(username=username.encode('utf8'),
                                 password=password.encode('utf8'),
                                 host=self.audioscrobbler_post_host,
                                 protocol_version=self.audioscrobbler_post_version,
                                 client_name=self.client_name,
                                 client_version=self.client_version,
                                 verbose=verbose)
        return ret
        

class AudioScrobblerCache:
    def __init__(self, elemtree, last):
        self.elemtree = elemtree
        self.requestdate = last
        
    def created(self):
        return self.requestdate
        
    def gettree(self):
        return self.elemtree

        
class AudioScrobblerQuery:
    
    def __init__(self,
                 version=audioscrobbler_request_version, 
                 host=audioscrobbler_request_host, 
                 **kwargs):
        
        if len(kwargs) != 1:
            raise TypeError("__init__() takes exactly 1 audioscrobbler "
                            "request argument, %s given" % str(len(kwargs))
                           )
        self.type = kwargs.keys()[0]
        self.param = str(kwargs[self.type])
        self.baseurl = 'http://%s/%s/%s/%s' % (host, 
                                               version, 
                                               urllib.quote(self.type), 
                                               urllib.quote(self.param), 
                                              )
        self._cache = {}
        
    def __getattr__(self, name):
        def method(_self=self, name=name, **params):
            # Build the URL
            url = '%s/%s.xml' % (_self.baseurl, urllib.quote(name))
            if len(params) != 0:
                for key in params.keys():
                    # This little mess is required to get round the fact that
                    # 'from' is a reserved word and can't be passed as a
                    # parameter name.
                    if key.startswith('_'):
                        params[key[1:]] = params[key]
                        del params[key]
                url = '%s?%s' % (url, urllib.urlencode(params))
            req = urllib2.Request(url)
            
            # Check the cache
            cache = _self._cache
            if url in cache and cache[url].created() is not None:
                req.add_header('If-Modified-Since', cache[url].created())
            
            # Open the URL and test the response
            try:
                response = urllib2.urlopen(url)
            except urllib2.HTTPError, error:
                if error.code == 304:
                    return AudioScrobblerItem(cache[url].getroot(), _self, url)
                if error.code == 400:
                    raise AudioScrobblerConnectionError('ws', 400, error.fp.read())
                raise AudioScrobblerConnectionError('http', error.code, error.msg)
            except urllib2.URLError, error:
                code = error.reason.args[0]
                message = error.reason.args[1]
                raise AudioScrobblerConnectionError('network', code, message)
            elemtree = ElementTree(file=response)
            if response.headers.get('pragma', None) != 'no-cache':
                last_modified = response.headers.get('last-modified', None)
            else:
                last_modified = None
            _self._cache[url] = AudioScrobblerCache(elemtree, last_modified)
            return AudioScrobblerItem(elemtree.getroot(), _self, url)
        return method
        
    def __repr__(self):
        return "AudioScrobblerQuery(%s='%s')" % (self.type, self.param)
        
    def __str__(self):
        return self.__repr__()

        
class AudioScrobblerItem:
    
    def __init__(self, element, parent, url=None):
        self._element = element
        self._parent = parent
        self.tag = element.tag
        self.text = element.text
        self._url = url
        if self._url is None:
            self._url = self._parent._url
    
    def __repr__(self):
        if isinstance(self._parent, AudioScrobblerQuery):
            return "<AudioScrobbler response from %s>" % (self._url,)
        return "<AudioScrobbler %s element at %s>" % (self.tag, id(self))
        
    def __str__(self):
        if self.text is None:
            return ''
        text = self.text
        try:
            retval = text.encode(enc)
        except AttributeError:
            retval = text
        return retval
    
    def __getattr__(self, name):
        result = self._element.findall(name)
        if len(result) == 0:
            raise AttributeError("AudioScrobbler %s element has no "
                                 "subelement '%s'" % (self.tag, name)
                                )
        ret = [ AudioScrobblerItem(i, self) for i in result ]
        if len(ret) == 1:
            return ret[0]
        return ret
    
    def __iter__(self):
        for i in self._element:
            yield AudioScrobblerItem(i, self)
            
    def __getitem__(self, i):
        return self._element.attrib[i]
        
    def get(self, i, default):
        if i in self._element.attrib:
            return self._element.attrib[i]
        else:
            return default
        
    def __getslice__(self, i, j):
        return [ AudioScrobblerItem(x, self) for x in self._element[i:j] ]
    
    def raw(self):
        def getparent(obj):
            if isinstance(obj._parent, AudioScrobblerQuery):
                return obj._parent
            return getparent(obj._parent)
        return getparent(self)._cache[self._url].gettree()
    
    def element(self):
        return self._element


class AudioScrobblerPost:
    
    """
    Provide the ability to post tracks played to a user's Last.fm
    account
    """
    
    def __init__(self,
                 username=u'',
                 password=u'',
                 client_name=client_name,
                 client_version=pyscrobbler_version,
                 protocol_version=audioscrobbler_post_version,
                 host=audioscrobbler_post_host,
                 verbose=False):
    
        # Capture the information passed for future use
        self.params = dict(username=username,
                           password=password,
                           client_name=client_name,
                           client_version=client_version,
                           protocol_version=protocol_version,
                           host=host)
        
        self.verbose = verbose
        
        self.auth_details = {}
        self.last_post = None
        self.interval = 0
        self.cache = []
        self.loglines = []
        self.last_shake = None
        self.authenticated = False
        self.updateurl = None
        self.posturl = None
        
    def auth(self):
        
        """ Authenticate against the server """
        
        if self.authenticated:
            return True
        now = datetime.datetime.utcnow()
        interval = datetime.timedelta(minutes=30)
        if self.last_shake is not None and self.last_shake + interval > now:
            last_shake_string = self.last_shake.strftime("%Y-%m-%d %H:%M:%S")
            msg = ("Tried to reauthenticate too soon after last try "
                   "(last try at %s)" % (last_shake_string,))
            raise AudioScrobblerHandshakeError(msg)
        
        p = {}
        p['hs'] = 'true'
        p['u'] = self.params['username']
        p['c'] = self.params['client_name']
        p['v'] = self.params['client_version']
        p['p'] = self.params['protocol_version']
        plist = [(k, urllib.quote_plus(v.encode('utf8'))) for k, v in p.items()]
        
        authparams = urllib.urlencode(plist)
        url = 'http://%s/?%s' % (self.params['host'], authparams)
        req = urllib2.Request(url)
        try:
            url_handle = urllib2.urlopen(req)
        except urllib2.HTTPError, error:
            self.authenticated = False
            raise AudioScrobblerConnectionError('http', error.code, error.msg)
        except urllib2.URLError, error:
            self.authenticated = False
            code = error.reason.args[0]
            message = error.reason.args[1]
            raise AudioScrobblerConnectionError('network', code, message)
        
        self.last_shake = datetime.datetime.utcnow()
        response = url_handle.readlines()
        if len(response) == 0:
            raise AudioScrobblerHandshakeError('Got nothing back from the server')
        
        # Get the interval if there is one
        find_interval = re.match('INTERVAL (\d+)', response[-1])
        if find_interval is not None:
            self.interval = int(find_interval.group(1))
            
        username = self.params['username']
        password = self.params['password']
        # First we test the best and most likely case
        if response[0].startswith('UPTODATE'):
            ask = response[1].strip()
            answer = md5.md5(md5.md5(password).hexdigest() + ask).hexdigest()
            self.auth_details['u'] = urllib.quote_plus(username.encode('utf8'))
            self.auth_details['s'] = answer
            self.posturl = response[2].strip()
            self.authenticated = True
            
        # Next we test the least significant failure.
        elif response[0].startswith('UPDATE'):
            updateurl = result[0][7:].strip()
            
            ask = response[1].strip()
            answer = md5.md5(md5.md5(password).hexdigest() + ask).hexdigest()
            
            self.auth_details['u'] = urllib.quote_plus(username.encode('utf8'))
            self.auth_details['s'] = answer
            self.posturl = response[2].strip()
            self.authenticated = True
            self.updateavailable = updateurl
            
        # Then the various failure states....
        elif response[0].startswith('BADUSER'):
            self.authenticated = False
            msg = "Username '%s' unknown by Last.fm"
            raise AudioScrobblerHandshakeError(msg % (username,))
            
        elif response[0].startswith('FAILED'):
            self.authenticated = False
            reason = response[0][6:]
            msg = reason.decode('utf8').encode(enc)
            raise AudioScrobblerHandshakeError(msg)
            
        else:
            self.authenticated = False
            msg = "Unknown response from server: %r" % (response,)
            raise AudioScrobblerHandshakeError(msg)
            
    def posttrack(self, 
                  artist_name,
                  song_title,
                  length,
                  date_played, 
                  album=u'',
                  mbid=u''):
        
        """
        Add the track to the local cache, and try to post it to the server
        """
        
        self.addtrack(artist_name=artist_name,
                      song_title=song_title,
                      length=length,
                      date_played=date_played,
                      album=album,
                      mbid=mbid)
        self.post()
        
    __call__ = posttrack
    
    def addtrack(self, 
                 artist_name,
                 song_title,
                 length,
                 date_played, 
                 album=u'',
                 mbid=u''):
        
        """ Add a track to the local cache """
        
        # Quick sanity check on track length
        if type(length) == type(0):
            sane_length = length
        elif type(length) == type('') and length.isdigit():
            sane_length = int(length)
        else:
            sane_length = -1
        
        # If the track length is less than 30 move on
        if sane_length < 30:
            msg = ("Track '%s' by '%s' only %s seconds in length, so "
                   "not added" % (song_title, artist_name, sane_length))
            self.log(msg)
        # Otherwise build the track dictionary and add it to the local cache
        else:
            track = {'a[%s]': artist_name.decode(enc).encode('utf8'),
                     't[%s]': song_title.decode(enc).encode('utf8'),
                     'l[%s]': str(sane_length),
                     'i[%s]': date_played,
                     'b[%s]': album.decode(enc).encode('utf8'),
                     'm[%s]': mbid.encode('utf8'),
                    }
            self.cache.append(track)
        
    def post(self):
        
        """
        Post the tracks by popping the first ten off the cache and attempting
        to post them.
        """
        
        if len(self.cache) == 0:
            return
        if len(self.cache) > 10:
            number = 10
        else:
            number = len(self.cache)
        
        params = {}
        count = 0
        for track in self.cache[:number]:
            for k in track.keys():
                params[k % (count,)] = track[k]
        
        self.auth()
        params.update(self.auth_details)
        postdata = urllib.urlencode(params)
        req = urllib2.Request(url=self.posturl, data=postdata)
        
        now = datetime.datetime.utcnow()
        interval = datetime.timedelta(seconds=self.interval)
        if self.last_post is not None and self.last_post + interval > now:
            time.sleep(self.interval)
        try:
            url_handle = urllib2.urlopen(req)
        except urllib2.HTTPError, error:
            raise AudioScrobblerConnectionError('http', error.code, error.msg)
        except urllib2.URLError, error:
            args = getattr(error.reason, 'args', None)
            code = '000'
            message = str(error)
            if args is not None:
                if len(args) == 1:
                    message = error.reason.args[0]
                elif len(args) == 2:
                    code = error.reason.args[0]
                    message = error.reason.args[1]
            raise AudioScrobblerConnectionError('network', code, message)
        
        self.last_post = now
        response = url_handle.readlines()
        
        # Get the interval if there is one
        find_interval = re.match('INTERVAL (\d+)', response[-1])
        if find_interval is not None:
            self.interval = int(find_interval.group(1))
            
        # Test the various responses possibilities:
        if response[0].startswith('OK'):
            self.log("Uploaded %s tracks successfully" % (number,))
            del self.cache[:number]
        elif response[0].startswith('BADAUTH'):
            self.log("Got BADAUTH")
            self.authenticated = False
        elif response[0].startswith('FAILED'):
            reason = response[0][6:].strip()
            raise AudioScrobblerPostFailed(reason)
        else:
            msg = "Server returned something unexpected"
            raise AudioScrobblerPostFailed(msg)
        
    def flushcache(self):
        
        """ Post all the tracks in the cache """
        
        while len(self.cache) > 0:
            self.post()
        
    def log(self, msg):
        
        """ Add a line to the log, print it if verbose """
        
        time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.loglines.append("%s: %s" % (time, msg))
        if self.verbose:
            print self.loglines[-1]
            
    def getlog(self, clear=False):
        
        """ Return the entire log, clear it if requested """
        
        if clear:
            retval = self.loglines
            self.loglines = []
            return retval
        return self.loglines
