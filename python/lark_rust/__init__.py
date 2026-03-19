from .lark_rust import (
    Token,
    BasicLexer,
    LexerState,
    LexerThread as RustLexerThread,
    LineCounter,
    LALR_Parser as RustLALR_Parser,
    ParseConf,
    ParseTable,
    Rule,
    Scanner,
    Tree,
    Meta,
    plugins,
    __version__,
)

from lark.parsers.lalr_analysis import LALR_Analyzer
from lark.parsers.lalr_parser import _Parser


class LexerThread:
    def __init__(self, lexer, lexer_state=None):
        self._thread = RustLexerThread(lexer, lexer_state)

    @classmethod
    def from_text(cls, lexer, text):
        thread = RustLexerThread.from_text(lexer, text)
        instance = cls.__new__(cls)
        instance._thread = thread
        return instance

    def next_token(self, parser_state):
        return self._thread.next_token(parser_state)

    def lex(self, parser_state):
        while True:
            try:
                yield self._thread.next_token(parser_state)
            except EOFError:
                break

    def __copy__(self):
        instance = self.__new__(type(self))
        instance._thread = self._thread.__copy__()
        return instance


class LALR_Parser:
    def __init__(self, parser_conf, debug=False, strict=False):
        analysis = LALR_Analyzer(parser_conf, debug=debug, strict=strict)
        analysis.compute_lalr()
        self._parse_table = analysis.parse_table
        self.parser_conf = parser_conf
        self.parser = _Parser(self._parse_table, parser_conf.callbacks, debug)

    def parse(self, lexer, start):
        return self.parser.parse(lexer, start)


plugins = {
    'BasicLexer': BasicLexer,
    'LexerThread': LexerThread,
    'LALR_Parser': LALR_Parser,
}

__all__ = ["Token", "Tree", "Meta", "plugins", "__version__", "BasicLexer", "LexerThread", "LexerState", "LineCounter", "Scanner", "ParseConf", "ParseTable", "Rule"]
