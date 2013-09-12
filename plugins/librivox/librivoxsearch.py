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

import urllib
from xml.etree import ElementTree
from xl import common
import logging
logger = logging.getLogger(__name__)

class AppURLopener(urllib.FancyURLopener):
    version = "App/1.7"
urllib._urlopener = AppURLopener()

search_url = 'http://librivox.org/newcatalog/search_xml.php?simple='

class Book():
    def __init__(self, title, rssurl):
        self.title=title
        self.rssurl=rssurl
        self.chapters=[]
        self.info=None
        self.is_loading=False
        self.xmldata=None
        self.xmltree=None
        self.loaded=False


    def get_all(self):
        '''
            Unified function for getting chapters and info at the same
            time.
        '''
        if self.loaded:
            return

        try:
            self.xmldata=urllib.urlopen(self.rssurl).read()
            self.xmltree=ElementTree.XML(self.xmldata)
        except:
            logger.error("LIBRIVOX: XML or connection error")
            return
        self.chapters=[]
        items=self.xmltree.findall("channel/item")
        for item in items:
            title=item.find("title").text
            link=item.find("link").text
            duration=item.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration").text
            link=link.replace("_64kb.mp3", ".ogg")
            self.chapters.append([title+" "+"("+duration+")", link])

        self.info=self.xmltree.find("channel/description")
        self.info=self.info.text
        self.loaded=True
        return






def find_books(keyword):
    '''
        Returns a list of Book instances, with unknown chapters...
    '''
    old_keyword=keyword #transform 'keyw1 keyw2 keyw3' into 'key1+key2+key3'
    keyword=''
    for letter in old_keyword:
        if letter!=' ':
            keyword=keyword+letter
        else:
            keyword=keyword+'+'

    url=search_url+keyword
    try:
        data = urllib.urlopen(url).read()
        tree=ElementTree.XML(data)
    except:
        logger.error("LIBRIVOX: XML or connection error")
        return []
    booksXML=tree.findall("book")
    books=[]
    for BK in booksXML:
        title=BK.find("title").text
        rssurl=BK.find("rssurl").text
        book=Book(title, rssurl)
        books.append(book)
    return books

