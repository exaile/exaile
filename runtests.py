import unittest, doctest, os, shutil, sys, imp
from tests import base
import xl

sys.path.append('plugins')

checks = 'all'
try:
    checks = sys.argv[1]
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
                suite.addTest(doctest.DocTestSuite(mod))
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
            path = os.path.join('plugins', file)
            if os.path.isdir(path):
                if not os.path.isfile(os.path.join(path, 'test.py')):
                    print "Warning: no tests for %s" % file
                    continue
                mod = imp.load_source(path, os.path.join(path, 'test.py'))
                suite.addTests(loader.loadTestsFromModule(mod))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    shutil.rmtree('.testtemp')

    if not result.wasSuccessful():
        sys.exit(1) # use this so make recognizes that we failed and aborts
