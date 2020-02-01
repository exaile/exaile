#!/usr/bin/env python3
#
# Copyright (C) 2016 Dustin Spicuzza
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
#

#
# This requires click to be installed, which is not an Exaile dependency
#


import copy
import datetime
from dbm import whichdb
import json
import os.path
import pickle
import pprint
import shelve

import bsddb3 as bsddb
import click


class Utf8Unpickler(pickle.Unpickler):
    def __init__(self, *args, **kwargs):
        kwargs['encoding'] = 'utf-8'
        super().__init__(*args, **kwargs)


# For compatibility with Python 2 shelves
shelve.Unpickler = Utf8Unpickler

exaile_db = os.path.join(os.path.expanduser('~'), '.local', 'share', 'exaile',
                         'music.db')
exaile_pickle_protocol = 2


def tracks(data):
    for k, v in data.items():
        if not k.startswith('tracks-'):
            continue
        yield k, v


@click.group()
@click.option('--db', default=exaile_db)
@click.pass_context
def cli(ctx, db):
    '''
        Tool that allows low-level exploration of an Exaile music database
    '''
    # simpler version of trackdb.py
    try:
        d = bsddb.hashopen(db, 'r')
        contents = shelve.Shelf(d, protocol=exaile_pickle_protocol)
    except Exception:
        try:
            contents = shelve.open(db, flag='r', protocol=exaile_pickle_protocol)
        except Exception:
            if os.path.exists(db):
                raise
            else:
                raise click.ClickException("%s does not exist" % db)

    ctx.obj = contents

    def _on_close():
        ctx.obj.close()

    ctx.call_on_close(_on_close)


@cli.command()
@click.pass_obj
@click.pass_context
@click.argument('dbtype')
def cvtdb(ctx, data, dbtype):
    '''
        Only used for testing purposes
    '''

    db = ctx.parent.params['db']
    newdb = db + '.new'

    if dbtype == 'gdbm':
        import dbm.gnu
        new_d = dbm.gnu.open(newdb, 'n')
    elif dbtype == 'dbm':
        import dbm.ndbm
        new_d = dbm.ndbm.open(newdb, 'n')
    elif dbtype == 'dbhash':
        import dbm.bsd
        new_d = dbm.bsd.open(newdb, 'n')
    elif dbtype == 'bsddb':
        new_d = bsddb.hashopen(newdb, 'n')
    elif dbtype == 'dumbdbm':
        import dbm.dumb
        new_d = dbm.dumb.open(newdb, 'n')
    else:
        raise click.ClickException("Invalid type %s" % dbtype)

    new_data = shelve.Shelf(new_d, protocol=exaile_pickle_protocol)

    for k, v in data.items():
        new_data[k] = v

    new_data.sync()
    new_data.close()


@cli.command()
@click.pass_obj
@click.argument('output')
def tojson(data, output):
    '''
        Export Exaile's database to JSON
    '''

    # not really a db type, but useful?
    d = {}
    for k, v in data.items():
        d[k] = v
    with open(output, 'w') as fp:
        json.dump(d, fp, sort_keys=True, indent=4, separators=(',', ': '))


@cli.command()
@click.pass_obj
@click.pass_context
def info(ctx, data):
    '''
        Display summary information about the DB
    '''
    print('DB Type:', whichdb(ctx.parent.params['db']))
    print('Version:', data.get('_dbversion'))
    print('Name   :', data.get('name'))
    print('Key    :', data.get('_key'))
    print("Count  :", len(data))
    print()
    print('Location(s):')
    pprint.pprint(data.get('_serial_libraries'))


@cli.command()
@click.argument('search')
@click.option('-t', '--tag', default='title')
@click.pass_obj
def search(data, tag, search):
    '''
        Search for tracks via the contents of particular tags
    '''
    tag = str(tag)
    for k, tr in tracks(data):
        tr = tr[0]
        val = tr.get(tag)
        if val:
            if isinstance(val, list):
                val = val[0]
            if search in val:
                print('%10s: %s' % (k, val))


def _date_fix(tags):
    tags = copy.deepcopy(tags)
    for t in ['__date_added', '__last_played', '__modified']:
        if t in tags:
            try:
                dt = datetime.datetime.fromtimestamp(tags[t])
                tags[t] = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

    return tags


def _print_tr(tr, raw):
    if tr is not None:
        tags, key, attrs = tr
        print("Track key", key)
        print("Tags:")
        if not raw:
            tags = _date_fix(tags)
        pprint.pprint(tags)
        print("Attrs:")
        pprint.pprint(attrs)


@cli.command('track-by-idx')
@click.argument('idx')
@click.option('--raw/--no-raw', default=False)
@click.pass_obj
def track_by_idx(data, idx, raw):
    '''
        pprint a track by its index in the database
    '''
    key = str('tracks-%s' % idx)
    tr = data.get(key)
    _print_tr(tr, raw)


@cli.command()
@click.pass_obj
def tags(data):
    '''
        Display summary information about tags present
    '''

    tags = set()

    for k, v in tracks(data):
        # print(v[0].keys())
        tags.update(set(v[0].keys()))

    print("All tags:")
    pprint.pprint(tags)


if __name__ == '__main__':
    cli()
