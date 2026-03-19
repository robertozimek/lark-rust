from lark_rust import BasicLexer, LexerState


def test_lexer_basic():
    from lark.lark import LexerConf
    from lark.lexer import TerminalDef, PatternStr
    import re

    terminals = [
        TerminalDef("WORD", PatternStr("hello"), 1),
        TerminalDef("NUM", PatternStr("123"), 1),
    ]
    conf = LexerConf(terminals, re, ignore=[], callbacks={})
    lexer = BasicLexer(conf)

    state = lexer.make_lexer_state("hello123")
    assert isinstance(state, LexerState)
    assert state.text == "hello123"


def test_lexer_next_token():
    from lark.lark import LexerConf
    from lark.lexer import TerminalDef, PatternStr
    import re

    terminals = [
        TerminalDef("WORD", PatternStr("hello"), 1),
        TerminalDef("NUM", PatternStr("123"), 1),
    ]
    conf = LexerConf(terminals, re, ignore=[], callbacks={})
    lexer = BasicLexer(conf)

    state = lexer.make_lexer_state("hello")
    token = lexer.next_token(state, None)
    assert token is not None
    assert token.value == "hello"
    assert token.type == "WORD"

