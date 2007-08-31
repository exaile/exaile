#!/usr/bin/env python

import re, os, cgi, time, urllib, sys
import os.path, shutil


name_re = re.compile(r'PLUGIN_NAME\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
version_re = re.compile(r'PLUGIN_VERSION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)
author_re = re.compile(r'PLUGIN_AUTHORS\s+=\s(\[.*?\])', re.DOTALL|re.MULTILINE)
description_re = re.compile(r'PLUGIN_DESCRIPTION\s+=\s+r?(\'\'?\'?|""?"?)(.*?)(\1)', re.DOTALL|re.MULTILINE)

out = open('plugin_info.txt', 'w+')

if not os.path.isdir('.htmain'):
    os.system('bzr checkout --lightweight http://bazaar.launchpad.net/~exaile-devel/exaile/main .htmain')
    os.chdir('.htmain/plugins')
else:
    os.chdir('.htmain/plugins')
    os.system('bzr update')


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

files = os.listdir('.')
for file in files:
    if os.path.isdir(file):
        data = open('%s/%s.py' % (file, file)).read()
        inf = get_plugin_info('%s.exz' % file, data)

        os.chdir(file)
        os.system('zip -r ../../../%s.exz *' % file)
        os.chdir('..')
    else:
        data = open(file).read()
        shutil.copyfile(file, '../../%s' % file)
        inf = get_plugin_info(file, data)

    if not inf: continue
    out.write('\t'.join(inf) + '\n')

out.close()
