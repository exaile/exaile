import unittest, doctest, os, shutil
import tests.collection, tests.playlists, tests.cover

# doctest stuff
from xl import collection, common, playlist, settings, radio
from plugins import shoutcast

doctests = [collection, common, playlist, settings, radio,
    shoutcast]

if __name__ == '__main__':
    print " -- Exaile Test Suite --\n"
    if not os.path.isdir(".testtemp"):
        os.mkdir(".testtemp", 0755)

    # run doctests first
    suite = unittest.TestSuite()
    for mod in doctests:
        suite.addTest(doctest.DocTestSuite(mod))

    loader = unittest.TestLoader()
    for mod in (tests.collection, tests.playlists, tests.cover):
        suite.addTests(loader.loadTestsFromModule(mod))

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

    shutil.rmtree('.testtemp')
