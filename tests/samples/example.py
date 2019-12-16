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
    result = print_stack()
    return result


def print_stack():
    result = ""
    frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))

    for line in frame_info.lines:
        def convert_variable_range(_):
            return "<var>", "</var>"

        if isinstance(line, Line):
            markers = markers_from_ranges(line.variable_ranges, convert_variable_range)
            result += '{:4} | {}\n'.format(line.lineno, line.render_with_markers(markers))
        else:
            assert line is LINE_GAP
            result += '(...)\n'

    for var in frame_info.variables:
        result += " ".join([var.name, '=', repr(var.value), '\n'])
    print(result)
    return result
