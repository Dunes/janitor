from operator import attrgetter

__all__ = ["Period", "get_contiguous_periods"]


class Period:

    def __init__(self, start, end):
        self.start = start
        self.end = end

    @property
    def duration(self):
        return self.end - self.start

    def __eq__(self, other):
        if not isinstance(other, Period):
            return False
        return self.start == other.start and self.end == other.end

    def __lt__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self.end <= other.start

    def __gt__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self.start >= other.end

    def abuts(self, other):
        return self.start == other.end or self.end == other.start

    def contiguous(self, other):
        return (not (self < other or self > other)) or self.abuts(other)

    def __or__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        if not self.contiguous(other):
            raise ValueError("Cannot or non-contiguous periods")
        return Period(min(self.start, other.start), max(self.end, other.end))

    def __repr__(self):
        return "Period(start={}, end={})".format(self.start, self.end)


def get_contiguous_periods(actions):
    """
    Converts a list of actions in a sorted list of contiguous periods
    >>> get_contiguous_periods([Action(start_time=0, duration=2), Action(start_time=2, duration=2), Action(start_time=5, duration=1)])
    [Period(start=0, end=4, Period(start=5, end=6)]
    :param actions: list[action.Action]
    :return: list[Period]
    """
    base_periods = sorted((Period(a.start_time, a.start_time + a.duration) for a in actions),
                          key=attrgetter("start", "end"))
    it = iter(base_periods)
    periods = [next(it)]
    for p in it:
        if p.contiguous(periods[-1]):
            periods[-1] |= p
        else:
            periods.append(p)
    return periods
