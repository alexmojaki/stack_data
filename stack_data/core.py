import ast
import os
import sys
from collections import defaultdict, Counter
from textwrap import dedent
from tokenize import TokenInfo
from typing import (
    Iterator, List, Tuple, Optional, NamedTuple,
    Any, Iterable, Callable, Union
)
from types import FrameType, CodeType, TracebackType

from typing import Mapping

import executing
from executing import only
from pure_eval import Evaluator, is_expression_interesting
from stack_data.utils import (
    truncate, unique_in_order, line_range,
    frame_and_lineno, iter_stack, collapse_repeated, group_by_key_func,
)

Range = NamedTuple('Range',
                   [('start', int),
                    ('end', int),
                    ('data', Any)])

Marker = NamedTuple('Marker',
                    [('position', int),
                     ('is_start', bool),
                     ('string', str)])


class Piece(NamedTuple('_Piece',
                       [('start', int),
                        ('end', int)])):
    @property
    def range(self) -> range:
        return range(self.start, self.end)


class Variable(
    NamedTuple('_Variable',
               [('name', str),
                ('nodes', List[ast.AST]),
                ('value', Any)])
):
    __hash__ = object.__hash__


class Source(executing.Source):
    """
    The source code of a single file and associated metadata.

    In addition to the attributes from the base class executing.Source,
    if .tree is not None, meaning this is valid Python code, objects have:
        - pieces: a list of Piece objects
        - tokens_by_lineno: a defaultdict(list) mapping line numbers to lists of tokens.

    Don't construct this class. Get an instance from frame_info.source.
    """

    def __init__(self, *args, **kwargs):
        super(Source, self).__init__(*args, **kwargs)
        if self.tree:
            self.lines = self.text.split('\n')
            self.pieces = list(self._clean_pieces())  # type: List[Piece]
            self.tokens_by_lineno = group_by_key_func(
                self.asttokens().tokens,
                lambda tok: tok.start[0],
            )  # type: Mapping[int, List[TokenInfo]]
        else:
            self.lines = []

    def _clean_pieces(self) -> Iterator[Piece]:
        pieces = self._raw_split_into_pieces(self.tree, 0, len(self.lines))
        pieces = [
            (start, end)
            for (start, end) in pieces
            if end > start
        ]

        starts = [start for start, end in pieces[1:]]
        ends = [end for start, end in pieces[:-1]]
        if starts != ends:
            joins = list(map(set, zip(starts, ends)))
            mismatches = [s for s in joins if len(s) > 1]
            raise AssertionError("Pieces mismatches: %s" % mismatches)

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

    def _raw_split_into_pieces(
            self,
            stmt: ast.AST,
            start: int,
            end: int,
    ) -> Iterator[Tuple[int, int]]:
        self.asttokens()

        for name, body in ast.iter_fields(stmt):
            if (
                    isinstance(body, list) and body and
                    isinstance(body[0], (ast.stmt, ast.ExceptHandler))
            ):
                for rang, group in sorted(group_by_key_func(body, line_range).items()):
                    sub_stmt = group[0]
                    for inner_start, inner_end in self._raw_split_into_pieces(sub_stmt, *rang):
                        yield start, inner_start
                        yield inner_start, inner_end
                        start = inner_end

        yield start, end


def cached_property(func):
    key = func.__name__

    def cached_property_wrapper(self, *args, **kwargs):
        result = self._cache.get(key)
        if result is None:
            result = self._cache[key] = func(self, *args, **kwargs)
        return result

    return property(cached_property_wrapper)


class Options:
    def __init__(
            self,
            before: int = 3,
            after: int = 1,
            include_signature: bool = False,
            max_lines_per_piece: int = 6,
    ):
        self.before = before
        self.after = after
        self.include_signature = include_signature
        self.max_lines_per_piece = max_lines_per_piece

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))


class LineGap(object):
    def __repr__(self):
        return "LINE_GAP"


LINE_GAP = LineGap()


class Line(object):
    def __init__(
            self,
            frame_info: 'FrameInfo',
            lineno: int,
    ):
        self.frame_info = frame_info
        self.lineno = lineno
        self.text = frame_info.source.lines[lineno - 1]  # type: str
        self.leading_indent = None  # type: Optional[int]

    def __repr__(self):
        return "<{self.__class__.__name__} {self.lineno} (current={self.is_current}) " \
               "{self.text!r} of {self.frame_info.filename}>".format(self=self)

    @property
    def is_current(self) -> bool:
        return self.lineno == self.frame_info.lineno

    @property
    def tokens(self) -> List[TokenInfo]:
        return self.frame_info.source.tokens_by_lineno[self.lineno]

    @property
    def token_ranges(self) -> List[Range]:
        return [
            Range(
                token.start[1],
                token.end[1],
                token,
            )
            for token in self.tokens
        ]

    @property
    def variable_ranges(self) -> List[Range]:
        return [
            self.range_from_node(node, (variable, node))
            for variable, node in self.frame_info.variables_by_lineno[self.lineno]
        ]

    @property
    def executing_node_ranges(self) -> List[Range]:
        ex = self.frame_info.executing
        node = ex.node
        if node:
            rang = self.range_from_node(node, ex)
            if rang:
                return [rang]
        return []

    def range_from_node(self, node: ast.AST, data: Any) -> Optional[Range]:
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
    def dedented_text(self) -> str:
        return self.text[self.leading_indent:]

    def render_with_markers(
            self,
            markers: Iterable[Marker],
            strip_leading_indent: bool = True,
    ) -> str:
        text = self.text

        # This just makes the loop below simpler
        # Don't use append or += to not mutate the input
        markers = list(markers) + [Marker(position=len(text), is_start=False, string='')]

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


def markers_from_ranges(
        ranges: Iterable[Range],
        converter: Callable[[Range], Optional[Tuple[str, str]]],
) -> List[Marker]:
    markers = []
    for rang in ranges:
        converted = converter(rang)
        if converted is None:
            continue

        start_string, end_string = converted
        markers += [
            Marker(position=rang.start, is_start=True, string=start_string),
            Marker(position=rang.end, is_start=False, string=end_string),
        ]
    return markers


class RepeatedFrames:
    def __init__(
            self,
            frames: List[FrameType],
            frame_keys: List[Tuple[CodeType, int]],
    ):
        self.frames = frames
        self.frame_keys = frame_keys

    @property
    def description(self) -> str:
        counts = sorted(Counter(self.frame_keys).items(),
                        key=lambda item: (-item[1], item[0][0].co_name))
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
    def __init__(
            self,
            frame_or_tb: Union[FrameType, TracebackType],
            options: Optional[Options] = None,
    ):
        self.executing = Source.executing(frame_or_tb)
        frame, self.lineno = frame_and_lineno(frame_or_tb)
        self.frame = frame
        self.code = frame.f_code
        self.options = options or Options()  # type: Options
        self._cache = {}
        self.source = self.executing.source  # type: Source

    def __repr__(self):
        return "{self.__class__.__name__}({self.frame})".format(self=self)

    @classmethod
    def stack_data(
            cls,
            frame_or_tb: Union[FrameType, TracebackType],
            options: Optional[Options] = None,
    ) -> Iterator[Union['FrameInfo', RepeatedFrames]]:
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
    def scope_pieces(self) -> List[Piece]:
        if not self.scope:
            return []

        scope_start, scope_end = line_range(self.scope)
        return [
            piece
            for piece in self.source.pieces
            if scope_start <= piece.start and piece.end <= scope_end
        ]

    @cached_property
    def filename(self) -> str:
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
    def executing_piece(self) -> Piece:
        return only(
            piece
            for piece in self.scope_pieces
            if self.lineno in piece.range
        )

    @cached_property
    def included_pieces(self) -> List[Piece]:
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
    def lines(self) -> List[Union[Line, LineGap]]:
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
            ]  # type: List[Line]
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
    def scope(self) -> Optional[ast.AST]:
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
    def variables(self) -> List[Variable]:
        if not self.scope:
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
    def variables_by_lineno(self) -> Mapping[int, List[Tuple[Variable, ast.AST]]]:
        result = defaultdict(list)
        for var in self.variables:
            for node in var.nodes:
                for lineno in range(*line_range(node)):
                    result[lineno].append((var, node))
        return result

    @cached_property
    def variables_in_lines(self) -> List[Variable]:
        return unique_in_order(
            var
            for line in self.lines
            if isinstance(line, Line)
            for var, node in self.variables_by_lineno[line.lineno]
        )

    @cached_property
    def variables_in_executing_piece(self) -> List[Variable]:
        return unique_in_order(
            var
            for lineno in self.executing_piece.range
            for var, node in self.variables_by_lineno[lineno]
        )
