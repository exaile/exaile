# Copyright (C) 2008-2010 Adam Olsen
# Copyright (C) 2015 Dustin Spicuzza
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
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.


import logging
import logging.handlers
from pprint import PrettyPrinter
import os.path
import sys

__all__ = ['start_logging', 'stop_logging']


MAX_VARS_LINES = 30
MAX_LINE_LENGTH = 100


class FilterLogger(logging.Logger):
    class Filter(logging.Filter):
        def filter(self, record):
            pass_record = True

            if FilterLogger.module is not None:
                pass_record = record.name == self.module

            if FilterLogger.level != logging.NOTSET and pass_record:
                pass_record = record.levelno == self.level

            return pass_record

    module = None
    level = logging.NOTSET

    def __init__(self, name):
        logging.Logger.__init__(self, name)

        log_filter = self.Filter(name)
        log_filter.module = FilterLogger.module
        log_filter.level = FilterLogger.level
        self.addFilter(log_filter)


class SafePrettyPrinter(PrettyPrinter):
    def _repr(self, *args, **kwargs):
        try:
            return PrettyPrinter._repr(self, *args, **kwargs)
        except Exception as e:
            return "!! Cannot format: %s" % e


class VerboseExceptionFormatter(logging.Formatter):
    """
    Taken from https://word.bitly.com/post/69080588278/logging-locals
    """

    def __init__(self, log_locals_on_exception=True, *args, **kwargs):
        self._log_locals = log_locals_on_exception
        self._printer = SafePrettyPrinter(indent=2)
        super(VerboseExceptionFormatter, self).__init__(*args, **kwargs)

    def formatException(self, exc_info):
        # First get the original formatted exception.
        exc_text = super(VerboseExceptionFormatter, self).formatException(exc_info)
        if not self._log_locals or exc_info[2] is None:
            return exc_text
        # Now we're going to format and add the locals information.
        output_lines = [exc_text, '']
        tb = exc_info[2]  # This is the outermost frame of the traceback.
        while tb.tb_next:
            tb = tb.tb_next  # Zoom to the innermost frame.
        output_lines.append('Locals at innermost frame:\n')
        locals_text = self._printer.pformat(tb.tb_frame.f_locals)

        locals_lines = locals_text.split('\n')
        if len(locals_lines) > MAX_VARS_LINES:
            locals_lines = locals_lines[:MAX_VARS_LINES]
            locals_lines[-1] = '...'
        output_lines.extend(
            line[: MAX_LINE_LENGTH - 3] + '...' if len(line) > MAX_LINE_LENGTH else line
            for line in locals_lines
        )
        output_lines.append('')
        return '\n'.join(output_lines)


def start_logging(debug, quiet, debugthreads, module_filter, level_filter):
    """
    Starts logging, only should be called from xl.main
    """

    console_format = "%(levelname)-8s: %(message)s"
    console_loglevel = logging.INFO

    file_format = '%(asctime)s %(levelname)-8s: %(message)s (%(name)s)'
    file_loglevel = logging.INFO

    datefmt = "%H:%M:%S"

    if debugthreads:
        console_format = "%(threadName)s:" + console_format
    else:
        logging.logThreads = 0

    logging.logMultiprocessing = 0
    logging.logProcesses = 0

    if debug:
        file_loglevel = logging.DEBUG
        console_loglevel = logging.DEBUG
        console_format = "%(asctime)s,%(msecs)03d:" + console_format
        console_format += " (%(name)s)"  # add module name
    elif quiet:
        console_loglevel = logging.WARNING

    if debug:
        fmt_class = VerboseExceptionFormatter
    else:
        fmt_class = logging.Formatter

    # Logging to terminal
    handler = logging.StreamHandler()
    handler.setFormatter(fmt_class(fmt=console_format, datefmt=datefmt))
    logging.root.addHandler(handler)
    logging.root.setLevel(console_loglevel)

    if module_filter or level_filter:
        FilterLogger.module = module_filter
        if level_filter is not None:
            FilterLogger.level = getattr(logging, level_filter)
        logging.setLoggerClass(FilterLogger)

    # Create log directory
    from . import xdg

    logdir = xdg.get_logs_dir()

    # Logging to file; this also automatically rotates the logs
    logfile = logging.handlers.RotatingFileHandler(
        os.path.join(logdir, 'exaile.log'), mode='a', backupCount=5, delay=True
    )
    logfile.doRollover()  # each session gets its own file
    logfile.setLevel(file_loglevel)
    logfile.setFormatter(fmt_class(fmt=file_format, datefmt=datefmt))
    logging.root.addHandler(logfile)

    # GTK3 supports sys.excepthook
    if debug:
        logger = logging.getLogger('gtk')

        def log_unhandled_exception(*args):
            logger.error("Unhandled exception", exc_info=args)

        sys.excepthook = log_unhandled_exception

    # Strictly speaking, this isn't logging, but it's useful for debugging
    # when Exaile hangs.
    if sys.stderr.isatty():
        import faulthandler

        # Windows doesn't allow custom fault handler registration
        if hasattr(faulthandler, 'register'):
            import signal

            faulthandler.register(signal.SIGUSR2)
        faulthandler.enable()


def stop_logging():
    logging.shutdown()
