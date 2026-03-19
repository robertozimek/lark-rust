"""Tests for lark_cython API compatibility.

These tests mirror the lark_cython test suite to ensure full drop-in compatibility.
"""
from lark import Lark, Tree
import lark_rust


def test_minimal():
    """Mirrors lark_cython test_minimal."""
    parser = Lark('!start: "a" "b"', parser="lalr", _plugins=lark_rust.plugins)
    res = parser.parse("ab")
    assert isinstance(res, Tree)
    assert all(isinstance(t, lark_rust.Token) for t in res.children)
    assert [t.value for t in res.children] == ["a", "b"]


def test_lark_meta_propagation():
    """Mirrors lark_cython test_lark_meta_propagation."""
    parser = Lark(
        """
        start: INT*

        COMMENT: /#.*/

        %import common (INT, WS)
        %ignore COMMENT
        %ignore WS
    """,
        parser="lalr",
        _plugins=lark_rust.plugins,
        propagate_positions=True,
    )
    res = parser.parse(
        """
        1 2 3  # hello
        # world
        4 5 6
        """
    )
    tokens = res.children
    assert isinstance(res, Tree)
    assert res.meta.line == 2
    assert all(isinstance(t, lark_rust.Token) for t in tokens)
    assert all(hasattr(t, "__lark_meta__") for t in tokens)
    assert all(t.__lark_meta__() == t for t in tokens)
    assert tokens[0].line == tokens[1].line == tokens[2].line == 2
    assert tokens[0].end_line == tokens[1].end_line == tokens[2].end_line == 2
    assert tokens[3].line == tokens[4].line == tokens[5].line == 4
    assert tokens[3].end_line == tokens[4].end_line == tokens[5].end_line == 4
    assert tokens[0].column == tokens[3].column == 9
    assert tokens[1].column == tokens[4].column == 11
    assert tokens[2].column == tokens[5].column == 13


def test_no_placeholders():
    """Mirrors lark_cython test_no_placeholders."""
    parser = Lark(
        '!start: "a" ["b"]',
        parser="lalr",
        _plugins=lark_rust.plugins,
        maybe_placeholders=True,
    )
    assert len(parser.parse("a").children) == 2
    assert len(parser.parse("ab").children) == 2

    parser = Lark(
        '!start: "a" ["b"]',
        parser="lalr",
        _plugins=lark_rust.plugins,
        maybe_placeholders=False,
    )
    assert len(parser.parse("a").children) == 1
    assert len(parser.parse("ab").children) == 2


def test_start():
    """Mirrors lark_cython test_start."""
    parser = Lark(
        '!x: "a" "b"',
        parser="lalr",
        _plugins=lark_rust.plugins,
        start="x",
    )
    res = parser.parse("ab")
    assert [t.value for t in res.children] == ["a", "b"]


def test_lexer_callbacks():
    """Mirrors lark_cython test_lexer_callbacks."""
    comments = []
    parser = Lark(
        """
        start: INT*

        COMMENT: /#.*/

        %import common (INT, WS)
        %ignore COMMENT
        %ignore WS
    """,
        parser="lalr",
        _plugins=lark_rust.plugins,
        lexer_callbacks={"COMMENT": comments.append},
    )
    res = parser.parse(
        """
        1 2 3  # hello
        # world
        4 5 6
        """
    )
    assert isinstance(res.children[0], lark_rust.Token)
    assert isinstance(comments[0], lark_rust.Token)
    assert len(comments) == 2


# ---------------------------------------------------------------------------
# Token API tests
# ---------------------------------------------------------------------------

def test_token_eq_str():
    """Token should compare equal to a string by value."""
    t = lark_rust.Token("WORD", "hello", 0, 1, 1)
    assert t == "hello"
    assert t != "world"


def test_token_eq_token():
    """Token equality compares type and value."""
    t1 = lark_rust.Token("WORD", "hello", 0, 1, 1)
    t2 = lark_rust.Token("WORD", "hello", 5, 2, 3)  # different pos
    t3 = lark_rust.Token("NUM", "hello", 0, 1, 1)
    assert t1 == t2  # same type+value
    assert t1 != t3  # different type


def test_token_hash():
    """Token hash is based on value (like lark_cython)."""
    t1 = lark_rust.Token("WORD", "hello", 0, 1, 1)
    t2 = lark_rust.Token("NUM", "hello", 5, 2, 3)
    assert hash(t1) == hash(t2)  # same value => same hash
    assert hash(t1) == hash("hello")


def test_token_update():
    """Token.update() returns a copy with optionally updated type/value."""
    t = lark_rust.Token("WORD", "hello", 0, 1, 1, end_line=1, end_column=6, end_pos=5)
    t2 = t.update(type_="NUM")
    assert t2.type == "NUM"
    assert t2.value == "hello"
    assert t2.start_pos == 0
    assert t2.end_line == 1

    t3 = t.update(value="world")
    assert t3.type == "WORD"
    assert t3.value == "world"


def test_token_new_borrow_pos():
    """Token.new_borrow_pos creates a new token borrowing position from another."""
    t = lark_rust.Token("WORD", "hello", 5, 2, 3, end_line=2, end_column=8, end_pos=10)
    t2 = lark_rust.Token.new_borrow_pos("NUM", "42", t)
    assert t2.type == "NUM"
    assert t2.value == "42"
    assert t2.start_pos == 5
    assert t2.line == 2
    assert t2.column == 3
    assert t2.end_line == 2
    assert t2.end_column == 8
    assert t2.end_pos == 10


def test_token_lark_meta():
    """Token.__lark_meta__() returns the token itself (identity for position info)."""
    t = lark_rust.Token("WORD", "hello", 0, 1, 1)
    meta = t.__lark_meta__()
    assert meta == t
    assert meta.line == 1
    assert meta.column == 1


def test_token_repr():
    """Token repr matches lark_cython format."""
    t = lark_rust.Token("WORD", "hello", 0, 1, 1)
    r = repr(t)
    assert "WORD" in r
    assert "hello" in r


def test_token_reduce():
    """Token supports pickling via __reduce__."""
    import pickle
    t = lark_rust.Token("WORD", "hello", 5, 2, 3, end_line=2, end_column=8, end_pos=10)
    data = pickle.dumps(t)
    t2 = pickle.loads(data)
    assert t2.type == "WORD"
    assert t2.value == "hello"
    assert t2.start_pos == 5
    assert t2.line == 2
    assert t2.column == 3


def test_token_default_params():
    """Token constructor defaults: start_pos=-1, line=-1, column=-1."""
    t = lark_rust.Token("WORD", "hello")
    assert t.start_pos == -1
    assert t.line == -1
    assert t.column == -1
    assert t.end_line is None
    assert t.end_column is None
    assert t.end_pos is None


# ---------------------------------------------------------------------------
# LexerState API tests
# ---------------------------------------------------------------------------

def test_lexer_state_copy():
    """LexerState supports __copy__."""
    import copy
    lc = lark_rust.LineCounter("\n")
    state = lark_rust.LexerState("hello", lc)
    state2 = copy.copy(state)
    assert state2.text == "hello"
    assert state2.last_token is None


def test_lexer_state_eq():
    """LexerState supports __eq__."""
    lc1 = lark_rust.LineCounter("\n")
    lc2 = lark_rust.LineCounter("\n")
    s1 = lark_rust.LexerState("hello", lc1)
    s2 = lark_rust.LexerState("hello", lc2)
    assert s1 == s2


# ---------------------------------------------------------------------------
# LineCounter API tests
# ---------------------------------------------------------------------------

def test_line_counter_eq():
    """LineCounter supports __eq__."""
    lc1 = lark_rust.LineCounter("\n")
    lc2 = lark_rust.LineCounter("\n")
    assert lc1 == lc2
    lc1.feed("hello", False)
    assert lc1 != lc2


def test_line_counter_newline_char():
    """LineCounter exposes newline_char."""
    lc = lark_rust.LineCounter("\n")
    assert lc.newline_char == "\n"


# ---------------------------------------------------------------------------
# Integration: contextual lexer
# ---------------------------------------------------------------------------

def test_contextual_lexer():
    """Test that ContextualLexer plugin works (used by default in lark)."""
    parser = Lark(
        '''
        start: NAME "=" value
        value: NAME | NUMBER
        NAME: /[a-z]+/
        NUMBER: /[0-9]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    res = parser.parse("x = 42")
    assert res.data == "start"


# ---------------------------------------------------------------------------
# Integration: transformer
# ---------------------------------------------------------------------------

def test_transformer():
    """Test that Transformer works with our Tree."""
    from lark import Transformer

    class T(Transformer):
        def start(self, items):
            return sum(items)

        def value(self, items):
            return int(items[0].value)

    parser = Lark(
        '''
        start: value+
        value: NUMBER
        NUMBER: /[0-9]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    result = T().transform(parser.parse("1 2 3"))
    assert result == 6


# ---------------------------------------------------------------------------
# Integration: expand1, maybe_placeholders
# ---------------------------------------------------------------------------

def test_expand1():
    """Test ?rule (expand single child) works."""
    parser = Lark(
        '''
        start: item+
        ?item: NAME
        NAME: /[a-z]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    res = parser.parse("hello world")
    assert res.data == "start"
    # Children should be tokens directly, not item trees
    assert all(isinstance(c, lark_rust.Token) for c in res.children)


def test_inlined_rule():
    """Test _rule (inline) works."""
    parser = Lark(
        '''
        start: _item+
        _item: NAME
        NAME: /[a-z]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    res = parser.parse("hello world")
    assert res.data == "start"
    assert len(res.children) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_input():
    """Test parsing empty-ish input."""
    parser = Lark(
        '''
        start: NAME*
        NAME: /[a-z]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    res = parser.parse("")
    assert res.data == "start"
    assert len(res.children) == 0


def test_unexpected_char():
    """Test that unexpected characters raise proper lark exceptions."""
    from lark.exceptions import UnexpectedCharacters
    parser = Lark(
        '''
        start: NAME+
        NAME: /[a-z]+/
        %ignore " "
    ''',
        parser="lalr",
        _plugins=lark_rust.plugins,
    )
    try:
        parser.parse("hello 123")
        assert False, "Should have raised"
    except UnexpectedCharacters:
        pass  # Expected


def test_unexpected_token_str():
    """Test that str() on UnexpectedToken works (requires ParserState.copy(deepcopy_values=...)).

    Regression: lark 1.3.1's InteractiveParser.copy() calls
    parser_state.copy(deepcopy_values=...) but lark-rust's ParserState.copy()
    did not accept that kwarg, causing a TypeError when str() was called on
    UnexpectedToken (which internally copies the interactive parser to compute
    accepted tokens).
    """
    from lark.exceptions import UnexpectedToken
    parser = Lark(
        '''
        start: pair+
        pair: NAME "=" NAME
        NAME: /[a-z]+/
        %ignore " "
    ''',
        parser="lalr",
        lexer="basic",
        _plugins=lark_rust.plugins,
    )
    try:
        # After parsing "a = b", the parser sees "c" (NAME) and expects "=" next
        parser.parse("a = b c")
        assert False, "Should have raised"
    except UnexpectedToken as e:
        # This used to blow up because ParserState.copy() didn't accept deepcopy_values.
        # str(e) internally calls InteractiveParser.copy() -> parser_state.copy(deepcopy_values=...)
        msg = str(e)
        assert "Unexpected token" in msg
