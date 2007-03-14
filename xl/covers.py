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


import httplib, re, urllib, md5, threading, sys, os, xlmisc
import urllib2
import config
import gobject

__revision__ = ".01"

#LOCALES = ['ca', 'de', 'fr', 'jp', 'uk', 'us']

def get_server(locale):
    if locale in ('en', 'us'):
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
    r"http://(images(?:-\w\w)?\.amazon\.com)(/images/.*?LZ+\.jpg)")

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
        handle = open(savepath, "w")
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

# test case functions
def done(covers): 
    for cover in covers:
        if(cover['status'] == 200): cover.save()

if __name__ == "__main__":
    if(len(sys.argv) != 2):
        print "Usage: %s <search string>" % sys.argv[0]
        sys.exit(1)

    CoverFetcherThread(sys.argv[1], done).start()

