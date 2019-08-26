from stack_data.stack_data import Source, print_lines

filename = '/Users/alexhall/Desktop/python/stack_data/stack_data/stack_data.py'
source = Source.for_filename(filename)
for start, end in source.pieces:
    for i in range(start, end):
        print(i, source.lines[i - 1])
    print('-----')


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
