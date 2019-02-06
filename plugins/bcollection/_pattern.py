# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import re

from collections import defaultdict

from _base import SETTINGS
from _utils import SQLStatements, get_icon


#: list: Constant fields
CONST_FIELDS = ['count', 'albums', 'albumartists', 'tracks', 'length', 'bpm']

#: str: Const fields select
_CONST_SELECT_FIELDS_SQL = ', '.join(
    [
        'count(*)',
        'count(distinct albumartist||album)',
        'count(distinct albumartist)',
        'count(distinct path)',
        'sum(length)',
        'avg(bpm)',
    ]
)

# CHARS #
#: str: Char to be used as escape
_ESCAPE_CHAR = '\\'

#: str: Close bracket chars
_CLOSE_BRACKETS = ')]'

#: str: Open bracket chars
_OPEN_BRACKETS = '(['

#: str: Mark to subgroup
_SUBGROUP_MARK = '%'
#: str: Mark to tooltip
_TOOLTIP_MARK = '&'

# REGEX #
#: SRE_Pattern: Evaluable field regex
_EVAL_FIELD_REGEX = re.compile(r'^\(([?!])([a-z_]+):(.+)\)$')

#: SRE_Pattern: Hidden field regex
_HIDDEN_FIELD_REGEX = re.compile(r'^\([*>]?([a-z_]+)(:.*)?\)$')

#: SRE_Pattern: Output field regex
_OUTPUT_FIELD_REGEX = re.compile(r'^\[[*>]?([a-z_]+)(:.*)?\]$')

#: SRE_Pattern: Regex for subgroup names
_NAME_REGEX = re.compile(r'^\([:](.+)\)$')


def _split(text, sep):
    """
        Split text

        Empty expressions are ignored, so you can use how much characters
        you want (e.g. group1%%%group2)

        Use '\' to escape

        Usage:
            >>> _split('group 1%group 2%group 3', '%')
            ['group 1', 'group 2', 'group 3']
            >>> _split('group 1%%%group 2%%%group 3', '%')
            ['group 1', 'group 2', 'group 3']

        :param text: str
        :return: list of split groups [str]
    """
    text_it = iter(text)
    text_char = ['']
    current_expression = ['']
    expressions = []

    def end_expression():
        """
            Ends an expression
            Expressions must be not ''
            :return: None
        """
        if current_expression[0]:
            expressions.append(current_expression[0])
            current_expression[0] = ''

    def go_next():
        """
            Go next text_it
            :return: None
        """
        size = 2 if text_char[0] == _ESCAPE_CHAR else 1
        while size > 0:
            current_expression[0] += text_char[0]
            text_char[0] = next(text_it)
            size -= 1

    try:
        text_char[0] = next(text_it)
        while True:
            if text_char[0] == sep:
                end_expression()
                text_char[0] = next(text_it)
            else:
                go_next()
    except StopIteration:
        end_expression()

    return expressions


def _split_expressions(text):
    """
        Split text in expressions

        Are considered expressions any pair of parenthesis ('(', ')')
        or crotchets ('[', ']'), or any free text, not inside those pairs

        Ignore escaped characters ('\\')

        Usage:
        >>> text = 'first exp (exp n two(not a)) [exp 3 (Not_Exp)] ...'
        >>> result = _split_expressions(text)
        >>> result
        ['first exp ', '(exp n two(not a))', ' ', '[exp 3 (Not_Exp)]', ' ...']
        >>> ''.join(result)
        'first exp (exp n two(not a)) [exp 3 (Not_Exp)] ...'
        >>> text = '[()]free(())'
        >>> result = _split_expressions(text)
        >>> result
        ['[()]', 'free', '(())']
        >>> ''.join(result) == text
        True

        :param text: str
        :return: list
    """
    text_it = iter(text)
    text_char = ['']
    exp_stack = []
    current_expression = ['']
    expressions = []

    def end_expression():
        """
            Appends and defines another
            :return: None
        """
        if current_expression[0]:
            expressions.append(current_expression[0])
            current_expression[0] = ''
            del exp_stack[:]

    def go_next():
        """
            Gets next expression
            :return:
        """
        size = 2 if text_char[0] == _ESCAPE_CHAR else 1
        while size > 0:
            current_expression[0] += text_char[0]
            text_char[0] = next(text_it)
            size -= 1

    try:
        text_char[0] = next(text_it)
        while True:
            end_exp = False
            if exp_stack and text_char[0] == exp_stack[-1]:
                exp_stack.pop()
                end_exp = len(exp_stack) == 0
            else:
                open_index = _OPEN_BRACKETS.find(text_char[0])
                if open_index + 1:
                    if len(exp_stack) == 0:
                        end_expression()
                    exp_stack.append(_CLOSE_BRACKETS[open_index])
            go_next()
            if end_exp:
                end_expression()
    except StopIteration:
        end_expression()

    return expressions


def _parse_text(text, all_fields, fields, output_fields, output, icons, names, desc):
    """
        Parse text looking for fields

        >>> params = ('all_fields', 'fields', 'output_fields', 'output', \
                      'icons', 'names')
        >>> values = defaultdict(list)
        >>> _parse_text('begin[first](?second:not)(:A Name)[*third]' + \
                       'middle(*fourth)[last]end(!fifth:nothing)', \
                       *[values[i] for i in params])
        >>> for i in params: print(i, values[i])
        all_fields ['first', 'second', 'third', 'fourth', 'last', 'fifth']
        fields ['first', 'second', 'third', 'fourth', 'last', 'fifth']
        output_fields ['first', 'third', 'last']
        output ['begin', '{first}', ('?', 'second', ['not']), '{third}', 'middle', '{last}', 'end', ('!', 'fifth', ['nothing'])]
        icons ['third', 'fourth']
        names ['A Name']

        :param text: str
        :param all_fields: list
        :param fields: list
        :param output: list
        :param output_fields: list
        :param icons: list
        :param names: list
        :return: None
    """

    def add_field(field, first_char='', icon_size=None):
        """
            Adds the field
            :param field: str - name
            :param first_char: char - char of first group
            :param icon_size: str - icon size or None
            :return: None
        """
        if field and field not in CONST_FIELDS:
            if field not in all_fields:
                all_fields.append(field)

            if field not in fields:
                fields.append(field)

        if first_char:
            if first_char == '*':
                icons.append((field, icon_size))
            elif first_char == '>':
                desc.append(field)

    for i in _split_expressions(text):
        match_object = _NAME_REGEX.match(i)
        if match_object:
            names.append(match_object.group(1))
        else:
            match_object = _OUTPUT_FIELD_REGEX.match(i)
            if match_object:
                groups = match_object.groups('')
                add_field(groups[0], i[1])
                output_fields.append(groups[0])
                output.append('{' + ''.join(groups) + '}')
                continue

            match_object = _HIDDEN_FIELD_REGEX.match(i)
            if match_object:
                add_field(match_object.group(1), i[1], match_object.group(2))
                continue

            match_object = _EVAL_FIELD_REGEX.match(i)
            if match_object:
                groups = match_object.groups()
                add_field(groups[1])
                inner_output = []
                _parse_text(
                    groups[2],
                    all_fields,
                    fields,
                    output_fields,
                    inner_output,
                    icons,
                    names,
                    desc,
                )
                output.append((groups[0], groups[1], inner_output))
                continue

            if _OPEN_BRACKETS.find(i[0]) == _CLOSE_BRACKETS.find(i[-1]) != -1:
                output.append(i[0])
                _parse_text(
                    i[1 : len(i) - 2],
                    all_fields,
                    fields,
                    output_fields,
                    output,
                    icons,
                    names,
                    desc,
                )
                output.append(i[-1])
            else:
                output.append(i)


def _clean_text(text):
    """
        Remove escape char from text
        :param text: str
        :return: str
    """
    text_result = ''
    text_it = iter(text)
    try:
        while True:
            current_char = next(text_it)
            if current_char == '\\':
                current_char = next(text_it)
            text_result += current_char
    except StopIteration:
        return text_result  # always pass here


def _clean_output(output):
    """
        Clean output

        Output it's a list of strings and tuple (evaluated type),
        so it clean it, unifying and pre-processing strings

        :param output: list
        :return: list cleaned
    """
    new_output = []
    current_str = ''
    for i in output:
        if isinstance(i, (tuple,)):
            if current_str:
                new_output.append(current_str)
                current_str = ''

            new_output.append((('?' == i[0]), i[1], _clean_output(i[2])))
        else:
            current_str += _clean_text(i)

    if current_str:
        new_output.append(current_str)

    return new_output


class ViewPattern(list):
    """
        Pattern to the tree view
    """

    class Subgroup(object):
        """
            A pattern subgroup
        """

        class Icons:
            """
                Class to handle icons
            """

            def __init__(self, name):
                """
                    Constructor
                    :param name: str
                """
                self.name = name

            def __getitem__(self, size):
                """
                    Get icon
                    :param size: int
                    :return: GdkPixbuf.Pixbuf
                """
                return get_icon(self.name, size)

        class Output:
            """
                Class that handles the format to output texts
            """

            def __init__(self, data):
                """
                    Constructor
                    :param data: dict
                """
                self.data = _clean_output(data['output'])
                self.fields = data['fields']

            @classmethod
            def __format(cls, output, item_data):
                """
                    Generate/Process text to output and item data
                    :param output: list
                    :param item_data: dict
                    :return: str
                """
                result = ''
                for i in output:
                    if isinstance(i, (tuple,)):
                        if bool(item_data[i[1]]) == i[0]:
                            result += cls.__format(i[2], item_data)
                    else:
                        result += i.format(**item_data)

                return result.replace("<br>", "\n")

            def format(self, item_data):
                """
                    Format the text to output
                    :param item_data:
                    :return: str
                """
                return self.__format(self.data, item_data)

        def __init__(self, parent_subgroup, all_fields, names, text):
            """
                Constructor
                :param parent_subgroup: ViewPattern._Subgroup
                :param all_fields: []
                :param names: []
                :param text: str
            """

            def try_icons(fields):
                """
                    Try to get icon
                    :param fields:
                    :return: str, '' as not found
                """
                for i in fields:
                    try:
                        return SETTINGS['icons'][i]
                    except KeyError:
                        continue

                return ''

            specs = ('tree_view', 'tooltip')
            subgroup_data = defaultdict(list)
            spec_data = defaultdict(lambda: defaultdict(list))

            def parse_text(text, data):
                """
                    Helper to parse text on data
                    :param text: str
                    :param data: defaultdict
                    :return: None
                """
                _parse_text(
                    text,
                    all_fields,
                    subgroup_data['fields'],
                    data['fields'],
                    data['output'],
                    data['icons'],
                    subgroup_data['names'],
                    subgroup_data['desc'],
                )

            split_text = _split(text, _TOOLTIP_MARK)

            parse_text(split_text[0], spec_data[specs[0]])
            if len(split_text) > 1:
                parse_text(split_text[1], spec_data[specs[1]])
            else:
                spec_data[specs[1]] = spec_data[specs[0]]

            if len(subgroup_data['fields']) == 0:
                raise ValueError('Subgroup must have fields')

            if len(subgroup_data['names']) == 1:
                names.append(_clean_text(subgroup_data['names'][0]))
            elif len(subgroup_data['names']) > 1:
                names.append(
                    '('
                    + ' - '.join([_clean_text(name) for name in subgroup_data['names']])
                    + ')'
                )

            self.parent_subgroup = parent_subgroup
            self.fields = subgroup_data['fields']

            self.outputs = {i: self.Output(spec_data[i]) for i in specs}

            self.order_by_statement = 'order by %s' % ', '.join(
                [
                    'normalize(%s) %s' % i
                    for i in zip(
                        self.fields,
                        [
                            'desc' if i in subgroup_data['desc'] else 'asc'
                            for i in self.fields
                        ],
                    )
                ]
            )

            icons = self.icons = {}
            for i in specs:
                data = spec_data[i]
                icon_size = SETTINGS['icon_size']
                for (j, exp) in filter(lambda x: x[1], data['icons']):
                    if exp:
                        try:
                            icon_size = int(exp[1:])
                        except:
                            pass

                icon_name = (
                    try_icons(map(lambda x: x[0], data['icons']))
                    or try_icons(data['fields'])
                    or try_icons(subgroup_data['fields'])
                    or 'image-x-generic'
                )

                icons[i] = get_icon(icon_name, icon_size)

            self.__paths_sql = self.__sql = None
            self.is_root = parent_subgroup is None
            self.is_bottom = False

        @classmethod
        def __get_each_parent(cls, parent_subgroup):
            """
                Get each parent to a subgroup
                :param parent_subgroup: ViewPattern._Subgroup
                :return: yield each top-down
            """
            if parent_subgroup:
                for i in cls.__get_each_parent(parent_subgroup.parent_subgroup):
                    yield i
                yield parent_subgroup

        def __get_parent_fields(self):
            """
                Get all fields from parents
                :return: yield each field (top-down order)
            """
            for subgroup in self.get_each_parent():
                for field in subgroup.fields:
                    yield field

        def get_each_parent(self):
            """
                Get each parent to self
                :return: each parent top-down
            """
            return self.__class__.__get_each_parent(self.parent_subgroup)

        @staticmethod
        def __mount_where_clause(fields, values, where_search=''):
            """
                Mounts the where clause for sql statement
                :param fields: list
                :param values: list
                :param where_search: str
                :return: str
            """
            where_sql = ' and '.join(
                '(%s)' % i
                for i in filter(
                    None,
                    [
                        ' and '.join(
                            [
                                ('%s is null' if v is None else '%s = ?') % f
                                for f, v in zip(fields, values)
                            ]
                        ),
                        where_search,
                    ],
                )
            )
            return ('where ' + where_sql) if where_sql else ''

        def get_select(self, parent_values, where_search=''):
            """
                Build the select sql statement
                :param parent_values: [] - values from parent
                :param where_search: str
                :return: str - sql statement
            """
            pre_fields = []
            if self.parent_subgroup is None and SETTINGS['draw_separators']:
                pre_fields = ['get_letter_group(%s)' % self.fields[0]]

            select_fields_sql = ', '.join(pre_fields + self.fields)
            sql_statement = SQLStatements(
                'select %s, %s from items', select_fields_sql, _CONST_SELECT_FIELDS_SQL
            )
            sql_statement.append(
                self.__mount_where_clause(
                    self.__get_parent_fields(), parent_values, where_search
                )
            )

            sql_statement.append('group by %s', select_fields_sql)
            sql_statement.append(self.order_by_statement)

            return sql_statement.result

        def get_select_path(self, values, where_search=''):
            """
                Build the select sql statement for `path` field, only
                :return: str
            """
            sql_statement = SQLStatements('select path from items')
            sql_statement.append(
                self.__mount_where_clause(
                    list(self.__get_parent_fields()) + self.fields, values, where_search
                )
            )
            sql_statement.append(self.order_by_statement)

            return sql_statement.result

    def __init__(self, text):
        """
            Constructor
            :param text: str
        """
        super(ViewPattern, self).__init__()

        all_fields = CONST_FIELDS[:]
        names = []
        parent_subgroup = None
        for i in _split(text, _SUBGROUP_MARK):  # subgroups
            try:
                subgroup = self.Subgroup(parent_subgroup, all_fields, names, i)
            except ValueError:
                pass
            else:
                self.append(subgroup)
                parent_subgroup = subgroup

        if parent_subgroup is None:
            raise ValueError('at least one valid subgroup is required')
        else:
            parent_subgroup.is_bottom = True
            self.name = ' - '.join(names)
            self.all_fields = all_fields[len(CONST_FIELDS) :]


def parse_patterns(pattern):
    """
        Parse patterns
        :param pattern: list of str - each item representing a line
        :return: list of ViewPattern
    """
    view_patterns = []
    expressions = []

    def add_view_pattern():
        """
            Adds a view pattern
            :return: None
        """
        if expressions:
            try:
                view_patterns.append(ViewPattern(''.join(expressions)))
            except ValueError:
                pass

            del expressions[:]

    for i in pattern:
        if i == '':
            add_view_pattern()
        else:
            expressions.append(i)
    add_view_pattern()  # load last

    return view_patterns
