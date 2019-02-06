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
from _utils import normalize


class _DataHandler:
    """
        Store and parse data grouping it
        :see: _parse
    """
    def __init__(self, data, tokenized_list_it):
        """
            Constructor
            :param data: [str] - a list to keep the current data
            :param tokenized_list_it: iter
        """
        self.field = self.operator = ''
        self.data = data[0]
        data[0] = next(tokenized_list_it, '')
        if data[0] and data[0] in '=<>~':
            op = data[0]
            data[0] = next(tokenized_list_it)
            if op != '~' and data[0] == '=':
                op += '='
                data[0] = next(tokenized_list_it)

            self.field = self.data
            self.operator = op
            self.data = data[0]
            data[0] = next(tokenized_list_it, '')


def _tokenize(text):
    """
        Tokenize a text separating operators and words

        Usage:
        >>> _tokenize(u'(!lalala)(lelele) lilili')
        [u'(', u'!', u'lalala', u')', u'(', u'lelele', u')', u'lilili']
        >>> _tokenize(u'(!var_name)(varname) any text')
        [u'(', u'!', u'var_name', u')', u'(', u'varname', u')', u'any', u'text']
        >>> _tokenize(u'(!varname1)(var_name2) some_text to check')
        [u'(', u'!', u'varname1', u')', u'(', u'var_name2', u')', u'some_text', u'to', u'check']

        :param text: str
        :return: [str] - tokenized list
    """
    data_it = iter(text)
    data = ['']
    result = []
    current_text = ['']
    reading_str = False

    def add_expression():
        if current_text[0]:
            result.append(current_text[0])
            current_text[0] = ''

    try:
        while True:
            data[0] = next(data_it)
            if data[0] == '\\':
                current_text[0] += next(data_it)
            else:
                if data[0] == '"':
                    reading_str = not reading_str
                    add_expression()
                elif not reading_str and data[0] in ' ()|!=<>~':
                    add_expression()
                    if data[0] != ' ':
                        result.append(data[0])
                else:
                    current_text[0] += data[0]
    except StopIteration:
        add_expression()

    return result


def _parse(tokenized_list):
    """
        Parse syntax, grouping it as `_DataHandler`

        Usage:
        >>> _parse([u'(', u'!', u'lalala', u')', u'(', u'lelele', u')', u'lilili'])
        [u'(', u'!', <__main__._DataHandler instance at 0x...>, u')', u'(', <__main__._DataHandler instance at 0x...>, u')', <__main__._DataHandler instance at 0x...>]
        >>> _parse([u'(', u'!', u'var_name', u')', u'(', u'varname', u')', u'any', u'text'])
        [u'(', u'!', <__main__._DataHandler instance at 0x...>, u')', u'(', <__main__._DataHandler instance at 0x...>, u')', <__main__._DataHandler instance at 0x...>, <__main__._DataHandler instance at 0x...>]
        >>> _parse([u'(', u'!', u'varname1', u')', u'(', u'var_name2', u')', u'some_text', u'to', u'check'])
        [u'(', u'!', <__main__._DataHandler instance at 0x...>, u')', u'(', <__main__._DataHandler instance at 0x...>, u')', <__main__._DataHandler instance at 0x...>, <__main__._DataHandler instance at 0x...>, <__main__._DataHandler instance at 0x...>]

        :param tokenized_list: [str] - result of `_tokenize`
        :return: [_DataHandler]
    """
    data = ['']
    result = []
    tokenized_list_it = iter(tokenized_list)
    try:
        data[0] = next(tokenized_list_it)
        while data[0] != '':
            if data[0] in '!()|':
                result.append(data[0])
                data[0] = next(tokenized_list_it)
            else:
                result.append(_DataHandler(data, tokenized_list_it))
    except StopIteration:
        pass

    return result


def mount_where_sql(text, search_fields):
    """
        Mount the where sql

        Usage:
        >>> mount_where_sql('(artist = test1 album = "album test1") | (albumartist= "value ext" year= 2000)', [])
        ('( `artist` like ? and `album` like ? ) or ( `albumartist` like ? and `year` like ? )', ['%test1%', '%album test1%', '%value ext%', '%2000%'])

        :param text: str
        :param search_fields: [str]
        :return: (str, []) - sql, values
    """
    data_list = _parse(_tokenize(text))

    result = []
    values = []
    join_stack = []

    def pop_join():
        try:
            value = join_stack.pop()
        except IndexError:
            pass
        else:
            result.append(value)

    def use_or_as_join():
        if join_stack:
            del join_stack[:]
            join_stack.append('or')

    def add_value(field_, operator, value):
        pop_join()
        result.append('normalize(`' + field_ + '`)')
        if operator == '~':
            operator = 'regexp'
        elif operator == '=':
            operator = 'like'
            value = '%' + value.replace('%', '\%') + '%'
        elif operator == '==':
            operator = 'like'

        result.append(operator)
        result.append('?')
        values.append(normalize(value.decode('utf-8')))
        join_stack.append('and')

    for i in data_list:
        if isinstance(i, (_DataHandler,)):
            if i.operator:
                add_value(i.field, i.operator, i.data)
            elif search_fields:
                pop_join()
                result.append('(')
                for field in search_fields:
                    use_or_as_join()
                    add_value(field, '=', i.data)
                result.append(')')
        elif i == ')':
            result.append(')')
        elif i == '(':
            pop_join()
            result.append('(')
        elif i == '!':
            pop_join()
            result.append('not')
        elif i == '|':
            use_or_as_join()

    return (
        ' '.join(result), values
    )
