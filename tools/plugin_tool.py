#!/usr/bin/env python3

import re
import os
from os.path import abspath, dirname, join, exists
import sys

v_re1 = re.compile(r"^Version='(.*)'$")
v_re2 = re.compile(r'^Version="(.*)"$')


def _find_bad_plugin_versions(plugins_dir):
    for pname in os.listdir(plugins_dir):
        p = join(plugins_dir, pname, 'PLUGININFO')
        if exists(p):
            with open(p) as fp:
                contents = fp.read()

            s = contents.splitlines()
            for i, l in enumerate(s):
                m = v_re1.match(l) or v_re2.match(l)
                if m:
                    vv = m.group(1)
                    if vv != v:
                        yield pname, p, vv, s[:i] + s[i + 1:]

                    break
            else:
                print("Warning: no version found in %s" % pname)


def check(v, plugins):
    retval = 0
    for pname, _, vv, _ in plugins:
        print("ERROR: Plugin %s version is %s, not %s" % (pname, vv, v))
        retval = 1

    return retval


def fixversion(v, plugins):
    v = "Version='%s'" % v
    for _, p, _, contents in plugins:
        contents = '\n'.join([v] + contents) + '\n'
        with open(p, 'w') as fp:
            fp.write(contents)


if __name__ == '__main__':
    exaile_dir = abspath(join(dirname(__file__), '..'))
    plugins_dir = join(exaile_dir, 'plugins')

    os.environ['EXAILE_DIR'] = exaile_dir
    sys.path.insert(0, exaile_dir)

    import xl.version
    v = '%s' % (xl.version.__version__.split("-")[0].split("+")[0])

    arg = sys.argv[1] if len(sys.argv) > 1 else ''

    if arg == 'check':
        retval = check(v, _find_bad_plugin_versions(plugins_dir))
    elif arg == 'fix':
        retval = fixversion(v, _find_bad_plugin_versions(plugins_dir))
    else:
        print('Usage: %s check|fix' % sys.argv[0])
        retval = 1

    exit(retval)
