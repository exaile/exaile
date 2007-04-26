#!/usr/bin/env python

import re, os, cgi, time, urllib, sys
import os.path
import cgitb; cgitb.enable()
info = cgi.FieldStorage()

print 'Content-type: text/plain\n\n',

name_re = re.compile(r'PLUGIN_NAME\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
version_re = re.compile(r'PLUGIN_VERSION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
author_re = re.compile(r'PLUGIN_AUTHORS\s+=\s(\[.*?\])', re.DOTALL|re.MULTILINE)
description_re = re.compile(r'PLUGIN_DESCRIPTION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
plugin_re = re.compile(r'<a class="file" title="View File" href=".*?">(\w+.py)</a>', re.DOTALL|re.MULTILINE)

h = open('new_pluginlog.txt', 'a+')
date = time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime())
h.write("%s\t%s\t%s\n" % (date, os.getenv('REMOTE_ADDR'),
    info['version'].value))
h.close()

data = urllib.urlopen('http://exaile.org/trac/browser/plugins/%s' %
    info['version'].value).read()

try:
    h = open('plugins_%s.cache' % info['version'].value, 'r')
    check_size = h.readline().strip()
    lines = h.readlines()
    h.close()
    if str(len(data)) == check_size:
        for line in lines:
            print line,
        sys.exit(0)
except IOError:
    # plugin cache doesn't exist, move on
    pass

h = open('plugins_%s.cache' % info['version'].value, 'w')
h.write("%d\n" % len(data))
plugins = plugin_re.findall(data)

for plugin in plugins:
    data = \
        urllib.urlopen('http://www.exaile.org/trac/browser/plugins/%s/%s?format=txt'
        % (info['version'].value, plugin)).read()

    m = name_re.search(data)
    if not m: continue

    name = m.group(2)

    m = version_re.search(data)
    if not m: continue

    version = m.group(2)

    m = author_re.search(data)
    if not m: continue

    author = eval(m.group(1))
    author = ", ".join(author)

    m = description_re.search(data)
    if not m: continue

    description = m.group(2)
    description = description.replace('\n', ' ')

    text = "%s\t%s\t%s\t%s\t%s" % (plugin, name, version, author,
        description)
    print text
    h.write("%s\n" % text)

h.close()
