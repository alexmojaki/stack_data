import math


def foo(x=1, y=2):
    """
    a docstring
    """
    z = 0
    for i in range(5):
        z += i * x * math.sin(y)
        # comment1
        # comment2
        z += math.copysign(
            -1,
            2,
        )

    for i in range(6):
        try:
            str(i)
        except:
            pass

        try:
            int(i)
        except (ValueError,
                TypeError):
            pass
        finally:
            str("""
            foo
            """)


def foo2(
        x=1,
        y=2,
):
    pass


class Foo(object):
    pass
