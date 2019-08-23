from stack_data import Source

filename = '/Users/alexhall/Desktop/python/stack_data/stack_data.py'
source = Source.for_filename(filename)
for start, end in source.pieces:
    for i in range(start, end):
        print(i, source.lines[i - 1])
    print('-----')
