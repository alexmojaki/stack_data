import inspect
import token as token_module

from stack_data.stack_data import FrameInfo, Options, Line, LINE_GAP


class Colors:
    grey = '\x1b[90m'
    red = '\x1b[31m\x1b[1m'
    green = '\x1b[32m\x1b[1m'
    cyan = '\x1b[36m\x1b[1m'
    bold = '\x1b[1m'
    reset = '\x1b[0m'


def formatted_lines(frame_info):
    for line in frame_info.lines:
        if isinstance(line, Line):
            markers = []

            for start, end, _ in line.variable_ranges:
                markers.append((start, True, Colors.cyan))
                markers.append((end, False, Colors.reset))

            for start, end, token in line.token_ranges:
                if token.type == token_module.OP:
                    markers.append((start, True, Colors.green))
                    markers.append((end, False, Colors.reset))

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
