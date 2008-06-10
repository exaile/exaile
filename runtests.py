import unittest, doctest, os, shutil
from tests.collection import *
from tests.playlists import *
from tests.cover import *

# doctest stuff
from xl import collection, common, playlist, settings

doctests = [collection, common, playlist, settings]

if __name__ == '__main__':
    print " -- Exaile Test Suite --\n"
    print "Running doctests..."
    if not os.path.isdir(".testtemp"):
        os.mkdir(".testtemp", 0755)

    # run doctests first
    suite = unittest.TestSuite()
    for mod in doctests:
        suite.addTest(doctest.DocTestSuite(mod))

    runner = unittest.TextTestRunner()
    runner.run(suite)

    print "\nRunning other tests..."

    unittest.main()
