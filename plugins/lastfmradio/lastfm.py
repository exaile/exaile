
import httpclient
import time
import string
import playlist
import sys

class lastfm:

    def __init__(self):
        self.version = "1.3.1.1"
        self.platform = "linux"
        self.host = "ws.audioscrobbler.com"
        self.port = 80
        self.info = None
        self.playlist = playlist.playlist()
        self.debug = 0

    def parselines(self, str):
        res = {}
        vars = string.split(str, "\n")
        numerrors = 0
        for v in vars:
            x = string.split(string.rstrip(v), "=", 1)
            if len(x) == 2:
                res[x[0]] = x[1]
            elif x != [""]:
                print "(urk?", x, ")"
                numerrors = numerrors + 1
            if numerrors > 5:
                print "Too many errors parsing response."
                return {}
        return res

    def connect(self, username, password):

        s = httpclient.httpclient(self.host, self.port)
        s.req("/radio/handshake.php?version=" + self.version + "&platform=" + self.platform + "&username=" + username + "&passwordmd5=" + password + "&language=en&player=lastfmproxy")

        self.info = self.parselines(s.response)


    def getplaylist(self):

        if self.debug:
            sys.stderr.write("Fetching playlist...\n")

        s = httpclient.httpclient(self.info["base_url"])
        s.req(self.info["base_path"] + "/xspf.php?sk=" + self.info["session"] + "&discovery=0&desktop=" + self.version)

        self.playlist.parse(s.response)

        # debug
        if self.debug:
            if len(self.playlist.data.tracks):
                f = open("playlist.xspf", "w")
                f.write(s.response)
                f.close()
            elif False:
                print "No playlist?? Using cached version instead..."
                f = open("playlist.xspf", "r")
                cache = f.read()
                f.close()
                self.playlist.parse(cache)
                self.playlist.pos = 0 #len(self.playlist.data.tracks) -1

        return len(self.playlist.data.tracks)

    def command(self, cmd):
        # commands = skip, love, ban, rtp, nortp

        if self.debug:
            sys.stderr.write("command " + cmd + "\n")

        s = httpclient.httpclient(self.info["base_url"], 80)
        s.req(self.info["base_path"] + "/control.php?command=" + cmd + "&session=" + self.info["session"])
        res = self.parselines(s.response)
        
        if not res.has_key("response") or res["response"] != "OK":
            sys.stderr.write("command " + cmd + " returned:" + repr(res) + "\n")
        
        return res

    def changestation(self, url):
        
        if self.debug:
            sys.stderr.write("changestation " + url + "\n")
        
        s = httpclient.httpclient(self.info["base_url"], 80)
        s.req(self.info["base_path"] + "/adjust.php?session=" + self.info["session"] + "&url=" + url)
        res = self.parselines(s.response)

        if not res.has_key("response") or res["response"] != "OK":
            sys.stderr.write("changestation " + url + " returned:" + repr(res) + "\n")
        
        return res

