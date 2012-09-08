#!/usr/bin/env python

'''
    Script to install a setup.py-based python module from a tar.gz file
'''

import os
import os.path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ret = 1
setup_py = None

target = tempfile.mkdtemp()
if target[-1] != os.path.sep:
    target += os.path.sep

def safe_extract(tar):
    # inspired by a post on stack overflow
    global setup_py
    for item in tar:
        fname = os.path.abspath(os.path.join(target,item.name))
        if fname.startswith(target):
            if fname.endswith('setup.py'):
                setup_py = fname
            yield item

try:
    # extract tar.gz file
    tar = tarfile.open(sys.argv[1], 'r:gz')
    tar.extractall(path=target, members=safe_extract(tar))
    
    # run installer
    if setup_py is not None:
        ret = subprocess.call([sys.executable, setup_py, 'install'], cwd=os.path.dirname(setup_py))    
except:
    pass

# cleanup and go away
shutil.rmtree(target, ignore_errors=True)
    
exit(ret)
