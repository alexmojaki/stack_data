import ast
import inspect
import json
from collections import defaultdict
from textwrap import dedent

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


class Options(object):
    def __init__(
            self,
            before=3,
            after=1,
            include_signature=False,
            max_lines_per_piece=6,
    ):
        self.before = before
        self.after = after
        self.include_signature = include_signature
        self.max_lines_per_piece = max_lines_per_piece


class _LineGap(object):
    def __repr__(self):
        return "LINE_GAP"


LINE_GAP = _LineGap()


class Line(object):
    def __init__(
            self,
            frame_info,
            lineno,
    ):
        self.frame_info = frame_info
        self.lineno = lineno
        self.text = frame_info.source.lines[lineno - 1]

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
    def __init__(self, frame, options=None):
        self.frame = frame
        self.code = frame.f_code
        self.options = options or Options()
        self._cache = {}
        self.source = Source.for_frame(self.frame)

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
            name=code.co_name,
            qualname=ex.code_qualname(),
            executing_text_range=ex.text_range(),
            executing_text=ex.text(),
        )

    @property
    def executing(self):
        return Source.executing(self.frame)

    @property
    def lineno(self):
        return self.frame.f_lineno

    @cached_property
    def lines(self):
        scope = self.scope
        scope_start = scope.first_token.start[0]
        scope_end = scope.last_token.end[0] + 1
        scope_pieces = [
            (start, end)
            for (start, end) in self.source.pieces
            if scope_start <= start and end <= scope_end
        ]

        pos, main_piece = only(
            (i, (start, end))
            for (i, (start, end)) in enumerate(scope_pieces)
            if start <= self.lineno < end
        )

        pieces_start = max(0, pos - self.options.before)
        pieces_end = pos + 1 + self.options.after
        pieces = scope_pieces[pieces_start:pieces_end]
        result = []

        def lines_from_piece(pc):
            lines = [
                Line(self, i)
                for i in range(pc[0], pc[1])
            ]
            if pc != main_piece:
                lines = truncate(
                    lines,
                    max_length=self.options.max_lines_per_piece,
                    middle=[LINE_GAP],
                )
            result.extend(lines)

        if (
                self.options.include_signature
                and isinstance(scope, ast.FunctionDef)
                and pieces_start > 0
        ):
            lines_from_piece(scope_pieces[0])
            if pieces_start > 1:
                result.append(LINE_GAP)

        for piece in pieces:
            lines_from_piece(piece)

        real_lines = [
            line
            for line in result
            if isinstance(line, Line)
        ]

        text = "\n".join(
            line.text
            for line in real_lines
        )
        dedented_lines = dedent(text).splitlines()

        for line, dedented in zip(real_lines, dedented_lines):
            line.text = dedented

        return result

    @cached_property
    def scope(self):
        if not self.source.tree:
            return None

        stmt = list(self.executing.statements)[0]
        while True:
            # Get the parent first in case the original statement is already
            # a function definition, e.g. if we're calling a decorator
            # In that case we still want the surrounding scope, not that function
            stmt = stmt.parent
            if isinstance(stmt, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                return stmt

    @cached_property
    def variables(self):
        names = defaultdict(list)
        for node in ast.walk(self.scope):
            if isinstance(node, ast.Name):
                names[node.id].append(node)

        result = []
        for name, nodes in names.items():
            sentinel = object()
            value = self.frame.f_locals.get(name, sentinel)
            is_local = value != sentinel
            if not is_local:
                value = self.frame.f_globals.get(name, sentinel)
                if value == sentinel:
                    # builtin or undefined
                    continue

            # TODO proximity to execution

            result.append(Variable(name, nodes, is_local, value))

        return result

    def formatted_lines(self):
        for line in self.lines:
            if isinstance(line, Line):
                yield '{:4} | {}'.format(line.lineno, line.text)
            else:
                assert line is LINE_GAP
                yield '(...)'


class Variable(object):
    def __init__(self, name, nodes, is_local, value):
        self.name = name
        self.nodes = nodes
        self.is_local = is_local
        self.value = value


def print_stack_data():
    for frame_info in FrameInfo.stack_data(inspect.currentframe().f_back):
        print(json.dumps(frame_info.to_dict(), indent=4, sort_keys=True))


def print_lines():
    frame_info = FrameInfo(inspect.currentframe().f_back, Options(include_signature=True))
    for line in frame_info.formatted_lines():
        print(line)


def truncate(seq, max_length, middle):
    if len(seq) > max_length:
        left = (max_length - len(middle)) // 2
        right = max_length - len(middle) - left
        seq = seq[:left] + middle + seq[-right:]
    return seq
