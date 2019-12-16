import ast
import inspect
import os
import re
import sys
import token
from itertools import islice
from pathlib import Path

from executing import only

from stack_data import Options, Line, LINE_GAP, markers_from_ranges, Variable
from stack_data import Source, FrameInfo
from stack_data.utils import line_range


def test_lines_with_gaps():
    lines = []
    dedented = False

    def gather_lines():
        frame_info = FrameInfo(inspect.currentframe().f_back, options)
        lines[:] = [
            (line.dedented_text if dedented else line.text)
            if isinstance(line, Line) else line
            for line in frame_info.lines
        ]

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
        lst += [99]
        return lst

    options = Options(include_signature=True)
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
        '        lst += [99]',
    ]

    options = Options()
    foo()
    assert lines == [
        '        lst = [1]',
        '        lst.insert(0, x)',
        '        lst.append(',
        '            [',
        '                1,',
        LINE_GAP,
        '                6',
        '            ][0])',
        '        gather_lines()',
        '        lst += [99]',
    ]

    def foo():
        gather_lines()

    foo()
    assert lines == [
        '    def foo():',
        '        gather_lines()',
    ]

    def foo():
        lst = [1]
        lst.insert(0, 2)
        lst.append(
            [
                1,
                2,
                3,
                gather_lines(),
                5,
                6
            ][0])
        lst += [99]
        return lst

    foo()
    assert lines == [
        '    def foo():',
        '        lst = [1]',
        '        lst.insert(0, 2)',
        '        lst.append(',
        '            [',
        '                1,',
        '                2,',
        '                3,',
        '                gather_lines(),',
        '                5,',
        '                6',
        '            ][0])',
        '        lst += [99]'
    ]

    dedented = True

    foo()
    assert lines == [
        'def foo():',
        '    lst = [1]',
        '    lst.insert(0, 2)',
        '    lst.append(',
        '        [',
        '            1,',
        '            2,',
        '            3,',
        '            gather_lines(),',
        '            5,',
        '            6',
        '        ][0])',
        '    lst += [99]'
    ]


def test_markers():
    options = Options(before=0, after=0)
    line = only(FrameInfo(inspect.currentframe(), options).lines)
    assert line.is_current
    assert '*'.join(t.string for t in line.tokens) == \
           'line*=*only*(*FrameInfo*(*inspect*.*currentframe*(*)*,*options*)*.*lines*)*\n'

    def convert_token_range(r):
        if r.data.type == token.NAME:
            return '[[', ']]'

    markers = markers_from_ranges(line.token_ranges, convert_token_range)
    assert line.render_with_markers(markers) == \
           '[[line]] = [[only]]([[FrameInfo]]([[inspect]].[[currentframe]](), [[options]]).[[lines]])'
    assert line.render_with_markers(markers, strip_leading_indent=False) == \
           '    [[line]] = [[only]]([[FrameInfo]]([[inspect]].[[currentframe]](), [[options]]).[[lines]])'

    def convert_variable_range(r):
        return '[[', ' of type {}]]'.format(r.data[0].value.__class__.__name__)

    markers = markers_from_ranges(line.variable_ranges, convert_variable_range)
    assert sorted(markers) == [
        (4, True, '[['),
        (8, False, ' of type Line]]'),
        (50, True, '[['),
        (57, False, ' of type Options]]'),
    ]
    assert line.render_with_markers(markers) == \
           '[[line of type Line]] = only(FrameInfo(inspect.currentframe(), [[options of type Options]]).lines)'


def test_variables():
    options = Options(before=1, after=0)

    def foo(arg):
        y = 123986
        str(y)
        x = 982347298304
        str(x)
        return (
            FrameInfo(inspect.currentframe(), options),
            arg,
            arg,
        )[0]

    frame_info = foo('this is arg')

    assert sum(line.is_current for line in frame_info.lines) == 1

    body = frame_info.scope.body
    variables = sorted(frame_info.variables)

    tup = body[-1].value.value.elts
    call = tup[0]
    assert frame_info.executing.node == call
    assert frame_info.code == foo.__code__
    assert frame_info.filename.endswith(frame_info.code.co_filename)
    assert frame_info.filename.endswith("test_core.py")
    assert os.path.isabs(frame_info.filename)
    assert variables == [
        Variable(
            name='arg',
            nodes=(
                tup[1],
                tup[2],
                frame_info.scope.args.args[0],
            ),
            value='this is arg',
        ),
        Variable(
            name='options',
            nodes=(call.args[1],),
            value=options,
        ),
        Variable(
            name='x',
            nodes=(
                body[2].targets[0],
                body[3].value.args[0],
            ),
            value=982347298304,
        ),
        Variable(
            name='y',
            nodes=(
                body[0].targets[0],
                body[1].value.args[0],
            ),
            value=123986,
        ),
    ]

    assert (
            sorted(frame_info.variables_in_executing_piece) ==
            variables[:2]
    )

    assert (
            sorted(frame_info.variables_in_lines) ==
            variables[:3]
    )


def test_pieces():
    filename = Path(__file__).parent / "samples/pieces.py"
    source = Source.for_filename(str(filename))
    pieces = [
        [
            source.lines[i - 1]
            for i in piece.range
        ]
        for piece in source.pieces
    ]
    assert pieces == [
        ['import math'],
        ['def foo(x=1, y=2):'],
        ['    """',
         '    a docstring',
         '    """'],
        ['    z = 0'],
        ['    for i in range(5):'],
        ['        z += i * x * math.sin(y)'],
        ['        # comment1',
         '        # comment2'],
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


def sys_modules_sources():
    for module in sys.modules.values():
        try:
            filename = inspect.getsourcefile(module)
        except TypeError:
            continue

        if not filename:
            continue

        filename = os.path.abspath(filename)
        print(filename)
        source = Source.for_filename(filename)
        if not source.tree:
            continue

        yield source


def test_sys_modules():
    modules = sys_modules_sources()
    if not os.environ.get('STACK_DATA_SLOW_TESTS'):
        modules = islice(modules, 0, 3)

    for source in modules:
        check_pieces(source)


def check_pieces(source):
    pieces = source.pieces

    assert pieces == sorted(pieces)

    stmts = sorted({
        line_range(node)
        for node in ast.walk(source.tree)
        if isinstance(node, ast.stmt)
        if not isinstance(getattr(node, 'body', None), list)
    })
    if not stmts:
        return

    stmts_iter = iter(stmts)
    stmt = next(stmts_iter)
    for piece in pieces:
        contains_stmt = stmt[0] <= piece[0] < piece[1] <= stmt[1]
        before_stmt = piece[0] < piece[1] <= stmt[0] < stmt[1]
        assert contains_stmt ^ before_stmt
        if contains_stmt:
            try:
                stmt = next(stmts_iter)
            except StopIteration:
                break

    blank_linenos = set(range(1, len(source.lines) + 1)).difference(
        *(piece.range for piece in pieces))

    for lineno in blank_linenos:
        assert not source.lines[lineno - 1].strip(), lineno


def test_example():
    from .samples.example import foo
    assert foo() == """\
   6 | def foo():
(...)
   8 |     <var>lst</var> = [1]
  10 |     <var>lst</var>.insert(0, <var>x</var>)
  11 |     <var>lst</var>.append(
  12 |         <var>[</var>
  13 | <var>            1,</var>
(...)
  18 | <var>            6</var>
  19 | <var>        ][0]</var>)
  20 >     result = <exec>print_stack()</exec>
  21 |     return result
x = 1 
lst = [1, 1, 1] 
[
            1,
            2,
            3,
            4,
            5,
            6
        ][0] = 1 
"""
