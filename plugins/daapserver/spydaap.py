#!/usr/bin/env python
#Copyright (C) 2008 Erik Hetzner

#This file is part of Spydaap. Spydaap is free software: you can
#redistribute it and/or modify it under the terms of the GNU General
#Public License as published by the Free Software Foundation, either
#version 3 of the License, or (at your option) any later version.

#Spydaap is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

import BaseHTTPServer, SocketServer, getopt, grp, httplib, logging, os, pwd, select, signal, spydaap, sys
import spydaap.daap, spydaap.metadata, spydaap.containers, spydaap.cache, spydaap.server, spydaap.zeroconf
from spydaap.daap import do
import config

logging.basicConfig()
log = logging.getLogger('spydaap')

cache = spydaap.cache.Cache(spydaap.cache_dir)
md_cache = spydaap.metadata.MetadataCache(os.path.join(spydaap.cache_dir, "media"), spydaap.parsers)
container_cache = spydaap.containers.ContainerCache(os.path.join(spydaap.cache_dir, "containers"), spydaap.container_list)
keep_running = True

class Log:
    """file like for writes with auto flush after each write
    to ensure that everything is logged, even during an
    unexpected exit."""
    def __init__(self, f):
        self.f = f
    def write(self, s):
        self.f.write(s)
        self.f.flush()

class MyThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""
    timeout = 1

    def __init__(self, *args):
        BaseHTTPServer.HTTPServer.__init__(self,*args)
        self.keep_running = True

    def serve_forever(self):
        while self.keep_running:
            self.handle_request()

    def force_stop(self):
        self.keep_running = False
        self.server_close()

def rebuild_cache(signum=None, frame=None):
    md_cache.build(os.path.abspath(spydaap.media_path))
    container_cache.clean()
    container_cache.build(md_cache)
    cache.clean()

def usage():
    sys.stderr.write("Usage: %s [OPTION]\n"%(sys.argv[0]))
    sys.stderr.write("  -f, --foreground        run in foreground, rather than daemonizing\n")
    sys.stderr.write("  -g, --group=groupname   specify group to run as\n")
    sys.stderr.write("  -h, --help              print this help\n")
    sys.stderr.write("  -l, --logfile=file      use .log file (default is ./spydaap.log\n")
    sys.stderr.write("  -p, --pidfile=file      use .pid file (default is ./spydaap.pid\n")
    sys.stderr.write("  -u, --user=username     specify username to run as\n")

def make_shutdown(httpd):
    def _shutdown(signum, frame): 
        httpd.force_stop() 
    return _shutdown

def really_main():
    rebuild_cache()
    zeroconf = spydaap.zeroconf.Zeroconf(spydaap.server_name,
                                         spydaap.port,  
                                         stype="_daap._tcp")
    zeroconf.publish()
    log.warn("Listening.")
    httpd = MyThreadedHTTPServer(('0.0.0.0', spydaap.port), 
                                 spydaap.server.makeDAAPHandlerClass(spydaap.server_name, cache, md_cache, container_cache))
    
    signal.signal(signal.SIGTERM, make_shutdown(httpd))
    signal.signal(signal.SIGHUP, rebuild_cache)

    while httpd.keep_running:
        try:
            httpd.serve_forever()
        except select.error:
            pass
        except KeyboardInterrupt:
            httpd.force_stop()
    log.warn("Shutting down.")
    zeroconf.unpublish()

def main():
    daemonize = True
    logfile = os.path.abspath("spydaap.log")
    pidfile = os.path.abspath("spydaap.pid")
    uid = os.getuid()
    gid = os.getgid()
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "fg:hl:p:u:", ["foreground", "group=", "help", "logfile=", "pidfile=", "user="])
        for o, a in opts:
            if o in ("-h", "--help"):
                usage()
                sys.exit()
            elif o in ("-g", "--group"):
                gid = grp.getgrnam(a)[2]
            elif o in ("-f", "--foreground"):
                daemonize = False
            elif o in ("-l", "--logfile"):
                logfile = a
            elif o in ("-p", "--pidfile"):
                pidfile = a
            elif o in ("-u", "--user"):
                uid = pwd.getpwnam(a)[2]
            else:
                assert False, "unhandled option"
    except getopt.GetoptError, err:
        # print help information and exit:
        sys.stderr.write(str(err))
        usage()
        sys.exit(2)

    if uid == 0 or gid == 0:
        sys.stderr.write("spydaap must not run as root\n")
        sys.exit(2)
    #ensure the that the daemon runs a normal user
    os.setegid(gid)
    os.seteuid(uid)

    if not(daemonize):
        really_main()
    else:
        #redirect outputs to a logfile
        sys.stdout = sys.stderr = Log(open(logfile, 'a+'))
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")   #don't prevent unmounting....
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent, print eventual PID before
                #print "Daemon PID %d" % pid
                open(pidfile,'w').write("%d"%pid)
                sys.exit(0)
        except OSError, e:
            print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
            sys.exit(1)
        really_main()

if __name__ == "__main__":
    main()
