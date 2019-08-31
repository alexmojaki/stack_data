from pathlib import Path

from stack_data import Source
from stack_data.test_utils import print_pieces, print_lines

filename = str(Path(__file__).parent / "stack_data/core.py")
source = Source.for_filename(filename)
print_pieces(source)


def bar():
    def foo():
        x = 1
        lst = [
            1,
            2,
            3,
            4,
            5,
            6
        ]
        lst.insert(0, x)

        lst.append(x)
        print_lines()
        return lst

    foo()


bar()
