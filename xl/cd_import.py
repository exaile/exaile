#!/usr/bin/env python

# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import pygtk
pygtk.require('2.0')
import gtk, gobject

import pygst
pygst.require('0.10')
import gst

from gettext import gettext as _
import string, os

import xlmisc, common, media, library 

# some info for every import format (a bit ugly perhaps)
formatdict = {
            "MP3": {
                "Very High":192,
                "High":160,
                "Medium":128,
                "Low":64,
                "ext":"mp3",
                "plugin":"lame"
            },
            "MP3 VBR": {
                "Very High":192,
                "High":160,
                "Medium":128,
                "Low":64,
                "ext":"mp3",
                "plugin":"lame"
            },
            "Ogg Vorbis": {
                "Very High":0.8,
                "High":0.6,
                "Medium":0.4,
                "Low":0.2,
                "ext":"ogg",
                "plugin":"vorbisenc"
            },
            "FLAC": {
                "Very High":8,
                "High": 6,
                "Medium": 4,
                "Low": 2,
                "ext":"flac",
                "plugin":"flacenc"
            }
}


def check_import_formats():
    """
        Return a list of supported encoding formats for importing
    """
    ret = []
    for format, caps in formatdict.iteritems():
        try:
            x = gst.element_factory_find(caps["plugin"])
        except gst.PluginNotFoundError:
            continue
        ret.append(format)

    return ret

class CDImporter(object):
    """
        Imports CDs
    """
    def __init__(self, exaile):
        """
            Initialize 
        """
        self.exaile = exaile
        self.xml = exaile.xml
        self.settings = exaile.settings

        self.importing = False
        self.gst_running = False
        self.overwrite_answer = None

        self.pipeline = None

    def get_pipeline(self, tracknum, dest):
        """
            Construct a gstreamer pipeline either from a list of presets
            or from a string given by the user.
        """
        if self.settings.get_boolean('import/use_custom', False):
            mapping = dict(dest=dest)
            import_custom = self.settings.get_string('import/custom', '')
            template = string.Template(import_custom)
            try:
                cmd = template.substitute(mapping)
            except KeyError, e:
                xlmisc.log('Could not substitute $' + e)
                return
            
            return gst.parse_launch(cmd)
        else:
            format = self.settings.get_str('import/format')
            quality = self.settings.get_str('import/quality')
            vbr = self.settings.get_boolean('import/vbr', False)

            if format == 'MP3':
                encoder = 'lame bitrate=%d ! id3mux v1-tag=1' % (formatdict[format][quality],)
            elif format == 'MP3 VBR':
                encoder = 'lame vbr=4 vbr-mean-bitrate=%d ! id3mux v1-tag=1' % \
                    (formatdict[format][quality],)
            elif format == 'Ogg Vorbis':
                encoder = 'vorbisenc quality=%0.1f ! oggmux' % (formatdict[format][quality],)
            elif format == 'FLAC':
                encodern = 'flacenc quality=%d' % (formatdict[format][quality],)
            else:
                xlmisc.log("Unknown import format")
                return None

            source = "cdparanoiasrc track=%d" % (tracknum,)
            sink = "filesink location=\"%s\"" % (dest,)
            cmd = '%s ! audioconvert ! %s ! %s' % (source, encoder, sink)
            try:
                pipe = gst.parse_launch(cmd)
            except Exception, e:
                xlmisc.log("Could not construct gstreamer pipe:" + str(e))

            return pipe

    @common.threaded
    def do_import(self, songs):
        """
            Start importing the given songs
        """
        if not self.exaile.settings.get_str('import/location', '') \
            or not self.exaile.settings.get_str('import/naming', ''):
            gobject.idle_add(common.error, self.exaile.window, 
                            _('Please set the import settings'
                            ' in the Preferences dialog before importing '
                            'anything.'))
            return

        import_xml = gtk.glade.XML('exaile.glade', 'ImportDialog', 'exaile')

        dialog = import_xml.get_widget('ImportDialog')
        dialog.set_transient_for(self.exaile.window)
        dialog.show_all()

        bar = import_xml.get_widget('import_progressbar')
        label = import_xml.get_widget('import_status')
        stop_button = import_xml.get_widget('import_stop_button')
        stop_button.connect('clicked', lambda *e: self.stop_import())

        self.importing = True
        self.overwrite_answer = None

        for i, song in enumerate(songs):
            if not self.importing: break 
            # TRANSLATORS: CD import status
            bar.set_text(_("Track %(current)d/%(total)d") % {
                'imported': i + 1,
                'total': len(songs)
            })
            bar.set_fraction(float(i)/len(songs))
            label.set_markup('<big>' + song.title + '</big>')
            self.import_track(song)
            while self.gst_running:
                continue

        dialog.destroy()

        return

    @common.synchronized
    def import_track(self, song):
        """
            Imports one track using a gstreamer pipeline
        """
        song.loc = self.make_dest(song)
        if not song.loc:
            xlmisc.log('Could not construct destination filename for ' + str(song))
        try:
            if not os.path.exists(os.path.dirname(song.io_loc)):
                os.makedirs(os.path.dirname(song.io_loc))
            if os.path.exists(song.io_loc):
                if self.overwrite_answer != "yes_all" \
                    and self.overwrite_answer != "no_all":
                    self.overwrite_answer = None
                    gobject.idle_add(ask_overwrite, self, self.exaile.window, song)
                    while not self.overwrite_answer:
                        pass

                if self.overwrite_answer == "yes" \
                    or self.overwrite_answer == "yes_all":
                    pass
                elif self.overwrite_answer == "no" \
                    or self.overwrite_answer == "no_all":
                    return

        except os.error, e:
                xlmisc.log('Could not create directory "' + 
                    os.path.dirname(song.io_loc) + '": ' + e.args[1])
        
        self.pipeline = self.get_pipeline(song.track, song.io_loc)
        if not self.pipeline:
            xlmisc.log('Could not construct gstreamer pipeline, check your settings!')

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self.gst_error_cb)
        bus.connect('message::eos', self.gst_eos_cb, song)
        self.gst_running = True
        self.pipeline.set_state(gst.STATE_PLAYING)
        return

    def tag_track(self, track):
        """
            Use the track's metadata to tag the file
        """
        media.write_tag(track)
        return

    def add_track(self, track):
        """
            Add a track to the library
        """
        dir = [os.path.dirname(track.io_loc)]
        self.exaile.library_manager.update_library_add(dir)
        return

    def make_dest(self, song):
        """
            Constructs the destination filename using the 
            metadata and preferences
        """
        location = self.settings.get_str('import/location', '')
        naming = self.settings.get_str('import/naming', '')
        pref = self.settings.get_str('import/format', 'MP3')
        if not pref or not location: 
            print "VVL, satan:", pref, location # FIXME: ??
            return ''

        extension = formatdict[pref]['ext']

        # TODO: this mapping should be more complete (e.g. cd number?)
        mapping = dict(artist=song.artist, album=song.album, title=song.title,\
                    ext=extension, num=(song.track or ''))
        template = string.Template(naming)
        try:
            ret = template.substitute(mapping)
        except KeyError, e:
            xlmisc.log('Could not substitute $' + e)
        ret = os.path.join(location, ret)
        return ret

    def gst_error_cb(self, bus, msg, *args):
        """
            If Gstreamer encounters an error, handle it here
            (Right now all we do is print to the log and stop)
        """
        error = None
        debug = None
        (error, debug) = msg.parse_error()
        xlmisc.log('gstreamer error: ' + error.message)

        self.stop_import()
        return

    def gst_eos_cb(self, bus, msg, track):
        """
        Stop the pipeline when EOS is reached, tag the track and add to library
        """
        self.pipeline.set_state(gst.STATE_NULL)
        self.gst_running = False
        self.tag_track(track)
        self.add_track(track)
        return

    def stop_import(self):
        """
            Stop importing when stop button is clicked
        """
        self.pipeline.set_state(gst.STATE_NULL)
        self.gst_running = False
        self.importing = False


def ask_overwrite(importer, parent, path):
    """
        Throws up a dialog asking whether the user wants to overwrite an 
        existing file, with yes/no/yes to all/no to all alternatives
    """
    dialog = gtk.Dialog(_('Overwrite file'), parent, 
        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        (_('Yes to All'), gtk.RESPONSE_OK,
        gtk.STOCK_YES, gtk.RESPONSE_YES,
        gtk.STOCK_NO, gtk.RESPONSE_NO,
        _('No to All'), gtk.RESPONSE_CLOSE))

    image = gtk.image_new_from_stock(gtk.STOCK_DIALOG_QUESTION, 
        gtk.ICON_SIZE_DIALOG)
    text = gtk.Label(_('The file %s already exists, do you want to '
            'overwrite it?') % (path,))
    text.set_line_wrap(True)

    hb = gtk.HBox(spacing=8)
    hb.pack_start(image)
    hb.pack_start(text)

    dialog.vbox.pack_start(hb)
    dialog.vbox.show_all()

    response = dialog.run()

    
    if response == gtk.RESPONSE_YES:
        importer.overwrite_answer = "yes" 
    elif response == gtk.RESPONSE_NO:
        importer.overwrite_answer = "no" 
    elif response == gtk.RESPONSE_OK:
        importer.overwrite_answer = "yes_all" 
    elif response == gtk.RESPONSE_CLOSE or \
            response == gtk.RESPONSE_DELETE_EVENT:
        importer.overwrite_answer = "no_all" 

    dialog.destroy()

    return False
