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

    for i in range(
            0,
            6
    ):
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
            str(f"""
            {str(str)}
            """)
            str(f"""
            foo
            {
                str(
                    str
                )
            }
            bar
            {str(str)}
            baz
            {
                str(
                    str
                )
            }
            spam
            """)


def foo2(
        x=1,
        y=2,
):
    while 9:
        while (
                9 + 9
        ):
            if 1:
                pass
            elif 2:
                pass
            elif (
                    3 + 3
            ):
                pass
            else:
                pass


class Foo(object):
    @property
    def foo(self):
        return 3
