
import base64
import config
import socket
import string

True = 1
False = 0

class httpclient:

    def __init__(self, host, port = None):
        self.host = host
        self.port = port
        self.path = None
        self.status = None
        self.headers = None
        self.response = None
        self.debug = 0

        if self.host[:7] == "http://":
            self.host = self.host[7:]
            p = self.host.find("/")
            self.path = self.host[p:]
            self.host = self.host[:p]

        if not self.port:
            p = self.host.find(":")
            if p >= 0:
                self.port = int(self.host[p+1:])
                self.host = self.host[:p]
            else:
                self.port = 80

    def readline(self, s):
        res = ""
        while True:
            try:
                c = s.recv(1)
            except:
                break
            res = res + c
            if c == '\n':
                break
            if not c:
                break
        if self.debug:
            print "<<< " + res.replace("\n", "")
        return res

    def post(self, postdata):
        return self.req(None, postdata)

    def req(self, url=None, postdata=None):

        if not url:
            url = self.path

        if not url:
            print "httpclient: No URL?"
            return

        method = "GET"
        if postdata:
            method = "POST"

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if config.useproxy:
            try:
                s.connect((config.proxyhost, config.proxyport))
            except:
                self.response = ""
                return

            req = method + " http://" + self.host + ":" + str(self.port) + url + " HTTP/1.1"
            if self.debug:
                print ">>> " + req
            s.send(req + "\r\n")
            if config.proxyuser != "":
                s.send("Proxy-Authorization: Basic " + base64.b64encode(config.proxyuser + ":" + config.proxypass) + "\r\n")
        else:
            try:
                s.connect((self.host, self.port))
            except:
                self.response = ""
                return
            req = method + " " + url + " HTTP/1.1"
            if self.debug:
                print ">>> " + req
            s.send(req + "\r\n")
        s.send("Host: " + self.host + "\r\n")
        s.send("Connection: close\r\n")

        if postdata:
            s.send("Content-Type: application/x-www-form-urlencoded\r\n")
            s.send("Content-Length: " + str(len(postdata)) + "\r\n")

        s.send("\r\n")

        if postdata:
            if self.debug:
                print ">>> postdata: " + postdata
            s.send(postdata)

        line = self.readline(s)
        self.status = string.rstrip(line)

        self.headers = {}
        while True:
            line = self.readline(s)
            if not line:
                break
            if line == "\r\n":
                break
            tmp = string.split(line, ": ")
            self.headers[tmp[0]] = string.rstrip(tmp[1])

        self.response = ""
        while True:
            line = self.readline(s)
            if not line:
                break
            self.response = self.response + line
        s.close()

