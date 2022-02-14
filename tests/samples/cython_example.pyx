def foo():
    bar()

cdef bar():
    raise ValueError("bar!")
