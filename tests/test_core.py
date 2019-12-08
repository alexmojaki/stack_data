import inspect
import re
from pathlib import Path

from stack_data import Options, Line, LINE_GAP
from stack_data import Source, FrameInfo


def test_lines_with_gaps():
    lines = []

    def gather_lines():
        frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))
        for line in frame_info.lines:
            if isinstance(line, Line):
                line = line.text
            lines.append(line)

    def foo():
        x = 1
        lst = [1]

        lst.insert(0, x)
        lst.append(
            [
                1,
                2,
                3,
                4,
                5,
                6
            ][0])
        gather_lines()
        return lst

    foo()
    assert lines == [
        '    def foo():',
        LINE_GAP,
        '        lst = [1]',
        '        lst.insert(0, x)',
        '        lst.append(',
        '            [',
        '                1,',
        LINE_GAP,
        '                6',
        '            ][0])',
        '        gather_lines()',
        '        return lst',
    ]


def test_pieces():
    filename = Path(__file__).parent / "samples/pieces.py"
    source = Source.for_filename(str(filename))
    pieces = [
        [
            source.lines[i - 1]
            for i in range(start, end)
        ]
        for start, end in source.pieces
    ]
    assert pieces == [
        ['import math'],
        ['def foo(x=1, y=2):'],
        ['    z = 0'],
        ['    for i in range(5):'],
        ['        z += i * x * math.sin(y)'],
        ['        z += math.copysign(',
         '            -1,',
         '            2,',
         '        )'],
        ['    for i in range(',
         '            0,',
         '            6',
         '    ):'],
        ['        try:'],
        ['            str(i)'],
        ['        except:'],
        ['            pass'],
        ['        try:'],
        ['            int(i)'],
        ['        except (ValueError,',
         '                TypeError):'],
        ['            pass'],
        ['        finally:'],
        ['            str("""',
         '            foo',
         '            """)'],
        ['def foo2(',
         '        x=1,',
         '        y=2,', '):'],
        ['    while 9:'],
        ['        while (',
         '                9 + 9',
         '        ):'],
        ['            if 1:'],
        ['                pass'],
        ['            elif 2:'],
        ['                pass'],
        ['            elif (',
         '                    3 + 3',
         '            ):'],
        ['                pass'],
        ['            else:'],
        ['                pass'],
        ['class Foo(object):'],
        ['    pass'],
    ]


def test_skipping_frames():
    def factorial(n):
        if n <= 1:
            return 1 / 0  # exception lineno
        return n * foo(n - 1)  # factorial lineno

    def foo(n):
        return factorial(n)  # foo lineno

    try:
        factorial(20)  # test_skipping_frames lineno
    except Exception as e:
        # tb = sys.exc_info()[2]
        tb = e.__traceback__
        result = []
        for x in FrameInfo.stack_data(tb):
            if isinstance(x, FrameInfo):
                result.append((x.code, x.lineno))
            else:
                result.append(x.description)
        source = Source.for_filename(__file__)
        linenos = {}
        for lineno, line in enumerate(source.lines):
            match = re.search(r" # (\w+) lineno", line)
            if match:
                linenos[match.group(1)] = lineno + 1

        def simple_frame(func):
            return func.__code__, linenos[func.__name__]

        assert result == [
            simple_frame(test_skipping_frames),
            simple_frame(factorial),
            simple_frame(foo),
            simple_frame(factorial),
            simple_frame(foo),
            ("test_skipping_frames.<locals>.factorial at line {factorial} (16 times), "
             "test_skipping_frames.<locals>.foo at line {foo} (16 times)"
             ).format(**linenos),
            simple_frame(factorial),
            simple_frame(foo),
            (factorial.__code__, linenos["exception"]),
        ]
