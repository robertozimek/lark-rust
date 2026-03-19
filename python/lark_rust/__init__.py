from copy import copy, deepcopy
from functools import partial, wraps
from collections import OrderedDict
from typing import Any, Iterator, Optional, Dict, Collection

from .lark_rust import (
    Token,
    BasicLexer,
    LexerState,
    LexerThread as RustLexerThread,
    LineCounter,
    Scanner,
    CompiledParseTable,
    __version__,
)

from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedToken,
    UnexpectedInput,
    GrammarError,
    ConfigurationError,
)
from lark.lexer import CallChain, _create_unless, TerminalDef, _regexp_has_newline
from lark.parsers.lalr_analysis import LALR_Analyzer, Shift, Reduce, IntParseTable
from lark.parsers.lalr_interactive_parser import InteractiveParser
from lark.utils import Serialize
from lark.visitors import Transformer_InPlace
from lark.visitors import _vargs_meta, _vargs_meta_inline


# ---------------------------------------------------------------------------
# Lexer components
# ---------------------------------------------------------------------------

class LexerThread:
    """A thread that ties a lexer instance and a lexer state, to be used by the parser."""

    def __init__(self, lexer, lexer_state):
        self.lexer = lexer
        self.state = lexer_state

    @classmethod
    def from_text(cls, lexer, text):
        return cls(lexer, lexer.make_lexer_state(text))

    def next_token(self, parser_state):
        return self.lexer.next_token(self.state, parser_state)

    def lex(self, parser_state):
        try:
            while True:
                yield self.lexer.next_token(self.state, parser_state)
        except EOFError:
            pass

    def __copy__(self):
        return type(self)(self.lexer, copy(self.state))

    _Token = Token


class ContextualLexer:
    """Contextual lexer that switches between different BasicLexer instances
    based on the current parser state."""

    def __init__(self, conf, states, always_accept=()):
        terminals = list(conf.terminals)
        trad_conf = copy(conf)
        trad_conf.terminals = terminals

        lexer_by_tokens = {}
        self.lexers = {}
        for state, accepts in states.items():
            key = frozenset(accepts)
            try:
                lexer = lexer_by_tokens[key]
            except KeyError:
                accepts = set(accepts) | set(conf.ignore) | set(always_accept)
                lexer_conf = copy(trad_conf)
                lexer_conf.terminals = [
                    conf.terminals_by_name[n]
                    for n in accepts
                    if n in conf.terminals_by_name
                ]
                lexer = BasicLexer(lexer_conf)
                lexer_by_tokens[key] = lexer
            self.lexers[state] = lexer

        assert trad_conf.terminals is terminals
        self.root_lexer = BasicLexer(trad_conf)

    def make_lexer_state(self, text):
        return self.root_lexer.make_lexer_state(text)

    def next_token(self, lexer_state, parser_state):
        try:
            lexer = self.lexers[parser_state.position]
            return lexer.next_token(lexer_state, parser_state)
        except UnexpectedCharacters as e:
            try:
                last_token = lexer_state.last_token
                token = self.root_lexer.next_token(lexer_state, parser_state)
                raise UnexpectedToken(
                    token, e.allowed, state=parser_state,
                    token_history=[last_token],
                    terminals_by_name=self.root_lexer.terminals_by_name,
                )
            except UnexpectedCharacters:
                raise e

    def lex(self, lexer_state, parser_state):
        try:
            while True:
                yield self.next_token(lexer_state, parser_state)
        except EOFError:
            pass


# ---------------------------------------------------------------------------
# Parser components
# ---------------------------------------------------------------------------

class ParseConf:
    __slots__ = ('parse_table', 'callbacks', 'start', 'start_state', 'end_state',
                 'states', '_compiled')

    def __init__(self, parse_table, callbacks, start):
        self.parse_table = parse_table
        self.start_state = parse_table.start_states[start]
        self.end_state = parse_table.end_states[start]
        self.states = parse_table.states
        self.callbacks = callbacks
        self.start = start
        self._compiled = CompiledParseTable(self)


class ParserState:
    __slots__ = ('parse_conf', 'lexer', 'state_stack', 'value_stack')

    def __init__(self, parse_conf, lexer, state_stack=None, value_stack=None):
        self.parse_conf = parse_conf
        self.lexer = lexer
        self.state_stack = state_stack or [parse_conf.start_state]
        self.value_stack = value_stack or []

    @property
    def position(self):
        return self.state_stack[-1]

    def __eq__(self, other):
        if not isinstance(other, ParserState):
            return NotImplemented
        return (len(self.state_stack) == len(other.state_stack)
                and self.position == other.position)

    def __copy__(self):
        return self.copy()

    def copy(self, deepcopy_values=True):
        return type(self)(
            self.parse_conf,
            self.lexer,
            copy(self.state_stack),
            deepcopy(self.value_stack) if deepcopy_values else copy(self.value_stack),
        )

    def feed_token(self, token, is_end=False):
        compiled = self.parse_conf._compiled
        return compiled.feed_token(
            self.state_stack, self.value_stack,
            token, token.type, is_end, self,
        )


class _Parser:
    def __init__(self, parse_table, callbacks, debug=False):
        self.parse_table = parse_table
        self.callbacks = callbacks
        self.debug = debug

    def parse(self, lexer, start, value_stack=None, state_stack=None,
              start_interactive=False):
        parse_conf = ParseConf(self.parse_table, self.callbacks, start)
        parser_state = ParserState(
            parse_conf, lexer, state_stack, value_stack
        )
        if start_interactive:
            return InteractiveParser(self, parser_state, parser_state.lexer)
        return self.parse_from_state(parser_state)

    def parse_from_state(self, state, last_token=None):
        try:
            lexer = state.lexer
            compiled = state.parse_conf._compiled

            if (last_token is None
                    and hasattr(lexer, 'state')
                    and isinstance(lexer.lexer, BasicLexer)):
                # Fast path: LexerThread with BasicLexer — run entire
                # lex+parse loop in a single Rust call.
                return compiled.parse_loop(
                    lexer.lexer, lexer.state,
                    state.state_stack, state.value_stack,
                    state,
                )

            # Fallback: ContextualLexer or resume with last_token
            token = last_token
            if hasattr(lexer, 'state'):
                inner_lexer = lexer.lexer
                lexer_state = lexer.state
                try:
                    while True:
                        token = inner_lexer.next_token(lexer_state, state)
                        state.feed_token(token)
                except EOFError:
                    pass
            else:
                for token in lexer.lex(state):
                    assert token is not None
                    state.feed_token(token)

            end_token = (
                Token.new_borrow_pos('$END', '', token)
                if token
                else Token('$END', '', 0, 1, 1)
            )
            return state.feed_token(end_token, True)
        except UnexpectedInput as e:
            try:
                e.interactive_parser = InteractiveParser(
                    self, state, state.lexer
                )
            except NameError:
                pass
            raise e
        except Exception as e:
            if self.debug:
                print("")
                print("STATE STACK DUMP")
                print("----------------")
                for i, s in enumerate(state.state_stack):
                    print('%d)' % i, s)
                print("")
            raise


class LALR_Parser(Serialize):
    def __init__(self, parser_conf, debug=False, strict=False):
        analysis = LALR_Analyzer(parser_conf, debug=debug, strict=strict)
        analysis.compute_lalr()
        callbacks = parser_conf.callbacks

        self._parse_table = analysis.parse_table
        self.parser_conf = parser_conf
        self.parser = _Parser(analysis.parse_table, callbacks, debug)

    @classmethod
    def deserialize(cls, data, memo, callbacks, debug=False):
        inst = cls.__new__(cls)
        inst._parse_table = IntParseTable.deserialize(data, memo)
        inst.parser = _Parser(inst._parse_table, callbacks, debug)
        return inst

    def serialize(self, memo=None):
        return self._parse_table.serialize(memo)

    def parse_interactive(self, lexer, start):
        return self.parser.parse(lexer, start, start_interactive=True)

    def parse(self, lexer, start, on_error=None):
        try:
            return self.parser.parse(lexer, start)
        except UnexpectedInput as e:
            if on_error is None:
                raise

            while True:
                if isinstance(e, UnexpectedCharacters):
                    s = e.interactive_parser.lexer_state.state
                    p = s.line_ctr.char_pos

                if not on_error(e):
                    raise e

                if isinstance(e, UnexpectedCharacters):
                    if p == s.line_ctr.char_pos:
                        s.line_ctr.feed(s.text[p:p+1])

                try:
                    return e.interactive_parser.resume_parse()
                except UnexpectedToken as e2:
                    if (isinstance(e, UnexpectedToken)
                            and e.token.type == e2.token.type == '$END'
                            and e.interactive_parser == e2.interactive_parser):
                        raise e2
                    e = e2
                except UnexpectedCharacters as e2:
                    e = e2


# ---------------------------------------------------------------------------
# Tree components
# ---------------------------------------------------------------------------

class Meta:
    def __init__(self):
        self.empty = True


class Tree:
    def __init__(self, data, children, meta=None):
        self.data = data
        self.children = children
        self._meta = meta

    @property
    def meta(self):
        if self._meta is None:
            self._meta = Meta()
        return self._meta

    def __repr__(self):
        return 'Tree(%r, %r)' % (self.data, self.children)

    def __str__(self):
        return self.pretty()

    def _pretty_label(self):
        return self.data

    def _pretty(self, level, indent_str):
        if len(self.children) == 1 and not isinstance(self.children[0], Tree):
            return [indent_str*level, self._pretty_label(), '\t',
                    '%s' % (self.children[0],), '\n']
        l = [indent_str*level, self._pretty_label(), '\n']
        for n in self.children:
            if isinstance(n, Tree):
                l += n._pretty(level+1, indent_str)
            else:
                l += [indent_str*(level+1), '%s' % (n,), '\n']
        return l

    def pretty(self, indent_str='  '):
        return ''.join(self._pretty(0, indent_str))

    def __eq__(self, other):
        try:
            return self.data == other.data and self.children == other.children
        except AttributeError:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.data, tuple(self.children)))

    def __lark_meta__(self):
        return self.meta

    def iter_subtrees(self):
        queue = [self]
        subtrees = OrderedDict()
        for subtree in queue:
            subtrees[id(subtree)] = subtree
            queue += [c for c in reversed(subtree.children)
                      if isinstance(c, Tree) and id(c) not in subtrees]
        del queue
        return reversed(list(subtrees.values()))

    def iter_subtrees_topdown(self):
        stack = [self]
        while stack:
            node = stack.pop()
            if not isinstance(node, Tree):
                continue
            yield node
            for n in reversed(node.children):
                stack.append(n)

    def find_pred(self, pred):
        return filter(pred, self.iter_subtrees())

    def find_data(self, data):
        return self.find_pred(lambda t: t.data == data)

    def expand_kids_by_data(self, *data_values):
        changed = False
        for i in range(len(self.children)-1, -1, -1):
            child = self.children[i]
            if isinstance(child, Tree) and child.data in data_values:
                self.children[i:i+1] = child.children
                changed = True
        return changed

    def scan_values(self, pred):
        for c in self.children:
            if isinstance(c, Tree):
                yield from c.scan_values(pred)
            else:
                if pred(c):
                    yield c

    def __deepcopy__(self, memo):
        return type(self)(self.data, deepcopy(self.children, memo), meta=self._meta)

    def copy(self):
        return type(self)(self.data, self.children)

    def set(self, data, children):
        self.data = data
        self.children = children


# ---------------------------------------------------------------------------
# ParseTreeBuilder components
# ---------------------------------------------------------------------------

def apply_visit_wrapper(func, name, wrapper):
    if wrapper is _vargs_meta or wrapper is _vargs_meta_inline:
        raise NotImplementedError(
            "Meta args not supported for internal transformer"
        )

    @wraps(func)
    def f(children):
        return wrapper(func, name, children, None)
    return f


def inplace_transformer(func):
    @wraps(func)
    def f(children):
        tree = Tree(func.__name__, children)
        return func(tree)
    return f


class ExpandSingleChild:
    def __init__(self, node_builder):
        self.node_builder = node_builder

    def __call__(self, children):
        if len(children) == 1:
            return children[0]
        return self.node_builder(children)


class PropagatePositions:
    def __init__(self, node_builder, node_filter=None):
        self.node_builder = node_builder
        self.node_filter = node_filter

    def __call__(self, children):
        res = self.node_builder(children)
        if isinstance(res, Tree):
            res_meta = res.meta
            first_meta = self._pp_get_meta(children)
            if first_meta is not None:
                if not hasattr(res_meta, 'line') or res_meta.empty:
                    res_meta.line = getattr(first_meta, 'container_line',
                                            getattr(first_meta, 'line', None))
                    res_meta.column = getattr(first_meta, 'container_column',
                                              getattr(first_meta, 'column', None))
                    res_meta.start_pos = getattr(first_meta, 'container_start_pos',
                                                 getattr(first_meta, 'start_pos', None))
                    res_meta.empty = False

                res_meta.container_line = getattr(first_meta, 'container_line',
                                                  getattr(first_meta, 'line', None))
                res_meta.container_column = getattr(first_meta, 'container_column',
                                                    getattr(first_meta, 'column', None))

            last_meta = self._pp_get_meta(reversed(children))
            if last_meta is not None:
                if not hasattr(res_meta, 'end_line') or res_meta.empty:
                    res_meta.end_line = getattr(last_meta, 'container_end_line',
                                                getattr(last_meta, 'end_line', None))
                    res_meta.end_column = getattr(last_meta, 'container_end_column',
                                                  getattr(last_meta, 'end_column', None))
                    res_meta.end_pos = getattr(last_meta, 'container_end_pos',
                                               getattr(last_meta, 'end_pos', None))
                    res_meta.empty = False

                res_meta.container_end_line = getattr(last_meta, 'container_end_line',
                                                      getattr(last_meta, 'end_line', None))
                res_meta.container_end_column = getattr(last_meta, 'container_end_column',
                                                        getattr(last_meta, 'end_column', None))
        return res

    def _pp_get_meta(self, children):
        for c in children:
            if self.node_filter is not None and not self.node_filter(c):
                continue
            if isinstance(c, Tree):
                if not c.meta.empty:
                    return c.meta
            elif isinstance(c, Token):
                return c
        return None


def _make_propagate_positions(option):
    if callable(option):
        return partial(PropagatePositions, node_filter=option)
    elif option is True:
        return PropagatePositions
    elif option is False:
        return None
    raise ConfigurationError(
        'Invalid option for propagate_positions: %r' % option
    )


def _should_expand(sym):
    name = sym.name
    if not isinstance(name, str):
        name = name.value
    return not sym.is_term and name.startswith('_')


class ChildFilter:
    def __init__(self, to_include, append_none, node_builder):
        self.node_builder = node_builder
        self.to_include = to_include
        self.append_none = append_none

    def __call__(self, children):
        filtered = []
        for i, to_expand, add_none in self.to_include:
            if add_none:
                filtered += [None] * add_none
            if to_expand:
                filtered += children[i].children
            else:
                filtered.append(children[i])
        if self.append_none:
            filtered += [None] * self.append_none
        return self.node_builder(filtered)


class ChildFilterLALR(ChildFilter):
    """Optimized childfilter for LALR (assumes no duplication in parse tree)."""

    def __call__(self, children):
        filtered = []
        for i, to_expand, add_none in self.to_include:
            if add_none:
                filtered += [None] * add_none
            if to_expand:
                if filtered:
                    filtered += children[i].children
                else:
                    filtered = children[i].children
            else:
                filtered.append(children[i])
        if self.append_none:
            filtered += [None] * self.append_none
        return self.node_builder(filtered)


class ChildFilterLALR_NoPlaceholders(ChildFilter):
    """Optimized childfilter for LALR without placeholders."""

    def __init__(self, to_include, node_builder):
        self.node_builder = node_builder
        self.to_include = to_include

    def __call__(self, children):
        filtered = []
        for i, to_expand in self.to_include:
            if to_expand:
                child = children[i]
                if filtered:
                    filtered += child.children
                else:
                    filtered = child.children
            else:
                filtered.append(children[i])
        return self.node_builder(filtered)


def maybe_create_child_filter(expansion, keep_all_tokens, ambiguous,
                              _empty_indices):
    if _empty_indices:
        assert _empty_indices.count(False) == len(expansion)
        s = ''.join(str(int(b)) for b in _empty_indices)
        empty_indices = [len(ones) for ones in s.split('0')]
        assert len(empty_indices) == len(expansion) + 1
    else:
        empty_indices = [0] * (len(expansion) + 1)

    to_include = []
    nones_to_add = 0
    for i, sym in enumerate(expansion):
        nones_to_add += empty_indices[i]
        if keep_all_tokens or not (sym.is_term and sym.filter_out):
            to_include.append((i, _should_expand(sym), nones_to_add))
            nones_to_add = 0

    nones_to_add += empty_indices[len(expansion)]

    if (_empty_indices or len(to_include) < len(expansion)
            or any(to_expand for i, to_expand, _ in to_include)):
        if _empty_indices or ambiguous:
            return partial(
                ChildFilter if ambiguous else ChildFilterLALR,
                to_include, nones_to_add,
            )
        else:
            return partial(
                ChildFilterLALR_NoPlaceholders,
                [(i, x) for i, x, _ in to_include],
            )


class ParseTreeBuilder:
    def __init__(self, rules, tree_class, propagate_positions=False,
                 ambiguous=False, maybe_placeholders=False):
        self.tree_class = Tree
        self.propagate_positions = propagate_positions
        self.ambiguous = ambiguous
        self.maybe_placeholders = maybe_placeholders
        self.rule_builders = list(self._init_builders(rules))

    def _init_builders(self, rules):
        propagate_positions = _make_propagate_positions(self.propagate_positions)

        for rule in rules:
            options = rule.options
            keep_all_tokens = options.keep_all_tokens
            expand_single_child = options.expand1

            wrapper_chain = list(filter(None, [
                (expand_single_child and not rule.alias) and ExpandSingleChild,
                maybe_create_child_filter(
                    rule.expansion, keep_all_tokens, self.ambiguous,
                    options.empty_indices if self.maybe_placeholders else None,
                ),
                propagate_positions,
            ]))

            yield rule, wrapper_chain

    def create_callback(self, transformer=None):
        callbacks = {}

        default_handler = getattr(transformer, '__default__', None)
        if default_handler:
            def default_callback(data, children):
                return default_handler(data, children, None)
        else:
            default_callback = self.tree_class

        for rule, wrapper_chain in self.rule_builders:
            user_callback_name = (
                rule.alias or rule.options.template_source or rule.origin.name
            )
            try:
                if not isinstance(user_callback_name, str):
                    user_callback_name = user_callback_name.value
                f = getattr(transformer, user_callback_name)
                wrapper = getattr(f, 'visit_wrapper', None)
                if wrapper is not None:
                    f = apply_visit_wrapper(f, user_callback_name, wrapper)
                elif isinstance(transformer, Transformer_InPlace):
                    f = inplace_transformer(f)
            except AttributeError:
                f = partial(default_callback, user_callback_name)

            for w in wrapper_chain:
                f = w(f)

            if rule in callbacks:
                raise GrammarError("Rule '%s' already exists" % (rule,))

            callbacks[rule] = f

        return callbacks


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

plugins = {
    'BasicLexer': BasicLexer,
    'ContextualLexer': ContextualLexer,
    'LexerThread': LexerThread,
    'LALR_Parser': LALR_Parser,
    '_Parser': _Parser,
    'ParseTreeBuilder': ParseTreeBuilder,
}

__all__ = [
    "Token", "Tree", "Meta", "plugins", "__version__",
    "BasicLexer", "ContextualLexer", "LexerThread", "LexerState",
    "LineCounter", "Scanner", "LALR_Parser", "ParseTreeBuilder",
]
