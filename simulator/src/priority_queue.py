from heapq import heapify, heappop, heappush


class PriorityQueue:

    def __init__(self, initial_queue=()):
        self.queue = list(initial_queue)
        heapify(self.queue)

    def put(self, item):
        heappush(self.queue, item)

    def get(self):
        return heappop(self.queue)

    def empty(self):
        return not self.queue
