import os
import re
import sys
from contextlib import contextmanager

import pytest

from stack_data import Formatter, FrameInfo, Options, BlankLines
from tests.utils import compare_to_file


class BaseFormatter(Formatter):
    def format_frame_header(self, frame_info: FrameInfo) -> str:
        # noinspection PyPropertyAccess
        frame_info.filename = os.path.basename(frame_info.filename)
        return super().format_frame_header(frame_info)

    def format_variable_value(self, value) -> str:
        result = super().format_variable_value(value)
        result = re.sub(r'0x\w+', '0xABC', result)
        return result


class MyFormatter(BaseFormatter):
    def format_frame(self, frame):
        if not frame.filename.endswith(("formatter_example.py", "<string>", "cython_example.pyx")):
            return
        yield from super().format_frame(frame)


def test_example(capsys):
    from .samples.formatter_example import bar, print_stack1, format_stack1, format_frame, f_string, blank_lines

    @contextmanager
    def check_example(name):
        yield
        stderr = capsys.readouterr().err
        compare_to_file(stderr, name)

    with check_example("variables"):
        try:
            bar()
        except Exception:
            MyFormatter(show_variables=True).print_exception()

    with check_example("pygmented"):
        try:
            bar()
        except Exception:
            MyFormatter(pygmented=True).print_exception()

    with check_example("plain"):
        MyFormatter().set_hook()
        try:
            bar()
        except Exception:
            sys.excepthook(*sys.exc_info())

    with check_example("print_stack"):
        print_stack1(MyFormatter())

    with check_example("format_stack"):
        formatter = MyFormatter()
        formatted = format_stack1(formatter)
        formatter.print_lines(formatted)

    with check_example("format_frame"):
        formatter = BaseFormatter()
        formatted = format_frame(formatter)
        formatter.print_lines(formatted)

    with check_example(f"f_string_{'old' if sys.version_info[:2] < (3, 8) else 'new'}"):
        try:
            f_string()
        except Exception:
            MyFormatter().print_exception()

    from .samples.formatter_example import block_right, block_left

    with check_example(f"block_right_{'old' if sys.version_info[:2] < (3, 8) else 'new'}"):
        try:
            block_right()
        except Exception:
            MyFormatter().print_exception()

    with check_example(f"block_left_{'old' if sys.version_info[:2] < (3, 8) else 'new'}"):
        try:
            block_left()
        except Exception:
            MyFormatter().print_exception()

    from .samples import cython_example

    with check_example("cython_example"):
        try:
            cython_example.foo()
        except Exception:
            MyFormatter().print_exception()

    with check_example("blank_visible"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(options=Options(blank_lines=BlankLines.VISIBLE)).print_exception()

    with check_example("blank_single"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(options=Options(blank_lines=BlankLines.SINGLE)).print_exception()

    with check_example("blank_invisible_no_linenos"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(show_linenos=False, current_line_indicator="").print_exception()

    with check_example("blank_visible_no_linenos"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(show_linenos=False,
                        current_line_indicator="",
                        options=Options(blank_lines=BlankLines.VISIBLE)).print_exception()

    with check_example("linenos_no_current_line_indicator"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(current_line_indicator="").print_exception()

    with check_example("blank_visible_with_linenos_no_current_line_indicator"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(current_line_indicator="",
                        options=Options(blank_lines=BlankLines.VISIBLE)).print_exception()

    with check_example("single_option_linenos_no_current_line_indicator"):
        try:
            blank_lines()
        except Exception:
            MyFormatter(current_line_indicator="",
                        options=Options(blank_lines=BlankLines.SINGLE)).print_exception()

def test_invalid_single_option():
    with pytest.raises(ValueError):
        MyFormatter(show_linenos=False, options=Options(blank_lines=BlankLines.SINGLE))

