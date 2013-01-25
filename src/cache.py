# Cache implementation
import time

class Cache:
    def __init__(self, limit=None, shared=False, debug=False, top_cache=None):
        self.keys = []
        self.limit = limit
        self.shared = shared
        self.debug = debug
        self.store = {}
        self.hits = 0
        self.misses = 0
        self.chained = []

        if top_cache:
            top_cache.add_chained(self)

    def __add_key(self, key):
        if self.limit is None:
            return

        if len(self.keys) == self.limit:
            older = self.keys[0]
            del self.store[older]
            del self.keys[0]

        self.keys.append(key)

    def __refresh_key(self, key):
        if self.limit is None:
            return

        del self.keys[self.keys.index(key)]
        self.keys.append(key)

    def __setitem__(self, key, value):
        self.__add_key(key)
        self.store[key] = value

    def __getitem__(self, key):
        try:
            start = time.time()
            value = self.store[key]
            self.trace(key, "found in the cache")
            self.hits += 1
            self.__refresh_key(key)
            return value
        except:
            self.misses += 1
            raise

    def add_chained(self, chained):
        self.chained.append(chained)

    def invalidate(self, partial_key):
        matches = []

        for key in self.store:
            if partial_key in key:
                matches.append(key)

        for key in matches:
            self.trace("Invalidating", key)
            del self.store[key]
            if self.keys:
                self.keys.remove(key)

        for chained in self.chained:
            chained.invalidate(partial_key)

    def trace(self, *args):
        if self.debug: print " ".join(map(str,args))

def cached(cache_=None, key_func=None):
    def func(method):
        def wrapper(self, *args, **kwargs):
            if not cache_:
                if not hasattr(self, "__cache__"):
                    self.__cache__ = Cache()
                cache = self.__cache__
            else:
                cache = cache_
    
            if key_func:
                key = key_func(self)
            else:
                key = tuple()

                # if the cache is shared, self must NOT be
                # included in the key (so multiple instances
                # calling the same method with the same args
                # share the same result).
                if not cache.shared:
                    key += (hash(self),)

                key += (method.__name__,)
                key += args
                key += tuple(kwargs.items())

            try:
                return cache[key]
            except:
                start = time.time()
                value = method(self, *args, **kwargs)
                cache.trace(key, "NOT found in the cache, value obtained in", 
                            time.time() - start, "seconds")
                cache[key] = value
                return value
        return wrapper
    return func

