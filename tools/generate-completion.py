#!/usr/bin/env python3

# Copyright (C) 2015, 2017-2018  Johannes Sasongko <sasongko@gmail.com>
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


def bash_completion(parser):
    """
    :type parser: argparse.ArgumentParser
    """

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

    opt_names = []
    filearg_opt_names = []
    dirarg_opt_names = []
    arg_opt_names = []
    for action in parser._actions:
        names = action.option_strings
        if not names:  # Positional arg
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


def fish_completion(parser):
    """
    :type parser: argparse.ArgumentParser
    """

    import pipes

    options = []
    for action in parser._actions:
        names = action.option_strings
        if not names:  # Positional arg
            continue
        option = ['complete -c exaile']
        for name in names:
            assert len(name) >= 2 and name[0] == '-' and name != '--'
            if len(name) == 2:
                option.append('-s ' + pipes.quote(name[1]))
            elif name[1] == '-':
                option.append('-l ' + pipes.quote(name[2:]))
            else:
                option.append('-o ' + pipes.quote(name[1:]))
        if action.metavar in ('LOCATION', 'DIRECTORY'):
            option.append('-r')
        elif action.metavar is not None:
            option.append('-x')
        if action.choices:
            choices = action.choices
            if isinstance(choices, (list, tuple)):
                choices = (pipes.quote(str(c))+'\\t' for c in choices)
                option.append('-a ' + pipes.quote(' '.join(choices)))
        if action.help:
            option.append('-d ' + pipes.quote(action.help % action.__dict__))
        options.append(' '.join(option))

    return '\n'.join(options)


if __name__ == '__main__':
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    os.environ['LC_ALL'] = 'C'  # Avoid getting translated metavars
    os.environ['EXAILE_DIR'] = root
    sys.path.insert(1, root)
    from xl import main
    p = main.create_argument_parser()
    if len(sys.argv) < 2 or sys.argv[1] == 'bash':
        completion = bash_completion
    elif sys.argv[1] == 'fish':
        completion = fish_completion
    print(completion(p))
