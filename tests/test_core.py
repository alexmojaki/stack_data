import ast
import inspect
import os
import re
import sys
import token
from itertools import islice
from pathlib import Path

import pygments
import pytest
from executing import only
# noinspection PyUnresolvedReferences
from pygments.lexers import Python3Lexer
from stack_data import Options, Line, LINE_GAP, markers_from_ranges, Variable, RangeInLine
from stack_data import Source, FrameInfo
from stack_data.utils import line_range


def test_lines_with_gaps():
    lines = []
    dedented = False

    def gather_lines():
        frame = inspect.currentframe().f_back
        frame_info = FrameInfo(frame, options)
        assert repr(frame_info) == "FrameInfo({})".format(frame)
        lines[:] = [
            line.render(strip_leading_indent=dedented)
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
    assert re.match(r"<Line \d+ ", repr(line))
    assert (
            " (current=True) "
            "'    line = only(FrameInfo(inspect.currentframe(), options).lines)'"
            " of "
            in repr(line)
    )
    assert repr(line).endswith("test_core.py>")
    assert repr(LINE_GAP) == "LINE_GAP"

    assert '*'.join(t.string for t in line.tokens) == \
           'line*=*only*(*FrameInfo*(*inspect*.*currentframe*(*)*,*options*)*.*lines*)*\n'

    def convert_token_range(r):
        if r.data.type == token.NAME:
            return '[[', ']]'

    markers = markers_from_ranges(line.token_ranges, convert_token_range)
    assert line.render(markers) == \
           '[[line]] = [[only]]([[FrameInfo]]([[inspect]].[[currentframe]](), [[options]]).[[lines]])'
    assert line.render(markers, strip_leading_indent=False) == \
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
    assert line.render(markers) == \
           '[[line of type Line]] = only(FrameInfo(inspect.currentframe(), [[options of type Options]]).lines)'


def test_invalid_converter():
    def converter(_):
        return 1, 2

    ranges = [RangeInLine(0, 1, None)]
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        markers_from_ranges(ranges, converter)


def test_variables():
    options = Options(before=1, after=0)
    assert repr(options) == 'Options(after=0, before=1, include_signature=False, ' \
                            'max_lines_per_piece=6, pygments_formatter=None)'

    def foo(arg):
        y = 123986
        str(y)
        x = {982347298304}
        str(x)
        return (
            FrameInfo(inspect.currentframe(), options),
            arg,
            arg,
        )[0]

    frame_info = foo('this is arg')

    assert sum(line.is_current for line in frame_info.lines) == 1

    body = frame_info.scope.body

    tup = body[-1].value.value.elts
    call = tup[0]
    assert frame_info.executing.node == call
    assert frame_info.code == foo.__code__
    assert frame_info.filename.endswith(frame_info.code.co_filename)
    assert frame_info.filename.endswith("test_core.py")
    assert os.path.isabs(frame_info.filename)
    expected_variables = [
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
            value={982347298304},
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
    expected_variables = [tuple(v) for v in expected_variables]
    variables = [tuple(v) for v in sorted(frame_info.variables)]
    assert expected_variables == variables

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
            for i in piece
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


def check_skipping_frames(collapse: bool):
    def factorial(n):
        if n <= 1:
            return 1 / 0  # exception lineno
        return n * foo(n - 1)  # factorial lineno

    def foo(n):
        return factorial(n)  # foo lineno

    try:
        factorial(20)  # check_skipping_frames lineno
    except Exception as e:
        # tb = sys.exc_info()[2]
        tb = e.__traceback__
        result = []
        for x in FrameInfo.stack_data(tb, collapse_repeated_frames=collapse):
            if isinstance(x, FrameInfo):
                result.append((x.code, x.lineno))
            else:
                result.append(repr(x))
        source = Source.for_filename(__file__)
        linenos = {}
        for lineno, line in enumerate(source.lines):
            match = re.search(r" # (\w+) lineno", line)
            if match:
                linenos[match.group(1)] = lineno + 1

        def simple_frame(func):
            return func.__code__, linenos[func.__name__]

        if collapse:
            middle = [
                simple_frame(factorial),
                simple_frame(foo),
                simple_frame(factorial),
                simple_frame(foo),
                ("<RepeatedFrames "
                 "check_skipping_frames.<locals>.factorial at line {factorial} (16 times), "
                 "check_skipping_frames.<locals>.foo at line {foo} (16 times)>"
                 ).format(**linenos),
                simple_frame(factorial),
                simple_frame(foo),
            ]
        else:
            middle = [
                *([
                      simple_frame(factorial),
                      simple_frame(foo),
                  ] * 19)
            ]

        assert result == [
            simple_frame(check_skipping_frames),
            *middle,
            (factorial.__code__, linenos["exception"]),
        ]


def test_skipping_frames():
    check_skipping_frames(True)
    check_skipping_frames(False)


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
        check_pygments_tokens(source)


def check_pieces(source):
    pieces = source.pieces

    assert pieces == sorted(pieces, key=lambda p: (p.start, p.stop))

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
        contains_stmt = stmt[0] <= piece.start < piece.stop <= stmt[1]
        before_stmt = piece.start < piece.stop <= stmt[0] < stmt[1]
        assert contains_stmt ^ before_stmt
        if contains_stmt:
            try:
                stmt = next(stmts_iter)
            except StopIteration:
                break

    blank_linenos = set(range(1, len(source.lines) + 1)).difference(*pieces)

    for lineno in blank_linenos:
        assert not source.lines[lineno - 1].strip(), lineno


def check_pygments_tokens(source):
    lexer = Python3Lexer(stripnl=False)
    pygments_tokens = [value for ttype, value in pygments.lex(source.text, lexer)]
    assert ''.join(pygments_tokens) == source.text


def test_invalid_source():
    filename = str(Path(__file__).parent / "not_code.txt")
    source = Source.for_filename(filename)
    assert not source.tree
    assert not hasattr(source, "pieces")
    assert not hasattr(source, "tokens_by_lineno")


def test_example():
    from .samples.example import bar
    result = bar()
    print(result)
    assert result == """\
bar at line 26
--------------
  24 | def bar():
  25 |     <var>names</var> = {}
  26 >     <exec>exec("result = foo()", globals(), <var>names</var>)</exec>
  27 |     return <var>names</var>["result"]
names = {} 

<module> at line 1
------------------

foo at line 20
--------------
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
[
            1,
            2,
            3,
            4,
            5,
            6
        ][0] = 1 
lst = [1, 1, 1] 
x = 1 

"""


def test_pygments_example():
    from .samples.pygments_example import bar
    result = bar()
    print(result)
    assert result == """\
Terminal256Formatter native:

   9 | \x1b[38;5;70;01mdef\x1b[39;00m\x1b[38;5;252m \x1b[39m\x1b[38;5;68mbar\x1b[39m\x1b[38;5;252m(\x1b[39m\x1b[38;5;252m)\x1b[39m\x1b[38;5;252m:\x1b[39m
  10 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;252mx\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252m=\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;67m1\x1b[39m
  11 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;31mstr\x1b[39m\x1b[38;5;252m(\x1b[39m\x1b[38;5;252mx\x1b[39m\x1b[38;5;252m)\x1b[39m
  12 > \x1b[38;5;252m    \x1b[39m\x1b[38;5;252mresult\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252m=\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252mprint_stack\x1b[39m\x1b[38;5;252m(\x1b[39m\x1b[38;5;252m)\x1b[39m
  13 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;70;01mreturn\x1b[39;00m\x1b[38;5;252m \x1b[39m\x1b[38;5;252mresult\x1b[39m

====================

Terminal256Formatter <class \'stack_data.core.style_with_executing_node.<locals>.NewStyle\'>:

   9 | \x1b[38;5;70;01mdef\x1b[39;00m\x1b[38;5;252m \x1b[39m\x1b[38;5;68mbar\x1b[39m\x1b[38;5;252m(\x1b[39m\x1b[38;5;252m)\x1b[39m\x1b[38;5;252m:\x1b[39m
  10 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;252mx\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252m=\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;67m1\x1b[39m
  11 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;31mstr\x1b[39m\x1b[38;5;252m(\x1b[39m\x1b[38;5;252mx\x1b[39m\x1b[38;5;252m)\x1b[39m
  12 > \x1b[38;5;252m    \x1b[39m\x1b[38;5;252mresult\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252m=\x1b[39m\x1b[38;5;252m \x1b[39m\x1b[38;5;252;48;5;58mprint_stack\x1b[39;49m\x1b[38;5;252;48;5;58m(\x1b[39;49m\x1b[38;5;252;48;5;58m)\x1b[39;49m
  13 | \x1b[38;5;252m    \x1b[39m\x1b[38;5;70;01mreturn\x1b[39;00m\x1b[38;5;252m \x1b[39m\x1b[38;5;252mresult\x1b[39m

====================

TerminalFormatter native:

   9 | \x1b[34mdef\x1b[39;49;00m \x1b[32mbar\x1b[39;49;00m():
  10 |     x = \x1b[34m1\x1b[39;49;00m
  11 |     \x1b[36mstr\x1b[39;49;00m(x)
  12 >     result = print_stack()
  13 |     \x1b[34mreturn\x1b[39;49;00m result

====================

TerminalFormatter <class \'stack_data.core.style_with_executing_node.<locals>.NewStyle\'>:

   9 | \x1b[34mdef\x1b[39;49;00m \x1b[32mbar\x1b[39;49;00m():
  10 |     x = \x1b[34m1\x1b[39;49;00m
  11 |     \x1b[36mstr\x1b[39;49;00m(x)
  12 >     result = print_stack()
  13 |     \x1b[34mreturn\x1b[39;49;00m result

====================

TerminalTrueColorFormatter native:

   9 | \x1b[38;2;106;184;37;01mdef\x1b[39;00m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;68;127;207mbar\x1b[39m\x1b[38;2;208;208;208m(\x1b[39m\x1b[38;2;208;208;208m)\x1b[39m\x1b[38;2;208;208;208m:\x1b[39m
  10 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;208;208;208mx\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208m=\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;54;119;169m1\x1b[39m
  11 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;36;144;157mstr\x1b[39m\x1b[38;2;208;208;208m(\x1b[39m\x1b[38;2;208;208;208mx\x1b[39m\x1b[38;2;208;208;208m)\x1b[39m
  12 > \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;208;208;208mresult\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208m=\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208mprint_stack\x1b[39m\x1b[38;2;208;208;208m(\x1b[39m\x1b[38;2;208;208;208m)\x1b[39m
  13 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;106;184;37;01mreturn\x1b[39;00m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208mresult\x1b[39m

====================

TerminalTrueColorFormatter <class \'stack_data.core.style_with_executing_node.<locals>.NewStyle\'>:

   9 | \x1b[38;2;106;184;37;01mdef\x1b[39;00m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;68;127;207mbar\x1b[39m\x1b[38;2;208;208;208m(\x1b[39m\x1b[38;2;208;208;208m)\x1b[39m\x1b[38;2;208;208;208m:\x1b[39m
  10 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;208;208;208mx\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208m=\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;54;119;169m1\x1b[39m
  11 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;36;144;157mstr\x1b[39m\x1b[38;2;208;208;208m(\x1b[39m\x1b[38;2;208;208;208mx\x1b[39m\x1b[38;2;208;208;208m)\x1b[39m
  12 > \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;208;208;208mresult\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208m=\x1b[39m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208;48;2;68;68;0mprint_stack\x1b[39;49m\x1b[38;2;208;208;208;48;2;68;68;0m(\x1b[39;49m\x1b[38;2;208;208;208;48;2;68;68;0m)\x1b[39;49m
  13 | \x1b[38;2;208;208;208m    \x1b[39m\x1b[38;2;106;184;37;01mreturn\x1b[39;00m\x1b[38;2;208;208;208m \x1b[39m\x1b[38;2;208;208;208mresult\x1b[39m

====================

HtmlFormatter native:

   9 | <span class="k">def</span> <span class="nf">bar</span><span class="p">():</span>
  10 |     <span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>
  11 |     <span class="nb">str</span><span class="p">(</span><span class="n">x</span><span class="p">)</span>
  12 >     <span class="n">result</span> <span class="o">=</span> <span class="n">print_stack</span><span class="p">()</span>
  13 |     <span class="k">return</span> <span class="n">result</span>

====================

HtmlFormatter <class \'stack_data.core.style_with_executing_node.<locals>.NewStyle\'>:

   9 | <span class="k">def</span> <span class="nf">bar</span><span class="p">():</span>
  10 |     <span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>
  11 |     <span class="nb">str</span><span class="p">(</span><span class="n">x</span><span class="p">)</span>
  12 >     <span class="n">result</span> <span class="o">=</span> <span class="n n-ExecutingNode">print_stack</span><span class="p p-ExecutingNode">()</span>
  13 |     <span class="k">return</span> <span class="n">result</span>

====================

"""
