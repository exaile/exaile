from xml.sax import make_parser, handler, SAXParseException
import xml.sax


class XSPFParser( handler.ContentHandler):

    def __init__(self):
        self.path = ""
        self.curURL = ""
        self.tracks = []
        self.track = {}

    def parseFile(self, fileName):
       
        try:
            parser = make_parser()
            parser.setContentHandler(self)
            parser.parse(fileName)
            return True
        except SAXParseException:
            return False

    def parseBuff(self, buff):
        buff = '<?xml version="1.0" encoding="UTF-8"?>'+"\n"+ buff
        try:
            xml.sax.parseString(buff,self)
            return True
        except SAXParseException:
            return False

    def getTracks(self):
        return self.tracks
        
    def startElement(self, name, attrs):
        self.path += "/%s" % name
        self.content = ""
        if self.path == "/playlist/trackList/track/link":
            self.rel= attrs.get('rel',"")
        else:
            self.rel=""

    def characters(self, content):
        self.content = self.content + content

    def endElement(self, name):
        if self.path == "/playlist/trackList/track":
            self.tracks.append(self.track)
            self.track={}
            self.track["playlisttitle"] = self.title
        
        if self.path == "/playlist/trackList/track/location":
            self.track["location"]=self.content
        if self.path == "/playlist/trackList/track/title":
            self.track["title"]=self.content.encode('utf8')
        if self.path == "/playlist/trackList/track/creator":
            self.track["creator"]=self.content.encode('utf8')
        if self.path == "/playlist/trackList/track/id":
            self.track["id"] = self.content
        if self.path == "/playlist/trackList/track/album":
            self.track["album"] = self.content.encode('utf8')
        if self.path == "/playlist/trackList/track/duration":
            self.track["duration"] = self.content
        if self.path == "/playlist/trackList/track/image":
            self.track["image"] = self.content
        if self.path == "/playlist/trackList/track/lastfm:trackauth":
            self.track["trackauth"] = self.content
        if self.path == "/playlist/trackList/track/lastfm:albumId":
            self.track["albumId"] = self.content
        if self.path == "/playlist/trackList/track/lastfm:artistId":
            self.track["artistId"] = self.content

        if self.path == "/playlist/trackList/track/link":
            if self.rel=="http://www.last.fm/artistpage":
                self.track["artistpage"] = self.content
                if self.rel=="http://www.last.fm/albumpage":
                    self.track["albumpage"] = self.content
            if self.rel=="http://www.last.fm/trackpage":
                self.track["trackpage"] = self.content
            if self.rel=="http://www.last.fm/buyTrackURL":
                self.track["buytrackpage"] = self.content
            if self.rel=="http://www.last.fm/buyAlbumURL":
                self.track["buyalbumpage"] = self.content
            if self.rel=="http://www.last.fm/freeTrackURL":
                self.track["freetrackpage"] = self.content

        if self.path == "/playlist/title":
            self.title = self.content

        offset = self.path.rfind("/")
        if offset >= 0:
            self.path = self.path[0:offset]


if __name__ == "__main__":
    a=XSPFParser()
    a.parseFile("playlist.xspf")
    print a.getTracks()

