#!/usr/bin/env python

import re, os, cgi, time, urllib, sys
import os.path

version = sys.argv[1]
url = "http://www.exaile.org/trac/browser/plugins/%s" % version

name_re = re.compile(r'PLUGIN_NAME\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
version_re = re.compile(r'PLUGIN_VERSION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
author_re = re.compile(r'PLUGIN_AUTHORS\s+=\s(\[.*?\])', re.DOTALL|re.MULTILINE)
description_re = re.compile(r'PLUGIN_DESCRIPTION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
dir_re = re.compile(r'<a class="dir" title="Browse Directory" href=".*?">([\w-]+)</a>', re.DOTALL|re.MULTILINE)
plugin_re = '<a href="([^\">]*/([-\w]+.py))" title="Download[^\">]*?"> download </a>'

data = urllib.urlopen(url).read()

dirs = dir_re.findall(data)
plugins = plugin_re.findall(data)

out = open('plugin_info.txt', 'w+')

def get_plugin_info(file, data):
    m = name_re.search(data)
    if not m: return None

    name = m.group(2)

    m = version_re.search(data)
    if not m: return None

    version = m.group(2)

    m = author_re.search(data)
    if not m: return None

    author = eval(m.group(1))
    author = ", ".join(author)

    m = description_re.search(data)
    if not m: return None

    description = m.group(2)
    description = description.replace('\n', ' ')

    return (file, name, version, author, description)

for plugin in plugins:
    data = urllib.urlopen('%s/%s?format=txt' % (url, plugin)).read()
    inf = get_plugin_info(plugin, data)
    if not inf: continue

    h = open(plugin, 'w+')
    h.write(data)
    h.close()

    out.write('\t'.join(inf) + '\n')

for dir in dirs:
    data = urllib.urlopen('%s/%s/%s.py?format=txt' % (url, dir, dir)).read()
    inf = get_plugin_info('%s.exz' % dir, data)
    if not inf: continue

    os.system('rm -rf .temp_dir')
    os.system('svn export svn://exaile.org/usr/local/svn/exaile/plugins/%s/%s '
        '.temp_dir' % (version, dir))
    os.chdir('.temp_dir')
    os.system('zip -r ../%s.exz *' % (dir))
    os.chdir('..')
    os.system('rm -rf .temp_dir')

    out.write('\t'.join(inf) + '\n')

out.close()
