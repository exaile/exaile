
# script to turn a plugin dir into a .exz file suitable for distribution

# takes one commandline parameter: the name of the ptlugin to build, which must
# be a subdirectory of the current directory

# outputs the built plugin to the current directory, overwriting any current
# build of that plugin

from optparse import OptionParser
p = OptionParser()
p.add_option("-c", "--compression", dest="compression", 
        action="store", choices=("", "gz", "bz2"), default="bz2")
p.add_option("-e", "--ignore-extension", dest="extensions",
        action="append", default=(".pyc", ".pyo"))
p.add_option("-f", "--ignore-file", dest="files",
        action="append", default=("test.py"))
options, args = p.parse_args()

# allowed values: "", "gz", "bz2"
COMPRESSION = options.compression

# don't add files with these extensions to the archive
IGNORED_EXTENSIONS = options.extensions #[".pyc", ".pyo" ]

# don't add files with this exact name to the archive
IGNORED_FILES = options.files # ["test.py"]


import sys, os, tarfile

for dir in args:

    if not os.path.exists(dir):
        print "No such folder %s" % dir
        break

    print "Making plugin %s..."%dir

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

print "Done."
