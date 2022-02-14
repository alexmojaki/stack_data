import os
import re
import sys
from contextlib import contextmanager

from stack_data import Formatter, FrameInfo
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
    from .samples.formatter_example import bar, print_stack1, format_stack1, format_frame, f_string

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

    from .samples import cython_example

    with check_example("cython_example"):
        try:
            cython_example.foo()
        except Exception:
            MyFormatter().print_exception()
