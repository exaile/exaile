import locale, gettext

# set the locale to LANG, or the user's default
locale.setlocale(locale.LC_ALL, '')

# this installs _ into python's global namespace, so we don't have to
# explicitly import it elsewhere
gettext.install("exaile")


from xl import settings
settings._SETTINGSMANAGER = \
        settings.SettingsManager('.testtemp/test_exaile_settings.ini')
import logging
from xl import collection, event, common, xdg
import unittest, hashlib, time, imp, os


event._TESTING = True
common._TESTING = True
class BaseTestCase(unittest.TestCase):
    def setUp(self):
        gettext.install("exaile")
        self.loading = False
        self.setup_logging()
        self.temp_col_loc = '.testtemp/col%s.db' % \
            hashlib.md5(str(time.time())).hexdigest()
        self.collection = collection.Collection("TestCollection", 
            self.temp_col_loc)

        self.library1 = collection.Library("./tests/data")
        self.collection.add_library(self.library1)
        self.collection.rescan_libraries()

    def load_plugin(self, pluginname):
        path = 'plugins/' + pluginname
        if path is None:
            return False
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        return plugin

    def setup_logging(self):
        console_format = "%(levelname)-8s: %(message)s"
        loglevel = logging.INFO
        logging.basicConfig(level=logging.INFO,
                format='%(asctime)s %(levelname)-8s: %(message)s (%(name)s)',
                datefmt="%m-%d %H:%M",
                filename=os.path.join(xdg.get_config_dir(), "exaile.log"),
                filemode="a")
        console = logging.StreamHandler()
        console.setLevel(loglevel)
        formatter = logging.Formatter(console_format)
        console.setFormatter(formatter)       
