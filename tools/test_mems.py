# Copyright (C) 2008-2009 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import subprocess, time, os

settings = """[playlist]
open_last = B: False
save_queue = B: False

[collection]
libraries = L: [%s]

[player]
gapless = B: False

[playback]
repeat = B: False
shuffle = B: False
dynamic = B: False

[plugins]
enabled = L: []"""

library_str = "('%s', False, 0)"

library_path = "/home/reacocard/music/OMGMUSIC/%s"

settings_file = "/home/reacocard/.config/exaile/settings.ini"

rescan_command = "exaile.collection.rescan_libraries()\n"
save_command = "exaile.collection.save_to_location()\n"
quit_command = "exaile.quit()\n"

dumpfile = open("memdump", "w")

exailecmd = "./cli"

os.rename(settings_file, settings_file + ".bak")

for n in range(21):
    print "Pass: ", n

    #generate new settings file
    libs = []
    for n2 in range(1,n+1):
        libs.append(library_str%(library_path%n2))
    libstr = ", ".join(libs)
    f = open(settings_file, "w")
    f.write(settings%libstr)
    f.close()


    exaileproc = subprocess.Popen(["python", "-i", "exaile.py", "--no-hal"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    exaileproc.communicate(rescan_command+save_command+quit_command)

    print "Scan complete"

    exaileproc = subprocess.Popen(["python", "-i", "exaile.py", "--no-hal"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    pid = exaileproc.pid
    time.sleep(10)
    data = subprocess.Popen(["ps", "-p",  "%s"%pid, "-F"], stdout=subprocess.PIPE, stdin=subprocess.PIPE).stdout.read()
    mem = data.split("\n")[1].split()[5]

    exaileproc.communicate(quit_command)

    print "Mem: ", mem

    dumpfile.write("Pass %s: %s"%(n, mem))

dumpfile.close()


os.rename(settings_file + ".bak", settings_file)
