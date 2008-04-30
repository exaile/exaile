import pygtk
pygtk.require('2.0')
import sys, traceback, os
import xl.media as media
import xl.common as common
import cPickle as pickle
import gtk

def scan_dir(dir, files=None, skip=(), exts=(), scanned=None):
    """
        Scans a directory recursively
    """
    regex = None
    if skip:
        match_string = r"^.*(" + r"|".join(skip) + r").*$"
        regex = re.compile(match_string)
    if files is None: 
        files = []
    if scanned is None:
        scanned = set()

    try:
        dir = os.path.realpath(dir)
        to_scan = os.listdir(dir)
    except OSError:
        return files

    if dir in scanned: return files
    scanned.add(dir)

    for file in to_scan:
        try:
            file = os.path.join(dir, file)
        except UnicodeDecodeError:
            common.log("Error decoding filename %s" % file)
            continue
        except:
            common.log_exception()
            continue

        try:
            if os.path.isdir(file):
                if regex and regex.match(file): continue
                scan_dir(file, files=files, skip=skip, exts=exts, scanned=scanned)
        except:
            common.log("Error scanning %s" % file)
            traceback.print_exc()
       
        try:
            (stuff, ext) = os.path.splitext(file)
            if ext.lower() in exts and not file in files:
                files.append(file)
        except:
            traceback.print_exc()
            continue

    return files     

def count_files(directories, skip=()):
    """
        Recursively counts the number of supported files in the specified
        directories
    """
    paths = []
    for dir in directories:
        paths.extend(scan_dir(dir, skip=skip, exts=media.SUPPORTED_MEDIA))

    return paths

def get_sort_list(self):
    return (str(self.track), self.title, self.artist, self.album, self.length,
        self)

def set_songs(model, songs, tag, reverse):
    songs = [(song.get_sortable(tag), song.album, song.track, song.artist,
        song) for song in songs]

    songs.sort()
    if reverse: songs.reverse()
    model.clear()
    for info in songs:
        model.append(info[-1:][0].get_sort_list())

def set_sort_by(header, info, tag=None, order=None, refresh=True):
    tree, columns, songs = info

    if header != None and tag == None: tag = header.get_title()
    reverse = False
    for h in columns:
        column = h
        if h.get_title() == tag:
            order = column.get_sort_order()
            if order == gtk.SORT_DESCENDING:
                order = gtk.SORT_ASCENDING
            else:
                reverse = True
                order = gtk.SORT_DESCENDING

            column.set_sort_indicator(True)
            column.set_sort_order(order)
        else:
            h.set_sort_indicator(False)

    print reverse
    set_songs(model, songs, tag, reverse) 

def get_sortable(self, tag):
    return getattr(self, tag.lower())

#    if refresh:
#        self.get_model().set_songs()


if __name__ == '__main__':
    dir_to_scan = sys.argv[1]
    save_file = sys.argv[2]

    if not os.path.isfile(save_file):
        songs = []
        paths = count_files([dir_to_scan])
        for path in paths:
            song = media.read_from_path(path)
            if song.track and song.title and song.artist and song.album:
                songs.append(song)

        print "Total songs:", len(songs)
        f = open(save_file, 'wb')
        pickle.dump(songs, f, pickle.HIGHEST_PROTOCOL)
        print "File saved..."
        f.close()
    else:
        f = open(save_file, 'rb')
        songs = pickle.load(f)
        f.close()

    window = gtk.Window()

    box = gtk.HBox()
    window.add(box)
    tree = gtk.TreeView()
    tree.set_headers_clickable(True)

    items = ('#', 'Title', 'Artist', 'Album', 'Length')
    columns = []
    for i, item in enumerate(items):
        cellr = gtk.CellRendererText()
        col = gtk.TreeViewColumn(item, cellr, text=i)
        col.set_clickable(True)
        col.set_reorderable(True)
        col.connect('clicked', set_sort_by, (tree, columns, songs))
        col.set_sort_indicator(False)
        columns.append(col)
        tree.append_column(col)

    model = gtk.ListStore(str, str, str, str, str, object)
    media.Track.get_sort_list = get_sort_list
    media.Track.get_sortable = get_sortable

    s = songs[:]
    songs.extend(s)
    s = songs[:]
    songs.extend(s)

    print "friggin %d songs" % len(songs)
    for song in songs:
        model.append(song.get_sort_list())

    tree.set_model(model)

    scroll = gtk.ScrolledWindow()
    scroll.add(tree)
    box.pack_start(scroll, True, True)

    window.resize(800,400)
    window.show_all()

    gtk.main()
