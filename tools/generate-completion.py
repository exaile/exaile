#!/usr/bin/env python

# Copyright (C) 2015, 2017  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import division, print_function, unicode_literals

import argparse


TEMPLATE = '''_%(prog)s() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    case "${prev}" in
%(prev_opts)s
    esac
    case "${cur}" in
%(cur_opts)s
    esac
}
complete -F _%(prog)s %(prog)s'''

TEMPLATE_OPT = '''        %(opt)s)
%(reply)s
            return 0
            ;;'''

TEMPLATE_REPLY_W = '''            COMPREPLY=( $(compgen -W "%(opts)s" -- ${cur}) )'''
TEMPLATE_REPLY_f = '''            COMPREPLY=( $(compgen -f ${cur}) )'''
TEMPLATE_REPLY_d = '''            COMPREPLY=( $(compgen -d ${cur}) )'''
TEMPLATE_REPLY_empty = '''            COMPREPLY=()'''


def bash_completion(parser):
    """
    :type parser: argparse.ArgumentParser
    """
    actions = parser._actions

    opt_names = []
    filearg_opt_names = []
    dirarg_opt_names = []
    arg_opt_names = []
    for action in actions:
        names = action.option_strings
        if not names:  # Positional args
            continue
        opt_names.extend(names)
        if action.metavar == 'LOCATION':
            filearg_opt_names.extend(names)
        elif action.metavar == 'DIRECTORY':
            dirarg_opt_names.extend(names)
        elif action.metavar is not None:
            arg_opt_names.extend(names)

    return TEMPLATE % {
        'prog': 'exaile',
        'prev_opts': '\n'.join([
            TEMPLATE_OPT % {
                'opt': '|'.join(filearg_opt_names),
                'reply': TEMPLATE_REPLY_f,
            },
            TEMPLATE_OPT % {
                'opt': '|'.join(dirarg_opt_names),
                'reply': TEMPLATE_REPLY_d,
            },
            TEMPLATE_OPT % {
                'opt': '|'.join(arg_opt_names),
                'reply': TEMPLATE_REPLY_empty,
            },
        ]),
        'cur_opts': '\n'.join([
            TEMPLATE_OPT % {
                'opt': '-*',
                'reply': TEMPLATE_REPLY_W % {'opts': ' '.join(opt_names)},
            },
            TEMPLATE_OPT % {
                'opt': '*',
                'reply': TEMPLATE_REPLY_f,
            },
        ]),
    }

if __name__ == '__main__':
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    os.environ['LC_ALL'] = 'C'  # Avoid getting translated metavars
    os.environ['EXAILE_DIR'] = root
    sys.path.append(root)
    from xl import main
    p = main.create_argument_parser()
    print(bash_completion(p))
