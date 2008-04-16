
import httpclient
import time
import string
import md5

class audioscrobbler:

    def __init__(self):
        self.clientid = "lfp"
        self.clientversion = "0.1"

        self.handshakeurl = "post.audioscrobbler.com"

        # Saved here in case we need to re-handshake later
        self.username = None
        self.password = None
        self.version = None

        self.session = None
        self.nowplayingurl = None
        self.submiturl = None

        self.queue = []

        self.debug = 0

    def hexify(self, s):
        result = ""
        for c in s:
            result = result + ("%02x" % ord(c))
        return result

    def urlencode(self, s):
        result = ""
        for c in s:
            o = ord(c)
            if (o >= ord('a') and o <= ord('z')) or (o >= ord('A') and o <= ord('Z')) or (o >= ord('0') and o <= ord('1')):
                result = result + c
            else:
                result = result + ("%%%02x" % o)
        return result

    def handshake(self, username, password, version):

        self.username = username
        self.password = password

        timestamp = str(int(time.time()))
        auth = self.hexify(md5.md5(password).digest())
        auth = self.hexify(md5.md5(auth + timestamp).digest())
        req = "/?hs=true&p=1.2&c=" + self.clientid + "&v=" + self.clientversion + "&u=" + username + "&t=" + timestamp + "&a=" + auth

        s = httpclient.httpclient(self.handshakeurl)
        s.req(req)
        reslines = string.split(s.response, "\n")

        if self.debug:
            print "audioscrobbler: handshake " + reslines[0]

        if reslines[0] != "OK":
            print "audioscrobbler: Handshake error:"
            print repr(s.response)
            return True

        self.session = reslines[1]
        self.nowplayingurl = reslines[2]
        self.submiturl = reslines[3]
        return False

    def nowplaying(self, artist, track, album, length):
        if not self.session:
            return True

        if self.debug:
            print "audioscrobbler: now playing " + artist + " - " + track

        artist = self.urlencode(artist)
        track = self.urlencode(track)
        album = self.urlencode(album)

        req = "s=" + self.session + "&a=" + artist + "&t=" + track + "&b=" + album + "&l=" + str(length) + "&m="

        s = httpclient.httpclient(self.nowplayingurl)
        s.post(req)
        reslines = string.split(s.response, "\n")

        if reslines[0] != "OK":
            print "audioscrobbler: Now playing error:"
            print repr(s.response)

            if reslines[0] == "BADSESSION":
                self.session = None

            return True

        return False

    def submit(self, artist, track, album, starttime, rating, length, key):
        if not self.session:
            return True

        if self.debug:
            print "audioscrobbler: submitting " + artist + " - " + track

        artist = self.urlencode(artist)
        track = self.urlencode(track)
        album = self.urlencode(album)

        req = "s=" + self.session + "&a[0]=" + artist + "&t[0]=" + track + "&b[0]=" + album + "&r[0]=" + rating + "&i[0]=" + str(starttime) + "&l[0]=" + str(length) + "&o[0]=L" + key + "&n[0]=&m[0]="

        s = httpclient.httpclient(self.submiturl)
        s.post(req)
        reslines = string.split(s.response, "\n")

        if reslines[0] != "OK":
            print "audioscrobbler: Submission error:"
            print repr(s.response)
            
            if reslines[0] == "BADSESSION":
                self.session = None

            self.queue.append( (artist,track,album,starttime,rating,length,key) )

            f = open("scrobblerqueue.txt", "w")
            f.write(repr(self.queue))
            f.close()

            return True

        return False



