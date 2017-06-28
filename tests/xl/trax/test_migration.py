
try:
    import dbm
except ImportError:
    dbm = None

try:
    import gdbm
except ImportError:
    gdbm = None

try:
    import dumbdbm
except ImportError:
    dumbdbm = None

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
    with open(join(base, 'music.db.pickle')) as fp:
        truth = pickle.load(fp)
    
    if globals()[dbtype] is None:
        pytest.skip('Module %s does not exist' % dbtype)
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
    
    for k, v in truth.iteritems():
        assert k in db
        assert v == db[k]
    
    assert os.listdir(loc) == ['music.db']
    
    db.close()
