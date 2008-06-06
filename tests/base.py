from xl import settings, collection
import unittest, md5, time

settings.SettingsManager('/tmp/test_exaile_settings.ini')
class BaseTestClass(unittest.TestCase):
    def setUp(self):
        self.settings = settings.SettingsManager('/tmp/test_exaile_settings.ini')
        self.temp_col_loc = '/tmp/col%s.db' % \
            md5.new(str(time.time())).hexdigest()
        self.collection = collection.Collection("TestCollection", 
            self.temp_col_loc)

        self.library1 = collection.Library("./tests/data")
        self.collection.add_library(self.library1)
        self.collection.save_libraries()
        self.collection.rescan_libraries()
