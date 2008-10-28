
# script to turn a plugin dir into a .exz file suitable for distribution

# takes one commandline parameter: the name of the plugin to build, which must
# be a subdirectory of the current directory

# outputs the built plugin to the current directory, overwriting any current
# build of that plugin


# allowed values: "", "gz", "bz2"
COMPRESSION = "bz2"

# don't add files with these extensions to the archive
IGNORED_EXTENSIONS = [".pyc", ".pyo" ]

# don't add files with this exact name to the archive
IGNORED_FILES = ["test.py"]

import sys, os, tarfile

dir = sys.argv[1]

if not os.path.exists(dir):
    print "No such folder %s" % dir
    sys.exit(1)

tfile = tarfile.open(dir + ".exz", "w:%s"%COMPRESSION)
tfile.posix = True # we like being standards-compilant

for fold, subdirs, files in os.walk(dir):
    for file in files:
        stop = False
        for ext in IGNORED_EXTENSIONS:
            if file.endswith(ext):
                stop = True
                break
        if stop: break
        for name in IGNORED_FILES:
            if file == name:
                stop = True
                break
        if stop: continue

        path = os.path.join(fold, file)
        tfile.add(path)

tfile.close()
