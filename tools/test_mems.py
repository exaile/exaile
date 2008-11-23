
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
