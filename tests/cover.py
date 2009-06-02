from tests.base import BaseTestCase
from xl import cover
import time, hashlib, os, re

class CoverBaseTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        self.cm = cover.CoverManager(
            cache_dir=".testtemp/exaile_cache%s" %
            hashlib.md5(str(time.time())).hexdigest())
        self.cm.add_defaults()


class LocalCoverTestCase(CoverBaseTestCase):
    def setUp(self):
        CoverBaseTestCase.setUp(self)

    def testLocalCovers(self):
        track = self.collection.search('artist=Delerium')[0]
        self.cm.set_preferred_order(['local'])

        c = self.cm.find_covers(track)

        h = os.popen('/usr/bin/file %s' % os.path.realpath(c[0]))
        data = h.read()

        assert data.find('48 x 48') > -1, "Local cover search failed: %s" % \
            data


