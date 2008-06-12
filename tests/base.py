from xl import settings, collection
import unittest, md5, time, imp, os

settings.SettingsManager('.testtemp/test_exaile_settings.ini')
class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.settings = settings.SettingsManager('.testtemp/test_exaile_settings.ini')
        self.temp_col_loc = '.testtemp/col%s.db' % \
            md5.new(str(time.time())).hexdigest()
        self.collection = collection.Collection("TestCollection", 
            self.temp_col_loc)

        self.library1 = collection.Library("./tests/data")
        self.collection.add_library(self.library1)
        self.collection.save_libraries()
        self.collection.rescan_libraries()

    def load_plugin(self, pluginname):
        path = 'plugins/' + pluginname
        if path is None:
            return False
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        return plugin
