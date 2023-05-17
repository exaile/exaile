# Copyright (C) 2023 luzip665
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from xl import settings


def migrate():
    """
    Migration for flac bpm and tempo tag setting.
    In case it's a new instance disable the old behaviour.
    Otherwise leave it disabled
    """
    firstrun = settings.get_option("general/first_run", True)
    migrated = settings.get_option('collection/use_legacy_metadata_mapping', None)
    if not firstrun and migrated == None:
        settings.set_option('collection/use_legacy_metadata_mapping', True)
    elif firstrun:
        settings.set_option('collection/use_legacy_metadata_mapping', False)
