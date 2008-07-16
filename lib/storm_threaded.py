# this module wraps storm's sqlite support to handle access from
# multiple threads. note that due to the implementation, all
# storm dbs accessed via this will share a single thread of control,
# which may not be desirable.

from storm.databases.sqlite import *
import threading

from storm.database import register_scheme

class ThreadHolder(threading.Thread):
    def __init__(self):
        self.queue = []
        threading.Thread.__init__(self)
        self.process_event = threading.Event()
        self.setDaemon(True)
        self.start()

    def run(self):
        while True:
            while len(self.queue) == 0:
                self.process_event.wait()
            item = self.queue[0]
            self.queue = self.queue[1:]
            ret = None
            try:
                ret = item[0](*item[1], **item[2])
            except Exception, e:
                ret = e
            item[4] = ret
            item[3].set()

    def enqueue(self, function, args, kwargs):
        print "Storm: running %s, %s, %s"%(function, args, kwargs)
        if threading.currentThread() == self:
            return function(*args, **kwargs)
        event = threading.Event()
        item = [function, args, kwargs, event, None]
        self.queue.append(item)
        self.process_event.set()
        event.wait()
        self.process_event.clear()
        if isinstance(item[4], Exception):
            raise item[4]
        else:
            return item[4]

THREAD = ThreadHolder()

def one_thread(f):
    def wrapper(*args, **kwargs):
        return THREAD.enqueue(f, args, kwargs)

    wrapper.__name__ = f.__name__
    wrapper.__dict__ = f.__dict__
    wrapper.__doc__ = f.__doc__

    return wrapper

class SQLiteThreadedResult(SQLiteResult):
    @one_thread
    def close(self, *args, **kwargs):
        return SQLiteResult.close(self, *args, **kwargs)

    @one_thread
    def get_one(self, *args, **kwargs):
        return SQLiteResult.get_one(self, *args, **kwargs)

    @one_thread
    def get_all(self, *args, **kwargs):
        return SQLiteResult.get_all(self, *args, **kwargs)

    @one_thread
    def __iter__(self, *args, **kwargs):
        return SQLiteResult.__iter__(self, *args, **kwargs)

class SQLiteThreadedConnection(SQLiteConnection):
    result_factory = SQLiteThreadedResult

    @one_thread
    def raw_execute(self, *args, **kwargs):
        return SQLiteConnection.raw_execute(self, *args, **kwargs)

    @one_thread
    def close(self, *args, **kwargs):
        return SQLiteConnection.close(self, *args, **kwargs)

    @one_thread
    def rollback(self, *args, **kwargs):
        return SQLiteConnection.rollback(self, *args, **kwargs)    
    
    @one_thread
    def _check_disconnect(self, *args, **kwargs):
        return SQLiteConnection._check_disconnect(self, *args, **kwargs)

class SQLiteThreaded(SQLite):
    connection_factory = SQLiteThreadedConnection

    @one_thread
    def raw_connect(self, *args, **kwargs):
        return SQLite.raw_connect(self, *args, **kwargs)

# take advantage of storm's built-in scheme registry to override
# sqlite support when this is imported.
register_scheme("sqlite", SQLiteThreaded)

