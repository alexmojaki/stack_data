import random
from collections import Counter

from stack_data import FrameInfo
from stack_data.utils import highlight_unique, collapse_repeated, cached_property


def assert_collapsed(lst, expected, summary):
    assert ''.join(collapse_repeated(lst, collapser=lambda group, _: '.' * len(group))) == expected
    assert list(collapse_repeated(lst, collapser=lambda group, _: Counter(group))) == summary


def test_collapse_repeated():
    assert_collapsed(
        '0123456789BBCBCBBCBACBACBBBBCABABBABCCCCAACBABBCBBBAAACBBBCABACACCAACABBCBCCBBABBAAAAACBCCCAAAABBCBB',
        '0123456789BBC.C....A..A.......................................................................A..C.B',
        ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'B', 'B', 'C', Counter({'B': 1}), 'C',
         Counter({'B': 3, 'C': 1}), 'A', Counter({'C': 1, 'B': 1}), 'A', Counter({'B': 26, 'A': 24, 'C': 21}), 'A',
         Counter({'B': 2}), 'C', Counter({'B': 1}), 'B']
    )

    assert_collapsed(
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


def test_highlight_unique_properties():
    for _ in range(20):
        lst = list('0123456789' * 3) + [random.choice('ABCD') for _ in range(1000)]
        random.shuffle(lst)
        result = list(highlight_unique(lst))
        assert len(lst) == len(result)
        vals, highlighted = zip(*result)
        assert set(vals) == set('0123456789ABCD')
        assert set(highlighted) == {True, False}


def test_cached_property_from_class():
    assert FrameInfo.filename is FrameInfo.__dict__["filename"]
    assert isinstance(FrameInfo.filename, cached_property)
