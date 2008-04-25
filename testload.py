import sys, traceback, os
import xl.media as media
import xl.xlmisc as xlmisc
import cPickle as pickle

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
            xlmisc.log("Error decoding filename %s" % file)
            continue
        except:
            xlmisc.log_exception()
            continue

        try:
            if os.path.isdir(file):
                if regex and regex.match(file): continue
                scan_dir(file, files=files, skip=skip, exts=exts, scanned=scanned)
        except:
            xlmisc.log("Error scanning %s" % file)
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


if __name__ == '__main__':
    dir_to_scan = sys.argv[1]
    save_file = sys.argv[2]

    songs = []
    paths = count_files([dir_to_scan])
    for path in paths:
        song = media.read_from_path(path)
        songs.append(song)

    print "Total songs:", len(songs)
    f = open(save_file, 'wb')
    pickle.dump(songs, f, pickle.HIGHEST_PROTOCOL)
    print "File saved..."
    f.close()
