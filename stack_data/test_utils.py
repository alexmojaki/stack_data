import inspect
import random
import token as token_module
from collections import Counter

from stack_data.utils import highlight_unique, collapse_repeated
from . import FrameInfo, Options, Line, LINE_GAP, markers_from_ranges


class Colors:
    grey = '\x1b[90m'
    red = '\x1b[31m\x1b[1m'
    green = '\x1b[32m\x1b[1m'
    cyan = '\x1b[36m\x1b[1m'
    bold = '\x1b[1m'
    reset = '\x1b[0m'


def formatted_lines(frame_info):
    def convert_variable_range(_):
        return Colors.cyan, Colors.reset

    def convert_token_range(r):
        if r.data.type == token_module.OP:
            return Colors.green, Colors.reset

    for line in frame_info.lines:
        if isinstance(line, Line):
            markers = (
                    markers_from_ranges(line.variable_ranges, convert_variable_range) +
                    markers_from_ranges(line.token_ranges, convert_token_range)
            )
            yield '{:4} | {}'.format(line.lineno, line.render_with_markers(markers))
        else:
            assert line is LINE_GAP
            yield '(...)'

    for var in frame_info.variables:
        print(var.name, '=', repr(var.value))


def print_lines():
    frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))
    for line in formatted_lines(frame_info):
        print(line)


def print_pieces(source):
    for start, end in source.pieces:
        for i in range(start, end):
            print(i, source.lines[i - 1])
        print('-----')


def test_highlight(lst, expected, summary):
    assert ''.join(collapse_repeated(lst, collapser=lambda group, _: '.' * len(group))) == expected
    assert list(collapse_repeated(lst, collapser=lambda group, _: Counter(group))) == summary


def main():
    test_highlight(
        '0123456789BBCBCBBCBACBACBBBBCABABBABCCCCAACBABBCBBBAAACBBBCABACACCAACABBCBCCBBABBAAAAACBCCCAAAABBCBB',
        '0123456789BBC.C....A..A.......................................................................A..C.B',
        ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'B', 'B', 'C', Counter({'B': 1}), 'C',
         Counter({'B': 3, 'C': 1}), 'A', Counter({'C': 1, 'B': 1}), 'A', Counter({'B': 26, 'A': 24, 'C': 21}), 'A',
         Counter({'B': 2}), 'C', Counter({'B': 1}), 'B']
    )

    test_highlight(
        'BAAABABC3BCBBCBBCBAACBBBABBCCACCACB7BBBCA8ABB9B0AACABBCACCCCAAAAABBBBBCA2CBABCCCBB4ACCAACBBA1BBCB6A5',
        'BAA.BABC3BCB.C....AA............ACB7BBBCA8ABB9B0AAC.BBC..............BCA2CBABC.C.B4ACCA.CBBA1BBCB6A5',
        ['B', 'A', 'A', Counter({'A': 1}), 'B', 'A', 'B', 'C', '3', 'B', 'C', 'B', Counter({'B': 1}), 'C',
         Counter({'B': 3, 'C': 1}), 'A', 'A', Counter({'C': 5, 'B': 5, 'A': 2}),
         'A', 'C', 'B', '7', 'B', 'B', 'B', 'C', 'A', '8', 'A', 'B', 'B', '9', 'B', '0', 'A', 'A', 'C',
         Counter({'A': 1}), 'B', 'B', 'C', Counter({'A': 6, 'C': 4, 'B': 4}),
         'B', 'C', 'A', '2', 'C', 'B', 'A', 'B', 'C', Counter({'C': 1}), 'C',
         Counter({'B': 1}), 'B', '4', 'A', 'C', 'C', 'A', Counter({'A': 1}),
         'C', 'B', 'B', 'A', '1', 'B', 'B', 'C', 'B', '6', 'A', '5'],
    )

    for _ in range(100):
        lst = list('0123456789' * 3) + [random.choice('ABCD') for _ in range(1000)]
        random.shuffle(lst)
        result = list(highlight_unique(lst))
        assert len(lst) == len(result)
        vals, highlighted = zip(*result)
        assert set(vals) == set('0123456789ABCD')
        assert set(highlighted) == {True, False}


main()
