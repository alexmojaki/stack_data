import itertools
import types
from collections import OrderedDict, Counter, defaultdict


def truncate(seq, max_length, middle):
    if len(seq) > max_length:
        right = (max_length - len(middle)) // 2
        left = max_length - len(middle) - right
        seq = seq[:left] + middle + seq[-right:]
    return seq


def unique_in_order(it):
    return list(OrderedDict.fromkeys(it))


def line_range(node):
    return (
        node.first_token.start[0],
        node.last_token.end[0] + 1,
    )


def highlight_unique(lst):
    counts = Counter(lst)

    for is_common, group in itertools.groupby(lst, key=lambda x: counts[x] > 3):
        if is_common:
            group = list(group)
            highlighted = [False] * len(group)

            def highlight_index(f):
                try:
                    i = f()
                except ValueError:
                    return None
                highlighted[i] = True
                return i

            for item in set(group):
                first = highlight_index(lambda: group.index(item))
                if first is not None:
                    highlight_index(lambda: group.index(item, first + 1))
                highlight_index(lambda: -1 - group[::-1].index(item))
        else:
            highlighted = itertools.repeat(True)

        yield from zip(group, highlighted)


def identity(x):
    return x


def collapse_repeated(lst, *, collapser, mapper=identity, key=identity):
    keyed = list(map(key, lst))
    for is_highlighted, group in itertools.groupby(
            zip(lst, highlight_unique(keyed)),
            key=lambda t: t[1][1],
    ):
        original_group, highlighted_group = zip(*group)
        if is_highlighted:
            yield from map(mapper, original_group)
        else:
            keyed_group, _ = zip(*highlighted_group)
            yield collapser(original_group, keyed_group)


def is_frame(frame_or_tb):
    assert isinstance(frame_or_tb, (types.FrameType, types.TracebackType))
    return isinstance(frame_or_tb, (types.FrameType,))


def iter_stack(frame_or_tb):
    while frame_or_tb:
        yield frame_or_tb
        if is_frame(frame_or_tb):
            frame_or_tb = frame_or_tb.f_back
        else:
            frame_or_tb = frame_or_tb.tb_next


def frame_and_lineno(frame_or_tb):
    if is_frame(frame_or_tb):
        return frame_or_tb, frame_or_tb.f_lineno
    else:
        return frame_or_tb.tb_frame, frame_or_tb.tb_lineno


def group_by_key_func(iterable, key_func):
    """
    Create a dictionary from an iterable such that the keys are the result of evaluating a key function on elements
    of the iterable and the values are lists of elements all of which correspond to the key.

    >>> def si(d): return sorted(d.items())
    >>> si(group_by_key_func("a bb ccc d ee fff".split(), len))
    [(1, ['a', 'd']), (2, ['bb', 'ee']), (3, ['ccc', 'fff'])]
    >>> si(group_by_key_func([-1, 0, 1, 3, 6, 8, 9, 2], lambda x: x % 2))
    [(0, [0, 6, 8, 2]), (1, [-1, 1, 3, 9])]
    """
    result = defaultdict(list)
    for item in iterable:
        result[key_func(item)].append(item)
    return result
