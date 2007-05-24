#!/usr/bin/env python

import re, os, cgi, time, urllib, sys
import os.path
plugin_re = re.compile(r'<a class="file" title="View File" href=".*?">([-\w]+.py)</a>', re.DOTALL|re.MULTILINE)

if len(sys.argv) != 2:
    print "usage: python pluginupdater.py [exaile_version]"
    sys.exit(0)
version = sys.argv[1]
data = urllib.urlopen('http://exaile.org/trac/browser/plugins/%s' %
    version).read()

plugins = plugin_re.findall(data)


print "Updating plugin list"
for plugin in plugins:
    data = \
        urllib.urlopen('http://www.exaile.org/plugins/plugins.py?version=%s&plugin=%s'
        % (version, plugin)).read()

    plugindir = '/home/%s/.exaile/plugins' % os.getlogin()
    if not os.path.isdir(plugindir):
        os.mkdir(plugindir, 0777)

    print "Writing %s" % plugin
    h = open('/home/%s/.exaile/plugins/%s' % (os.getlogin(), plugin), 'w')
    h.write(data)
    h.close()

print "Done.\n"
