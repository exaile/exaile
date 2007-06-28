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


import httplib, re, urllib, md5, threading, sys, os, xlmisc
import urllib2, config, gobject, gtk, time
import tracks
from gettext import gettext as _
COVER_WIDTH = 100

__revision__ = ".01"

#LOCALES = ['ca', 'de', 'fr', 'jp', 'uk', 'us']

def get_server(locale):
    #do 'es' here because webservices.amazon.es doesn't exist
    if locale in ('en', 'us', 'es'):
        return "xml.amazon.com"
    elif locale in ('jp', 'uk'):
        return "webservices.amazon.co.%s" % locale
    else:
        return "webservices.amazon.%s" % locale

def get_encoding(locale):
    if locale == 'jp':
        return 'utf-8'
    else:
        return 'iso-8859-1'

KEY = "15VDQG80MCS2K1W2VRR2" # Adam Olsen's key (synic)
QUERY = "/onca/xml3?t=webservices-20&dev-t=%s&mode=music&type=lite&" % (KEY) + \
    "locale={locale}&page=1&f=xml&KeywordSearch="
IMAGE_PATTERN = re.compile(
    r"<ImageUrlLarge>http://(\w+\.images-amazon\.com)"
    "(/images/.*?\.jpg)</ImageUrlLarge>", re.DOTALL)

"""
    Fetches album covers from Amazon.com
"""

class Cover(dict):
    """
        Represents a single album cover
    """
    def save(self, savepath='.'):
        """
            Saves the image to a file
        """
        if not os.path.isdir(savepath):
            os.mkdir(savepath)

        savepath = "%s%s%s.jpg" % (savepath, os.sep, self['md5'])
        handle = open(savepath, "w")
        handle.write(self['data'])
        handle.close()
        self['filename'] = savepath

    def filename(self):
        return "%s.jpg" % self['md5']

class CoverFetcherThread(threading.Thread):
    """
        Fetches all covers for a search string
    """
    def __init__(self, search_string, _done_func, fetch_all=False, locale='us'): 
        """
            Constructor expects a search string and a function to call
            when it's _done
        """

        xlmisc.log("new thread created with %s" % search_string)
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self._done = False
        self._done_func = _done_func
        self.search_string = search_string
        self.locale = locale
        self.fetch_all = fetch_all
    

    def abort(self):
        """
            Aborts the download thread. Note that this does not happen
            immediately, but happens when the thread is done blocking on its
            current operation
        """
        self._done = True
    

    def run(self):
        """
            Actually connects and fetches the covers
        """
        xlmisc.log("cover thread started")
        conn = httplib.HTTPConnection(get_server(self.locale))

        if self._done: return
        try:
            query = QUERY.replace("{locale}", self.locale)
            # FIXME: always UTF-8?
            search_string = self.search_string.decode('utf-8')
            search_string = search_string.encode(
                get_encoding(self.locale), 'replace')
            string = query + urllib.quote(search_string, '')
        except KeyError:
            string = ""
        try:
            conn.request("GET", string)
        except urllib2.URLError:
            pass
        except:
            xlmisc.log_exception()
            pass
        if self._done: return

        response = conn.getresponse()
        if response.status != 200:
            print dir(response)
            print response.reason
            print get_server(self.locale), string
            xlmisc.log("Invalid response received: %s" % response.status)
            gobject.idle_add(self._done_func, [])
            return

        page = response.read()

        covers = []
        for m in IMAGE_PATTERN.finditer(page):
            if self._done: return

            cover = Cover()

            conn = httplib.HTTPConnection(m.group(1))
            try:
                conn.request("GET", m.group(2))
            except urllib2.URLError:
                continue
            response = conn.getresponse()
            cover['status'] = response.status
            if response.status == 200:
                data = response.read()
                if self._done: return
                conn.close()
                cover['data'] = data
                cover['md5'] = md5.new(data).hexdigest()

                # find out if the cover is valid
                if len(data) > 1200:
                    covers.append(cover)
                    if not self.fetch_all: break

        conn.close()

        if len(covers) == 0:
            xlmisc.log("Thread done.... *shrug*, no covers found")

        if self._done: return

        # call after the current pending event in the gtk gui
        gobject.idle_add(self._done_func, covers)

class CoverEventBox(gtk.EventBox):
    def __init__(self, exaile):
        gtk.EventBox.__init__(self)
        self.exaile = exaile
        self.db = exaile.db
        self.setup_cover_menu()
        self.connect('button_press_event', self.cover_clicked)

    def setup_cover_menu(self):
        """
            Sets up the menu for when the user right clicks on the album cover
        """
        menu = xlmisc.Menu()
        self.cover_full = menu.append(_("View Full Image"),
            self.cover_menu_activate)
        self.cover_fetch = menu.append(_("Fetch from Amazon"),
            self.cover_menu_activate)
        self.cover_search = menu.append(_("Search Amazon"),
            self.cover_menu_activate)
        self.cover_custom = menu.append(_("Set Custom Image"),
            self.cover_menu_activate)
        self.remove_cover = menu.append(_("Remove Cover"),
            self.remove_cover)
        self.cover_menu = menu

    def remove_cover(self, item, param=None):
        """
            removes the cover art for the current track
        """
        track = self.exaile.player.current
        if not track: return

        artist_id = tracks.get_column_id(self.db, 'artists', 'name',
            track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        self.db.execute("UPDATE albums SET image='nocover' WHERE id=?", (album_id,))
        self.exaile.cover.set_image(os.path.join("images", "nocover.png"))

    def cover_menu_activate(self, item, user_param=None): 
        """
            Called when one of the menu items in the album cover popup is
            selected
        """
        if item == self.cover_fetch:
            self.exaile.status.set_first(_("Fetching from Amazon..."))
            xlmisc.CoverFrame(self.exaile, self.exaile.player.current)
        elif item == self.cover_search:
            xlmisc.CoverFrame(self.exaile, self.exaile.player.current, True)
        elif item == "showcover" or item == self.cover_full:
            if "nocover" in self.cover.loc: return
            track = self.exaile.player.current
            xlmisc.CoverWindow(self.exaile.window, self.exaile.cover.loc, 
                _("%(album)s by %(artist)s") %
                {
                    'album': track.album,
                    'artist': track.artist
                })
        elif item == self.cover_custom:
            track = self.exaile.player.current

            dialog = gtk.FileChooserDialog(_("Choose an image"), self.exaile.window,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_current_folder(self.exaile.get_last_dir())

            # Image Files
            filter = gtk.FileFilter()
            filter.set_name(_("Image Files"))
            for pattern in ('*.jpg', '*.jpeg', '*.gif', '*.png'):
                filter.add_pattern(pattern)
            dialog.add_filter(filter)
            # All Files
            filter = gtk.FileFilter()
            filter.set_name(_("All Files"))
            filter.add_pattern('*')
            dialog.add_filter(filter)

            result = dialog.run()
            dialog.hide()

            if result == gtk.RESPONSE_OK:
                self.exaile.last_open_dir = dialog.get_current_folder()
                handle = open(dialog.get_filename(), "r")
                data = handle.read()
                handle.close()

                (f, ext) = os.path.splitext(dialog.get_filename())
                newname = md5.new(data).hexdigest() + ext
                handle = open(os.path.join(self.exaile.get_settings_dir(), "covers",
                    newname), "w")
                handle.write(data)
                handle.close()

                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                artist_id = tracks.get_column_id(self.db, 'artists', 'name',
                    track.artist)
                album_id  = tracks.get_album_id(self.db, artist_id,
                    track.album)

                xlmisc.log(newname)

                self.db.execute("UPDATE albums SET image=? WHERE id=?",
                    (newname, album_id))

                if track == self.exaile.player.current:
                    self.exaile.cover_manager.stop_cover_thread()
                    self.exaile.exaile.cover.set_image(
                        os.path.join(self.get_settings_dir(),
                        "covers", newname))

    def cover_clicked(self, widget, event):
        """
            Called when the cover is clicked on
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if 'nocover' in self.exaile.cover.loc: return
            track = self.exaile.player.current
            
            xlmisc.CoverWindow(self.exaile.window, self.exaile.cover.loc,
                _("%(album)s by %(artist)s") %
                {
                    'album': track.album,
                    'artist': track.artist
                })
        elif event.button == 3:
            if not self.exaile.player.current: return
            self.cover_menu.popup(None, None, None, 
                event.button, event.time)

class CoverManager(object):
    """
        Manages album art for Exaile
    """
    def __init__(self, exaile):
        self.cover_thread = None
        self.exaile = exaile
        self.db = exaile.db

    def got_stream_cover(self,covers):
        xlmisc.log("got stream cover")
        self.exaile.status.set_first(None)
        if len(covers) == 0:
            self.exaile.status.set_first(_("No covers found."), 2000)
        
        for cover in covers:
            if(cover['status'] == 200):
                savepath = os.path.join(self.exaile.get_settings_dir(), "covers",
                    "streamCover.jpg")
                handle = open(savepath, "w")
                handle.write(cover['data'])
                handle.close()
                self.exaile.cover.set_image(savepath)
                break

    def got_covers(self, covers): 
        """
            Gets called when all covers have been downloaded from amazon
        """
        track = self.exaile.player.current
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        self.exaile.status.set_first(None)
        if len(covers) == 0:
            self.exaile.status.set_first(_("No covers found."), 2000)
            self.db.execute("UPDATE albums SET image='nocover' WHERE id=?",
                (album_id,))

        # loop through all of the covers that have been found
        for cover in covers:
            if(cover['status'] == 200):
                cover.save(os.path.join(self.exaile.get_settings_dir(), "covers"))
                xlmisc.log(cover['filename'])
                self.exaile.cover.set_image(cover['filename'])

                self.db.execute("UPDATE albums SET image=?, amazon_image=1 WHERE id=?",
                    (cover['md5'] + ".jpg", album_id))
                
                break

    def check_image_age(self, album_id, image):
        """
            This checks to see if the image is too old for Amazon's ULA, and
            if it is, it refetches the image
        """
        info = os.stat(os.path.join(self.exaile.get_settings_dir(), 'covers', image))

        max_time = 30 * 24 * 60 * 60 # 1 month
        if time.time() - info[9] > max_time:
            self.exaile.status.set_first(_('Current amazon image is too old, '
                'fetching  a new one'), 2000)
            self.db.execute('UPDATE albums SET image=NULL, amazon_image=0 '
                'WHERE id=?', (album_id,))
            self.fetch_cover(self.exaile.player.current)
            return False
        return True
   
    def fetch_cover(self, track, popup=None): 
        """
            Fetches the cover from the database.  If it can't be found
            there it fetches it from amazon
        """
        w = COVER_WIDTH
        if not popup:
            self.exaile.cover.set_image(os.path.join("images", "nocover.png"))
        if track == None: return
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        # check to see if a cover already exists
        row = self.db.read_one("albums", "image, amazon_image", 'id=?', (album_id,))

        if row != None and row[0] != "" and row[0] != None:
            if row[0] == "nocover": 
                cover = self.fetch_from_fs(track)
                if cover:
                    if popup: return cover
                    self.exaile.cover.set_image(cover)
                    return
                return os.path.join("images", "nocover.png")
            if os.path.isfile(os.path.join(self.exaile.get_settings_dir(), 
                "covers", row[0])):

                if popup: return os.path.join(self.exaile.get_settings_dir(), 
                    "covers", row[0])

                # check to see if we need to recache this image
                if row[1]:
                    if not self.check_image_age(album_id, row[0]): return

                self.exaile.cover.set_image(os.path.join(self.exaile.get_settings_dir(), 
                    "covers", row[0]))
                return

        cover = self.fetch_from_fs(track)
        if cover:
            if popup: return cover
            else: self.exaile.cover.set_image(cover)
            return

        if popup != None: return os.path.join("images", "nocover.png")
        self.stop_cover_thread()

        if self.exaile.settings.get_boolean("fetch_covers", True):
            locale = self.exaile.settings.get_str('amazon_locale', 'us')
            if track.type == 'stream':
                xlmisc.log("we got a stream type cover fetch")
                self.cover_thread = CoverFetcherThread("%s %s"\
                    % (track.artist,track.title),
                    self.got_stream_cover, locale=locale)

            else:    
                album = track.album
                if not album:
                    album = track.title
                self.cover_thread = CoverFetcherThread("%s %s" \
                    % (album,track.artist),
                    self.got_covers, locale=locale)

            self.exaile.status.set_first(_("Fetching cover art from Amazon..."))
            self.cover_thread.start()
            
    def fetch_from_fs(self, track, event=None):
        """
            Fetches the cover from the filesystem (if there is one)
        """
        dir = os.path.dirname(track.loc)

        names = self.exaile.settings.get_list('art_filenames', 
            ['cover.jpg', 'folder.jpg', '.folder.jpg', 'album.jpg', 'art.jpg'])
        if not names: return None

        for f in names:
            f = f.strip()
            if os.path.isfile(os.path.join(dir, f)):
                return os.path.join(dir, f)

        return None

    def stop_cover_thread(self): 
        """
            Aborts the cover thread
        """

        if self.cover_thread != None:
            xlmisc.log("Aborted cover thread")
            self.cover_thread.abort()
            self.cover_thread = None
