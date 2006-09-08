# Copyright (C) 2006 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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


import urllib2,  urllib, re, time, md5, thread, sys, media, time, xlmisc
from urllib import urlencode
"""
    I found this class on the net via a google search.  I can't remember where,
    and there were no credits accompanying the file, or else I would put them
    here
"""

def urlencoded(num, track): 
    if not isinstance(track, media.Track):    
        lt = time.gmtime(track.time_played - 2082845972)
        len = track.tracklen / 1000
    else:
        len = track.duration
        lt = time.gmtime(time.time())

    date = "%02d-%02d-%02d %02d:%02d:%02d" % (lt[0], lt[1], lt[2],
        lt[3], lt[4], lt[5])

    try:
        encode = ""
        encode += "a["+str(num)+"]"+urlencode({'': unicode(track.artist)})
        encode += "&t["+str(num)+"]"+urlencode({'': unicode(track.title)})
        encode += "&l["+str(num)+"]"+urlencode({'': str(len)})
        encode += "&i["+str(num)+"]"+urlencode({'': date})
        encode += "&m["+str(num)+"]="
        encode += "&b["+str(num)+"]"+urlencode({'': unicode(track.album)})
    except UnicodeDecodeError:
        return ""
    return encode 

class Scrobbler(object): 
    def __init__(self,exaile,user,password,client="tst",version="0.0",
        url="http://post.audioscrobbler.com/"):
        self.exaile = exaile
        self.url = url
        self.user = user
        self.password = password
        self.client = client
        self.version = version
        self.md5 = None
    def handshake(self):
        if self.user == "" or self.password == "": return
        url = self.url+"?"+urllib.urlencode({
            "hs":"true",
            "p":"1.1",
            "c":self.client,
            "v":self.version,
            "u":self.user
            })
        result = urllib2.urlopen(url).readlines()
        xlmisc.log("[audioscrobbler] logging in")
        if result[0].startswith("BADUSER"):
            return self.baduser(result[1:])
        if result[0].startswith("UPTODATE") or result[0].startswith("UPDATE"):
            return self.uptodate(result[1:])
        if result[0].startswith("FAILED"):
            return self.failed(result)
    def uptodate(self,lines):
        self.md5 = re.sub("\n$","",lines[0])
        self.submiturl = re.sub("\n$","",lines[1])
        self.interval(lines[2])
    def baduser(self,lines):
        xlmisc.log("Bad user")
    def failed(self,lines):
        xlmisc.log(lines[0])
        self.interval(lines[1])
    def interval(self,line):
        match = re.match("INTERVAL (\d+)",line)
        if match is not None:
            xlmisc.log("[audioscrobbler] Sleeping for " + match.group(1) + " secs")
            time.sleep(int(match.group(1)))
    def submit(self,tracks):
        if self.md5 == None: return
        xlmisc.log("[audioscrobbler] Submitting")
        md5response = md5.md5(md5.md5(self.password).hexdigest()+self.md5
            ).hexdigest()
        post = "u="+self.user+"&s="+md5response
        count = 0
        for track in tracks:
            post += "&"
            post += urlencoded(count, track)
            count += 1
        post = unicode(post)
        xlmisc.log(post)
        result = urllib2.urlopen(self.submiturl,post)
        results = result.readlines()
        if results[0].startswith("OK"):
            xlmisc.log("OK")
            self.interval(results[1])
            return
        if results[0].startswith("FAILED"):
            self.failed([results[0],"INTERVAL 0"])
        self.exaile.status.set_first("Failed to submit track to "
            "last.fm.", 2500)

