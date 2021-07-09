'''
Provides IPython console widget.

@author: Eitan Isaacson
@organization: IBM Corporation
@copyright: Copyright (c) 2007 IBM Corporation
@license: BSD

All rights reserved. This program and the accompanying materials are made
available under the terms of the BSD which accompanies this distribution, and
is available at U{https://www.opensource.org/licenses/bsd-license.php}
'''

# Taken from [1] (rev 36e2742, 2019-07-27) with slight modifications.
# The exact license [2] is reproduced below (3-clause BSD).
#
# [1] https://git.gnome.org/browse/accerciser/tree/plugins/ipython_view.py
# [2] https://git.gnome.org/browse/accerciser/tree/COPYING

# Copyright (c) 2005, 2007 IBM Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#     * Neither the name of the IBM Corporation nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import re
import sys
import os
import subprocess

from io import StringIO
from functools import reduce

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

import IPython


IPYTHON_VERSION = int(IPython.__version__.split('.', 1)[0])


class IterableIPShell:
    """
    Create an IPython instance. Does not start a blocking event loop,
    instead allow single iterations. This allows embedding in GTK+
    without blockage.

    @ivar IP: IPython instance.
    @type IP: IPython.iplib.InteractiveShell
    @ivar iter_more: Indicates if the line executed was a complete command,
    or we should wait for more.
    @type iter_more: integer
    @ivar history_level: The place in history where we currently are
    when pressing up/down.
    @type history_level: integer
    @ivar complete_sep: Separation delimiters for completion function.
    @type complete_sep: _sre.SRE_Pattern
    """

    def __init__(self, user_ns=None, cin=None, cout=None, cerr=None, input_func=None):
        """

        @param argv: Command line options for IPython
        @type argv: list
        @param user_ns: User namespace.
        @type user_ns: dictionary
        @param user_global_ns: User global namespace.
        @type user_global_ns: dictionary.
        @param cin: Console standard input.
        @type cin: IO stream
        @param cout: Console standard output.
        @type cout: IO stream
        @param cerr: Console standard error.
        @type cerr: IO stream
        @param input_func: Replacement for builtin raw_input()
        @type input_func: function
        """

        self.prompt = None

        ip_io = IPython.utils.io
        if input_func:
            IPython.terminal.interactiveshell.raw_input_original = input_func
        if cin:
            ip_io.stdin = ip_io.IOStream(cin)
        if cout:
            ip_io.stdout = ip_io.IOStream(cout)
        if cerr:
            ip_io.stderr = ip_io.IOStream(cerr)

        # This is to get rid of the blockage that occurs during
        # IPython.Shell.InteractiveShell.user_setup()

        ip_io.raw_input = lambda x: None

        os.environ['TERM'] = 'dumb'
        excepthook = sys.excepthook

        if IPYTHON_VERSION >= 4:
            from traitlets.config.loader import Config
        else:
            from IPython.config.loader import Config

        cfg = Config()
        cfg.InteractiveShell.colors = "Linux"
        cfg.Completer.use_jedi = False

        # InteractiveShell's __init__ overwrites ip_io.stdout,ip_io.stderr with
        # sys.stdout, sys.stderr, this makes sure they are right
        #
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = ip_io.stdout.stream, ip_io.stderr.stream

        # InteractiveShell inherits from SingletonConfigurable, so use instance()
        #
        self.IP = IPython.terminal.embed.InteractiveShellEmbed.instance(
            config=cfg, user_ns=user_ns
        )

        sys.stdout, sys.stderr = old_stdout, old_stderr

        self.IP.system = lambda cmd: self.shell(
            self.IP.var_expand(cmd), header='IPython system call: '
        )
        # local_ns=user_ns)
        # global_ns=user_global_ns)
        # verbose=self.IP.rc.system_verbose)

        self.IP.raw_input = input_func
        sys.excepthook = excepthook
        self.iter_more = 0
        self.history_level = 0
        self.complete_sep = re.compile(r'[\s\{\}\[\]\(\)]')
        self.updateNamespace({'exit': lambda: None})
        self.updateNamespace({'quit': lambda: None})
        if int(IPYTHON_VERSION) < 5:  # HACK
            self.IP.readline_startup_hook(self.IP.pre_readline)
        # Workaround for updating namespace with sys.modules
        #
        self.__update_namespace()

        # help() is blocking, which hangs GTK+.
        import pydoc

        self.updateNamespace({'help': pydoc.doc})

        # Avoid using input splitter when not really needed.
        # Perhaps it could work even before 5.8.0
        # But it definitely does not work any more with >= 7.0.0
        self.no_input_splitter = IPYTHON_VERSION >= 5
        self.lines = []
        self.indent_spaces = ''

    def __update_namespace(self):
        """
        Update self.IP namespace for autocompletion with sys.modules
        """
        for key, value in sys.modules.items():
            if '.' not in key:
                self.IP.user_ns.update({key: value})

    def execute(self):
        """
        Executes the current line provided by the shell object.
        """
        self.history_level = 0

        # this is needed because some functions in IPython use 'print' to print
        # output (like 'who')
        #
        orig_stdout = sys.stdout
        sys.stdout = IPython.utils.io.stdout

        orig_stdin = sys.stdin
        sys.stdin = IPython.utils.io.stdin
        self.prompt = self.generatePrompt(self.iter_more)

        self.IP.hooks.pre_prompt_hook()
        if self.iter_more:
            try:
                self.prompt = self.generatePrompt(True)
            except:
                self.IP.showtraceback()
            if self.IP.autoindent:
                self.IP.rl_do_indent = True

        try:
            line = self.IP.raw_input(self.prompt)
        except KeyboardInterrupt:
            self.IP.write('\nKeyboardInterrupt\n')
            if self.no_input_splitter:
                self.lines = []
            else:
                self.IP.input_splitter.reset()
        except:
            self.IP.showtraceback()
        else:
            if self.no_input_splitter:
                self.lines.append(line)
                (status, self.indent_spaces) = self.IP.check_complete(
                    '\n'.join(self.lines)
                )
                self.iter_more = status == 'incomplete'
            else:
                self.IP.input_splitter.push(line)
                self.iter_more = self.IP.input_splitter.push_accepts_more()
            self.prompt = self.generatePrompt(self.iter_more)
            if not self.iter_more:
                if self.no_input_splitter:
                    source_raw = '\n'.join(self.lines)
                    self.lines = []
                else:
                    source_raw = self.IP.input_splitter.raw_reset()
                self.IP.run_cell(source_raw, store_history=True)
                self.IP.rl_do_indent = False
            else:
                # TODO: Auto-indent
                #
                self.IP.rl_do_indent = True

        sys.stdout = orig_stdout
        sys.stdin = orig_stdin

    def generatePrompt(self, is_continuation):
        """
        Generate prompt depending on is_continuation value

        @param is_continuation
        @type is_continuation: boolean

        @return: The prompt string representation
        @rtype: string

        """
        if IPYTHON_VERSION >= 5:  # HACK
            return '... ' if is_continuation else '>>> '
        if is_continuation:
            prompt = self.IP.prompt_manager.render('in2')
        else:
            prompt = self.IP.prompt_manager.render('in')

        return prompt

    def historyBack(self):
        """
        Provides one history command back.

        @return: The command string.
        @rtype: string
        """
        self.history_level -= 1
        if not self._getHistory():
            self.history_level += 1
        return self._getHistory()

    def historyForward(self):
        """
        Provides one history command forward.

        @return: The command string.
        @rtype: string
        """
        if self.history_level < 0:
            self.history_level += 1
        return self._getHistory()

    def _getHistory(self):
        """
        Get's the command string of the current history level.

        @return: Historic command string.
        @rtype: string
        """
        try:
            rv = self.IP.user_ns['In'][self.history_level].strip('\n')
        except IndexError:
            rv = ''
        return rv

    def updateNamespace(self, ns_dict):
        """
        Add the current dictionary to the shell namespace.

        @param ns_dict: A dictionary of symbol-values.
        @type ns_dict: dictionary
        """
        self.IP.user_ns.update(ns_dict)

    def complete(self, line):
        """
        Returns an auto completed line and/or possibilities for completion.

        @param line: Given line so far.
        @type line: string

        @return: Line completed as for as possible,
        and possible further completions.
        @rtype: tuple
        """
        split_line = self.complete_sep.split(line)
        if split_line[-1]:
            possibilities = self.IP.complete(split_line[-1])
        else:
            completed = line
            possibilities = ['', []]
        if possibilities:

            def _commonPrefix(str1, str2):
                """
                Reduction function. returns common prefix of two given strings.

                @param str1: First string.
                @type str1: string
                @param str2: Second string
                @type str2: string

                @return: Common prefix to both strings.
                @rtype: string
                """
                for i in range(len(str1)):
                    if not str2.startswith(str1[: i + 1]):
                        return str1[:i]
                return str1

            if possibilities[1]:
                common_prefix = (
                    reduce(_commonPrefix, possibilities[1]) or split_line[-1]
                )
                completed = line[: -len(split_line[-1])] + common_prefix
            else:
                completed = line
        else:
            completed = line
        return completed, possibilities[1]

    def shell(self, cmd, verbose=0, debug=0, header=''):
        """
        Replacement method to allow shell commands without them blocking.

        @param cmd: Shell command to execute.
        @type cmd: string
        @param verbose: Verbosity
        @type verbose: integer
        @param debug: Debug level
        @type debug: integer
        @param header: Header to be printed before output
        @type header: string
        """
        if verbose or debug:
            print((header + cmd))
        # flush stdout so we don't mangle python's buffering
        if not debug:
            popen = subprocess.Popen(
                cmd,
                bufsize=0,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
            print((popen.stdout.read()))


class ConsoleView(Gtk.TextView):
    """
    Specialized text view for console-like workflow.

    @cvar ANSI_COLORS: Mapping of terminal colors to X11 names.
    @type ANSI_COLORS: dictionary

    @ivar text_buffer: Widget's text buffer.
    @type text_buffer: gtk.TextBuffer
    @ivar color_pat: Regex of terminal color pattern
    @type color_pat: _sre.SRE_Pattern
    @ivar mark: Scroll mark for automatic scrolling on input.
    @type mark: gtk.TextMark
    @ivar line_start: Start of command line mark.
    @type line_start: gtk.TextMark
    """

    ANSI_COLORS = {
        '0;30': 'Black',
        '0;31': 'Red',
        '0;32': 'Green',
        '0;33': 'Brown',
        '0;34': 'Blue',
        '0;35': 'Purple',
        '0;36': 'Cyan',
        '0;37': 'LightGray',
        '1;30': 'DarkGray',
        '1;31': 'DarkRed',
        '1;32': 'SeaGreen',
        '1;33': 'Yellow',
        '1;34': 'LightBlue',
        '1;35': 'MediumPurple',
        '1;36': 'LightCyan',
        '1;37': 'White',
    }

    def __init__(self):
        """
        Initialize console view.
        """
        Gtk.TextView.__init__(self)
        pango_ctx = self.get_pango_context()
        chosen = None
        for f in pango_ctx.list_families():
            name = f.get_name()
            # These are known to show e.g U+FFFC
            if name in ["Courier New", "Courier Mono"]:
                chosen = name
                break
            # if name in ["Liberation Sans"]:
            #    chosen = name
            #    # But prefer a monospace one if possible
        if chosen == None:
            chosen = "Mono"
        self.modify_font(Pango.FontDescription(chosen))
        self.set_cursor_visible(True)
        self.text_buffer = self.get_buffer()
        self.mark = self.text_buffer.create_mark(
            'scroll_mark', self.text_buffer.get_end_iter(), False
        )
        for code in self.ANSI_COLORS:
            self.text_buffer.create_tag(
                code, foreground=self.ANSI_COLORS[code], weight=700
            )
        self.text_buffer.create_tag('0')
        self.text_buffer.create_tag('notouch', editable=False)
        self.color_pat = re.compile(r'\x01?\x1b\[(.*?)m\x02?')
        self.line_start = self.text_buffer.create_mark(
            'line_start', self.text_buffer.get_end_iter(), True
        )
        self.connect('key-press-event', self.onKeyPress)

    def write(self, text, editable=False):
        GLib.idle_add(self._write, text, editable)

    def _write(self, text, editable=False):
        """
        Write given text to buffer.

        @param text: Text to append.
        @type text: string
        @param editable: If true, added text is editable.
        @type editable: boolean
        """
        segments = self.color_pat.split(text)
        segment = segments.pop(0)
        start_mark = self.text_buffer.create_mark(
            None, self.text_buffer.get_end_iter(), True
        )
        self.text_buffer.insert(self.text_buffer.get_end_iter(), segment)

        if segments:
            ansi_tags = self.color_pat.findall(text)
            for tag in ansi_tags:
                i = segments.index(tag)
                self.text_buffer.insert_with_tags_by_name(
                    self.text_buffer.get_end_iter(), segments[i + 1], tag
                )
                segments.pop(i)
        if not editable:
            self.text_buffer.apply_tag_by_name(
                'notouch',
                self.text_buffer.get_iter_at_mark(start_mark),
                self.text_buffer.get_end_iter(),
            )
        self.text_buffer.delete_mark(start_mark)
        self.scroll_mark_onscreen(self.mark)

    def showPrompt(self, prompt):
        GLib.idle_add(self._showPrompt, prompt)

    def _showPrompt(self, prompt):
        """
        Prints prompt at start of line.

        @param prompt: Prompt to print.
        @type prompt: string
        """
        self._write(prompt)
        self.text_buffer.move_mark(self.line_start, self.text_buffer.get_end_iter())

    def changeLine(self, text):
        GLib.idle_add(self._changeLine, text)

    def _changeLine(self, text):
        """
        Replace currently entered command line with given text.

        @param text: Text to use as replacement.
        @type text: string
        """
        text_iter = self.text_buffer.get_iter_at_mark(self.line_start)
        text_iter.forward_to_line_end()
        self.text_buffer.delete(
            self.text_buffer.get_iter_at_mark(self.line_start), text_iter
        )
        self._write(text, True)

    def getCurrentLine(self):
        """
        Get text in current command line.

        @return: Text of current command line.
        @rtype: string
        """
        rv = self.text_buffer.get_slice(
            self.text_buffer.get_iter_at_mark(self.line_start),
            self.text_buffer.get_end_iter(),
            False,
        )
        return rv

    def showReturned(self, text):
        GLib.idle_add(self._showReturned, text)

    def _showReturned(self, text):
        """
        Show returned text from last command and print new prompt.

        @param text: Text to show.
        @type text: string
        """
        text_iter = self.text_buffer.get_iter_at_mark(self.line_start)
        text_iter.forward_to_line_end()
        self.text_buffer.apply_tag_by_name(
            'notouch', self.text_buffer.get_iter_at_mark(self.line_start), text_iter
        )
        self._write('\n' + text)
        if text:
            self._write('\n')
        self._write('\n')  # Add extra line, like normal IPython
        self._showPrompt(self.prompt)
        self.text_buffer.move_mark(self.line_start, self.text_buffer.get_end_iter())
        self.text_buffer.place_cursor(self.text_buffer.get_end_iter())

        if self.IP.rl_do_indent:
            if self.no_input_splitter:
                indentation = self.indent_spaces
            else:
                indentation = self.IP.input_splitter.indent_spaces * ' '
            self.text_buffer.insert_at_cursor(indentation)

    def onKeyPress(self, _widget, event):
        """
        Key press callback used for correcting behavior for console-like
        interfaces. For example 'home' should go to prompt, not to beginning of
        line.

        @param widget: Widget that key press occurred in.
        @type widget: gtk.Widget
        @param event: Event object
        @type event: gtk.gdk.Event

        @return: Return True if event should not trickle.
        @rtype: boolean
        """
        insert_mark = self.text_buffer.get_insert()
        insert_iter = self.text_buffer.get_iter_at_mark(insert_mark)
        selection_mark = self.text_buffer.get_selection_bound()
        selection_iter = self.text_buffer.get_iter_at_mark(selection_mark)
        start_iter = self.text_buffer.get_iter_at_mark(self.line_start)
        if event.keyval == Gdk.KEY_Home:
            if (
                event.state & Gdk.ModifierType.CONTROL_MASK
                or event.state & Gdk.ModifierType.MOD1_MASK
            ):
                pass
            elif event.state & Gdk.ModifierType.SHIFT_MASK:
                self.text_buffer.move_mark(insert_mark, start_iter)
                return True
            else:
                self.text_buffer.place_cursor(start_iter)
                return True
        elif event.keyval == Gdk.KEY_Left:
            insert_iter.backward_cursor_position()
            if not insert_iter.editable(True):
                return True
        elif not event.string:
            pass
        elif (
            start_iter.compare(insert_iter) <= 0
            and start_iter.compare(selection_iter) <= 0
        ):
            pass
        elif (
            start_iter.compare(insert_iter) > 0
            and start_iter.compare(selection_iter) > 0
        ):
            self.text_buffer.place_cursor(start_iter)
        elif insert_iter.compare(selection_iter) < 0:
            self.text_buffer.move_mark(insert_mark, start_iter)
        elif insert_iter.compare(selection_iter) > 0:
            self.text_buffer.move_mark(selection_mark, start_iter)

        return self.onKeyPressExtend(event)

    def onKeyPressExtend(self, event):
        """
        For some reason we can't extend onKeyPress directly (bug #500900).
        """
        pass


class IPythonView(ConsoleView, IterableIPShell):
    """
    Sub-class of both modified IPython shell and L{ConsoleView} this makes
    a GTK+ IPython console.
    """

    def __init__(self):
        """
        Initialize. Redirect I/O to console.
        """
        ConsoleView.__init__(self)
        self.cout = StringIO()
        IterableIPShell.__init__(
            self, cout=self.cout, cerr=self.cout, input_func=self.raw_input
        )
        #        self.connect('key_press_event', self.keyPress)
        self.interrupt = False
        self.execute()
        self.prompt = self.generatePrompt(False)
        self.cout.truncate(0)
        self.showPrompt(self.prompt)

    def raw_input(self, prompt=''):
        """
        Custom raw_input() replacement. Get's current line from console buffer.

        @param prompt: Prompt to print. Here for compatibility as replacement.
        @type prompt: string

        @return: The current command line text.
        @rtype: string
        """
        if self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt
        return self.getCurrentLine()

    def onKeyPressExtend(self, event):
        """
        Key press callback with plenty of shell goodness, like history,
        autocompletions, etc.

        @param widget: Widget that key press occurred in.
        @type widget: gtk.Widget
        @param event: Event object.
        @type event: gtk.gdk.Event

        @return: True if event should not trickle.
        @rtype: boolean
        """
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval == 99:
            self.interrupt = True
            self._processLine()
            return True
        elif event.keyval == Gdk.KEY_Return:
            self._processLine()
            return True
        elif event.keyval == Gdk.KEY_Up:
            self.changeLine(self.historyBack())
            return True
        elif event.keyval == Gdk.KEY_Down:
            self.changeLine(self.historyForward())
            return True
        elif event.keyval == Gdk.KEY_Tab:
            if not self.getCurrentLine().strip():
                return False
            completed, possibilities = self.complete(self.getCurrentLine())
            if len(possibilities) > 1:
                line_slice = self.getCurrentLine()
                self.write('\n')
                for symbol in possibilities:
                    self.write(symbol + '\n')
                self.showPrompt(self.prompt)
            self.changeLine(completed or line_slice)
            return True

    def _processLine(self):
        """
        Process current command line.
        """
        self.history_pos = 0
        self.execute()
        returnvalue = self.cout.getvalue()
        if returnvalue:
            returnvalue = returnvalue.strip('\n')
        self.showReturned(returnvalue)
        self.cout.truncate(0)
        self.cout.seek(0)


if __name__ == "__main__":
    window = Gtk.Window()
    window.set_default_size(640, 320)
    window.connect('delete-event', lambda x, y: Gtk.main_quit())
    window.add(IPythonView())
    window.show_all()
    Gtk.main()
