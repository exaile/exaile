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


import httplib, re, urllib, md5, threading, os, xlmisc
import urllib2, gobject, gtk, time
import library, common
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
        handle = open(savepath, "wb")
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
        self.cover_menu = CoverMenu(self.exaile, is_current_song=True)
        self.connect('button_press_event', self.cover_clicked)

    def cover_clicked(self, widget, event):
        """
            Called when the cover is clicked on
        """
        track = self.exaile.player.current
        if not track:
            return

        if event.type == gtk.gdk._2BUTTON_PRESS:
            if 'nocover' in self.exaile.cover.loc:
                CoverFrame(self.exaile, track)
            else:
                CoverWindow(self.exaile.window, self.exaile.cover.loc,
                    _("%(album)s by %(artist)s") %
                    {
                        'album': track.album,
                        'artist': track.artist
                    })
        elif event.button == 3:
            self.cover_menu.menu.popup(None, None, None,
                event.button, event.time)

FETCHER = None
def get_cover_fetcher(exaile):
    """
        gets the cover fetcher instance
    """
    global FETCHER

    try:
        if not CoverFetcher.stopped:
            return FETCHER
    except:
        xlmisc.log_exception()
        pass

    FETCHER = CoverFetcher(exaile)
    return FETCHER

class CoverManager(object):
    """
        Manages album art for Exaile
    """
    def __init__(self, exaile):
        self.cover_thread = None
        self.exaile = exaile
        self.db = exaile.db

    def fetch_covers(self, event):
        """
            Fetches all covers
        """
        fetcher = get_cover_fetcher(self.exaile)
        fetcher.dialog.show_all()

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
        artist_id = library.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = library.get_album_id(self.db, artist_id, track.album)

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
        artist_id = library.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = library.get_album_id(self.db, artist_id, track.album)

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
                self.cover_thread = CoverFetcherThread("%s - %s" \
                    % (track.artist, album),
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

class CoverWrapper(object):
    """
        Wraps a cover object
    """
    def __init__(self, artist, album, location):
        self.artist = artist
        self.album = album
        self.location = location

    def __str__(self):
        title = "%s" % (self.album)
        if len(title) > 12:
            title = title[0:10] + "..."
        return title

class CoverFetcher(object):
    """
        Fetches all covers in the library
    """
    stopped = True

    def __init__(self, parent):
        """ 
            Initializes the dialog
        """
        self.exaile = parent
        self.db = self.exaile.db
        xml = gtk.glade.XML('exaile.glade', 'CoverFetcher', 'exaile')
        self.icons = xml.get_widget('cover_icon_view')

        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_model(self.model)
        self.icons.set_item_width(90)
        self.artists = None
        self.go = False
        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)
        self.icons.connect('button-press-event',
            self.cover_clicked)
        # Leave blank since it just needs the reference for now
        self.current_path = None
        self.cover_menu = CoverMenu(self.exaile, self.model, self.current_path)
        self.status = xml.get_widget('cover_status_bar')
        self.icons.connect('motion-notify-event',
            self.mouse_move)
        self.icons.connect('leave-notify-event',
            lambda *e: self.status.set_label(''))
        self.dialog = xml.get_widget('CoverFetcher')
        self.dialog.connect('delete-event', self.cancel)

        self.progress = xml.get_widget('fetcher_progress')
        self.label = xml.get_widget('fetcher_label')

        xml.get_widget('fetcher_cancel_button').connect('clicked',
            self.cancel)
        self.stopstart = xml.get_widget('fetcher_stop_button')
        self.stopstart.connect('clicked', self.toggle_running)
        xml.get_widget('fetcher_refresh_button').connect('clicked',
            self.refresh)
        self.current = 0
        self.dialog.show_all()
        # Give it a parent now that it exists.
        self.cover_menu.set_parent(self.dialog)
        xlmisc.finish()
        self.total = self.calculate_total()
        self.label.set_label(_("%d covers left to collect.") % self.total)
        if self.go:
            self.toggle_running(None)

    def refresh(self, event):
        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_model(self.model)
        self.icons.set_item_width(90)
        self.total = self.calculate_total()

    def cancel(self, *event):
        """
            Closes the dialog
        """
        CoverFetcher.stopped = True
        self.dialog.destroy()

    def toggle_running(self, event):
        """
            Toggles the running state of the fetcher
        """
        if CoverFetcher.stopped:
            if not self.artists:
                self.go = True
                self.stopstart.set_use_stock(True)
                self.stopstart.set_label('gtk-stop')
                return
                
            CoverFetcher.stopped = False
            self.stopstart.set_use_stock(True)
            self.stopstart.set_label('gtk-stop')
            self.fetch_next()
        else:
            self.stopstart.set_use_stock(False)
            # TRANSLATORS: Start fetching cover arts
            self.stopstart.set_label(_('Start'))
            self.stopstart.set_image(gtk.image_new_from_stock('gtk-yes',
                gtk.ICON_SIZE_BUTTON))
            CoverFetcher.stopped = True
            if self.cover_thread:
                self.cover_thread.abort()

    def fetch_next(self, event=None):
        """
            Fetches the next cover in line
        """
        if not self.artists:
            self.label.set_label(_("All Covers have been Fetched."))
            self.stopstart.set_sensitive(False)
            return
        self.artist = self.artists[0]
        if CoverFetcher.stopped: return
        
        try:
            self.album = self.needs[self.artist].pop()
        except IndexError:
            del self.needs[self.artist]
            self.artists.remove(self.artist)
            self.fetch_next()
            return

        if not self.needs[self.artist]:
            del self.needs[self.artist]
            self.artists.remove(self.artist)

        locale = self.exaile.settings.get_str('amazon_locale', 'us')
        self.cover_thread = CoverFetcherThread("%s - %s" %
            (self.artist, self.album),
            self.got_covers, locale=locale)
        self.cover_thread.start()
        # TRANSLATORS: Album cover fetching status
        self.label.set_label(_("%(remaining)d left: %(album)s by %(artist)s") % 
            {
                'remaining': (self.total - self.current),
                'album': self.album,
                'artist': self.artist
            })

    def got_covers(self, covers):
        """
            Called when the fetcher thread has gotten all the covers for this
            album
        """
        if self.stopped: return
        artist_id = library.get_column_id(self.db, 'artists', 'name', self.artist)
        album_id = library.get_album_id(self.db, artist_id, self.album)
        if len(covers) == 0:
            self.db.execute("UPDATE albums SET image=? WHERE id=?",
                ('nocover', album_id,))
            
        # loop through all of the covers that have been found
        for cover in covers:
            if(cover['status'] == 200):
                cover.save(os.path.join(self.exaile.get_settings_dir(),
                    'covers'))
                xlmisc.log(cover['filename'])

                try:
                    self.db.execute("UPDATE albums SET image=? WHERE id=?", 
                        (cover['md5'] + ".jpg", album_id))
                except:
                    xlmisc.log_exception()

                image = os.path.join(self.exaile.get_settings_dir(), 'covers',
                    cover['md5'] + ".jpg")
                loc = image
                image = gtk.gdk.pixbuf_new_from_file(image)
                image = image.scale_simple(80, 80, 
                    gtk.gdk.INTERP_BILINEAR)
                
                if self.found.has_key("%s - %s" % (self.artist.lower(), self.album.lower())):
                    iter = self.found["%s - %s" % (self.artist.lower(), self.album.lower())] 
                    object = self.model.get_value(iter, 2)
                    object.location = loc
                    self.model.set_value(iter, 1, image)
                break

        if self.stopped: return
        self.current = self.current + 1
        self.progress.set_fraction(float(self.current) / float(self.total))
        self.fetch_next()

    def mouse_move(self, widget, event):
        """
            Called when the mouse moves in the icon view
        """
        x, y = event.get_coords()
        x = int(x)
        y = int(y)

        path = self.icons.get_path_at_pos(x, y)
        #saves path so that it can be used by the menu to locate the album
        self.current_path = path
        self.cover_menu.current_path = path
        if not path:
            self.status.set_label('')
            return

        iter = self.model.get_iter(path)
        object = self.model.get_value(iter, 2)

        self.status.set_markup("<b>" + common.escape_xml(_("%(album)s by %(artist)s") %
            {
                'album': object.album,
                'artist': object.artist
            }) + "</b>")

    def calculate_total(self):
        """
            Finds the albums that need a cover
        """
        all = self.db.select("SELECT artists.name, albums.name, albums.image "
            "FROM tracks,albums,artists WHERE blacklisted=0 AND type=0 AND ( "
            "artists.id=tracks.artist AND albums.id=tracks.album)"
            " ORDER BY albums.name, artists.name")
        self.needs = dict()

        self.found = dict()
        count = 0
        for (artist, album, image) in all:
            if artist == '<Unknown>' or album == '<Unknown>': continue
            if not self.needs.has_key(artist):
                self.needs[artist] = []
            if album in self.needs[artist]: continue

            if image:
                if "nocover" in image:
                    continue
                else:
                    image = os.path.join(self.exaile.get_settings_dir(),
                        'covers', image)
            else:
                self.needs[artist].append(album)
                image = os.path.join("images", "nocover.png")

            if self.found.has_key("%s - %s" % (artist.lower(), album.lower())):
                continue

            title = CoverWrapper(artist, album, image)
            image = gtk.gdk.pixbuf_new_from_file(image)
            image = image.scale_simple(80, 80, 
                gtk.gdk.INTERP_BILINEAR)

            self.found["%s - %s" % (artist.lower(), album.lower())] = \
                self.model.append([title, image, title])
            if count >= 200: 
                count = 0
                t = 0
                for k, v in self.needs.iteritems():
                    t += len(v)
                self.label.set_label(_("%d covers left to collect.") % t)
                xlmisc.finish()
            count += 1

        count = 0
        for k, v in self.needs.iteritems():
            count += len(v)

        self.artists = self.needs.keys()
        self.artists.sort()

        return count

    def cover_clicked(self, widget, event):
        """
            Called when the cover is clicked on
        """
        track = self.current_path
        if not track:
            return
        # On double click (removed item_activated signal)
        if event.type == gtk.gdk._2BUTTON_PRESS:
            iter = self.model.get_iter(self.current_path)
            object = self.model.get_value(iter, 2)
            CoverWindow(self.dialog, object.location, _("%(album)s by %(artist)s") %
            {
                'album': object.album,
                'artist': object.artist
            })
        # Creates the nice Right click menu
        if event.button == 3:
            self.cover_menu.menu.popup(None, None, None,
                event.button, event.time)

class CoverWindow(object):
    """
        Shows the fullsize cover in a window
    """
    def __init__(self, parent, cover, title=''):
        """
            Initializes and shows the cover
        """
        xml = gtk.glade.XML('exaile.glade', 'CoverWindow', 'exaile')
        window = xml.get_widget('CoverWindow')
        box = xml.get_widget('cw_box')
        pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        image = gtk.Image()
        image.set_from_file(cover)
        image.set_size_request(pixbuf.get_width(), pixbuf.get_height())
        eventbox = gtk.EventBox()
        eventbox.add(image)
        box.pack_start(eventbox)

        eventbox.connect('button_release_event', self.button_press)
        window.set_title(title)
        window.set_transient_for(parent)
        window.show_all()
        self.window = window

    def button_press(self, widget, event):
        """
            Called when someone clicks on the event box
        """
        self.window.destroy()

class CoverFrame(object):
    """
        Fetches all album covers for a string, and allows the user to choose
        one out of the list
    """
    def __init__(self, parent, track, search=False, exaile_parent=None):
        """
            Expects the parent control, a track, an an optional search string
        """
        self.xml = gtk.glade.XML('exaile.glade', 'CoverFrame', 'exaile')
        self.window = self.xml.get_widget('CoverFrame')
        self.window.set_title("%s %s" % (track.artist, track.album))

        # This basically has to be done for exaile to pass the database
        # correctly also for exaile to not be the parent of the searcher

        if (exaile_parent == None):
            self.window.set_transient_for(parent.window)
            self.parent = parent.window
            self.exaile = parent
            self.db = self.exaile.db
        else:
            self.window.set_transient_for(parent)
            self.parent = parent
            self.exaile = exaile_parent

        self.track = track
        self.db = self.exaile.db
        self.prev = self.xml.get_widget('cover_back_button')
        self.prev.connect('clicked', self.go_prev)
        self.prev.set_sensitive(False)
        self.next = self.xml.get_widget('cover_forward_button')
        self.next.connect('clicked', self.go_next)
        self.xml.get_widget('cover_newsearch_button').connect('clicked',
            self.new_search)
        self.xml.get_widget('cover_cancel_button').connect('clicked',
            lambda *e: self.window.destroy())
        self.ok = self.xml.get_widget('cover_ok_button')
        self.ok.connect('clicked',
            self.on_ok)
        self.box = self.xml.get_widget('cover_image_box')
        self.cover = xlmisc.ImageWidget()
        self.cover.set_image_size(350, 350)
        self.box.pack_start(self.cover, True, True)

        self.last_search = "%s - %s" % (track.artist, track.album)

        if not search:
            locale = self.exaile.settings.get_str('amazon_locale', 'us')
            CoverFetcherThread("%s - %s" % (track.artist, track.album),
                self.covers_fetched, locale=locale).start()
        else:
            self.new_search()

    def new_search(self, widget=None):
        """
            Creates a new search string
        """
        dialog = common.TextEntryDialog(self.parent,
            _("Enter the search text"), _("Enter the search text"))
        dialog.set_value(self.last_search)
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            self.last_search = dialog.get_value()
            self.exaile.status.set_first(
                _("Searching for %s...") % self.last_search)
            self.window.hide()

            locale = self.exaile.settings.get_str('amazon_locale', 'us')
            CoverFetcherThread(self.last_search,
                self.covers_fetched, True, locale=locale).start()

    def on_ok(self, widget=None):
        """
            Chooses the current cover and saves it to the database
        """
        track = self.track
        cover = self.covers[self.current]
        artist_id = library.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = library.get_album_id(self.db, artist_id, track.album)

        self.db.execute("UPDATE albums SET image=? WHERE id=?", (cover.filename(),
            album_id))

        if track == self.exaile.player.current:
            self.exaile.cover_manager.stop_cover_thread()
            self.exaile.cover.set_image(os.path.join(
                self.exaile.get_settings_dir(), 'covers', cover.filename()))
        self.window.destroy()

    def go_next(self, widget):
        """
            Shows the next cover
        """
        if self.current + 1 >= len(self.covers): return
        self.current = self.current + 1
        self.show_cover(self.covers[self.current])
        if self.current + 1 >= len(self.covers):
            self.next.set_sensitive(False)
        if self.current - 1 >= 0:
            self.prev.set_sensitive(True)

    def go_prev(self, widget):
        """
            Shows the previous cover
        """
        if self.current - 1 < 0: return
        self.current = self.current - 1
        self.show_cover(self.covers[self.current])

        if self.current + 1 < len(self.covers):
            self.next.set_sensitive(True)
        if self.current - 1 < 0:
            self.prev.set_sensitive(False)

    def show_cover(self, c):
        """
            Shows the current cover
        """
        c.save(os.path.join(self.exaile.get_settings_dir(), 'covers') + os.sep)

        xlmisc.log(c.filename())

        self.cover.set_image(os.path.join(self.exaile.get_settings_dir(),
            'covers', c.filename()))

        self.window.show_all()

    def covers_fetched(self, covers):
        """
            Called when the cover fetcher thread has fetched all covers
        """
        self.exaile.status.set_first(None)
        self.covers = covers
        self.prev.set_sensitive(False)

        if not covers:
            common.error(self.parent, _("Sorry, no covers were found."))
            self.next.set_sensitive(False)
            self.ok.set_sensitive(False)
            self.window.show_all()
            return

        self.next.set_sensitive(len(covers) > 1)
        self.ok.set_sensitive(True)

        self.current = 0

        self.show_cover(self.covers[self.current])

class CoverMenu(xlmisc.Menu):

    def __init__(self, exaile, model=None, current_path=None, is_current_song=False):
        self.exaile = exaile
        self.db = self.exaile.db
        self.model = model
        self.current_path = current_path
        self.is_current = is_current_song
        self.menu = xlmisc.Menu()
        self.cover_full = self.menu.append(_("View Full Image"),
            self.cover_menu_activate)
        self.cover_fetch = self.menu.append(_("Fetch from Amazon"),
            self.cover_menu_activate)
        self.cover_search = self.menu.append(_("Search Amazon"),
            self.cover_menu_activate)
        self.cover_custom = self.menu.append(_("Set Custom Image"),
            self.cover_menu_activate)
        self.remove_cover_menu = self.menu.append(_("Remove Cover"),
            self.cover_menu_activate)

    def cover_menu_activate(self, item, user_param=None):
        """
            Called when one of the menu items in the album cover popup is
            selected
        """

        if self.is_current:
            self.mother = self.exaile.window
            track = self.exaile.player.current
            loc = self.exaile.player.current
        else:
            iter = self.model.get_iter(self.current_path)
            track = self.model.get_value(iter, 2)
            loc = track.location

        if item == self.cover_fetch:
            self.exaile.status.set_first(_("Fetching from Amazon..."))
            CoverFrame(self.mother, track, exaile_parent=self.exaile)
        elif item == self.cover_search:
            CoverFrame(self.mother, track, True, exaile_parent=self.exaile)
        elif item == "showcover" or item == self.cover_full:
            if self.is_current:
                loc = self.exaile.cover.loc

            if "nocover" in loc: return
            CoverWindow(self.mother, loc, _("%(album)s by %(artist)s") %
            {
                'album': track.album,
                'artist': track.artist
            })
        elif item == self.cover_custom:

            dialog = gtk.FileChooserDialog(_("Choose an image"), self.mother,
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

                path_id = library.get_column_id(self.db, 'paths', 'name',
                    loc)
                artist_id = library.get_column_id(self.db, 'artists', 'name',
                    track.artist)
                album_id  = library.get_album_id(self.db, artist_id,
                    track.album)

                xlmisc.log(newname)

                self.db.execute("UPDATE albums SET image=? WHERE id=?",
                    (newname, album_id))

                if track == self.exaile.player.current:
                    self.exaile.cover_manager.stop_cover_thread()
                    self.exaile.cover.set_image(
                        os.path.join(self.exaile.get_settings_dir(),
                        "covers", newname))
        elif item == self.remove_cover_menu:
            artist_id = library.get_column_id(self.db, 'artists', 'name', track.artist)
            album_id = library.get_album_id(self.db, artist_id, track.album)
            print album_id

            # Sets image to NULL so that it is as if it never existed
            self.db.execute("UPDATE albums SET image=NULL WHERE id=?", (album_id,))
            # Always do this incase you remove the current tracks cover
            self.exaile.cover.set_image(os.path.join("images", "nocover.png"))

    def set_parent(self, parent):
        """
            This is used to set the parent.
        """
        # Cause you cant replace self.parent
        self.mother = parent
