#!/usr/bin/python

import sys
import config
import httpclient

if __name__ == '__main__':
    s = httpclient.httpclient("localhost", config.listenport)
    s.req("/" + sys.argv[1])

