import time

import threading

# Python tricks:
def trace(prefix, show_ret=False):
    def decorator(func):
        def wrapper(*args):
            signature = "[%s] %s.%s: %s" % (threading.current_thread().getName(),
                                            prefix, func.__name__, args)
            print signature, "..."
            ret = func(*args)
            if show_ret:
                print signature, "->", ret
            return ret
        return wrapper
    return decorator

def contract(pre, post):
    def func(method):
        def wrapper(self, *args, **kwargs):
            if not pre(self):
                raise Exception("Pre-condition not met")
            ret = method(self, *args, **kwargs)
            if not post(self):
                raise Exception("Post-condition not met")
            return ret
        return wrapper
    return func

def locked(lock_func):
    def func(method):
        def wrapper(self, *args, **kwargs):
            with lock_func(self):
                return method(self, *args, **kwargs)
        return wrapper
    return func

class Timer:
    def __init__(self, key):
        self.key = key

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_value, tb):
        end = time.time()
        print "%s took %.2f seconds" % (self.key, end - self.start)
