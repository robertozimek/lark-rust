from lark_rust import BasicLexer, LexerThread


def test_lexer_thread_basic():
    from lark.lark import LexerConf
    from lark.lexer import TerminalDef, PatternStr
    import re

    terminals = [
        TerminalDef("WORD", PatternStr("hello"), 1),
        TerminalDef("NUM", PatternStr("123"), 1),
    ]
    conf = LexerConf(terminals, re, ignore=[], callbacks={})
    lexer = BasicLexer(conf)
    thread = LexerThread.from_text(lexer, "hello123")

    token = thread.next_token(None)
    assert token.value == "hello"
    assert token.type == "WORD"

