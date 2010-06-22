
import logging
import gobject
from xl import collection, event, settings
import spydaap.parser.exaile

log = logging.getLogger(__file__)


# todo support multiple connections?
class CollectionWrapper:
    class TrackWrapper:
        def __init__(self, id, track):
            self.track = track
            self.id = id
            self.parser = spydaap.parser.exaile.ExaileParser()
            self.daap = None

        def get_dmap_raw(self):
            if self.daap is None:
                self.daap = ''.join([d.encode() for d in self.parser.parse(self.track)[0]])
            return self.daap

        def get_original_filename(self):
            return self.track.get_local_path()

    def __init__(self, collection):
        self.collection = collection
        self.map = []

    def __iter__(self):
        print 'GEN ITERRR'
        i = 0
        self.map = []
        for t in self.collection:
            self.map.append(self.TrackWrapper(i, t))
            yield self.map[i]
            i += 1
    
    def get_item_by_id(self, id):
        return self.map[int(id)]
    
    def __getitem__(self, idx):
        return self.map[idx]

    def __len__(self):
        return len(self.collection)

from server import DaapServer

ds = None

def _enable(exaile):
    # real enable
    global ds
    
    event.add_callback(on_settings_change, 'plugin_daapserver_option_set')
    
    port = int(settings.get_option('plugin/daapserver/port', 3689))
    name = settings.get_option('plugin/daapserver/name', 'Exaile Share')
    host = settings.get_option('plugin/daapserver/host', '0.0.0.0')
    
#    DaapServer.init(exaile.collection,port=port,name=name)
    ds = DaapServer(CollectionWrapper(exaile.collection), port=port, name=name, host=host)
    if( settings.get_option('plugin/daapserver/enabled', True) ):
        ds.start()

def __enb(evname, exaile, wat):
    gobject.idle_add(_enable, exaile)


def enable(exaile):
    if exaile.loading:
        event.add_callback(__enb, 'gui_loaded')
    else:
        __enb(None, exaile, None)

def teardown(exaile):
    ds.stop_server()

def disable(exaile):
    ds.stop_server()
    
    

# settings stuff
import daapserverprefs

def get_preferences_pane():
    return daapserverprefs
    
def on_settings_change(event, setting, option):
    if option == 'plugin/daapserver/name' and ds is not None:
        ds.set(name=settings.get_option(option,'Exaile Share'))
    if option == 'plugin/daapserver/port' and ds is not None:
        ds.set(port=settings.get_option(option,3689))
    if option == 'plugin/daapserver/host' and ds is not None:
        ds.set(host=settings.get_option(option,'0.0.0.0'))
    if option == 'plugin/daapserver/enabled' and ds is not None:
        enabled = setting.get_option(option, True)
        if enabled:
            if not ds.start():
                pass
#                settings.set_option('plugin/daapserver/enabled', False) ? 
        else:
            ds.stop_server()
