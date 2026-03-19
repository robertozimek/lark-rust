from lark import Lark, Tree
import lark_rust


def test_minimal():
    """Test basic parsing with lark_rust plugin"""
    parser = Lark('!start: "a" "b"', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("ab")
    assert isinstance(res, Tree)
    assert res.data == "start"
    assert len(res.children) == 2


def test_token_types():
    """Test that Token types are correct"""
    parser = Lark('''
        start: WORD+
        WORD: /[a-z]+/
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert res.data == "start"
    tokens = res.children
    assert len(tokens) == 2
    assert str(tokens[0]) == "hello"
    assert str(tokens[1]) == "world"


def test_ignored_tokens():
    """Test that ignored tokens (whitespace) work"""
    parser = Lark('''
        start: WORD+
        WORD: /[a-z]+/
        %ignore " "
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("hello world")
    assert len(res.children) == 2


def test_nested_rules():
    """Test nested grammar rules"""
    parser = Lark('''
        start: expr+
        expr: term ("+" term)*
        term: FACTOR
        FACTOR: /[0-9]+/
    ''', parser="lalr", lexer="basic", _plugins=lark_rust.plugins)
    res = parser.parse("1+2+3")
    assert res.data == "start"
