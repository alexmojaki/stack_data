import inspect
import token as token_module

from stack_data import FrameInfo, Options, Line, LINE_GAP, markers_from_ranges


class Colors:
    grey = '\x1b[90m'
    red = '\x1b[31m\x1b[1m'
    green = '\x1b[32m\x1b[1m'
    cyan = '\x1b[36m\x1b[1m'
    bold = '\x1b[1m'
    reset = '\x1b[0m'


def print_stack():
    frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))

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
            print('{:4} | {}'.format(line.lineno, line.render_with_markers(markers)))
        else:
            assert line is LINE_GAP
            print('(...)')

    for var in frame_info.variables:
        print(var.name, '=', repr(var.value))


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
    print_stack()
    return lst


foo()
