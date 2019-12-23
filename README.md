# stack_data

This is a library that extracts data from stack frames and tracebacks, particularly to display more useful tracebacks than the default.

You can install it from PyPI:

    pip install stack_data
    
## Basic usage

Here's some code we'd like to inspect:

```python
def foo():
    result = []
    for i in range(5):
        row = []
        result.append(row)
        print_stack()
        for j in range(5):
            row.append(i * j)
    return result
```

Note that `foo` calls a function `print_stack()`. In reality we can imagine that an exception was raised at this line, or a debugger stopped there, but this is easy to play with directly. Here's a basic implementation:

```python
import inspect
import stack_data


def print_stack():
    frame = inspect.currentframe().f_back
    frame_info = stack_data.FrameInfo(frame)
    print(f"{frame_info.code.co_name} at line {frame_info.lineno}")
    print("-----------")
    for line in frame_info.lines:
        print(f"{'-->' if line.is_current else '   '} {line.lineno:4} | {line.render()}")
```

(Beware that this has a major bug - it doesn't account for line gaps, which we'll learn about later)

The output of one call to `print_stack()` looks like:

```python
foo at line 9
-----------
       6 | for i in range(5):
       7 |     row = []
       8 |     result.append(row)
-->    9 |     print_stack()
      10 |     for j in range(5):
```

The code for `print_stack()` is fairly self-explanatory. If you want to learn more details about a particular class or method I suggest looking through some docstrings. `FrameInfo` is a class that accepts either a frame or a traceback object and provides a bunch of nice attributes and properties (which are cached so you don't need to worry about performance). In particular `frame_info.lines` is a list of `Line` objects. `line.render()` returns the source code of that line suitable for display. Without any arguments it simply strips any common leading indentation. Later on we'll see a more powerful use for it.

You can see that `frame_info.lines` includes some lines of surrounding context. By default it includes 3 pieces of context before the main line and 1 piece after. We can configure the amount of context by passing options:

```python
options = stack_data.Options(before=1, after=0)
frame_info = stack_data.FrameInfo(frame, options)
```

Then the output looks like:

```python
foo at line 9
-----------
       8 | result.append(row)
-->    9 | print_stack()
```

Note that these parameters are not the number of *lines* before and after to include, but the number of *pieces*. A piece is a range of one or more lines in a file that should logically be grouped together. A piece contains either a single simple statement or a part of a compound statement (loops, if, try/except, etc) that doesn't contain any other statements. Most pieces are a single line, but a multi-line statement or `if` condition is a single piece. In the example above, all pieces are one line, because nothing is spread across multiple lines. If we change our code to include some multiline bits:


```python
def foo():
    result = []
    for i in range(5):
        row = []
        result.append(
            row
        )
        print_stack()
        for j in range(
                5
        ):
            row.append(i * j)
    return result
```

and then run the original code with the default options, then the output is:

```python
foo at line 11
-----------
       6 | for i in range(5):
       7 |     row = []
       8 |     result.append(
       9 |         row
      10 |     )
-->   11 |     print_stack()
      12 |     for j in range(
      13 |             5
      14 |     ):
```

Now lines 8-10 and lines 12-14 are each a single piece. Note that the output is essentially the same as the original in terms of the amount of code. The division of files into pieces means that the edge of the context is intuitive and doesn't crop out parts of statements or expressions. For example, if context was measured in lines instead of pieces, the last line of the above would be `for j in range(` which is much less useful.

However, if a piece is very long, including all of it could be cumbersome. For this, `Options` has a parameter `max_lines_per_piece`, which is 6 by default. Suppose we have a piece in our code that's longer than that:

```python
        row = [
            1,
            2,
            3,
            4,
            5,
        ]
```

`frame_info.lines` will truncate this piece so that instead of 7 `Line` objects it will produce 5 `Line` objects and one `LINE_GAP` in the middle, making 6 objects in total for the piece. Our code doesn't currently handle gaps, so it will raise an exception. We can modify it like so:

```python
    for line in frame_info.lines:
        if line is stack_data.LINE_GAP:
            print("       (...)")
        else:
            print(f"{'-->' if line.is_current else '   '} {line.lineno:4} | {line.render()}")
```

Now the output looks like:

```python
foo at line 15
-----------
       6 | for i in range(5):
       7 |     row = [
       8 |         1,
       9 |         2,
       (...)
      12 |         5,
      13 |     ]
      14 |     result.append(row)
-->   15 |     print_stack()
      16 |     for j in range(5):
```

Alternatively, you can flip the condition around and check `if isinstance(line, stack_data.Line):`. Either way, you should always check for line gaps, or your code may appear to work at first but fail when it encounters a long piece.

Note that the executing piece, i.e. the piece containing the current line being executed (line 15 in this case) is never truncated, no matter how long it is.

The lines of context never stray outside `frame_info.scope`, which is the innermost function or class definition containing the current line. For example, this is the output for a short function which has neither 3 lines before nor 1 line after the current line:

```python
bar at line 6
-----------
       4 | def bar():
       5 |     foo()
-->    6 |     print_stack()
```

Sometimes it's nice to ensure that the function signature is always showing. This can be done with `Options(include_signature=True)`. The result looks like this:

```python
foo at line 14
-----------
       9 | def foo():
       (...)
      11 |     for i in range(5):
      12 |         row = []
      13 |         result.append(row)
-->   14 |         print_stack()
      15 |         for j in range(5):
```

To avoid wasting space, pieces never start or end with a blank line, and blank lines between pieces are excluded. So if our code looks like this:


```python
    for i in range(5):
        row = []

        result.append(row)
        print_stack()

        for j in range(5):
```

The output doesn't change much, except you can see jumps in the line numbers:

```python
      11 |     for i in range(5):
      12 |         row = []
      14 |         result.append(row)
-->   15 |         print_stack()
      17 |         for j in range(5):
```
