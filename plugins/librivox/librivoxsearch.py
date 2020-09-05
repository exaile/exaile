# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Arunas Radzvilavicius, arunas.rv@gmail.com

import urllib.parse
from xml.etree import ElementTree
from xl import common
import logging

logger = logging.getLogger(__name__)


# TODO: The 'new' API allows many fields and generic search. Update UI!
# TODO: New API docs: https://librivox.org/api/info
search_url = 'https://librivox.org/api/feed/audiobooks/?title='


class Book:
    def __init__(self, title, rssurl, user_agent):
        self.title = title
        self.rssurl = rssurl
        self.chapters = []
        self.info = None
        self.is_loading = False
        self.xmldata = None
        self.xmltree = None
        self.loaded = False
        self.user_agent = user_agent

    def get_all(self):
        """
        Unified function for getting chapters and info at the same
        time.
        """
        if self.loaded:
            return

        try:
            self.xmldata = common.get_url_contents(self.rssurl, self.user_agent)
        except Exception:
            logger.error("LIBRIVOX: Connection error")
            return

        try:
            self.xmltree = ElementTree.XML(self.xmldata)
        except Exception:
            logger.error("LIBRIVOX: XML error")
            return

        self.chapters = []
        items = self.xmltree.findall("channel/item")
        for item in items:
            title = item.find("title").text
            link = item.find("link").text
            duration = item.find(
                "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration"
            ).text
            if duration is None:
                duration = 'Unknown length'
            link = link.replace("_64kb.mp3", ".ogg")
            self.chapters.append([title + " " + "(" + duration + ")", link])

        self.info = self.xmltree.find("channel/description")
        self.info = self.info.text
        self.loaded = True
        return


def find_books(keyword, user_agent):
    """
    Returns a list of Book instances, with unknown chapters...
    """

    # urlencode the search string
    url = search_url + urllib.parse.quote_plus(keyword)

    try:
        data = common.get_url_contents(url, user_agent)
    except Exception:
        logger.error("LIBRIVOX: connection error")
        return []

    try:
        tree = ElementTree.XML(data)
    except Exception:
        logger.error("LIBRIVOX: XML error")
        return []

    books = []

    for elem in tree:
        if elem.tag == 'error':
            logger.error('LIBRIVOX: query error: %s', elem.text)

        elif elem.tag == 'books':
            for bk in elem.findall('book'):
                title = bk.find("title").text
                rssurl = bk.find("url_rss").text
                book = Book(title, rssurl, user_agent)
                books.append(book)

    return books
