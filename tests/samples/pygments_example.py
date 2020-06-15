import inspect

from pygments.formatters.html import HtmlFormatter
from pygments.formatters.terminal import TerminalFormatter
from pygments.formatters.terminal256 import Terminal256Formatter, TerminalTrueColorFormatter
from stack_data import FrameInfo, Options, style_with_executing_node


def bar():
    x = 1
    str(x)
    return print_stack()


def print_stack():
    result = ""
    for formatter_cls in [
        Terminal256Formatter,
        TerminalFormatter,
        TerminalTrueColorFormatter,
        HtmlFormatter,
    ]:
        for style in ["native", style_with_executing_node("native", "bg:#444400")]:
            result += "{formatter_cls.__name__} {style}:\n\n".format(**locals())
            formatter = formatter_cls(style=style)
            options = Options(pygments_formatter=formatter)
            frame = inspect.currentframe().f_back
            frame_info = FrameInfo(frame, options)
            for line in frame_info.lines:
                result += '{:4} {} {}\n'.format(
                    line.lineno,
                    '>' if line.is_current else '|',
                    line.render(pygmented=True)
                )
            result += "\n====================\n\n"
    return result


if __name__ == '__main__':
    print(bar())
    print(repr(bar()).replace("\\n", "\n")[1:-1])
