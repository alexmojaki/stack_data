import inspect

from stack_data import Formatter


def foo(n=5):
    if n > 0:
        return foo(n - 1)
    x = 1
    lst = (
            [
                x,
            ]
            + []
            + []
            + []
            + []
            + []
    )
    try:
        return int(str(lst))
    except:
        try:
            return 1 / 0
        except Exception as e:
            raise TypeError from e


def bar():
    exec("foo()")


def print_stack1(formatter):
    print_stack2(formatter)


def print_stack2(formatter):
    formatter.print_stack()


def format_stack1(formatter):
    return format_stack2(formatter)


def format_stack2(formatter):
    return list(formatter.format_stack())


def format_frame(formatter):
    frame = inspect.currentframe()
    return formatter.format_frame(frame)


def f_string():
    f"""{str
    (
        1 /
          0 + 4
        + 5
    )
    }"""


def block_right():
    nb = len(letter
             for letter
               in
             "words")


def block_left():
    nb_characters = len(letter
             for letter

               in
             "words")


def blank_lines():
    a = [1, 2, 3]

    length = len(a)


    return a[length]



if __name__ == '__main__':
    try:
        bar()
    except Exception:
        Formatter(show_variables=True).print_exception()
