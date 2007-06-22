#!/usr/bin/env python

import urllib, sys, re

reg = re.compile(r'<tr class="\w+ prio\d+"><td class="id">.*?class="summary">'
    '<a href="/trac/ticket/(\d+)" title="View ticket">(.*?)</a></td>.*?<td '
    'class="type"><span>(\w+)</span></td>', re.DOTALL)

version = sys.argv[1]
type = sys.argv[2]

data = urllib.urlopen('http://www.exaile.org/trac/query'
    '?status=closed&milestone=%s' % version).read()
data = data.replace('&#34;', '"')

items = reg.findall(data)
items.sort()

for item in items:
    if type == 'wiki':
        print "  * [ticket:%d #%d] (%s) %s" % (int(item[0]), 
            int(item[0]), item[2], item[1])
    else:
        print "  * #%d (%s) %s" % (int(item[0]), item[2], item[1])
