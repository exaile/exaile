import unittest, time, md5

from xl import collection, settings

# TODO:  move this to settings.py for settings testing
settings.SettingsManager('/tmp/test_exaile_settings.ini')

class CollectionTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_col_loc = '/tmp/col%s.db' % \
            md5.new(str(time.time())).hexdigest()
        self.collection = collection.Collection("TestCollection", 
            self.temp_col_loc)

        self.library1 = collection.Library("./tests/data")
        self.collection.add_library(self.library1)
        self.collection.rescan_libraries()

    def testCount(self):
        tracks = self.collection.search('')
        assert len(tracks) == 4, "Number of tracks scanned is incorrect"

    def testSaveLoad(self):
        self.collection.save_to_location()
        
        # test col
        col = collection.Collection("TestCollection2", self.temp_col_loc)
        tracks = self.collection.search('')
        assert len(tracks) == 4, "Number of tracks scanned is incorrect"

    def testAllFieldSearch(self):
        c = self.collection

        # search for a keyword in all fields
        tracks = c.search('Black')
        assert tracks[0]['title'].find('Black') > -1, "Keyword search failed"

    def testNotSearch(self):
        tracks = self.collection.search(
            """
                artist=="TestArtist" NOT album="Second"
            """
        )

        assert len(tracks) == 2, "Not search failed"

