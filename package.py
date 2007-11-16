#!/usr/bin/env python

import os, re, sys

h = open('debian/changelog')
line = h.readline()
h.close()

m = re.search('\(([^)]+)\)', line)
if not m:
    print "Could not determine version number, bailing!"
    sys.exit(1)

version = m.group(1)
print "Creating packages for exaile version: %s" % version

h = open('exaile.py')
lines = h.readlines()
h.close()

h = open('exaile.py', 'w')
for line in lines:
    line = re.sub("__version__ = '[^']+'", "__version__ = '%s'" % version,
        line)
    h.write(line)

h.close()

cur = os.getcwd()
branch = cur.split('/').pop()
os.chdir('../build')
os.system('cp -rf ../%s exaile_%s' % (branch, version))
os.chdir('exaile_%s' % version)

for m in ('.pyc', '.pyo', '.bzr'):
    os.system('find . -name %s -exec rm -rf {} \;' % m)

os.system('debuild -i -S -sa')
os.system('make clean')
os.chdir('..')

os.system('rm -rf exaile_%s' % version)

# create md5s
for item in ('.tar.gz', '_i386.deb'):
    os.system('md5sum exaile_%s%s > exaile_%s%s.md5' % (version, item,
        version, item))
os.chdir(cur)
print 'Packages have been created successfully'
