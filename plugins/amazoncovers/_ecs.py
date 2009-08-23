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

import urllib
import sys
import hmac
import hashlib
import base64
import datetime
import re
from xl.nls import gettext as _
import logging

logger = logging.getLogger(__name__)

class AmazonSearchError(Exception): pass

def generate_timestamp():
    ret = datetime.datetime.utcnow()
    return ret.isoformat() + 'Z'

def generate_signature(key, params):

    param_string = urllib.urlencode(params)
    params = param_string.split('&')

    params.sort()
    param_string = '&'.join(params)

    hm = hmac.new(str(key), 
        "GET\nwebservices.amazon.com\n/onca/xml\n%s" %
        param_string, hashlib.sha256)

    h = urllib.quote(base64.b64encode(hm.digest())) 
    return (param_string, h)

def search_covers(search, api_key, secret_key):
    ts = generate_timestamp()

    params = {
        'Operation': 'ItemSearch',
        'Keywords': search,
        'Version': '2009-01-06',
        'Timestamp': ts,
        'AWSAccessKeyId': api_key,
        'SearchIndex': 'Music',
        'Service': 'AWSECommerceService',
        'ResponseGroup': 'ItemAttributes,Images',
        }

    (param_string, hmac) = generate_signature(secret_key, params)
    data = urllib.urlopen(
        'https://webservices.amazon.com/onca/xml?%s&Signature=%s'
        % (param_string, hmac)).read()

    # check for an error message
    m = re.search(r'<Message>(.*)</Message>', data, re.DOTALL)
    if m:
        logger.warning('Amazon Covers Search Error: %s' % m.group(1))
        raise AmazonSearchError(m.group(1)) 

    # check for large images
    regex = re.compile(r'<LargeImage><URL>([^<]*)', re.DOTALL)
    items = regex.findall(data)

    return items 
