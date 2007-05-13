#!/usr/bin/env python

import re, os, cgi, time, urllib, sys
os.chdir('/var/www/exaile.org/htdocs/plugins')
import os.path
from mod_python import apache
from mod_python.util import FieldStorage

def get_plugin(info, req):
    version = info['version'].value
    plugin = info['plugin'].value
    req.write(open('plugincache/%s/%s' % (version, plugin)).read())
    return apache.OK

def handler(req):
    info = FieldStorage(req)

    req.content_type = 'Content-type: text/plain'
    if info.has_key('plugin'):
        return get_plugin(info, req)

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

    version = info['version'].value
    data = urllib.urlopen('http://exaile.org/trac/browser/plugins/%s' %
        version).read()

    try:
        h = open('plugins_%s.cache' % info['version'].value, 'r')
        check_size = h.readline().strip()
        lines = h.readlines()
        h.close()
        if str(len(data)) == check_size:
            for line in lines:
                req.write(line)
            return apache.OK
    except IOError:
        # plugin cache doesn't exist, move on
        pass

    h = open('plugins_%s.cache' % info['version'].value, 'w')
    h.write("%d\n" % len(data))
    plugins = plugin_re.findall(data)

    appversion = version
    if not os.path.isdir('plugincache/%s' % version):
        os.mkdir('plugincache/%s' % version, 0777) 

    for plugin in plugins:
        data = \
            urllib.urlopen('http://www.exaile.org/trac/browser/plugins/%s/%s?format=txt'
            % (info['version'].value, plugin)).read()

        ph = open('plugincache/%s/%s' % (appversion, plugin), 'w+')
        ph.write(data)
        ph.close()

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
        req.write(text + "\n")
        h.write("%s\n" % text)

    h.close()
    return apache.OK
