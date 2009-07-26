from xl import xdg, metadata
from xl.nls import gettext as _
import os
import gtk
import gobject
import gtk.glade

class TrackPropertiesDialog(gobject.GObject):
    def __init__(self, parent, track):
        gobject.GObject.__init__(self)

        self.track = track
        self.xml = gtk.glade.XML(
            xdg.get_data_path('glade/trackproperties_dialog.glade'),
            'TrackPropertiesDialog', 'exaile')
        self.dialog = self.xml.get_widget('TrackPropertiesDialog')
        self.dialog.set_transient_for(parent)

        self._setup_widgets()
        self._connect_events()
        self._populate_from_track(track)

    def _connect_events(self):
        self.xml.signal_autoconnect({
            'on_ok_button_clicked': self._on_ok,
            'on_delete': self._on_close,
            'on_close_button_clicked': self._on_close,
        })

    def _setup_widgets(self):

        for item in ('title', 'artist', 'album', 'tracknumber', 
            'genre', 'date', 'loc', 'length', 'bitrate', 'size',
            'playcount'):
            field = self.xml.get_widget('%s_entry' % item)
            setattr(self, '%s_entry' % item, field)

    def _populate_from_track(self, track):
        
        for item in ('title', 'artist', 'album', 'tracknumber',
            'date'):
            value = metadata.j(track[item])
            field = getattr(self, '%s_entry' % item)
            if not value: value = ''
            field.set_text(value)

        self.loc_entry.set_text(track.get_loc())

        try:
            seconds = track.get_duration()
            text = _("%(minutes)d:%(seconds)02d") % \
                {'minutes' : seconds // 60, 'seconds' : seconds % 60}
        except:
            #TRANSLATORS: Default track length
            text = _("0:00")

        self.length_entry.set_text(text)
        self.bitrate_entry.set_text(track.get_bitrate())
   
        if track.is_local():
            text = "%.02fMB" % (os.path.getsize(track.local_file_name())
                / 1024.0 / 1024.0)
            self.size_entry.set_text(text)
        else:
            self.size_entry.set_text('N/A')

        value = track['__playcount']
        if not value: value = 0 
        self.playcount_entry.set_text(str(value))

    def _on_ok(self, *e):
        track = self.track
        for item in ('title', 'artist', 'album', 'tracknumber', 'date'):
            value = getattr(self, '%s_entry' % item).get_text()
            track[item] = value

        self.track.write_tags()
        self.dialog.response(gtk.RESPONSE_OK)

    def _on_close(self, *e):
        self.dialog.response(gtk.RESPONSE_CANCEL)

    def run(self):
        return self.dialog.run()

    def hide(self):
        self.dialog.hide()

# vim: et sts=4 sw=4
