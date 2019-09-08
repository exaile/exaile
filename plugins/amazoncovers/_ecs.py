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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import urllib.parse
import urllib.request
import hmac
import hashlib
import base64
import datetime
import re
from xl import common
import logging

logger = logging.getLogger(__name__)


class AmazonSearchError(Exception):
    pass


def generate_timestamp():
    ret = datetime.datetime.utcnow()
    return ret.isoformat() + 'Z'


# make a valid RESTful AWS query, that is signed, from a dictionary
# https://docs.aws.amazon.com/AWSECommerceService/latest/DG/RequestAuthenticationArticle.html
# code by Robert Wallis: SmilingRob@gmail.com, your hourly software contractor


def get_aws_query_string(aws_access_key_id, secret, query_dictionary):
    query_dictionary["AWSAccessKeyId"] = aws_access_key_id
    query_dictionary["Timestamp"] = generate_timestamp()
    query_pairs = sorted(
        map(lambda k, v: (k + "=" + urllib.parse.quote(v)), query_dictionary.items())
    )
    # The Amazon specs require a sorted list of arguments
    query_string = "&".join(query_pairs)
    hm = hmac.new(
        secret,
        "GET\nwebservices.amazon.com\n/onca/xml\n" + query_string,
        hashlib.sha256,
    )
    signature = urllib.parse.quote(base64.b64encode(hm.digest()))
    query_string = "https://webservices.amazon.com/onca/xml?%s&Signature=%s" % (
        query_string,
        signature,
    )
    return query_string


def search_covers(search, api_key, secret_key, user_agent):
    params = {
        'Operation': 'ItemSearch',
        'Keywords': str(search),
        'AssociateTag': 'InvalidTag',  # now required for AWS cover search API
        'Version': '2009-01-06',
        'SearchIndex': 'Music',
        'Service': 'AWSECommerceService',
        'ResponseGroup': 'ItemAttributes,Images',
    }

    query_string = get_aws_query_string(
        str(api_key).strip(), str(secret_key).strip(), params
    )

    headers = {'User-Agent': user_agent}
    req = urllib.request.Request(query_string, None, headers)
    data = urllib.request.urlopen(req).read()

    data = common.get_url_contents(query_string, user_agent)

    # check for an error message
    m = re.search(r'<Message>(.*)</Message>', data, re.DOTALL)
    if m:
        logger.warning('Amazon Covers Search Error: %s', m.group(1))
        raise AmazonSearchError(m.group(1))

    # check for large images
    regex = re.compile(r'<LargeImage><URL>([^<]*)', re.DOTALL)
    items = regex.findall(data)

    return items
