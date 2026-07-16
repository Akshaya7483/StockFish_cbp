from collections import OrderedDict


class AnalysisCache:
    def __init__(self, max_size=500):
        self.max_size = max_size
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None

        # Mark as recently used
        self.cache.move_to_end(key)

        return self.cache[key]

    def set(self, key, value):

        if key in self.cache:
            self.cache.move_to_end(key)

        self.cache[key] = value

        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()

    def size(self):
        return len(self.cache)