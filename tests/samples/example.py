import inspect

from stack_data import FrameInfo, Options, Line, LINE_GAP, markers_from_ranges


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
    result = print_stack(
             )
    return result


def bar():
    names = {}
    exec("result = foo()", globals(), names)
    return names["result"]


def print_stack():
    result = ""
    options = Options(include_signature=True)
    frame = inspect.currentframe().f_back
    for frame_info in list(FrameInfo.stack_data(frame, options))[-3:]:
        result += render_frame_info(frame_info) + "\n"
    return result


def render_frame_info(frame_info):
    result = "{} at line {}".format(
        frame_info.executing.code_qualname(),
        frame_info.lineno
    )
    result += '\n' + len(result) * '-' + '\n'

    for line in frame_info.lines:
        def convert_variable_range(_):
            return "<var>", "</var>"

        def convert_executing_range(_):
            return "<exec>", "</exec>"

        if isinstance(line, Line):
            markers = (
                markers_from_ranges(line.variable_ranges, convert_variable_range) +
                markers_from_ranges(line.executing_node_ranges, convert_executing_range)
            )
            result += '{:4} {} {}\n'.format(
                line.lineno,
                '>' if line.is_current else '|',
                line.render(markers)
            )
        else:
            assert line is LINE_GAP
            result += '(...)\n'

    for var in sorted(frame_info.variables, key=lambda v: v.name):
        result += " ".join([var.name, '=', repr(var.value), '\n'])
    return result


if __name__ == '__main__':
    print(bar())
