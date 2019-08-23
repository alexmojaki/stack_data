import ast
import inspect
import json

import executing
from littleutils import only


class Source(executing.Source):
    def __init__(self, *args, **kwargs):
        super(Source, self).__init__(*args, **kwargs)
        if self.tree:
            self.lines = self.text.splitlines()
            self.pieces = list(self._clean_pieces())
        else:
            self.lines = []

    def _clean_pieces(self):
        pieces = self._raw_split_into_pieces(self.tree)
        pieces = [
            (start, end)
            for (start, end) in pieces
            if end > start
        ]
        assert (
                [end for start, end in pieces[:-1]] ==
                [start for start, end in pieces[1:]]
        )

        def is_blank(i):
            return not self.lines[i - 1].strip()

        for start, end in pieces:
            while is_blank(start):
                start += 1
            while is_blank(end - 1):
                end -= 1
            if start < end:
                yield start, end

    def _raw_split_into_pieces(self, stmt):
        self.asttokens()
        start = stmt.first_token.start[0]

        for name, body in ast.iter_fields(stmt):
            if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
                for sub_stmt in body:
                    for inner_start, inner_end in self._raw_split_into_pieces(sub_stmt):
                        yield start, inner_start
                        yield inner_start, inner_end
                        start = inner_end
        end = stmt.last_token.end[0] + 1
        yield start, end


def cached_property(func):
    key = func.__name__

    def wrapper(self, *args, **kwargs):
        result = self._cache.get(key)
        if result is None:
            result = self._cache[key] = func(self, *args, **kwargs)
        return result

    return property(wrapper)


class Context(object):
    def __init__(
            self,
            before,
            after,
    ):
        self.before = before
        self.after = after


class Line(object):
    def __init__(
            self,
            frame_info,
            lineno,
    ):
        self.frame_info = frame_info
        self.lineno = lineno

    @property
    def text(self):
        return self.frame_info.source.lines[self.lineno - 1]

    @property
    def is_current(self):
        return self.lineno == self.frame_info.lineno


class StatementInfo(object):
    def __init__(
            self,
            frame_info,
            node,
    ):
        self.frame_info = frame_info
        self.node = node


class FrameInfo(object):
    def __init__(self, frame, context=None):
        self.frame = frame
        self.code = frame.f_code
        self.context = context or Context(before=3, after=1)
        self._cache = {}

    @classmethod
    def stack_data(cls, frame):
        while frame:
            yield cls(frame)
            frame = frame.f_back

    def to_dict(self):
        code = self.code
        ex = self.executing
        return dict(
            filename=code.co_filename,
            lineno=self.lineno,
            line=self.line.text,
            name=code.co_name,
            qualname=ex.code_qualname(),
            executing_text_range=ex.text_range(),
            executing_text=ex.text(),
            statements_text_range=self.statements_text_range,
            statements_text=self.statements_text,
            lines=[
                (line.lineno, line.text)
                for line in self.lines
            ]
        )

    @property
    def source(self):
        return Source.for_frame(self.frame)

    @property
    def executing(self):
        return Source.executing(self.frame)

    @property
    def lineno(self):
        return self.frame.f_lineno

    @cached_property
    def line(self):
        return Line(self, self.lineno)

    @cached_property
    def statements(self):
        main = self.executing.statements
        first = list(main)[0]
        body = []
        for name, body in ast.iter_fields(first.parent):
            if isinstance(body, list) and first in body:
                break
        pos = body.index(first)
        return body[max(0, pos - self.context.before)
                    :pos + len(main) + self.context.after]

    @cached_property
    def pieces(self):
        lineno = self.lineno
        pieces = self.source.pieces
        pos = only(
            i
            for i, (start, end) in enumerate(pieces)
            if start <= lineno < end
        )
        return pieces[max(0, pos - self.context.before)
                      :pos + 1 + self.context.after]

    @cached_property
    def lines(self):
        pieces = self.pieces
        return [
            Line(self, i)
            for i in range(pieces[0][0], pieces[-1][-1])
        ]

    @cached_property
    def statements_text_range(self):
        # TODO
        # source not available
        # compound statements

        tok = self.source.asttokens()
        ranges = [
            tok.get_text_range(stmt)
            for stmt in self.executing.statements
        ]
        start = min(r[0] for r in ranges)
        end = max(r[1] for r in ranges)
        return start, end

    @property
    def statements_text(self):
        start, end = self.statements_text_range
        return self.source.text[start:end]


def print_stack_data():
    for frame_info in FrameInfo.stack_data(inspect.currentframe().f_back):
        print(json.dumps(frame_info.to_dict(), indent=4, sort_keys=True))
