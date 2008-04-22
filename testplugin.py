#!/usr/bin/env python

import sys, os

plugindir = sys.argv[1]
cwd = os.getcwd()

userdir = os.path.expanduser('~/.exaile/plugins')
os.chdir('plugins/%s' % plugindir)
os.unlink(os.path.join(userdir, '%s.exz' % plugindir))
os.system('zip -r %s/%s.exz *' % (userdir, plugindir))
os.chdir(cwd)
os.system("./exaile")
