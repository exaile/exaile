
import xspf

class playlist:

    def __init__(self, string = None):

        self.pos = 0
        self.data = None

        if string:
            self.parse(string)

    def parse(self, string):
       
        self.data = xspf.XSPFParser()
        self.data.parseBuff(string)
        self.pos = 0

        # debug
        #for t in self.data.tracks:
        #    print "* " + t["creator"] + " - " + t["title"]





