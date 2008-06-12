data = """
###########################################################################
###                                                                     ###
### audioscrobbler plugin                                               ###
###                                                                     ###
### Not entirely sure how to write any test cases for it.  If you have  ###
### any good ideas, please add them here                                ###
###                                                                     ###
###########################################################################
"""

import sys
sys.path.append('plugins/audioscrobbler')
from tests.base import BaseTestCase
from xl import event

class AudioscrobblerTestCase(BaseTestCase):
    def setUp(self):
        print data
        self.plugin = self.load_plugin('audioscrobbler')
        self.plugin.enable(self)

    def testAudioScrobblerLoaded(self):
        assert self.plugin != None, "AS plugin did not load"

    def tearDown(self):
        self.plugin.disable(self)
        
