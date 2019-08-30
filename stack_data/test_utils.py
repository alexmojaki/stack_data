import inspect
import token as token_module

from stack_data.stack_data import FrameInfo, Options, Line, LINE_GAP, markers_from_ranges


class Colors:
    grey = '\x1b[90m'
    red = '\x1b[31m\x1b[1m'
    green = '\x1b[32m\x1b[1m'
    cyan = '\x1b[36m\x1b[1m'
    bold = '\x1b[1m'
    reset = '\x1b[0m'


def formatted_lines(frame_info):
    def convert_variable_range(_start, _end, _var):
        return Colors.cyan, Colors.reset

    def convert_token_range(_start, _end, token):
        if token.type == token_module.OP:
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


def print_lines():
    frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))
    for line in formatted_lines(frame_info):
        print(line)


def print_pieces(source):
    for start, end in source.pieces:
        for i in range(start, end):
            print(i, source.lines[i - 1])
        print('-----')
