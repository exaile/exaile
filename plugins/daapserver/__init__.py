import logging
from xl import event, settings
from . import exaile_parser
from .server import DaapServer
from . import daapserverprefs

logger = logging.getLogger(__file__)


# todo support multiple connections?
class CollectionWrapper:
    '''Class to wrap Exaile's collection to make it spydaap compatible'''

    class TrackWrapper:
        '''Wrap a single track for spydaap'''

        def __init__(self, id, track):
            self.track = track
            self.id = id
            self.parser = exaile_parser.ExaileParser()
            self.daap = None

        def get_dmap_raw(self):
            if self.daap is None:
                do = self.parser.parse(self.track)[0]
                if do is not None:
                    self.daap = b''.join([d.encode() for d in do])
                else:
                    self.daap = b''
            return self.daap

        def get_original_filename(self):
            return self.track.get_local_path()

    def __init__(self, collection):
        self.collection = collection
        self.map = []

    def __iter__(self):
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


class DaapServerPlugin:
    __exaile = None
    __daapserver = None

    def on_gui_loaded(self):
        event.add_callback(self.__on_settings_changed, 'plugin_daapserver_option_set')

        port = int(settings.get_option('plugin/daapserver/port', 3689))
        name = settings.get_option('plugin/daapserver/name', 'Exaile Share')
        host = settings.get_option('plugin/daapserver/host', '0.0.0.0')

        self.__daapserver = DaapServer(
            CollectionWrapper(self.__exaile.collection), port=port, name=name, host=host
        )
        if settings.get_option('plugin/daapserver/enabled', True):
            self.__daapserver.start()

    def enable(self, exaile):
        self.__exaile = exaile

    def teardown(self, exaile):
        self.__daapserver.stop_server()

    def disable(self, exaile):
        self.teardown(exaile)
        self.__daapserver = None

    def get_preferences_pane(self):
        return daapserverprefs

    def __on_settings_changed(self, event, setting, option):
        if self.__daapserver is None:
            logger.error('Option set on uninitialized plugin. This is wrong.')
        if option == 'plugin/daapserver/name':
            self.__daapserver.set(name=settings.get_option(option, 'Exaile Share'))
        if option == 'plugin/daapserver/port':
            self.__daapserver.set(port=int(settings.get_option(option, 3689)))
        if option == 'plugin/daapserver/host':
            self.__daapserver.set(host=settings.get_option(option, '0.0.0.0'))
        if option == 'plugin/daapserver/enabled':
            enabled = setting.get_option(option, True)
            if enabled:
                if not self.__daapserver.start():
                    logger.error('failed to start DAAP Server.')
            else:
                self.__daapserver.stop_server()


plugin_class = DaapServerPlugin
