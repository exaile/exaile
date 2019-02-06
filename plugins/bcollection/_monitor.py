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
import os.path
import threading
import time

from datetime import datetime

from xl import event

from _base import SETTINGS
from _database import ConnectionStatus, Logger, get_connection_status


#: int: Minimum timeout to monitor
MINIMUM_TIMEOUT = 5

#: log.Logger: Logger to file
_LOGGER = Logger(__name__)

_end_requested = False
_event = threading.Event()
_last_load = time.gmtime(0)
_log_msg = _LOGGER.debug
_thread = None


def _on_setting_changed(_event_name, _none, key):
    """
        On setting changed, set event to reload 'monitor' setting
        :param _event_name: str
        :param _none: None
        :param key: str
        :return: None
    """
    if key == 'monitor':
        _event.set()


def _run_monitor():
    """
        Runs database monitor
        :return: None
    """
    _log_msg('running database monitor at %s', datetime.now())
    if get_connection_status() == ConnectionStatus.Fine:
        database_path = SETTINGS['database']
        if _last_load < os.path.getmtime(database_path):
            _log_msg('database monitor notice a change')
            SETTINGS.EVENT.log(None, 'database')
        else:
            _log_msg('database monitor has not notice any change')
    else:
        _log_msg('database monitor has not a valid database connection to check')


def _run():
    """
        Thread run
        :return: None
    """
    _log_msg('database monitor thread started')
    while True:
        timeout = SETTINGS['monitor']
        if _event.wait(timeout if timeout >= MINIMUM_TIMEOUT else None):
            if _end_requested:
                break
            else:
                _event.clear()
        else:
            _run_monitor()

    _log_msg('database monitor thread ended')


def start(*_args):
    """
        Starts monitors thread
        :param _args: *args
        :return: None
    """
    global _thread
    stop()

    _thread = threading.Thread(target=_run)
    _thread.start()


def stop(*_args):
    """
        Stops monitors thread
        :param _args: *args
        :return: None
    """
    global _end_requested, _thread
    if _thread and _thread.is_alive():
        _log_msg('cancelling database monitor')
        _end_requested = True
        _event.set()
        _thread.join()
        _thread = None


def update_last_load():
    """
        Updates last load time
        :return: None
    """
    global _last_load
    _last_load = time.time()


SETTINGS.EVENT.connect(_on_setting_changed)
event.add_callback(stop, 'quit_application')
