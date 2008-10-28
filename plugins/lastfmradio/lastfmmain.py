#!/usr/bin/python

import sys
import time
import socket
import md5
import threading
import cgi
import os
import string

import config
import lastfm
import _scrobbler as scrobbler

True = 1
False = 0


class proxy:

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.lastfm = None
        self.audioscrobbler = None
        self.bookmarks = []
        self.lasttracks = []
        self.basedir = "."
        self.quit = False
        self.skip = 0
        self.stop = False
        self.version = "1.3b"
        self.streaming = 0
        self.recordtoprofile = 1
        self.starttime = 0
        self.rating = ""
        self.proxy_ready = False
        self.np_image_func = None
        self.last_cover = ''

        self.extraheaders = string.join([
                "Server: LastFMProxy/" + self.version + "\r\n",
                "Pragma: no-cache\r\n",
                "Cache-Control: max-cache=0\r\n"
                ], "");

    def hexify(self, s):
        result = ""
        for c in s:
            result = result + ("%02x" % ord(c))
        return result

    def storebookmark(self, station):
        newbookmarks = []
        newbookmarks.append(station)
        for s in self.bookmarks:
            if s != station:
                newbookmarks.append(s)

        self.bookmarks = newbookmarks
        if len(self.bookmarks) > 10:
            self.bookmarks = self.bookmarks[:10]

        f = open(os.path.join(self.basedir, "bookmarks.txt"), "w")
        for s in self.bookmarks:
            f.write(s + "\n")
        f.close()

    def storetrack(self, track):
        if len(self.lasttracks) > 0 and track == self.lasttracks[0]:
            return
        self.lasttracks = ([ track ] + self.lasttracks)[:6]

    def gotconnection(self, clientsock):
        metaint = 1024*32
        sendmetadata = False

        req = ""
        while True:
            data = clientsock.recv(1)
            if data == "":
                break
            req = req + data
            if req[-4:] == "\r\n\r\n":
                break
        req = string.split(req, "\n")
        http = {}
        for line in req:
            tmp = string.split(line, ":", 1)
            #print tmp
            if len(tmp) == 2:
                http[tmp[0]] = string.strip(tmp[1])
                if string.lower(tmp[0]) == "icy-metadata":
                    sendmetadata = int(tmp[1])

        # Make sure http "Host" variable is fully qualified
        if not http.has_key("Host"):
            http["Host"] = "localhost:" + str(config.listenport)
        elif string.find(http["Host"], ":") < 0:
            http["Host"] = http["Host"] + ":" + str(config.listenport)

        # Check request method
        req[0] = string.split(req[0], " ")
        if len(req[0]) != 3 or req[0][0] != "GET":
            print "Unhandled method:", req[0]
            try:
                clientsock.sendall("HTTP/1.0 405 Method Not Allowed\r\n");
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Allow: GET\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall("Unhandled method.\r\n")
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        tmp = string.split(req[0][1], "?", 1)
        station = tmp[0]
        if len(tmp) > 1:
            args = cgi.parse_qs(tmp[1])
        else:
            args = None

        if self.lastfm.debug:
            sys.stderr.write("station=" + station + "\n")

        if station == "/frames":
            cont = "<frameset rows=\"220, *\"><FRAME src=\"/\"><frame src=\"http://www.last.fm/\"></frameset>\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/quit":
            self.quit = True
            cont = "Bye!\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station[:9] == "/settheme":
            theme = station[10:]
            try:
                tmp = os.stat(os.path.join(self.basedir, "data", theme + ".css"))
                tmp = os.stat(os.path.join(self.basedir, "data", theme + ".html"))
                config.theme = theme
                url = "http://" + http["Host"] + "/"
            except OSError:
                url = "http://" + http["Host"] + "/?msg=Theme%20" + theme + "%20not%20found!"
                
            cont = "Moved to <a href=\"" + url + "\">here</a>."

            try:
                clientsock.sendall("HTTP/1.0 307 Temporary Redirect\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Location: " + url + "\r\n")
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station[-4:] == ".pls":
            cont = "[playlist]\n"
            cont = cont + "File1=http://" + http["Host"] + string.replace(station, ".pls", ".mp3") + "\n"
            cont = cont + "Title1=Last.FM Radio\n"
            cont = cont + "Length1=-1\n"
            cont = cont + "NumberOfEntries=1\n"
            cont = cont + "Version=2\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: audio/x-scpls\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station[-4:] == ".m3u":
            cont = "http://" + http["Host"] + string.replace(station, ".m3u", ".mp3") + "\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: audio/x-mpegurl\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/skip" or station == "/love" or station == "/ban" or station[:8] == "/lastfm:" or station[:22] == "/changestation/lastfm:" or station == "/rtp" or station == "/nortp" or station == "/skip":

            redirect = 0

            if station == "/rtp":
                self.recordtoprofile = 1
                res = {"response": "OK, scrobbling enabled."}

            elif station == "/nortp":
                self.recordtoprofile = 0
                res = {"response": "OK, scrobbling disabled."}

            elif station == "/skip":
                self.skip = 1
                self.rating = "S"
                res = {"response": "OK, skipping..."}

            elif station[:8] == "/lastfm:":
                res = self.lastfm.changestation(station[1:])
                if res.has_key("response") and res["response"] == "OK":
                    self.skip = 1000
                    self.storebookmark(station[1:])
                redirect = 1

            # /changestation is used by javascript and should not be redirected
            elif station[:22] == "/changestation/lastfm:":
                res = self.lastfm.changestation(station[15:])
                if res.has_key("response") and res["response"] == "OK":
                    res["response"] = "OK, changing station..."
                    self.skip = 1000
                    self.storebookmark(station[15:])

            else:
                if station == "/love":
                    self.rating = "L"
                elif station == "/ban":
                    self.rating = "B"
                    self.skip = 1

                res = self.lastfm.command(station[1:])

            if res.has_key("response"):
                res = res["response"]
            else:
                print "hmm?", repr(res)
                res = "INTERNALERROR"

            cont = "result = '" + res + "';\n"

            try:
                if redirect:
                    clientsock.sendall("HTTP/1.0 307 Temporary Redirect\r\n")
                    clientsock.sendall("Location: http://" + http["Host"] + "/\r\n")
                else:
                    clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/plain\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/popup":
            cont = "<script>\nfunction popup(url,w,h) {\nwindow.open(url, \"LastFMProxy\", 'width='+w+',height='+h+'toolbar=no,location=no,directories=no,status=no,menubar=no,scrollbars=no,resizable=yes');\n}\n</script>\n"
            cont = cont + "<div><a href=\"javascript:popup('/',700,300);\">Click here to open popup-window</a></div>\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/np":

            cont = u"np_streaming = " + str(self.streaming) + ";\n"

            if self.streaming:
               
                try:
                    title = self.lastfm.playlist.data.title
                except:
                    title = "Wait..."

                cont = cont + "np_station = '" + title + "';\n"
                
                try:
                    m = self.lastfm.playlist.data.tracks[self.lastfm.playlist.pos]
                except:
                    m = False

                if m and m.has_key("trackpage") and m.has_key("creator") and m.has_key("title"):
                    tmp = "<a href=\"" + m["trackpage"] + "\">"
                    tmp = tmp + m["creator"].decode("utf8") + " - "
                    tmp = tmp + m["title"].decode("utf8") + "</a>"
                    self.storetrack(tmp)

                if m:
                    for tmp in m.keys():
                        # LASTFMPROXY:  Set album cover
                        if tmp == 'image':
                            if self.last_cover != m[tmp]:
                                self.np_image_func(m[tmp].decode('utf8'))
                            self.last_cover = m[tmp]
                        cont = cont + "np_" + tmp + " = '" + string.replace(m[tmp].decode("utf8"), "'", "\\'") + "';\n"

                cont = cont + "np_trackprogress = " + str(int(time.time() - self.starttime)) + ";\n"

            cont = cont + "np_recordtoprofile = " + str(self.recordtoprofile) + ";\n"

            cont = cont + "np_lasttracks = " + str(len(self.lasttracks)) + ";\n"
            cont = cont + "np_lasttrack = new Array(" + str(len(self.lasttracks)) + ");\n"
            for i in range(0,len(self.lasttracks)):
                cont = cont + "np_lasttrack[" + str(i) + "] = '" + string.replace(self.lasttracks[i], "'", "\\'") + "';\n"

            cont = cont + "np_bookmarks = " + str(len(self.bookmarks)) + ";\n"
            cont = cont + "np_bookmark = new Array(" + str(len(self.bookmarks)) + ");\n"
            for i in range(0,len(self.bookmarks)):
                cont = cont + "np_bookmark[" + str(i) + "] = '" + string.replace(self.bookmarks[i], "'", "\\'") + "';\n"

            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/plain\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont.encode("utf8"))
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/debug" or station == "/nodebug":
            self.lastfm.debug = station == "/debug"
            cont = "debug=" + str(self.lastfm.debug) + "\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/info":
            # Dump current metadata struct
            cont = "<p><pre>"
            for tmp in self.lastfm.info.keys():
                cont = cont + tmp + ": " + self.lastfm.info[tmp] + "\n"
            cont = cont + "</pre></p>\n"
            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station == "/":
            title = "LastFMProxy v" + self.version
            cont = "<html><head><title>" + title + "</title>\n"
            cont = cont + "<link rel=\"shortcut icon\" href=\"/data/favicon.ico\" />\n"
            cont = cont + "<link rel=\"icon\" href=\"/data/favicon.ico\" />\n"
            cont = cont + "<link rel=\"icon\" type=\"image/png\" href=\"/data/nice_favicon.png\" />\n"
            cont = cont + "<link rel=\"stylesheet\" type=\"text/css\" media=\"screen\" href=\"data/" + config.theme + ".css\" />\n"
            cont = cont + "<script>\n"
            cont = cont + "var host = 'http://" + http["Host"] + "';\n"
            f = open(os.path.join(self.basedir, "data", "main.js"), "r")
            cont = cont + f.read()
            f.close()
            cont = cont + "</script>\n"

            cont = cont + "</head><body>\n"
            cont = cont + "<form action=\"/\" name=\"lfmpform\" method=\"get\">"

            f = open(os.path.join(self.basedir, "data", config.theme + ".html"), "r")
            gui = f.read()
            f.close()

            tmp = "<a href=\"http://vidar.gimp.org/lastfmproxy/\" target=\"_blank\">LastFMProxy v" + self.version + "</a> - &copy; 2005-2007 Vidar Madsen"
            gui = string.replace(gui, "VERSION", tmp)

            gui = string.replace(gui, "STATION", "<span id=\"lfmp-dyn-station\">&nbsp;</span>")

            tmp = "<span id=\"lfmp-dyn-lasttracks-list\"></span>"
            gui = string.replace(gui, "LASTTRACKS", tmp)

            cover = "data/noalbum_medium.gif"
            gui = string.replace(gui, "COVER", "<span id=\"lfmp-dyn-cover\"><img width=130 height=130 src=\"" + cover + "\"></span>")
            gui = string.replace(gui, "SIMILAR", "<span id=\"lfmp-dyn-similarlink\">&nbsp;</span>")
            gui = string.replace(gui, "FANS", "<span id=\"lfmp-dyn-fanslink\">&nbsp;</span>")
            gui = string.replace(gui, "ARTIST", "<span id=\"lfmp-dyn-artist\">&nbsp;</span>")
            gui = string.replace(gui, "ALBUM", "<span id=\"lfmp-dyn-album\">&nbsp;</span>")
            gui = string.replace(gui, "TRACK", "<span id=\"lfmp-dyn-track\">&nbsp;</span>")
            gui = string.replace(gui, "DURATION", "<span id=\"lfmp-dyn-dur\">&nbsp;</span>")

            tmp = "<select name=\"stationselect\" onChange=\"selectstation();\"><option value=\"\">...</option></select>"
            gui = string.replace(gui, "BOOKMARKS", tmp)

            tmp = "<a href=\"/\" target=\"_self\" title=\"Refresh (R)\">Refresh</a> &middot; "

            tmp = tmp + "<span id=\"lfmp-buttons1\" style=\"display: none;\">"
            tmp = tmp + "<a href=\"javascript:skip();\" title=\"Skip track (space)\">Skip</a> &middot; "
            tmp = tmp + "<a href=\"javascript:love();\" title=\"Love this track (enter)\">Love</a> &middot; "
            tmp = tmp + "<a href=\"javascript:ban();\" title=\"Ban this track (backspace)\">Ban</a> &middot; "
            tmp = tmp + "<input type=\"checkbox\" onChange=\"togglertp();\" name=\"rtp\" id=\"lfmp-rtp\"> <label for=\"lfmp-rtp\">R<span class=\"lfmp-shortcut\">e</span>cord to profile</label> &middot; "
            tmp = tmp + "</span>"

            tmp = tmp + "<span id=\"lfmp-buttons2\" style=\"display: none;\">"
            tmp = tmp + "<a href=\"http://" + http["Host"] + "/lastfm.m3u\">Start radio</a>\n"
            tmp = tmp + "</span>"

            gui = string.replace(gui, "BUTTONS", tmp)

            cont = cont + gui

            cont = cont + "</form>"
            cont = cont + "<script>\ntick();\n</script>\n"
            cont = cont + "</body></html>\n"

            try:
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/html; charset=utf-8\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station[:6] == "/data/":
            if station[-4:] == ".css":
                type = "text/css"
            elif station[-4:] == ".png":
                type = "image/png"
            elif station[-4:] == ".jpg":
                type = "image/jpeg"
            elif station[-4:] == ".gif":
                type = "image/gif"
            else:
                type = "application/octet-stream"

            try:
                f = open(os.path.join(self.basedir, "data", station[6:]), "rb")
            except IOError:
                cont = "File \"" + station + "\" not found\n"
                try:
                    clientsock.sendall("HTTP/1.0 404 Not Found\r\n")
                    clientsock.sendall(self.extraheaders)
                    clientsock.sendall("Content-Type: text/plain\r\n")
                    clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                    clientsock.sendall("\r\n")
                    clientsock.sendall(cont)
                    clientsock.close()
                except socket.error:
                    clientsock.close()
                return

            cont = f.read()
            f.close()
            try:
                # No extraheaders here, since we want to cache these files.
                clientsock.sendall("HTTP/1.0 200 OK\r\n")
                clientsock.sendall("Server: LastFMProxy/" + self.version + "\r\n")
                clientsock.sendall("Content-Type: " + type + "\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return

        if station[-4:] != ".mp3":
            cont = "File \"" + station + "\" not found\n"
            try:
                clientsock.sendall("HTTP/1.0 404 Not Found\r\n")
                clientsock.sendall(self.extraheaders)
                clientsock.sendall("Content-Type: text/plain\r\n")
                clientsock.sendall("Content-Length: " + str(len(cont)) + "\r\n")
                clientsock.sendall("\r\n")
                clientsock.sendall(cont)
                clientsock.close()
            except socket.error:
                clientsock.close()
            return
        
        self.skip = 0
        self.stop = False
        retries = 0

        # Check if station is "last.mp3", and if not, send a station change
        if station != "/lastfm.mp3":
            station = "lastfm:/" + string.replace(station, ".mp3", "")
            #print "station:", station
            res = self.lastfm.changestation(station)
            if res.has_key("response") and res["response"] == "OK":
                self.storebookmark(station)
                self.skip = 1000
            #print repr(res)


        self.streaming = 1

        # Send HTTP headers to client
        try:
            clientsock.sendall("HTTP/1.1 200 OK\r\n");
            clientsock.sendall("Content-Type: audio/mpeg\r\n")
            clientsock.sendall("Cache-Control: no-cache, must-revalidate\r\n");
            if sendmetadata:
                for tmp in [ "icy-name:last.fm", 
                        "icy-pub:1", 
                        "icy-url:http://www.last.fm/",
                        "icy-metaint:" + str(metaint) ]:
                    clientsock.sendall(tmp + "\r\n")
            clientsock.sendall("\r\n")
        except:
            print "Error sending HTTP headers"
            self.stop = True

        while not self.quit and not self.stop:
                
            playlist = self.lastfm.playlist

            if self.skip or not playlist.data:
                playlist.pos = playlist.pos + self.skip
                if not playlist.data or playlist.pos >= len(playlist.data.tracks):
                    if not self.lastfm.getplaylist():
                        
                        print "Strangeness! No tracks in playlist? Sending station update..."
                        retries = retries + 1
                        if retries < 3:
                            if len(self.bookmarks) >= retries:
                                tmpstation = self.bookmarks[retries-1]
                            else:
                                tmpstation = "lastfm://user/" + self.username + "/neighbours"

                            print "Trying station " + tmpstation
                            res = self.lastfm.changestation(tmpstation)
                            if res.has_key("response") and res["response"] == "OK":
                                if self.lastfm.getplaylist():
                                    retries = 0
                                    continue

                        print "Unable to change station or get a playlist. Stopping."
                        self.stop = 1
                        break

                    playlist = self.lastfm.playlist
                self.skip = 0

            track = playlist.data.tracks[playlist.pos]

            url = track["location"]
            url = "%s" % url
            url = string.split(url, "/", 3)

            host = string.split(url[2], ":")
            if len(host) != 2:
                host = [ host[0], 80 ]
            else:
                host[1] = int(host[1])

            if self.lastfm.debug:
                sys.stderr.write("GET http://" + host[0] + ":" + str(host[1]) + "/" + url[3] + " HTTP/1.0\r\n")

            # Connect to actual server and request stream
            streamsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if config.useproxy:
                streamsock.connect((config.proxyhost, config.proxyport))
                streamsock.sendall("GET http://" + host[0] + ":" + str(host[1]) + "/" + url[3] + " HTTP/1.0\r\n")
            else:
                streamsock.connect((host[0], host[1]))
                streamsock.sendall("GET /" + url[3] + " HTTP/1.0\r\n")
            streamsock.sendall("Host: " + host[0] + "\r\n")
            streamsock.sendall("\r\n")

            # Read HTTP headers
            while True:
                line = ""
                while True:
                    c = streamsock.recv(1)
                    line = line + c
                    if c == '\n':
                        break

                if self.lastfm.debug:
                    sys.stderr.write("<<< " + line)

                # Handle "403 Invalid ticket" more gracefully
                if line[:6] == "HTTP/1":
                    tmp = string.split(line, " ", 3)
                    if tmp[1] != "200":
                        self.skip = 1
                        break

                if line == "\r\n":
                    break

            if self.skip:
                continue

            self.starttime = int(time.time())
            self.rating = ""

            tracklen = int(int(track["duration"])/1000)
            if self.recordtoprofile:
                self.audioscrobbler.now_playing(track["creator"], track["title"], 
                    track["album"], tracklen)

            scrobbled = False

            if self.lastfm.debug:
                sys.stderr.write("Starting stream...\n")

            # Stream data
            count = 0
            while not self.quit and not self.stop:
                l = metaint - count

                if self.skip:
                    data = ""
                else:
                    try:
                        data = streamsock.recv(l)
                    except socket.error:
                        print "Error receiving data from server"
                        data = ""

                if data == "":

                    # Send padding data so that metadata is offset correctly
                    if sendmetadata:
                        try:
                            clientsock.sendall("\0" * l)
                        except socket.error, (val,msg):
                            print "Error sending data to client:", msg
                            self.stop = 1
                            break

                        icytag = "StreamTitle='';StreamUrl='';" + chr(0) * 16
                        blocks = len(icytag) / 16
                        icytag = chr(blocks) + icytag[:blocks*16]
                        try:
                            clientsock.sendall(icytag)
                        except socket.error, (val,msg):
                            print "Error sending data to client:", msg
                            self.stop = 1
                            break

                    if not self.skip:
                        self.skip = 1
                    break

                #if self.lastfm.debug:
                #    sys.stderr.write("Got %d bytes\n" % len(data))

                count = count + len(data)
                if count == metaint:
                    count = 0

                try:
                    clientsock.sendall(data)
                except socket.error, (val,msg):
                    print "Error sending data to client:", msg
                    self.stop = 1
                    break

                # Inject Shoutcast tags
                if sendmetadata and count == 0:

                    trackname = track["creator"] + " - " + track["title"]

                    icytag = "StreamTitle='" + trackname + "';StreamUrl='';" + chr(0) * 16

                    blocks = len(icytag) / 16
                    icytag = chr(blocks) + icytag[:blocks*16]
                    try:
                        clientsock.sendall(icytag)
                    except socket.error, (val,msg):
                        print "Error sending data to client:", msg
                        self.stop = 1
                        break


            if self.lastfm.debug:
                sys.stderr.write("Stopped.\n")

            streamsock.close()

            if not scrobbled and self.recordtoprofile and not self.stop and not self.quit:
                if tracklen > 30 and (time.time() - self.starttime) > tracklen / 2:
                    scrobbled = True
                    self.audioscrobbler.submit(artist=track["creator"], 
                        track=track["title"], album=track["album"], time=self.starttime, 
                        rating=self.rating, length=tracklen, source='L' + track['trackauth'], 
                        autoflush=True)

        clientsock.close()
        self.streaming = 0

    def run(self, bind_address, port):
        print "Starting LastFMProxy " + self.version + "..."

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set socket options to allow binding to the same address
        # when the proxy has been closed and then restarted:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((bind_address, port))
        s.listen(5)

        print "Connecting to last.fm server..."
        self.lastfm = lastfm.lastfm();
        self.lastfm.connect(self.username, self.hexify(md5.md5(self.password).digest()))
        #print self.lastfm.info

        if not self.lastfm.info.has_key("session"):
            print "Handshake failed."
            print "DEBUG:", self.lastfm.info
            s.close()
            return

        if self.lastfm.info["session"] == "FAILED":
            print "Handshake failed. Bad login info, perhaps?"
            print "DEBUG:", self.lastfm.info
            s.close()
            return

        self.audioscrobbler = scrobbler

        self.bookmarks = []
        try:
            f = open(os.path.join(self.basedir, "bookmarks.txt"), "r")
            for line in f.readlines():
                self.bookmarks.append(string.rstrip(line))
            f.close()
        except IOError:
            try:
                f = open(os.path.join(self.basedir, "stations.txt"), "r")
                for line in f.readlines():
                    self.bookmarks.append(string.rstrip(line))
                f.close()
            except IOError:
                pass

        # Minor prettification
        if bind_address == "127.0.0.1" or bind_address == "0.0.0.0":
            bind_address = "localhost"

        print "To tune in, point your browser to:"
        print "  http://" + bind_address + ":" + str(port) + "/"

        self.proxy_ready = True
        runningthreads = []

        try:
            while not self.quit:
                (clientsocket, address) = s.accept()

                if self.lastfm.debug:
                    sys.stderr.write("\nGot connection from " + repr(address) + "\n")

                t = threading.Thread(target=self.gotconnection,args=(clientsocket,))
                t.start()
                runningthreads.append(t)
        except KeyboardInterrupt:
            self.quit = 1

        print "Shutting down..."
        for t in runningthreads:
            t.join()
        print "Done! Bye!"

        s.close()
        return

if __name__ == "__main__":
    p = proxy(config.username, config.password)
    p.basedir = os.path.dirname(sys.argv[0])
    p.run(config.bind_address, config.listenport)

