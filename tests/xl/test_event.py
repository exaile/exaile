from gi.repository import GLib
import threading
from xl import event

# nasty globals
on_ui_thread = [False]
calls = [0]


# TODO: monkeypatch instead
def glib_idle_add(fn, *args):
    was_ui_thread = on_ui_thread[0]
    on_ui_thread[0] = True

    try:
        fn(*args)
    finally:
        on_ui_thread[0] = was_ui_thread


GLib.idle_add = glib_idle_add


class NormalCallback:
    def __init__(self):
        self.called = False
        event.add_callback(self.on_cb, 'test')

    def destroy(self):
        event.remove_callback(self.on_cb, 'test')

    def on_cb(self, type, obj, data):
        self.called = True
        self.on_ui_thread = on_ui_thread[0]


class UiCallback:
    def __init__(self):
        self.called = False
        event.add_ui_callback(self.on_cb, 'test')

    def destroy(self):
        event.remove_callback(self.on_cb, 'test')

    def on_cb(self, type, obj, data):
        if on_ui_thread[0]:
            self.called = True


def _init_events():
    event.EVENT_MANAGER = event.EventManager()


def _finish_events():
    assert len(event.EVENT_MANAGER.callbacks) == 0
    assert len(event.EVENT_MANAGER.all_callbacks) == 0
    assert len(event.EVENT_MANAGER.ui_callbacks) == 0


def test_ui_events():
    _init_events()
    ucb = UiCallback()
    ncb = NormalCallback()

    on_ui_thread[0] = True
    event.log_event('test', ucb, None)

    assert ncb.called is True
    assert ncb.on_ui_thread is True
    assert ucb.called is True

    ucb.destroy()
    ncb.destroy()

    _finish_events()


def test_thread_events():

    _init_events()
    ucb = UiCallback()
    ncb = NormalCallback()

    def _run():
        on_ui_thread[0] = False
        event.log_event('test', ucb, None)

    t = threading.Thread(target=_run)
    t.start()
    t.join()

    assert ncb.called is True
    assert ncb.on_ui_thread is False
    assert ucb.called is True

    ucb.destroy()
    ncb.destroy()

    _finish_events()
