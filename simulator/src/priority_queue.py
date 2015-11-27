from collections import deque, Iterable
from functools import partial
from heapq import heapify, heappop, heappush
from copy import copy
from operator import attrgetter
from itertools import count


class AbstractBaseQueue:

    def __init__(self, sequence: (list, deque)):
        self._queue = sequence

    @property
    def queue(self):
        return self._queue

    def append(self, item):
        raise NotImplementedError()

    def extend(self, iterable):
        raise NotImplementedError()

    def pop(self):
        raise NotImplementedError()

    def peek(self):
        return self.queue[0]

    def empty(self):
        return not self

    def values(self):
        return iter(self.queue)

    def clear(self):
        self.queue.clear()

    def __bool__(self):
        return bool(self.queue)

    def __copy__(self):
        new = type(self)()
        new._queue = copy(self.queue)
        return new

    def __str__(self):
        return "{}([{!s}])".format(type(self).__name__, ", ".join(repr(i) for i in self.queue))

    __repr__ = __str__


class Queue(AbstractBaseQueue):
    def __init__(self, sequence=()):
        super().__init__(deque(sequence))

    def append(self, item):
        self.queue.append(item)

    def extend(self, iterable):
        self.queue.extend(iterable)

    def pop(self):
        return self.queue.popleft()


class PriorityQueue(AbstractBaseQueue):

    def __init__(self, sequence=()):
        super().__init__(list(sequence))
        heapify(self.queue)

    def __new__(cls, sequence=(), **kwargs):
        if "key" in kwargs:
            return object.__new__(KeyBasedPriorityQueue)
        return object.__new__(cls)

    def append(self, item):
        heappush(self.queue, item)

    def extend(self, iterable):
        self.queue.extend(iterable)
        heapify(self.queue)

    def pop(self):
        return heappop(self.queue)

    def pop_equal(self):
        first = self.pop()
        items = [first]
        while self and self.peek() == first:
            items.append(self.pop())
        return items

    def values(self):
        return sorted(self.queue)


class KeyBasedPriorityQueue(PriorityQueue):

    def __init__(self, sequence=(), *, key):
        super().__init__()
        self._unique_id = count()
        self.key = key
        self.extend(sequence)

    def append(self, item):
        super().append((self.key(item), next(self._unique_id), item))

    def extend(self, iterable):
        super().extend((self.key(item), next(self._unique_id), item) for item in iterable)

    def pop(self):
        return super().pop()[2]

    def peek(self):
        return super().peek()[2]

    def pop_equal(self):
        first_key, _id, first = super().pop()
        items = [first]
        while self and super().peek()[0] == first_key:
            items.append(self.pop())
        return items

    def values(self):
        items = copy(self)
        while not items.empty():
            yield items.pop()

    def __copy__(self):
        queue = KeyBasedPriorityQueue(key=self.key)
        queue._unique_id = count(next(self._unique_id))
        queue._queue = copy(self.queue)
        return queue


class MultiQueue:

    def __init__(self, sequence=(), *, queue_type=AbstractBaseQueue, key=None, cmp=None):
        if isinstance(sequence, queue_type):
            self._queue = copy(sequence)
        else:
            self._queue = queue_type(sequence)
        self.key = key if key else self.identity
        if cmp:
            self.cmp = cmp
        elif key:
            self.cmp = partial(MultiQueue.key_equals, key=key)
        else:
            self.cmp = MultiQueue.equals

    @property
    def queue(self):
        return self._queue

    @staticmethod
    def identity(value):
        return value

    @staticmethod
    def equals(x, y):
        return x == y

    @staticmethod
    def key_equals(x, y_key, *, key):
        return key(x) == y_key

    def peek(self):
        return self.queue.peek()

    def put(self, items):
        if isinstance(items, Iterable):
            self.queue.extend(items)
        else:
            self.queue.append(items)

    def get(self, *, key=None):
        if key:
            cmp = partial(MultiQueue.key_equals, key=key)
        else:
            key = self.key
            cmp = self.cmp
        items = [self.queue.pop()]
        first = key(items[0])
        while not self.queue.empty() and cmp(self.queue.peek(), first):
            items.append(self.queue.pop())
        return items

    def empty(self):
        return self.queue.empty()

    def clear(self):
        self.queue.clear()

    def values(self):
        return self.queue.values()

    def __copy__(self):
        return type(self)(self.queue, key=self.key)

    def __str__(self):
        return "{}({!s})".format(type(self).__name__, self.queue)

    __repr__ = __str__


class MultiActionQueue(MultiQueue):

    def __init__(self, sequence=()):
        super().__init__(sequence, queue_type=Queue, key=attrgetter("start_time"))

    def get_ends_before(self, time):
        actions = [a for a in self.queue.queue if a.end_time < time]
        rest = [a for a in self.queue.queue if a.end_time >= time]
        self.queue.clear()
        self.queue.extend(rest)
        return actions

    def get_starts_before(self, time):
        actions = [a for a in self.queue.queue if a.start_time < time]
        rest = [a for a in self.queue.queue if a.start_time >= time]
        self.queue.clear()
        self.queue.extend(rest)
        return actions

    def __copy__(self):
        return MultiActionQueue(self.queue)


class MultiActionStateQueue(MultiQueue):

    def __init__(self, sequence=()):
        super().__init__(sequence, queue_type=PriorityQueue)

    def __copy__(self):
        return MultiActionStateQueue(self.queue)