#!/usr/bin/python
# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import locale, gettext

# set the locale to LANG, or the user's default
locale.setlocale(locale.LC_ALL, '')

# this installs _ into python's global namespace, so we don't have to
# explicitly import it elsewhere
gettext.install("exaile")

try:
    import guitest
except ImportError:
    guitest = None

import unittest, doctest, os, shutil, sys, imp

sys.path.insert(0, os.getcwd())

from tests import base
import xl

sys.path.append('plugins')

checks = 'all'
try:
    checks = sys.argv[1]
except IndexError:
    pass

excludes = []
try:
    excludes = [ x[1:] for x in sys.argv[2:] if x.startswith("^") ]
except IndexError:
    pass

if __name__ == '__main__':
    print " -- Exaile Test Suite --\n"
    if not os.path.isdir(".testtemp"):
        os.mkdir(".testtemp", 0755)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if checks in ('doctests', 'all'):
        for file in os.listdir('xl'):
            if file in ('__init__.py', 'main.py') or not file.endswith('.py'): 
                continue

            mod = imp.load_source(file.replace('.py', ''), 
                os.path.join('xl', file))
            try:
                suite.addTest(doctest.DocTestSuite(mod, setUp=lambda self: gettext.install("exaile")))
            except ValueError:
                pass

    if checks in ('main', 'all'):
        for file in os.listdir('tests'):
            if file in ('base.py','__init__.py') or not file.endswith('.py'):
                continue

            mod = imp.load_source('xl/' + file.replace('.py', ''), 
                os.path.join('tests', file))
            suite.addTests(loader.loadTestsFromModule(mod))

    if checks in ('plugins', 'all'):
        for file in os.listdir('plugins'):
            if file in excludes:
                continue
            path = os.path.join('plugins', file)
            if os.path.isdir(path):
                if not os.path.isfile(os.path.join(path, 'test.py')):
                    print "Warning: no tests for %s" % file
                    continue
                mod = imp.load_source(path, os.path.join(path, 'test.py'))
                suite.addTests(loader.loadTestsFromModule(mod))
                
    if not guitest:
        print " **** guitest is not available. Cannot perform gui tests."
        print "Please download it from http://gintas.pov.lt/guitest/"
    else:
        # test gui elements
        # in order for these to work, you're going to need guitest from 
        # http://gintas.pov.lt/guitest/.  Thank you, come again.
        if checks in ('gui', 'all'):
            for file in os.listdir('tests/gui'):
                if file in ('base.py', '__init__.py') or not file.endswith('.py'):
                    continue

                mod = imp.load_source('tests/gui/' + file.replace('.py', ''),
                    'tests/gui/' + file)
                suite.addTests(loader.loadTestsFromModule(mod))


    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    shutil.rmtree('.testtemp')
    shutil.rmtree('.xdgtest')

    if not result.wasSuccessful():
        sys.exit(1) # use this so make recognizes that we failed and aborts
