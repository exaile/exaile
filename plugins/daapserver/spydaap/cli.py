#!/usr/bin/env python
# Copyright (C) 2008 Erik Hetzner

# This file is part of Spydaap. Spydaap is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.

# Spydaap is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

import optparse

import BaseHTTPServer
import SocketServer
import grp
import os
import pwd
import select
import signal
import spydaap
import sys
import socket
# import httplib, logging
import spydaap.daap
import spydaap.metadata
import spydaap.containers
import spydaap.cache
import spydaap.server
import spydaap.zeroconf

config_file = os.path.join(spydaap.spydaap_dir, "config.py")
if os.path.isfile(config_file):
    execfile(config_file)

cache = spydaap.cache.Cache(spydaap.cache_dir)
md_cache = spydaap.metadata.MetadataCache(os.path.join(spydaap.cache_dir, "media"), spydaap.parsers)
container_cache = spydaap.containers.ContainerCache(os.path.join(spydaap.cache_dir, "containers"), spydaap.container_list)
keep_running = True


class Log(object):
    """file like for writes with auto flush after each write
    to ensure that everything is logged, even during an
    unexpected exit."""

    def __init__(self, f, quiet):
        self.f = f
        self.quiet = quiet
        self.stdout = sys.__stdout__

    def write(self, s):
        self.f.write(s)
        self.f.flush()
        if not self.quiet:
            self.stdout.write(s)
            self.stdout.flush()


class MyThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""
    timeout = 1

    def __init__(self, *args):
        BaseHTTPServer.HTTPServer.__init__(self, *args)
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


def make_shutdown(httpd):
    def _shutdown(signum, frame):
        httpd.force_stop()
    return _shutdown

# invalid default pid ; prevents killing something unintended


def really_main(opts, parent_pid=99999999999999):
    rebuild_cache()
    zeroconf = spydaap.zeroconf.Zeroconf(spydaap.server_name,
                                         spydaap.port,
                                         stype="_daap._tcp")
    zeroconf.publish()
    try:
        httpd = MyThreadedHTTPServer(('0.0.0.0', spydaap.port),
                                     spydaap.server.makeDAAPHandlerClass(spydaap.server_name, cache, md_cache, container_cache))
        # write pid to pidfile
        open(opts.pidfile, 'w').write("%d" % parent_pid)
    except socket.error:
        if not opts.daemonize:
            print "Another DAAP server is already running. Exiting."

        sys.exit(0)  # silently exit; another instance is already running

    signal.signal(signal.SIGTERM, make_shutdown(httpd))
    signal.signal(signal.SIGHUP, rebuild_cache)

    while httpd.keep_running:
        try:
            httpd.serve_forever()
        except select.error:
            pass
        except KeyboardInterrupt:
            httpd.force_stop()
    zeroconf.unpublish()


def main():
    def getpwname(o, s, value, parser):
        parser.values.user = pwd.getpwnam(value)[2]

    def getgrname(o, s, value, parser):
        parser.values.group = grp.getgrnam(value)[2]

    parser = optparse.OptionParser()

    parser.add_option("-d", "--daemon", action="store_true",
                      dest="daemonize", default=False,
                      help="run in the background as a daemon process")

    parser.add_option("-k", "--kill", action="store_true",
                      dest="kill_daemon", default=False,
                      help="kill a running daemon process")

    parser.add_option("-n", "--servername", dest="servername",
                      default=None,
                      help="set the server-name (must be < 64 chars); default is 'spydaap'")

    parser.add_option("-f", "--folder", dest="folderpath",
                      default=None,
                      help="set the path to the media folder (default is ~/Music)")

    parser.add_option("-q", "--quiet", action="store_true",
                      dest="quiet", default=False,
                      help="suppress logging to stdout")

    parser.add_option("-g", "--group", dest="group", action="callback",
                      help="specify group to run as", type="str",
                      callback=getgrname, default=os.getgid())

    parser.add_option("-u", "--user", dest="user", action="callback",
                      help="specify username to run as", type="string",
                      callback=getpwname, default=os.getuid())

    parser.add_option("-l", "--logfile", dest="logfile",
                      default=os.path.join(spydaap.spydaap_dir, "spydaap.log"),
                      help="use log file (default is ~/.spydaap/spydaap.log)")

    parser.add_option("-p", "--pidfile", dest="pidfile",
                      default=os.path.join(spydaap.spydaap_dir, "spydaap.pid"),
                      help="use pid file (default is ~/.spydaap/spydaap.pid)")

    opts, args = parser.parse_args()

    if opts.user == 0 or opts.group == 0:
        sys.stderr.write("spydaap must not run as root\n")
        sys.exit(2)
    # ensure the that the daemon runs a normal user
    os.setegid(opts.group)
    os.seteuid(opts.user)

    if opts.kill_daemon:
        try:
            pid = int(open(opts.pidfile, 'r').read())
            os.kill(pid, signal.SIGTERM)
            print "Daemon killed."
        except (OSError, IOError):
            print "Unable to kill daemon -- not running, or missing pid file?"

        sys.exit(0)

    if opts.servername is not None:
        spydaap.server_name = opts.servername

    if len(spydaap.server_name) > 63:
        # truncate to max valid length (63 characters)
        spydaap.server_name = spydaap.server_name[:63]

    if opts.folderpath is not None:
        spydaap.media_path = os.path.expanduser(opts.folderpath)

    if not(opts.daemonize):
        if not opts.quiet:
            print "spydaap server started (use --help for more options).  Press Ctrl-C to exit."
        # redirect outputs to a logfile
        sys.stdout = sys.stderr = Log(open(opts.logfile, 'a+'), opts.quiet)
        really_main(opts)
    else:
        if not opts.quiet:
            print "spydaap daemon started in background."
        # redirect outputs to a logfile
        sys.stdout = sys.stderr = Log(open(opts.logfile, 'a+'), True)
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")  # don't prevent unmounting....
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            # if in second parent, exit from it
            if pid > 0:
                # store pid temporarily (don't overwrite real pidfile until we
                # know server has successfully started)
                open(opts.pidfile + '.tmp', 'w').write("%d" % pid)
                parent_pid = pid
                sys.exit(0)
        except OSError as e:
            print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
            sys.exit(1)
        # load parent pid
        parent_pid = int(open(opts.pidfile + '.tmp', 'r').read())

        really_main(opts, parent_pid)

if __name__ == "__main__":
    main()
