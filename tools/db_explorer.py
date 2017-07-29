#!/usr/bin/env python2
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

from __future__ import print_function

import copy
import datetime
import json
import os.path
import pprint
import shelve
from whichdb import whichdb

try:
    import bsddb3 as bsddb
except ImportError:
    import bsddb

import click


exaile_db = os.path.join(os.path.expanduser('~'), '.local', 'share', 'exaile',
                         'music.db')
exaile_pickle_protocol = 2

def tracks(data):
    for k, v in data.iteritems():
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
        import gdbm
        new_d = gdbm.open(newdb, 'n')
    elif dbtype == 'dbm':
        import dbm
        new_d = dbm.open(newdb, 'n')
    elif dbtype == 'dbhash':
        import dbhash
        new_d = dbhash.open(newdb, 'n')
    elif dbtype == 'bsddb':
        new_d = bsddb.hashopen(newdb, 'n')
    elif dbtype == 'dumbdbm':
        import dumbdbm
        new_d = dumbdbm.open(newdb, 'n')
    else:
        raise click.ClickException("Invalid type %s" % dbtype)
    
    new_data = shelve.Shelf(new_d, protocol=exaile_pickle_protocol)
    
    for k, v in data.iteritems():
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
    for k, v in data.iteritems():
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


def _print_tr(tr):
    if tr is not None:
        tags, key, attrs = tr
        print("Track key", key)
        print("Tags:")
        pprint.pprint(_date_fix(tags))
        print("Attrs:")
        pprint.pprint(attrs)


@cli.command('track-by-idx')
@click.argument('idx')
@click.pass_obj
def track_by_idx(data, idx):
    '''
        pprint a track by its index in the database
    '''
    key = str('tracks-%s' % idx)
    tr = data.get(key)
    _print_tr(tr)


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
