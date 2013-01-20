import sys

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

