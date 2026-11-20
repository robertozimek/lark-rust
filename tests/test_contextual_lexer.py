"""Regression tests for https://github.com/robertozimek/lark-rust/issues/1"""
import pytest
from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedToken
import lark_rust

GRAMMAR = r"""
INT_NUMBER: /\d+/
FLOAT_NUMBER: /\d*\.\d+|\d+e(\+|\-)\d+/
VARIABLE: /[a-zA-Z_]\w*/
NEWLINE: "\n"
PLUS: "+"
EQ: "="
LPAR: "("
RPAR: ")"
LBRACK: "["
RBRACK: "]"
COMMA: ","
TYPE_COMPLEX: "complex"

%ignore /[ \t]+/

start: (NEWLINE* instruction)+ NEWLINE*

instruction: expr
    | VARIABLE EQ expr

expr: expr PLUS atom
    | atom

atom: INT_NUMBER
    | FLOAT_NUMBER
    | VARIABLE
    | TYPE_COMPLEX LPAR expr COMMA expr RPAR
    | LBRACK expr RBRACK
"""


def _parsers():
    kw = dict(parser="lalr", lexer="contextual")
    return Lark(GRAMMAR, **kw), Lark(GRAMMAR, _plugins=lark_rust.plugins, **kw)


def _tokens(tree):
    return [(t.type, t.value) for t in tree.scan_values(lambda _: True)]


@pytest.mark.parametrize("text", [
    "complex_number = complex(2,3)",
    "complexity + complex(1, 2.5)",
    "x = 1e+5 + [y]",
    "a = 1\nb = a + 2\n",
])
def test_matches_lark(text):
    ref, rust = _parsers()
    assert _tokens(rust.parse(text)) == _tokens(ref.parse(text))


def test_keyword_prefix_lexed_as_variable():
    _, rust = _parsers()
    tokens = _tokens(rust.parse("complex_number = complex(2,3)"))
    assert tokens[0] == ("VARIABLE", "complex_number")
    assert tokens[2] == ("TYPE_COMPLEX", "complex")


def test_terminal_with_inner_group_does_not_shift_types():
    # FLOAT_NUMBER contains a capture group; tokens after it must keep their types.
    _, rust = _parsers()
    tokens = _tokens(rust.parse("x = 1e+5 + [y]"))
    assert ("FLOAT_NUMBER", "1e+5") in tokens
    assert ("LBRACK", "[") in tokens
    assert ("EQ", "=") in tokens


def test_basic_lexer_exposes_terminals_by_name():
    _, rust = _parsers()
    root = rust.parser.lexer.root_lexer
    assert "VARIABLE" in root.terminals_by_name


def test_unexpected_token_from_root_lexer():
    # "=" is valid for the root lexer but not after EQ, so the contextual
    # lexer raises UnexpectedToken built from root_lexer.terminals_by_name.
    ref, rust = _parsers()
    with pytest.raises(UnexpectedToken) as ref_exc:
        ref.parse("x = = 1")
    with pytest.raises(UnexpectedToken) as rust_exc:
        rust.parse("x = = 1")
    assert rust_exc.value.token.type == ref_exc.value.token.type == "EQ"
    assert rust_exc.value.expected == ref_exc.value.expected


def test_unexpected_characters():
    _, rust = _parsers()
    with pytest.raises(UnexpectedCharacters):
        rust.parse("x = 1 $ 2")
