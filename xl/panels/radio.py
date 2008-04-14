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

import md5, os, re, threading, time, urllib
from lib import feedparser
from gettext import gettext as _
import gobject, gtk
from xl import common, xlmisc, library, media
from xl.gui import playlist as trackslist
import xl.path

class CustomWrapper(object):
    """
        Wraps a custom radio station
    """
    def __init__(self, name):
        """
            initializes the wrapper
        """
        self.name = name

    def __str__(self):
        """
            Returns the name
        """
        return self.name

class PodcastWrapper(object):
    """
        Wraps a podcast
    """
    def __init__(self, name, path):
        """
            Initializes the wrapper
        """
        self.name = name
        self.path = path

    def __str__(self):
        """
            Returns the name
        """
        return self.name

class PodcastQueueThread(threading.Thread):
    """
        Downloads podcasts in the queue one by one
    """
    def __init__(self, transfer_queue, panel):
        """ 
            Initializes the transfer
        """
        threading.Thread.__init__(self)
        self.transfer_queue = transfer_queue
        self.panel = panel
        self.queue = transfer_queue.queue
        self.setDaemon(True)
        self.stopped = False

    def run(self):
        """
            Actually runs the thread
        """
        for song in self.queue: 
            (download_path, downloaded) = \
                self.panel.get_podcast_download_path(song.loc)
            if self.stopped: break
            hin = urllib.urlopen(song.loc)

            temp_path = "%s.part" % download_path
            hout = open(temp_path, "w+")

            count = 0
            while True:
                data = hin.read(1024)
                self.transfer_queue.downloaded_bytes += len(data)
                if count >= 10:
                    gobject.idle_add(self.transfer_queue.update_progress)
                    count = 0
                if not data: break
                hout.write(data)
                if self.stopped:
                    hout.close()
                    os.unlink(temp_path)
                    break

                count += 1

            hin.close()
            hout.close()

            if os.path.isfile(temp_path):
                os.rename(temp_path, download_path)
            if self.stopped: break

            self.transfer_queue.downloaded += 1
            gobject.idle_add(self.transfer_queue.update_progress)
            song.download_path = download_path
            temp = library.read_track(None, None, download_path)

            if temp:
                song.set_len(temp.duration)
                self.db = self.panel.exaile.db
                path_id = library.get_column_id(self.db, 'paths', 'name',
                    song.loc)
                podcast_path_id = library.get_column_id(self.db, 'paths', 
                    'name', song.podcast_path)

                self.panel.exaile.db.execute(
                    "UPDATE podcast_items SET length=? WHERE podcast_path=?"
                    " AND path=?", 
                    (temp.duration, podcast_path_id, path_id))
                self.panel.exaile.db.commit()

            gobject.idle_add(self.transfer_queue.update_song, song)
            xlmisc.log("Downloaded podcast %s" % song.loc)

        gobject.idle_add(self.transfer_queue.die)

class PodcastTransferQueue(gtk.VBox):
    """
        Represents the podcasts that should be downloaded
    """
    def __init__(self, panel):
        """
            Starts the transfer queue
        """
        gtk.VBox.__init__(self)
        self.panel = panel

        self.label = gtk.Label(_("Downloading Podcasts"))
        self.label.set_alignment(0, 0)

        self.pack_start(self.label)
        self.progress = gtk.ProgressBar()
        self.progress.set_text(_("Downloading..."))
        self.progress.set_size_request(-1, 24)
        
        vert = gtk.HBox()
        vert.set_spacing(3)
        vert.pack_start(self.progress, True, True)
        
        button = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-stop', 
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        button.set_image(image)
        button.set_size_request(32, 32)

        vert.pack_end(button, False, False)
        button.connect('clicked', self.stop)

        self.pack_start(vert)

        self.downloaded = 0
        self.downloaded_bytes = 0
        self.total = 0
        self.total_bytes = 0
        self.queue = library.TrackData()
        self.queue_thread = None
        panel.podcast_download_box.pack_start(self)
        self.show_all()

    def stop(self, widget):
        """
            Stops the download queue
        """
        if self.queue_thread:
            self.queue_thread.stopped = True

        self.label.set_label(_("Stopping..."))

    def update_song(self, song):
        """ 
            Updates song information in the display
        """
        nb = self.panel.exaile.playlists_nb
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            if isinstance(page, trackslist.TracksListCtrl):
                for item in page.songs:
                    if item == song:
                        page.refresh_row(song)

    def update_progress(self):
        """ 
            Update the progress bar with the percent of downloaded items
        """
        if self.total_bytes:
            total = float(self.total_bytes)
            down = float(self.downloaded_bytes)
            percent = down / total
            self.progress.set_fraction(percent)

        self.label.set_label(_("%(downloaded)d of %(total)d downloaded") % 
            {
                'downloaded': self.downloaded,
                'total': self.total
            })

    def append(self, song):
        """
            Appends an item to the queue
        """
        self.queue.append(song)
        self.total += 1
        self.total_bytes += song.size
        self.update_progress()
        if not self.queue_thread:
            self.queue_thread = PodcastQueueThread(self, self.panel)
            self.queue_thread.start()

    def die(self):
        """
            Removes the download queue
        """
        self.hide()
        self.panel.podcast_download_box.remove(self)
        self.panel.podcast_queue = None

class LastFMWrapper(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class EmptyRadioDriver(object):
    """
        Empty Driver
    """
    def __init__(self):
        pass

class RadioGenre(object):
    def __init__(self, name, driver=None, extra=None):
        self.name = name
        self.extra = extra
        self.driver = driver

    def __str__(self):
        return self.name

class RadioDriver(object):
    pass

class RadioPanel(object):
    """
        This will be a pluggable radio panel.  Plugins like shoutcast and
        live365 will go here
    """
    name = 'pradio'
    def __init__(self, exaile):
        """
            Initializes the panel
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = exaile.xml
        self.tree = self.xml.get_widget('radio_service_tree')
        icon = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn('radio')
        col.pack_start(icon, False)
        col.pack_start(text, True)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)
        self.podcasts = {}
        self.drivers = {}
        self.driver_names = {}
        self.__dragging = False

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.tree.set_model(self.model)

        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.track = gtk.gdk.pixbuf_new_from_file(xl.path.get_data('images',
            'track.png'))
        self.folder = xlmisc.get_icon('gnome-fs-directory')
        self.refresh_image = xlmisc.get_icon('gtk-refresh')

        self.track = gtk.gdk.pixbuf_new_from_file(xl.path.get_data('images',
            'track.png'))
        self.custom = self.model.append(None, [self.open_folder, "Saved Stations"])
        self.podcast = self.model.append(None, [self.open_folder, "Podcasts"])

        # load all saved stations from the database
        rows = self.db.select("SELECT name FROM radio "
            "ORDER BY name")
        for row in rows:
            self.model.append(self.custom, [self.track, CustomWrapper(row[0])])

        # load podcasts
        rows = self.db.select("SELECT title, paths.name FROM podcasts,paths "
            "WHERE paths.id=podcasts.path")
        for row in rows:
            title = row[0]
            path = row[1]
            if not title: title = path
            self.model.append(self.podcast, [self.track, 
                PodcastWrapper(title, path)])

        self.tree.expand_row(self.model.get_path(self.custom), False)
        self.tree.expand_row(self.model.get_path(self.podcast), False)

        self.radio_root = self.model.append(None, [self.open_folder, "Radio "
            "Streams"])

        self.drivers_expanded = {}
        self.load_nodes = {}
        self.tree.connect('row-expanded', self.on_row_expand)
        self.tree.connect('button-press-event', self.button_pressed)
        self.tree.connect('button-release-event', self.button_release)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('button-press-event', self.button_pressed)
        self.tree.connect('button-release-event', self.button_release)
        self.__dragging = False
        self.xml.get_widget('pradio_add_button').connect('clicked',
            self.on_add_station)
        self.xml.get_widget('pradio_remove_button').connect('clicked',
            self.remove_station)
        self.podcast_download_box = \
            self.xml.get_widget('ppodcast_download_box')
        self.podcast_queue = None
        self.setup_menus()

    def button_release(self, widget, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.__dragging: return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.tree.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.tree.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def button_pressed(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        selection.unselect_all()
        (x, y) = event.get_coords()
        x = int(x); y = int(y)
        if not self.tree.get_path_at_pos(x, y): return
        (path, col, x, y) = self.tree.get_path_at_pos(x, y)
        selection.select_path(path)
        model = self.model
        iter = model.get_iter(path)
        
        object = model.get_value(iter, 1)
        if event.button == 3:
            # if it's for podcasts
            if isinstance(object, PodcastWrapper) or \
                object == "Podcasts":
                self.podmenu.popup(None, None, None,
                    event.button, event.time)
                return

            if isinstance(object, CustomWrapper):
                self.cmenu.popup(None, None, None,
                    event.button, event.time)

            elif isinstance(object, RadioDriver) or isinstance(object,
                RadioGenre):
                if isinstance(object, RadioDriver):
                    driver = object
                else:
                    driver = object.driver
                self.setup_menus()
                if driver and hasattr(driver, 'get_menu'):
                    menu = driver.get_menu(object, self.menu)
                else:
                    menu = self.menu
                menu.popup(None, None, None, event.button, event.time)
                return True
            else:
                if object in ("Saved Stations", "Podcasts", "Shoutcast Stations"):
                    return
        elif event.type == gtk.gdk._2BUTTON_PRESS:
            if object == 'Last.fm Radio':
                self.tree.expand_row(path, False)                
            elif isinstance(object, CustomWrapper):
                self.open_station(object.name)
            elif isinstance(object, PodcastWrapper):
                self.open_podcast(object)
            elif isinstance(object, LastFMWrapper):
                self.open_lastfm(object)
            elif isinstance(object, RadioGenre):
                if object.driver:
                    tracks = trackslist.TracksListCtrl(self.exaile)
                    self.exaile.playlists_nb.append_page(tracks,
                        xlmisc.NotebookTab(self.exaile, str(object), tracks))
                    self.exaile.playlists_nb.set_current_page(
                        self.exaile.playlists_nb.get_n_pages() - 1)
                    self.exaile.tracks = tracks
                    object.driver.tracks = tracks
                    object.driver.load_genre(object)
            return True

    def cell_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, CustomWrapper):
            cell.set_property('text', str(object))
        else:
            cell.set_property('text', str(object))

    def add_driver(self, driver, name):
        """
            Adds a driver to the list of drivers
        """
        if not self.drivers.has_key(driver):
            driver.name = name
            self.driver_names[driver] = name
            node = self.model.append(self.radio_root, [self.folder, driver])

            self.load_nodes[driver] = self.model.append(node, 
                [self.refresh_image, _("Loading streams...")])
            self.drivers[driver] = node
            self.tree.expand_row(self.model.get_path(self.radio_root), False)
            if self.exaile.settings.get_boolean('row_expanded', plugin=name,
                default=False):
                self.tree.expand_row(self.model.get_path(node), False)

    def remove_driver(self, driver):
        """
            Removes a radio driver
        """
        if self.drivers.has_key(driver):
            self.model.remove(self.drivers[driver])
            del self.drivers[driver]

    def open_lastfm(self, object):
        """
            Opens and plays a Last.fm station
        """
        station = str(object)
        user = self.exaile.settings.get_str('lastfm/user', '')
        password = self.exaile.settings.get_crypted('lastfm/pass', '')

        if not user or not password:
            common.error(self.exaile.window, _("You need to have a Last.fm "
                "username and password set in your preferences."))
            return

        if station == "Neighbor Radio":
            url = "lastfm://user/%s/neighbours" % user
        else:
            url = "lastfm://user/%s/personal" % user

        tr = media.Track(url)
        tr.type = 'lastfm'
        tr.track = -1
        tr.title = station
        tr.album = _("%(user)s's Last.fm %(station)s") % \
            {
                'user': user,
                'station': station
            }


        self.exaile.playlist_manager.append_songs((tr,))

    def open_podcast(self, wrapper):
        """
            Opens a podcast
        """
        podcast_path_id = library.get_column_id(self.db, 'paths', 'name',
            wrapper.path)

        xlmisc.log("Opening podcast %s" % wrapper.name)
        row = self.db.read_one("podcasts", "description", "path=?", 
            (podcast_path_id, ))
        if not row: return

        desc = row[0]
        limit = self.exaile.settings.get_str('podcast_show_limit', '0')
        limiter = ""
        if int(limit) > 0: limiter = "LIMIT %s" % limit
        rows = self.db.select("SELECT paths.name, title, description, length, "
            "pub_date, size FROM podcast_items, paths WHERE podcast_path=? "
            "AND paths.id=podcast_items.path ORDER BY "
            "pub_date DESC %s" % limiter, 
            (podcast_path_id,))

        songs = library.TrackData()
        for row in rows:
            t = common.strdate_to_time(row[4])
            year = time.strftime("%x", time.localtime(t))
            info = ({
                'title': row[1],
                'artist': row[2],
                'album': desc.replace('\n', ' '),
                'loc': row[0],
                'year': row[4], 
                'length': row[3], 
            })

            song = media.Track()
            song.set_info(**info)
            song.type = 'podcast'
            song.size = row[5]
            song.year = song.year.replace(' 00:00:00', '')

            (download_path, downloaded) = \
                self.get_podcast_download_path(row[0])

            if not downloaded:
                song.download_path = ''
            else:
                song.download_path = download_path

            song.podcast_path = wrapper.path
            songs.append(song)
            self.podcasts[song.loc] = song

        self.exaile.new_page(str(wrapper), songs)

    def get_podcast(self, url):
        """
            Returns the podcast for the specified url
        """
        if self.podcasts.has_key(url):
            return self.podcasts[url]
        else: return None

    def add_podcast_to_queue(self, song):
        """
            Add to podcast transfer queue
        """
        if not self.podcast_queue:
            self.podcast_queue = PodcastTransferQueue(self)

        if not song.loc in self.podcast_queue.queue.paths:
            self.podcast_queue.append(song)

    def get_podcast_download_path(self, loc):
        """
            Gets the location of the downloaded pocast item
        """
        (path, ext) = os.path.splitext(loc)
        hash = md5.new(loc).hexdigest()
        savepath = self.exaile.settings.get_str('feed_download_location',
            os.path.expanduser('~/.exaile/podcasts')) 
        if not os.path.isdir(savepath):
            os.mkdir(savepath, 0777)

        file = os.path.join(savepath, hash + ext)
        if os.path.isfile(file): return file, True
        else: return file, False

    def cell_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, CustomWrapper):
            cell.set_property('text', str(object))
        else:
            cell.set_property('text', str(object))
            
    def on_collapsed(self, tree, iter, path):
        """
            Called when someone collapses a tree item
        """
        driver = self.model.get_value(iter, 1)
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.model.set_value(iter, 0, self.folder)
        self.tree.queue_draw()
        self.exaile.settings.set_boolean('row_expanded', False,
            plugin=self.driver_names[driver])

    def on_row_expand(self, treeview, iter, path):
        """
            Called when the user clicks on a row to expand the stations under
        """
        driver = self.model.get_value(iter, 1)
        self.model.set_value(iter, 0, self.open_folder)
        self.tree.queue_draw()

        if not isinstance(driver, RadioDriver): return
        if self.drivers.has_key(driver) and not \
            self.drivers_expanded.has_key(driver):
            self.drivers_expanded[driver] = 1

            driver.load_streams(self.drivers[driver],
                self.load_nodes[driver]) 
        self.exaile.settings.set_boolean('row_expanded', True,
            plugin=self.driver_names[driver])

    def setup_menus(self):
        """
            Create the two different popup menus associated with this tree.
            There are two menus, one for saved stations, and one for
            shoutcast stations
        """
        self.menu = xlmisc.Menu()
        rel = self.menu.append(_("Refresh"), lambda e, f:
            self.refresh_streams(), 'gtk-refresh')

        # custom playlist menu
        self.cmenu = xlmisc.Menu()
        self.add = self.cmenu.append(_("Add Stream to Station"), 
            self.add_url_to_station)
        self.delete = self.cmenu.append(_("Delete this Station"),
            self.remove_station)

        self.podmenu = xlmisc.Menu()
        self.podmenu.append(_("Add Feed"), self.on_add_podcast)
        self.podmenu.append(_("Refresh Feed"), self.refresh_feed)
        self.podmenu.append(_("Delete Feed"), self.delete_podcast)

    def refresh_streams(self):
        """
            Refreshes the streams for the currently selected driver
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        if isinstance(object, RadioDriver):
            driver = object
            self.drivers_expanded[driver] = 1
            self.clean_node(self.drivers[driver])
            self.load_nodes[driver] = self.model.append(iter, 
                [self.refresh_image, _("Loading streams...")])
            driver.load_streams(self.drivers[driver], 
                self.load_nodes[driver], False)
            self.tree.expand_row(self.model.get_path(iter), False)
        elif isinstance(object, RadioGenre):
            if object.driver:
                tracks = trackslist.TracksListCtrl(self.exaile)
                self.exaile.playlists_nb.append_page(tracks,
                    xlmisc.NotebookTab(self.exaile, str(object), tracks))
                self.exaile.playlists_nb.set_current_page(
                    self.exaile.playlists_nb.get_n_pages() - 1)
                self.exaile.tracks = tracks
                object.driver.tracks = tracks
                object.driver.load_genre(object, rel=True)

    def clean_node(self, node):
        """
            Cleans a node of all it's children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)

    def refresh_feed(self, widget, event):
        """
            Refreshes a feed
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        if isinstance(object, PodcastWrapper):
            self.refresh_podcast(object.path, iter)

    def on_add_podcast(self, widget, event):
        """
            Called when a request to add a podcast is made
        """
        dialog = common.TextEntryDialog(self.exaile.window, _("Enter the location of"
            " the podcast"), _("Add a podcast"))

        if dialog.run() == gtk.RESPONSE_OK:
            name = dialog.get_value()
            dialog.destroy()
            path_id = library.get_column_id(self.db, 'paths', 'name', name)
            if self.db.record_count("podcasts", "path=?", (name, )):
                common.error(self.exaile.window, 
                    _("A podcast with that url already"
                    " exists"))
                return

            self.db.execute("INSERT INTO podcasts( path ) VALUES( ? )",
                (path_id,))
            self.db.commit()

            item = self.model.append(self.podcast,
                [self.track, PodcastWrapper(_("Fetching..."), name)])
            self.tree.expand_row(self.model.get_path(self.podcast), False)

            self.refresh_podcast(name, item)
        dialog.destroy()

    @common.threaded
    def refresh_podcast(self, path, item):
        """
            Refreshes a podcast
        """
        try:
            feed = feedparser.parse(path)
        except IOError:
            gobject.idle_add(common.error, self.exaile.window, 
                _("Could not read feed."))
            return

        gobject.idle_add(self.parse_podcast_xml, path, item, feed)

    def parse_podcast_xml(self, path, iter, feed):
        """
            Parses the xml from the podcast and stores the information to the
            database
        """
        title = feed.feed.title
        description = feed.feed.description
        if not description: description = ""

        try: pub_date = feed.feed.updated
        except AttributeError: pub_date = ""

        # TODO: use the image from the feed as the cover image
        image = ""
        path_id = library.get_column_id(self.db, 'paths', 'name', path)

        self.db.execute("UPDATE podcasts SET title=?, "
            "pub_date=?, description=?, image=? WHERE"
            " path=?", (title, pub_date, description, image, path_id))

        self.model.set_value(iter, 1, PodcastWrapper(title, path))
        root_title = title

        found_items = []
        
        for item in feed['entries']:
            title = item.title 
            link = item.link
            print title, link
            desc = item.description

            desc = self.clean_desc(desc)
            enc = None
            try:
                enc = item.enclosures
            except AttributeError:
                pass

            date = item.updated
            if enc:
                try: size = enc[0].length
                except AttributeError: size = 0
                try: length = enc[0].duration
                except AttributeError: length = 0
                try: loc = str(enc[0].href)
                except AttributeError: loc = ''
            else: continue
            loc_id = library.get_column_id(self.db, 'paths', 'name', loc)
            found_items.append(loc_id)

            row = self.db.read_one("podcast_items", "path", 
                "podcast_path=? AND path=?", (path_id, loc_id))

            # if the feed already exists, don't add it again
            if row: continue

            t = common.strdate_to_time(date)
            date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

            self.db.update("podcast_items",
                {
                    "podcast_path": path_id,
                    "path": loc_id,
                    "pub_date": date,
                    "description": desc,
                    "size": size,
                    "title": title,
                    "length": length,
                }, "path=? AND podcast_path=?", 
                (loc_id, path_id), row == None)

        # delete all items that aren't still in the feed
        where = ["path!=\"%d\" " % (x) for x in found_items]
        where = " AND ".join(where)
        cur = self.db.cursor()
        cur.execute("DELETE FROM podcast_items WHERE (%s) AND podcast_path=?"
            % (where,), (path_id,))

        self.db.commit()

        gobject.timeout_add(500, self.open_podcast, PodcastWrapper(root_title, path))

    def clean_desc(self, desc):
        """ 
            Cleans description of html, and shortens it to 70 chars
        """
        reg = re.compile("<[^>]*?>", re.IGNORECASE|re.DOTALL)
        desc = reg.sub('', desc)
        desc = re.sub(r"\s+", " ", desc)

        if len(desc) > 70:
            desc = desc[:67] + '...'

        return desc

    def delete_podcast(self, widget, event):
        """ 
            Removes a podcast
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        path_id = library.get_column_id(self.db, 'paths', 'name', object.path)

        if not isinstance(object, PodcastWrapper): return
        dialog = gtk.MessageDialog(self.exaile.window,
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            _("Are you sure you want to delete this podcast?"))
        if dialog.run() == gtk.RESPONSE_YES:
            self.db.execute("DELETE FROM podcasts WHERE path=?", (path_id,))
            self.db.execute("DELETE FROM podcast_items WHERE podcast_path=?", 
                (path_id,))

            self.model.remove(iter)
            self.tree.queue_draw()
            
        dialog.destroy()

    def add_url_to_station(self, item, event):
        """
            Adds a url to an existing station
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        station = model.get_value(iter, 1)
        radio = library.get_column_id(self.db, 'radio', 'name', str(station))
        
        dialog = common.MultiTextEntryDialog(self.exaile.window,
            _("Add Stream to Station"))
        # TRANSLATORS: Address of a radio station
        dialog.add_field(_("URL:"))
        # TRANSLATORS: Description of a radio station
        dialog.add_field(_("Description:"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            (stream, desc) = dialog.get_values()
            path_id = library.get_column_id(self.db, 'paths', 'name', stream)

            self.db.execute("INSERT INTO radio_items(radio, path, title, "
                "description) VALUES( ?, ?, ?, ?)", 
                (radio, path_id, desc, desc))
            
    def remove_station(self, item, event=None):
        """
            Removes a saved station
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        name = model.get_value(iter, 1)
        if not isinstance(name, CustomWrapper): return
        name = str(name)

        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected "
            "station?"))
        result = dialog.run()
        dialog.destroy()
        radio_id = library.get_column_id(self.db, 'radio', 'name', name)

        if result == gtk.RESPONSE_YES:
            
            self.db.execute("DELETE FROM radio WHERE id=?", (radio_id,))
            self.db.execute("DELETE FROM radio_items WHERE radio=?", (radio_id,))
            if library.RADIO.has_key(name):
                del library.RADIO[name]

            self.model.remove(iter)
            self.tree.queue_draw()

    def open_station(self, playlist):
        """
            Opens a station
        """
        all = self.db.select("SELECT title, description, paths.name, bitrate FROM "
            "radio_items,radio,paths WHERE radio_items.radio=radio.id AND "
            "paths.id=radio_items.path AND radio.name=?", (playlist,))

        songs = library.TrackData()
        t = trackslist.TracksListCtrl(self.exaile)
        self.exaile.playlists_nb.append_page(t,
            xlmisc.NotebookTab(self.exaile, playlist, t))
        self.exaile.playlists_nb.set_tab_reorderable(t, True)     
        self.exaile.playlists_nb.set_current_page(
            self.exaile.playlists_nb.get_n_pages() - 1)

        self.exaile.tracks = t

        for row in all:
            info = dict()
            info['artist'] = row[2]
            info['album'] = row[1]
            info['loc'] = row[2]
            info['title'] = row[0]
            info['bitrate'] = row[3]

            track = media.Track()
            track.set_info(**info)
            track.type = 'stream'
            songs.append(track)
        t.playlist = playlist
        t.set_songs(songs)
        t.queue_draw()

    def on_add_station(self, widget):
        """
            Adds a station
        """
        dialog = common.MultiTextEntryDialog(self.exaile.window, 
            _("Add Station"))
        dialog.add_field(_("Station Name:"))
        dialog.add_field(_("Description:"))
        dialog.add_field(_("URL:"))
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            (name, desc, url) = dialog.get_values()
            if not name or not url:
                common.error(self.exaile.window, _("The 'Name' and 'URL'"
                    " fields are required"))
                self.on_add_station(widget)
                return

            c = self.db.record_count("radio", "name=?", (name,))

            if c > 0:
                common.error(self.exaile.window, _("Station name already exists."))
                return
            radio_id = library.get_column_id(self.db, 'radio', 'name', name)
            path_id = library.get_column_id(self.db, 'paths', 'name', url)
            self.db.execute("INSERT INTO radio_items(radio, path, title, "
                "description) VALUES( ?, ?, ?, ? )", (radio_id, path_id, desc,
                desc))
            
            item = self.model.append(self.custom, [self.track, 
                CustomWrapper(name)])
            path = self.model.get_path(self.custom)
            self.tree.expand_row(path, False)

    def on_add_to_station(self, widget, event):
        """
            Adds a playlist to the database
        """
        dialog = common.TextEntryDialog(self.exaile.window,
            _("Enter the name of the station"),
            _("Enter the name of the station"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if name == "": return
            c = self.db.record_count("radio", "name=?",
                (name,))

            if c > 0:
                common.error(self, _("Station already exists."))
                return

            station_id = library.get_column_id(self.db, 'radio', 
                'name', name)
            
            self.model.append(self.custom, [self.track, CustomWrapper(name)])
            self.tree.expand_row(self.model.get_path(self.custom), False)

            self.add_items_to_station(station=name)

    def add_items_to_station(self, item=None, event=None, 
        ts=None, station=None):
        """
            Adds the selected tracks tot he playlist
        """

        if ts == None: ts = self.exaile.tracks
        songs = ts.get_selected_tracks()

        if station:
            playlist = station
        else:
            playlist = unicode(item.get_child().get_text(), 'utf-8')

        station_id = library.get_column_id(self.db, 'radio', 'name', playlist)

        for track in songs:
            if track.type != 'stream': continue
            path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
            try:
                album = track.album
                if not album: album = track.artist
                self.db.execute("INSERT INTO radio_items( radio, title, path, "
                    "description, bitrate ) " \
                    "VALUES( ?, ?, ?, ?, ? )",
                    (station_id, track.title, path_id,
                    album, track.bitrate))
            except sqlite.IntegrityError:
                pass
        self.db.commit()

