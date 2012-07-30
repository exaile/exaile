import gobject
import gtk

from xlgui import oldmenu as xlmenu

class JamendoMenu(xlmenu.GenericTrackMenu):

    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, ()),
        'download-items': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self):
        xlmenu.GenericTrackMenu.__init__(self);

    def _create_menu(self):
        self.append_item = self.append('Append to Current', lambda *e:
            self.on_append_items(), gtk.STOCK_ADD)
        self.download_item = self.append('Download to Library', lambda *e:
            self.on_download(), gtk.STOCK_SAVE)

    def on_append_items(self, selected=None):
        self.emit('append-items')

    def on_download(self, selected=None):
        self.emit('download-items')

