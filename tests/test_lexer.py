from lark_rust import BasicLexer, LexerState

def test_lexer_basic():
    terminals = [
        ("WORD", r"[a-zA-Z]+", 1),
        ("NUM", r"[0-9]+", 1),
    ]
    lexer = BasicLexer(terminals, [], {})
    
    state = lexer.make_lexer_state("hello123")
    assert isinstance(state, LexerState)
    assert state.text == "hello123"

def test_lexer_next_token():
    terminals = [
        ("WORD", r"[a-zA-Z]+", 1),
        ("NUM", r"[0-9]+", 1),
    ]
    lexer = BasicLexer(terminals, [], {})
    
    state = lexer.make_lexer_state("hello")
    token = lexer.next_token(state, None)
    assert token is not None
    assert token.value == "hello"
    assert token.type == "WORD"
