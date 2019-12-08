import inspect
import re

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
        LINE_GAP,
        '                5,',
        '                6',
        '            ][0])',
        '        gather_lines()',
        '        return lst',
    ]


def test_skipping_frames():
    def factorial(n):
        if n <= 1:
            return 1 / 0  # oops, a bug!
        return n * foo(n - 1)  # factorial lineno

    def foo(n):
        return factorial(n)  # foo lineno

    try:
        factorial(20)  # test_skipping_frames lineno
    except Exception as e:
        # tb = sys.exc_info()[2]
        tb = e.__traceback__
        result = ""
        for x in FrameInfo.stack_data(tb):
            if isinstance(x, FrameInfo):
                result += '{}:{}'.format(x.executing.code_qualname(), x.lineno) + "\n"
            else:
                result += '[... {}]'.format(x.description) + "\n"
        source = Source.for_filename(__file__)
        linenos = {}
        for lineno, line in enumerate(source.lines):
            match = re.search(r" # (\w+) lineno", line)
            if match:
                linenos[match.group(1)] = lineno + 1
        assert result == """\
test_skipping_frames:{test_skipping_frames}
test_skipping_frames.<locals>.factorial:{factorial}
test_skipping_frames.<locals>.foo:{foo}
test_skipping_frames.<locals>.factorial:{factorial}
test_skipping_frames.<locals>.foo:{foo}
[... test_skipping_frames.<locals>.factorial:{factorial} x16, test_skipping_frames.<locals>.foo:{foo} x16]
test_skipping_frames.<locals>.factorial:{factorial}
test_skipping_frames.<locals>.foo:{foo}
test_skipping_frames.<locals>.factorial:{exception}
""".format(exception=linenos["factorial"] - 1, **linenos)
