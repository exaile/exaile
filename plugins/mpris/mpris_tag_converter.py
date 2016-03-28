# Copyright (C) 2009-2010 Abhishek Mukherjee
#
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
"""
A converter utility to convert from exaile tags to mpris Metadata
"""

import logging
_LOG = logging.getLogger('exaile.plugins.mpris.mpris_tag_converter')

# Dictionary to map MPRIS tags to Exaile Tags
# Each key is the mpris tag, each value is a dictionary with possible keys:
#   * out_type: REQUIRED, function that will convert to the MPRIS type
#   * exaile_tag: the name of the tag in exaile, defaults to the mpris tag
#   * conv: a conversion function to call on the exaile metadata, defaults to
#           lambda x: x
#   * desc: a description of what's in the tag
#   * constructor: a function to call that takes (exaile, track) and returns
#                  the value for the key. If it returns None, the tag is not
#                  set
MPRIS_TAG_INFORMATION = {
        'location'   : {'out_type'  : str,
                        'exaile_tag': '__loc',
                        'desc'      : 'Name',
                        },
        'artist'      : {'out_type'  : str,
                        'desc'      : 'Name of artist or band',
                        },
        'title'      : {'out_type'  : str,
                        'desc'      : 'Name of artist or band',
                        },
        'album'      : {'out_type'  : str,
                        'desc'      : 'Name of compilation',
                        },
        'tracknumber': {'out_type'  : str,
                        'desc'      : 'The position in album',
                        },
        'time'       : {'out_type'  : int,
                        'exaile_tag': '__length',
                        'desc'      : 'The duration in seconds',
                        },
        'mtime'      : {'out_type'  : int,
                        'desc'      : 'The duration in milliseconds',
                        },
        'genre'      : {'out_type'  : str,
                        'desc'      : 'The genre',
                        },
        'comment'    : {'out_type'  : str,
                        'desc'      : 'A comment about the work',
                        },
        'rating'     : {'out_type'  : int,
                        'desc'      : 'A "taste" rate value, out of 5',
                        },
        'year'       : {'out_type'  : int,
                        'exaile_tag': 'date',
                        'conv'      : lambda x: x.split('-')[0],
                        'desc'      : 'The year of performing',
                        },
        'date'       : {'out_type'  : int,
                        'exaile_tag': None,
                        'desc'      : 'When the performing was realized, '
                                      'since epoch',
                        },
        'arturl'     : {'out_type'  : str,
                        'desc'      : 'an URI to an image',
                        },
        'audio-bitrate': {'out_type': int,
                        'exaile_tag': '__bitrate',
                        'desc'      : 'The number of bits per second',
                        },
        'audio-samplerate': {'out_type': int,
                        'desc'      : 'The number of samples per second',
                        },
        }
EXAILE_TAG_INFORMATION = {}
def __fill_exaile_tag_information():
    """
        Fille EXAILE_TAG_INFORMATION with the exaile_tag: mpris_tag, the
        inverse of MPRIS_TAG_INFORMATION
    """
    for mpris_tag in MPRIS_TAG_INFORMATION:
        if 'exaile_tag' in MPRIS_TAG_INFORMATION[mpris_tag]:
            exaile_tag = MPRIS_TAG_INFORMATION[mpris_tag]['exaile_tag']
        else:
            exaile_tag = mpris_tag
        if exaile_tag is None:
            continue
        EXAILE_TAG_INFORMATION[exaile_tag] = mpris_tag
__fill_exaile_tag_information()

class OutputTypeMismatchException(Exception):

    """
        Exception for when a tag from Exaile could not be converted to an MPRIS
        tag
    """

    def __init__(self, exaile_tag, mpris_tag, val):
        Exception.__init__(self,
                "Could not convert tag exaile:'%s' to mpris:'%s':"
                "Error converting '%s' to type '%s"
                % (exaile_tag, mpris_tag, val,
                    MPRIS_TAG_INFORMATION[mpris_tag]['out_type']))

class ExaileTagConverter(object):

    """
    Class to convert tags from Exaile to Metadata for MPRIS
    """

    def __init__(self, exaile):
        self.exaile = exaile

    def get_metadata(self, track):
        """
            Returns the Metadata for track as defined by MPRIS standard
        """
        metadata = {}
        for exaile_tag in track.list_tags():
            if exaile_tag not in EXAILE_TAG_INFORMATION:
                continue
            val = ExaileTagConverter.__get_first_item(track.get_tag_raw(exaile_tag))
            try:
                mpris_tag, mpris_val = ExaileTagConverter.convert_tag(
                        exaile_tag, val)
            except OutputTypeMismatchException as e:
                _LOG.exception(e)
                continue
            if mpris_tag is None:
                continue
            metadata[mpris_tag] = mpris_val

        for mpris_tag in MPRIS_TAG_INFORMATION:
            if 'constructor' in MPRIS_TAG_INFORMATION[mpris_tag]:
                val = MPRIS_TAG_INFORMATION[mpris_tag]['constructor'](
                            self.exaile,
                            track
                        )
                if val is not None:
                    try:
                        metadata[mpris_tag] = \
                            MPRIS_TAG_INFORMATION[mpris_tag]['out_type'](val)
                    except ValueError:
                        raise OutputTypeMismatchException(
                                MPRIS_TAG_INFORMATION[mpris_tag]['exaile_tag'],
                                mpris_tag,
                                val,
                              )


        return metadata

    @staticmethod
    def __get_first_item(value):
        """
            Unlists lists and returns the first value, if not a lists,
            returns value
        """
        if not isinstance(value, str) and hasattr(value, "__getitem__"):
            if len(value):
                return value[0]
            return None
        return value

    @staticmethod
    def convert_tag(exaile_tag, exaile_value):
        """
            Converts a single tag into MPRIS form, return a 2-tuple of
            (mpris_tag, mpris_val). Returns (None, None) if there is no
            translation
        """
        if exaile_tag not in EXAILE_TAG_INFORMATION:
            return (None, None)
        mpris_tag = EXAILE_TAG_INFORMATION[exaile_tag]
        info = MPRIS_TAG_INFORMATION[mpris_tag]
        if 'conv' in info:
            mpris_value = info['conv'](exaile_value)
        else:
            mpris_value = exaile_value
        try:
            mpris_value = info['out_type'](mpris_value)
        except ValueError:
            raise OutputTypeMismatchException(exaile_tag,
                                              mpris_tag,
                                              exaile_value,
                                              )
        return (mpris_tag, mpris_value)

