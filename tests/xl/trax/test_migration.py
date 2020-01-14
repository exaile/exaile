db_names = {
    'dbm': 'dbm.ndbm',
    'gdbm': 'dbm.gnu',
    'dumbdbm': 'dbm.dumb',
}  # Map of old db names to new module names
available_dbs = set()  # Set of available db's (old names)

try:
    import dbm.ndbm

    available_dbs.add('dbm')
except ImportError:
    pass

try:
    import dbm.gnu

    available_dbs.add('gdbm')
except ImportError:
    pass

try:
    import dbm.dumb

    available_dbs.add('dumbdbm')
except ImportError:
    pass

import glob
import os
from os.path import basename, dirname, join
import pickle
import shutil

import pytest

from xl.common import open_shelf


@pytest.fixture(params=['dbm', 'gdbm', 'dumbdbm'])
def data(request, tmpdir):
    dbtype = request.param
    base = join(dirname(__file__), '..', '..', 'data', 'db')
    truth = {}

    # uses pickle instead of JSON because of unicode issues...
    with open(join(base, 'music.db.pickle'), 'rb') as fp:
        truth = pickle.load(fp)

    if dbtype not in available_dbs:
        pytest.skip('Module %s (%s) does not exist' % (dbtype, db_names[dbtype]))
    else:
        # copy the test data to a tempdir
        loc = str(tmpdir.mkdir(dbtype))

        for f in glob.glob(join(base, dbtype, 'music.*')):
            shutil.copyfile(f, join(loc, basename(f)))

        return truth, loc, dbtype


def test_migration(data):
    truth, loc, dbtype = data

    print(os.listdir(loc))

    try:
        db = open_shelf(join(loc, 'music.db'))
    except Exception as e:
        if dbtype == 'dbm' and getattr(e, 'args', (None,))[0] == 2:
            # on fedora it seems like dbm is linked to gdbm, and on debian based
            # systems that dbm uses a bsd implementation. Ignore these errors,
            # as (presumably) users will only try to migrate databases on systems
            # that were previously able to read the database.
            pytest.skip("Invalid dbm module")
            return
        raise

    for k, v in truth.items():
        assert k in db
        assert v == db[k]

    assert os.listdir(loc) == ['music.db']

    db.close()
