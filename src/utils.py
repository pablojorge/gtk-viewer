import sys
import time

# Python tricks:
def trace(prefix):
    def decorator(func):
        def wrapper(*args):
            print "%s.%s: %s -> " % (prefix, func.__name__, args)
            ret = func(*args)
            #sys.stdout.write("%s\n" % ret)
            return ret
        return wrapper
    return decorator

class Timer:
    def __init__(self, key):
        self.key = key

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_value, tb):
        end = time.time()
        print "%s took %.2f seconds" % (self.key, end - self.start)
