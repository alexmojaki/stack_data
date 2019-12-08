import ast
import os
import sys
from collections import defaultdict, namedtuple, Counter
from textwrap import dedent

import executing
from littleutils import only, group_by_key_func
from pure_eval import Evaluator

from stack_data.utils import truncate, unique_in_order, line_range, frame_and_lineno, iter_stack, collapse_repeated


class Source(executing.Source):
    def __init__(self, *args, **kwargs):
        super(Source, self).__init__(*args, **kwargs)
        if self.tree:
            self.lines = self.text.splitlines()
            self.pieces = list(self._clean_pieces())
            self.tokens_by_lineno = group_by_key_func(self.asttokens().tokens, lambda tok: tok.start[0])
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
        start, end = line_range(stmt)

        for name, body in ast.iter_fields(stmt):
            if isinstance(body, list) and body and isinstance(body[0], (ast.stmt, ast.ExceptHandler)):
                for sub_stmt in body:
                    for inner_start, inner_end in self._raw_split_into_pieces(sub_stmt):
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
        self.frame_info: FrameInfo = frame_info
        self.lineno = lineno
        self.text = frame_info.source.lines[lineno - 1]
        self.leading_indent = None

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
        result = []
        for variable, node in self.frame_info.variables_by_lineno[self.lineno]:
            start, end = line_range(node)
            end -= 1
            assert start <= self.lineno <= end
            if start == self.lineno:
                range_start = node.first_token.start[1]
            else:
                range_start = 0

            if end == self.lineno:
                range_end = node.last_token.end[1]
            else:
                range_end = len(self.text)

            result.append(Range(
                range_start,
                range_end,
                (variable, node),
            ))

        return result

    @property
    def dedented_text(self):
        return self.text[self.leading_indent:]

    def render_with_markers(self, markers, strip_leading_indent=True):
        text = self.text

        # This just makes the loop below simpler
        # Don't use append or += to not mutate the input
        markers = markers + [(len(text), False, '')]

        markers.sort(key=lambda t: t[:2])

        parts = []
        if strip_leading_indent:
            start = self.leading_indent
        else:
            start = 0
        original_start = start

        for position, _is_start, part in markers:
            parts.append(text[start:position])
            parts.append(part)

            # Ensure that start >= leading_indent
            start = max(position, original_start)
        return ''.join(parts)


Range = namedtuple('Range', 'start end data')


def markers_from_ranges(ranges, converter):
    markers = []
    for rang in ranges:
        converted = converter(rang)
        if converted is None:
            continue

        markers += [
            (rang[0], True, converted[0]),
            (rang[1], False, converted[1]),
        ]

    return markers


class RepeatedFrames:
    def __init__(self, frames, frame_keys):
        self.frames = frames
        self.frame_keys = frame_keys

    @property
    def description(self):
        counts = Counter(self.frame_keys)
        return ', '.join(
            '{name}:{lineno} x{count}'.format(
                name=Source.for_filename(code.co_filename).code_qualname(code),
                lineno=lineno,
                count=count,
            )
            for (code, lineno), count in counts.most_common()
        )

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.description}>'


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
        return f"{self.__class__.__name__}({self.frame})"

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
            (start, end)
            for (start, end) in self.source.pieces
            if scope_start <= start and end <= scope_end
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
            (start, end)
            for (start, end) in self.scope_pieces
            if start <= self.lineno < end
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

            start, end = piece
            lines = [
                Line(self, i)
                for i in range(start, end)
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
        if not self.source.tree:
            return []

        evaluator = Evaluator.from_frame(self.frame)
        get_text = self.source.asttokens().get_text
        scope = self.scope
        node_values = evaluator.find_expressions(scope)

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
            if not all(value is values[0] for value in values):
                # Distinct values found for same expression
                # Probably indicates another thread is messing with things
                # Since no single correct value exists, ignore this expression
                continue
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
        start, end = self.executing_piece
        return unique_in_order(
            var
            for lineno in range(start, end)
            for var, node in self.variables_by_lineno[lineno]
        )


class Variable(object):
    def __init__(self, name, nodes, value):
        self.name = name
        self.nodes = nodes
        self.value = value
