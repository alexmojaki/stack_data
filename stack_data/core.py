import ast
import os
import sys
from collections import defaultdict, namedtuple, Counter
from textwrap import dedent

import executing
from executing import only
from pure_eval import Evaluator, is_expression_interesting

from stack_data.utils import (
    truncate, unique_in_order, line_range,
    frame_and_lineno, iter_stack, collapse_repeated, group_by_key_func,
)


class Source(executing.Source):
    def __init__(self, *args, **kwargs):
        super(Source, self).__init__(*args, **kwargs)
        if self.tree:
            self.lines = self.text.split('\n')
            self.pieces = list(self._clean_pieces())
            self.tokens_by_lineno = group_by_key_func(self.asttokens().tokens, lambda tok: tok.start[0])
        else:
            self.lines = []

    def _clean_pieces(self):
        pieces = self._raw_split_into_pieces(self.tree, 0, len(self.lines))
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
            try:
                return not self.lines[i - 1].strip()
            except IndexError:
                return False

        for start, end in pieces:
            while is_blank(start):
                start += 1
            while is_blank(end - 1):
                end -= 1
            if start < end:
                yield Piece(start, end)

    def _raw_split_into_pieces(self, stmt, start, end):
        self.asttokens()

        for name, body in ast.iter_fields(stmt):
            if isinstance(body, list) and body and isinstance(body[0], (ast.stmt, ast.ExceptHandler)):
                for rang, group in sorted(group_by_key_func(body, line_range).items()):
                    sub_stmt = group[0]
                    for inner_start, inner_end in self._raw_split_into_pieces(sub_stmt, *rang):
                        yield start, inner_start
                        yield inner_start, inner_end
                        start = inner_end

        yield start, end


def cached_property(func):
    key = func.__name__

    def wrapper(self, *args, **kwargs):
        result = self._cache.get(key)
        if result is None:
            result = self._cache[key] = func(self, *args, **kwargs)
        return result

    return property(wrapper)


class Options:
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

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))


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
        self.leading_indent = None

    def __repr__(self):
        return "<{self.__class__.__name__} {self.lineno} (current={self.is_current}) " \
               "{self.text!r} of {self.frame_info.filename}>".format(self=self)

    @property
    def is_current(self):
        return self.lineno == self.frame_info.lineno

    @property
    def tokens(self):
        return self.frame_info.source.tokens_by_lineno[self.lineno]

    @property
    def token_ranges(self):
        return [
            Range(
                token.start[1],
                token.end[1],
                token,
            )
            for token in self.tokens
        ]

    @property
    def variable_ranges(self):
        return [
            self.range_from_node(node, (variable, node))
            for variable, node in self.frame_info.variables_by_lineno[self.lineno]
        ]

    @property
    def executing_node_ranges(self):
        ex = self.frame_info.executing
        node = ex.node
        if node:
            rang = self.range_from_node(node, ex)
            if rang:
                return [rang]
        return []

    def range_from_node(self, node, data):
        start, end = line_range(node)
        end -= 1
        if not (start <= self.lineno <= end):
            return None
        if start == self.lineno:
            range_start = node.first_token.start[1]
        else:
            range_start = 0

        if end == self.lineno:
            range_end = node.last_token.end[1]
        else:
            range_end = len(self.text)

        return Range(range_start, range_end, data)

    @property
    def dedented_text(self):
        return self.text[self.leading_indent:]

    def render_with_markers(self, markers, strip_leading_indent=True):
        text = self.text

        # This just makes the loop below simpler
        # Don't use append or += to not mutate the input
        markers = markers + [Marker(position=len(text), is_start=False, string='')]

        markers.sort(key=lambda t: t[:2])

        parts = []
        if strip_leading_indent:
            start = self.leading_indent
        else:
            start = 0
        original_start = start

        for marker in markers:
            parts.append(text[start:marker.position])
            parts.append(marker.string)

            # Ensure that start >= leading_indent
            start = max(marker.position, original_start)
        return ''.join(parts)


Range = namedtuple('Range', 'start end data')
Marker = namedtuple('Marker', 'position is_start string')


class Piece(namedtuple('_Piece', 'start end')):
    @property
    def range(self):
        return range(self.start, self.end)


class Variable(namedtuple('_Variable', 'name nodes value')):
    __hash__ = object.__hash__


def markers_from_ranges(ranges, converter):
    markers = []
    for rang in ranges:
        converted = converter(rang)
        if converted is None:
            continue

        markers += [
            Marker(position=rang[0], is_start=True, string=converted[0]),
            Marker(position=rang[1], is_start=False, string=converted[1]),
        ]

    return markers


class RepeatedFrames:
    def __init__(self, frames, frame_keys):
        self.frames = frames
        self.frame_keys = frame_keys

    @property
    def description(self):
        counts = sorted(Counter(self.frame_keys).items(),
                        key=lambda item: (item[1], item[0][0].co_name))
        return ', '.join(
            '{name} at line {lineno} ({count} times)'.format(
                name=Source.for_filename(code.co_filename).code_qualname(code),
                lineno=lineno,
                count=count,
            )
            for (code, lineno), count in counts
        )

    def __repr__(self):
        return '<{self.__class__.__name__} {self.description}>'.format(self=self)


class FrameInfo(object):
    def __init__(self, frame_or_tb, options=None):
        self.executing = Source.executing(frame_or_tb)
        frame, self.lineno = frame_and_lineno(frame_or_tb)
        self.frame = frame
        self.code = frame.f_code
        self.options = options or Options()
        self._cache = {}
        self.source = self.executing.source

    def __repr__(self):
        return "{self.__class__.__name__}({self.frame})".format(self=self)

    @classmethod
    def stack_data(cls, frame_or_tb, options=None):
        def _frame_key(x):
            frame, lineno = frame_and_lineno(x)
            return frame.f_code, lineno

        yield from collapse_repeated(
            list(iter_stack(frame_or_tb)),
            mapper=lambda f: cls(f, options),
            collapser=RepeatedFrames,
            key=_frame_key,
        )

    @cached_property
    def scope_pieces(self):
        if not self.source.tree:
            return []

        scope_start, scope_end = line_range(self.scope)
        return [
            piece
            for piece in self.source.pieces
            if scope_start <= piece.start and piece.end <= scope_end
        ]

    @cached_property
    def filename(self):
        result = self.code.co_filename

        if (
                os.path.isabs(result) or
                (
                        result.startswith(str("<")) and
                        result.endswith(str(">"))
                )
        ):
            return result

        # Try to make the filename absolute by trying all
        # sys.path entries (which is also what linecache does)
        for dirname in sys.path:
            try:
                fullname = os.path.join(dirname, result)
                if os.path.isfile(fullname):
                    return os.path.abspath(fullname)
            except Exception:
                # Just in case that sys.path contains very
                # strange entries...
                pass

        return result

    @cached_property
    def executing_piece(self):
        return only(
            piece
            for piece in self.scope_pieces
            if self.lineno in piece.range
        )

    @cached_property
    def included_pieces(self):
        scope_pieces = self.scope_pieces
        if not self.scope_pieces:
            return []

        pos = scope_pieces.index(self.executing_piece)
        pieces_start = max(0, pos - self.options.before)
        pieces_end = pos + 1 + self.options.after
        pieces = scope_pieces[pieces_start:pieces_end]

        if (
                self.options.include_signature
                and not self.code.co_name.startswith('<')
                and isinstance(self.scope, ast.FunctionDef)
                and pieces_start > 0
        ):
            pieces.insert(0, scope_pieces[0])

        return pieces

    @cached_property
    def lines(self):
        pieces = self.included_pieces
        if not pieces:
            return []

        result = []
        for i, piece in enumerate(pieces):
            if (
                    i == 1
                    and pieces[0] == self.scope_pieces[0]
                    and pieces[1] != self.scope_pieces[1]
            ):
                result.append(LINE_GAP)

            lines = [
                Line(self, i)
                for i in piece.range
            ]
            if piece != self.executing_piece:
                lines = truncate(
                    lines,
                    max_length=self.options.max_lines_per_piece,
                    middle=[LINE_GAP],
                )
            result.extend(lines)

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
        leading_indent = len(real_lines[0].text) - len(dedented_lines[0])
        for line in real_lines:
            line.leading_indent = leading_indent

        return result

    @cached_property
    def scope(self):
        if not self.source.tree or not self.executing.statements:
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
        if not self.source.tree:
            return []

        evaluator = Evaluator.from_frame(self.frame)
        get_text = self.source.asttokens().get_text
        scope = self.scope
        node_values = [
            pair
            for pair in evaluator.find_expressions(scope)
            if is_expression_interesting(*pair)
        ]

        if isinstance(scope, ast.FunctionDef):
            for node in ast.walk(scope.args):
                if not isinstance(node, ast.arg):
                    continue
                name = node.arg
                try:
                    value = evaluator.names[name]
                except KeyError:
                    pass
                else:
                    node_values.append((node, value))

        # TODO use compile(...).co_code instead of ast.dump?
        # Group equivalent nodes together
        grouped = group_by_key_func(
            node_values,
            # Add parens to avoid syntax errors for multiline expressions
            lambda nv: ast.dump(ast.parse('(' + get_text(nv[0]) + ')')),
        )

        result = []
        for group in grouped.values():
            nodes, values = zip(*group)
            value = values[0]
            text = get_text(nodes[0])
            result.append(Variable(text, nodes, value))

        return result

    @cached_property
    def variables_by_lineno(self):
        result = defaultdict(list)
        for var in self.variables:
            for node in var.nodes:
                for lineno in range(*line_range(node)):
                    result[lineno].append((var, node))
        return result

    @cached_property
    def variables_in_lines(self):
        return unique_in_order(
            var
            for line in self.lines
            if isinstance(line, Line)
            for var, node in self.variables_by_lineno[line.lineno]
        )

    @cached_property
    def variables_in_executing_piece(self):
        return unique_in_order(
            var
            for lineno in self.executing_piece.range
            for var, node in self.variables_by_lineno[lineno]
        )
