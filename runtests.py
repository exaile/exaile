import unittest, doctest
from tests.collection import *
from tests.playlists import *

# doctest stuff
from xl import collection, common, playlist, settings

doctests = [collection, common, playlist, settings]

if __name__ == '__main__':
    print " -- Exaile Test Suite --\n"
    print "Running doctests..."

    # run doctests first
    suite = unittest.TestSuite()
    for mod in doctests:
        suite.addTest(doctest.DocTestSuite(mod))

    runner = unittest.TextTestRunner()
    runner.run(suite)

    print "\nRunning other tests..."

    unittest.main()
